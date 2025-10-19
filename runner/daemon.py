import asyncio
import uuid
from datetime import datetime, timezone
from typing import List, Dict
import pandas as pd
from storage.db import Database
from adapters.ccxt_public import CCXTAdapter
from ta.indicators import TAEngine
from signals.rules import SignalEngine
from execution.paper import PaperBroker
from analysis.sentiment import SentimentAnalyzer
from analysis.llm_advisor import LLMAdvisor
from analysis.reflection import ReflectionEngine
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TradingDaemon:
    def __init__(self, symbols: List[str] = None, timeframe: str = '5m'):
        self.db = Database()
        self.ccxt = CCXTAdapter('coinbase')
        self.ta_engine = TAEngine()
        self.signal_engine = SignalEngine()
        self.broker = PaperBroker()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.llm_advisor = LLMAdvisor()
        self.reflection_engine = ReflectionEngine()
        self.symbols = symbols or ['BTC/USD', 'ETH/USD']
        self.timeframe = timeframe
        self.running = False
        self.cycle_count = 0
        self.last_reflection = None
        self.sentiment_windows = {}  # Track last sentiment fetch per symbol
    
    async def init(self, nav: float):
        await self.db.connect()
        await self.db.init_nav(nav)
        logger.info(f"Initialized with NAV: ${nav:,.2f}")
        
        await self.db.log_event('INFO', ['INIT'], action='INITIALIZE_NAV', 
                               payload={'nav': nav})
        
        logger.info("Warming up historical data...")
        for symbol in self.symbols:
            candles = self.ccxt.warm_up_data(symbol, self.timeframe, days=120)
            if candles:
                await self.db.save_candles(symbol, self.timeframe, candles)
                logger.info(f"Loaded {len(candles)} candles for {symbol}")
    
    async def run_cycle(self):
        decision_id = str(uuid.uuid4())[:8]
        
        await self.db.log_event('INFO', ['CYCLE'], action='START_CYCLE', 
                               decision_id=decision_id)
        
        nav_data = await self.db.get_nav()
        if not nav_data:
            logger.error("No NAV data found. Run init first.")
            return
        
        nav = float(nav_data['nav_usd'])
        logger.info(f"Current NAV: ${nav:,.2f}")
        
        for symbol in self.symbols:
            try:
                await self.process_symbol(symbol, nav, decision_id)
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                await self.db.log_event('ERROR', ['CYCLE', 'ERROR'], 
                                      symbol=symbol, action='PROCESS_ERROR',
                                      decision_id=decision_id, payload={'error': str(e)})
        
        await self.update_nav()
        
        await self.db.log_event('INFO', ['CYCLE'], action='END_CYCLE', 
                               decision_id=decision_id)
    
    async def process_symbol(self, symbol: str, nav: float, decision_id: str):
        latest_candles = self.ccxt.fetch_ohlcv(symbol, self.timeframe, limit=5)
        if latest_candles:
            await self.db.save_candles(symbol, self.timeframe, latest_candles)
        
        candles = await self.db.get_candles(symbol, self.timeframe, limit=200)
        if not candles:
            return
        
        df = pd.DataFrame(candles)
        df = self.ta_engine.compute_indicators(df)
        
        regime = self.signal_engine.detect_regime(df)
        logger.info(f"{symbol} regime: {regime}")
        
        sentiment_data = None
        if await self.should_fetch_sentiment(symbol):
            sentiment_data = await self.sentiment_analyzer.analyze_symbol(symbol)
            if sentiment_data:
                await self.db.save_sentiment(
                    symbol,
                    sentiment_data['sent_24h'],
                    sentiment_data.get('sent_7d'),
                    sentiment_data.get('sent_trend'),
                    sentiment_data.get('burst'),
                    sentiment_data.get('sources')
                )
                current_window = self.get_sentiment_window()
                self.sentiment_windows[symbol] = current_window
                
                sources = sentiment_data.get('sources', {})
                summary = sources.get('summary', '') if isinstance(sources, dict) else ''
                logger.info(f"{symbol} sentiment: {sentiment_data['sent_24h']:.2f} (Reason: {summary[:100]}...)")
        else:
            cached = await self.db.get_latest_sentiment(symbol)
            if cached:
                sentiment_data = {
                    'sent_24h': float(cached.get('sent_24h', 0)),
                    'sent_7d': float(cached.get('sent_7d', 0)) if cached.get('sent_7d') else None,
                    'sent_trend': float(cached.get('sent_trend', 0)) if cached.get('sent_trend') else None,
                    'burst': float(cached.get('burst', 0)) if cached.get('burst') else None,
                    'sources': cached.get('sources')
                }
        
        positions = await self.db.get_positions()
        current_position = next((p for p in positions if p['symbol'] == symbol), None)
        
        if current_position:
            await self.check_exits(symbol, current_position, df, decision_id)
        else:
            if regime == 'trend':
                entry_signal = self.signal_engine.check_entry_long(df)
                
                llm_proposal = await self.llm_advisor.get_trade_proposal(
                    symbol, regime, entry_signal, sentiment_data, current_position
                )
                
                if llm_proposal and llm_proposal['side'] == 'long' and llm_proposal['confidence'] >= 50:
                    await self.db.log_event('INFO', ['PROPOSAL', 'LLM'], 
                                          symbol=symbol, action='LLM_RECOMMENDS_LONG',
                                          decision_id=decision_id, 
                                          payload={'proposal': llm_proposal})
                    logger.info(f"{symbol} LLM proposal: {llm_proposal['side']} ({llm_proposal['confidence']}%)")
                
                await self.check_entries(symbol, nav, df, decision_id)
    
    async def check_entries(self, symbol: str, nav: float, df: pd.DataFrame, decision_id: str):
        entry_signal = self.signal_engine.check_entry_long(df)
        
        if entry_signal['signal']:
            logger.info(f"Entry signal for {symbol}: {entry_signal}")
            
            qty = self.signal_engine.calculate_position_size(
                nav, entry_signal['entry'], entry_signal['stop'], symbol
            )
            
            if qty > 0:
                last_candle = df.iloc[-1]
                fill = self.broker.execute_entry(
                    symbol, entry_signal['side'], qty, entry_signal['entry'],
                    last_candle['h'], last_candle['l']
                )
                
                trade_id = await self.db.create_trade(
                    symbol, entry_signal['side'], qty, fill['entry_price'],
                    entry_fees=fill['fees'], slippage_bps=fill['slippage_bps']
                )
                
                await self.db.upsert_position(
                    symbol, qty, fill['entry_price'], 
                    entry_signal['side'], entry_signal['stop'], trade_id=trade_id
                )
                
                await self.db.log_event('INFO', ['TRADE', 'ENTRY'], 
                                      symbol=symbol, action='ENTER_LONG',
                                      decision_id=decision_id, trade_id=trade_id,
                                      payload=fill)
                
                logger.info(f"Entered {symbol}: {qty} @ ${fill['entry_price']:.2f}")
    
    async def check_exits(self, symbol: str, position: Dict, df: pd.DataFrame, decision_id: str):
        current_price = self.ccxt.get_latest_price(symbol)
        if not current_price:
            return
        
        pos_clean = {
            'avg_price': float(position['avg_price']),
            'qty': float(position['qty']),
            'side': position['side'],
            'stop': float(position.get('stop', 0)),
            'symbol': position['symbol']
        }
        
        exit_check = self.signal_engine.check_exit_conditions(pos_clean, current_price, df)
        
        if exit_check.get('should_exit'):
            last_candle = df.iloc[-1]
            fill = self.broker.execute_exit(
                symbol, pos_clean['side'], pos_clean['qty'], 
                exit_check['exit_price'], pos_clean['avg_price'],
                last_candle['h'], last_candle['l']
            )
            
            trade_id = position.get('trade_id')
            if trade_id:
                open_trade = await self.db.get_open_trade(symbol)
                entry_fees = float(open_trade.get('fees', 0)) if open_trade else 0
                
                total_pnl = fill['pnl'] - entry_fees
                
                await self.db.close_trade(
                    trade_id, fill['exit_price'], fill['fees'],
                    fill['slippage_bps'], total_pnl, reason=exit_check['reason']
                )
            
            await self.db.close_position(symbol)
            
            await self.db.log_event('INFO', ['TRADE', 'EXIT'], 
                                  symbol=symbol, action=f"EXIT_{exit_check['reason']}",
                                  decision_id=decision_id, trade_id=trade_id,
                                  payload=fill)
            
            logger.info(f"Exited {symbol}: PnL ${fill['pnl']:.2f}")
        
        elif exit_check.get('update_stop'):
            await self.db.upsert_position(
                symbol, pos_clean['qty'], pos_clean['avg_price'],
                pos_clean['side'], exit_check['update_stop'], trade_id=position.get('trade_id')
            )
            logger.info(f"Updated stop for {symbol}: ${exit_check['update_stop']:.2f}")
    
    def get_sentiment_window(self) -> str:
        """Get current sentiment window (00:00 or 12:00 UTC)"""
        now = datetime.now(timezone.utc)
        if now.hour < 12:
            return f"{now.date()}-00:00"
        else:
            return f"{now.date()}-12:00"
    
    async def should_fetch_sentiment(self, symbol: str) -> bool:
        """Check if we should fetch fresh sentiment (twice daily at 00:00 and 12:00 UTC)"""
        current_window = self.get_sentiment_window()
        
        if symbol in self.sentiment_windows:
            if self.sentiment_windows[symbol] == current_window:
                return False
        
        latest_sentiment = await self.db.get_latest_sentiment(symbol)
        if latest_sentiment:
            sentiment_ts = latest_sentiment['ts']
            sentiment_window = self._get_window_from_timestamp(sentiment_ts)
            
            if sentiment_window == current_window:
                self.sentiment_windows[symbol] = current_window
                return False
        
        return True
    
    def _get_window_from_timestamp(self, ts: datetime) -> str:
        """Convert a timestamp to its sentiment window"""
        ts_utc = ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts.astimezone(timezone.utc)
        if ts_utc.hour < 12:
            return f"{ts_utc.date()}-00:00"
        else:
            return f"{ts_utc.date()}-12:00"
    
    async def update_nav(self):
        initial_nav = await self.db.get_config('initial_nav')
        starting_cash = float(initial_nav['value']) if initial_nav else 10000.0
        
        realized_pnl = await self.db.get_total_realized_pnl()
        
        positions = await self.db.get_positions()
        total_unrealized = 0
        for pos in positions:
            try:
                current_price = self.ccxt.get_latest_price(pos['symbol'])
                avg_price = float(pos['avg_price'])
                qty = float(pos['qty'])
                if pos['side'] == 'long':
                    unrealized = (current_price - avg_price) * qty
                else:
                    unrealized = (avg_price - current_price) * qty
                total_unrealized += unrealized
            except RuntimeError as e:
                logger.warning(f"Could not fetch price for {pos['symbol']}: {e}")
        
        current_nav = starting_cash + realized_pnl + total_unrealized
        
        peak_nav_data = await self.db.get_config('peak_nav')
        peak_nav = float(peak_nav_data) if peak_nav_data else starting_cash
        if current_nav > peak_nav:
            peak_nav = current_nav
            await self.db.set_config('peak_nav', peak_nav)
        
        dd_pct = ((peak_nav - current_nav) / peak_nav * 100) if peak_nav > 0 else 0.0
        
        await self.db.update_nav(current_nav, realized_pnl, total_unrealized, dd_pct)
    
    async def run_daemon(self, cycle_seconds: int = 90):
        await self.db.connect()
        self.running = True
        logger.info(f"Starting daemon with {cycle_seconds}s cycles...")
        
        while self.running:
            try:
                await self.run_cycle()
                self.cycle_count += 1
                
                if self.cycle_count % 120 == 0:
                    await self.generate_reflection("4h")
                
                await asyncio.sleep(cycle_seconds)
            except KeyboardInterrupt:
                logger.info("Stopping daemon...")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Cycle error: {e}")
                await asyncio.sleep(cycle_seconds)
        
        await self.db.close()
    
    async def generate_reflection(self, window: str):
        try:
            nav_data = await self.db.get_nav()
            positions = await self.db.get_positions()
            
            stats = {
                'nav': float(nav_data['nav_usd']) if nav_data else 0,
                'realized_pnl': float(nav_data['realized_pnl']) if nav_data else 0,
                'unrealized_pnl': float(nav_data['unrealized_pnl']) if nav_data else 0,
                'dd_pct': float(nav_data['dd_pct']) if nav_data else 0,
                'positions': [
                    {
                        'symbol': p['symbol'],
                        'side': p['side'],
                        'qty': float(p['qty']),
                        'avg_price': float(p['avg_price'])
                    } for p in positions
                ]
            }
            
            reflection = await self.reflection_engine.generate_reflection(window, stats)
            if reflection:
                await self.db.save_reflection(
                    reflection['window'],
                    reflection['title'],
                    reflection['body'],
                    reflection['stats']
                )
                logger.info(f"Generated reflection: {reflection['title']}")
        except Exception as e:
            logger.error(f"Failed to generate reflection: {e}")
    
    async def status(self):
        nav_data = await self.db.get_nav()
        positions = await self.db.get_positions()
        
        if nav_data:
            print(f"\nNAV: ${nav_data['nav_usd']:,.2f}")
            print(f"Realized PnL: ${nav_data['realized_pnl']:,.2f}")
            print(f"Unrealized PnL: ${nav_data['unrealized_pnl']:,.2f}")
        
        print(f"\nPositions: {len(positions)}")
        for pos in positions:
            print(f"  {pos['symbol']}: {pos['qty']} {pos['side']} @ ${pos['avg_price']:.2f}, Stop: ${pos.get('stop', 0):.2f}")
    
    async def show_logs(self, limit: int = 50, level: str = None, tag: str = None):
        logs = await self.db.get_logs(limit=limit, level=level, tag=tag)
        
        if not logs:
            print("No logs found.")
            return
        
        print(f"\nShowing {len(logs)} recent events:")
        print("=" * 100)
        
        for log in reversed(logs):
            ts = log['ts'].strftime('%Y-%m-%d %H:%M:%S')
            level_str = log['level']
            tags_str = ','.join(log.get('tags', []))
            action = log.get('action', '')
            symbol = log.get('symbol', '')
            decision_id = log.get('decision_id', '')[:8] if log.get('decision_id') else ''
            
            line = f"[{ts}] {level_str:5s} [{tags_str:15s}]"
            if action:
                line += f" {action:20s}"
            if symbol:
                line += f" {symbol:10s}"
            if decision_id:
                line += f" ({decision_id})"
            
            print(line)
            
            if log.get('payload'):
                print(f"  └─ {log['payload']}")
