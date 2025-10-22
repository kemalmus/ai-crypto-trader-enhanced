import asyncio
import uuid
from datetime import datetime, timezone
from typing import List, Dict
import pandas as pd
from storage.db import Database
from adapters.ccxt_public import CCXTAdapter
import yaml
from ta.indicators import TAEngine
from signals.rules import SignalEngine
from execution.paper import PaperBroker
from analysis.sentiment import SentimentAnalyzer
from analysis.llm_advisor import LLMAdvisor
from analysis.consultant_agent import ConsultantAgent
from analysis.reflection import ReflectionEngine
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TradingDaemon:
    def __init__(self, symbols: List[str] = None, timeframe: str = '5m', config_path: str = 'configs/app.yaml'):
        self.db = Database()
        self.config = self._load_config(config_path)
        self.ccxt_adapters = self._initialize_exchanges()
        # Ensure config is never None
        if self.config is None:
            self.config = {}
        self.ta_engine = TAEngine()
        self.signal_engine = SignalEngine()
        self.broker = PaperBroker()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.consultant_agent = ConsultantAgent()
        self.llm_advisor = LLMAdvisor(consultant_agent=self.consultant_agent)
        self.reflection_engine = ReflectionEngine()
        self.symbols = symbols or self.config.get('symbols', ['BTC/USD', 'ETH/USD'])
        self.timeframe = timeframe
        self.running = False
        self.cycle_count = 0
        self.last_reflection = None
        self.sentiment_windows = {}  # Track last sentiment fetch per symbol

    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                return config if config is not None else {}
        except Exception as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")
            return {}

    def _initialize_exchanges(self) -> Dict[str, CCXTAdapter]:
        """Initialize CCXT adapters for different exchanges"""
        exchanges = {}
        default_exchange = self.config.get('exchange', 'coinbase') if self.config else 'coinbase'

        # Initialize default exchange
        exchanges[default_exchange] = CCXTAdapter(default_exchange)

        # Initialize symbol-specific exchanges if configured
        symbol_exchanges = self.config.get('symbol_exchanges') if self.config else {}
        if symbol_exchanges is None:
            symbol_exchanges = {}
        for symbol_exchange in symbol_exchanges.values():
            if symbol_exchange not in exchanges:
                exchanges[symbol_exchange] = CCXTAdapter(symbol_exchange)

        return exchanges

    def get_adapter_for_symbol(self, symbol: str) -> CCXTAdapter:
        """Get the appropriate CCXT adapter for a symbol"""
        symbol_exchanges = self.config.get('symbol_exchanges') if self.config else {}
        if symbol_exchanges is None:
            symbol_exchanges = {}
        default_exchange = self.config.get('exchange', 'coinbase') if self.config else 'coinbase'
        exchange = symbol_exchanges.get(symbol, default_exchange)
        return self.ccxt_adapters[exchange]

    def validate_symbol_availability(self, symbols: List[str] = None) -> Dict[str, bool]:
        """Validate which symbols are available on their configured exchanges"""
        symbols_to_check = symbols or self.symbols
        availability = {}

        logger.info("Validating symbol availability across configured exchanges...")

        for symbol in symbols_to_check:
            try:
                adapter = self.get_adapter_for_symbol(symbol)
                # Try to fetch a small amount of data to test availability
                candles = adapter.fetch_ohlcv(symbol, '1d', limit=1)
                availability[symbol] = len(candles) > 0
                if availability[symbol]:
                    logger.info(f"✓ {symbol} available on {adapter.exchange.id}")
                else:
                    logger.warning(f"✗ {symbol} returned no data on {adapter.exchange.id}")
            except Exception as e:
                availability[symbol] = False
                logger.error(f"✗ {symbol} error on {adapter.exchange.id}: {e}")

        return availability

    async def init(self, nav: float):
        await self.db.connect()
        await self.db.init_nav(nav)
        logger.info(f"Initialized with NAV: ${nav:,.2f}")
        
        await self.db.log_event('INFO', ['INIT'], action='INITIALIZE_NAV', 
                               payload={'nav': nav})
        
        logger.info("Warming up historical data...")
        for symbol in self.symbols:
            adapter = self.get_adapter_for_symbol(symbol)
            candles = adapter.warm_up_data(symbol, self.timeframe, days=120)
            if candles:
                await self.db.save_candles(symbol, self.timeframe, candles)
                logger.info(f"Loaded {len(candles)} candles for {symbol}")
            else:
                logger.warning(f"Failed to warm up data for {symbol} on {adapter.exchange.id}")
    
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
    
    async def ensure_sufficient_data(self, symbol: str, min_candles: int = 200):
        """Ensure symbol has sufficient historical data, backfill if needed"""
        candles = await self.db.get_candles(symbol, self.timeframe, limit=min_candles)
        candle_count = len(candles) if candles else 0
        
        if candle_count < min_candles:
            logger.info(f"{symbol} has only {candle_count} candles, backfilling to {min_candles}...")
            adapter = self.get_adapter_for_symbol(symbol)
            
            historical_candles = adapter.warm_up_data(symbol, self.timeframe, days=120)
            if historical_candles:
                await self.db.save_candles(symbol, self.timeframe, historical_candles)
                logger.info(f"✓ Backfilled {len(historical_candles)} candles for {symbol}")
                
                await self.db.log_event('INFO', ['BACKFILL'], 
                                      symbol=symbol, action='BACKFILL_DATA',
                                      payload={'candles_before': candle_count, 
                                              'candles_fetched': len(historical_candles)})
            else:
                logger.warning(f"Failed to backfill data for {symbol}")
                return False
        
        return True
    
    async def process_symbol(self, symbol: str, nav: float, decision_id: str):
        if not await self.ensure_sufficient_data(symbol):
            logger.warning(f"Skipping {symbol} - insufficient data")
            return
        
        adapter = self.get_adapter_for_symbol(symbol)
        latest_candles = adapter.fetch_ohlcv(symbol, self.timeframe, limit=5)
        if latest_candles:
            await self.db.save_candles(symbol, self.timeframe, latest_candles)
        
        candles = await self.db.get_candles(symbol, self.timeframe, limit=200)
        if not candles:
            return
        
        df = pd.DataFrame(candles)
        df = self.ta_engine.compute_indicators(df)

        # Enhanced signal logging
        regime = self.signal_engine.detect_regime(df)

        # Log regime detection with supporting indicators
        latest_indicators = df.iloc[-1] if not df.empty else {}
        regime_indicators = {
            'adx14': float(latest_indicators.get('adx14', 0)) if pd.notna(latest_indicators.get('adx14', 0)) else 0,
            'ema50': float(latest_indicators.get('ema50', 0)) if pd.notna(latest_indicators.get('ema50', 0)) else 0,
            'ema200': float(latest_indicators.get('ema200', 0)) if pd.notna(latest_indicators.get('ema200', 0)) else 0,
            'close': float(latest_indicators.get('c', 0)) if pd.notna(latest_indicators.get('c', 0)) else 0
        }

        await self.db.log_event('INFO', ['SIGNAL', 'REGIME'],
                              symbol=symbol, action=f'REGIME_{regime.upper()}',
                              decision_id=decision_id,
                              payload={'regime': regime, 'indicators': regime_indicators})

        logger.info(f"{symbol} regime: {regime} (ADX: {regime_indicators['adx14']:.2f}, "
                   f"EMA50/200: {regime_indicators['ema50']:.2f}/{regime_indicators['ema200']:.2f})")

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

                # Enhanced sentiment logging
                sources = sentiment_data.get('sources', {})
                reasoning = sources.get('reasoning', '') if isinstance(sources, dict) else ''

                # Extract key reasons from numbered list (keep structure visible)
                reasoning_lines = [line.strip() for line in reasoning.split('\n') if line.strip()]
                key_reasons = []
                for line in reasoning_lines:
                    # Match common bullet patterns: 1), 1., 2), 2., -, •, *, etc.
                    if line.startswith(('1)', '1.', '2)', '2.', '3)', '3.', '-', '•', '*', '+')):
                        key_reasons.append(line)

                sentiment_summary = {
                    'sent_24h': sentiment_data['sent_24h'],
                    'sent_7d': sentiment_data.get('sent_7d'),
                    'sent_trend': sentiment_data.get('sent_trend'),
                    'burst': sentiment_data.get('burst'),
                    'key_reasons': key_reasons[:3] if key_reasons else [reasoning[:100]]
                }

                await self.db.log_event('INFO', ['SENTIMENT', 'FETCH'],
                                      symbol=symbol, action='SENTIMENT_UPDATE',
                                      decision_id=decision_id,
                                      payload=sentiment_summary)

                if key_reasons:
                    reasons_str = ' | '.join(key_reasons[:3])
                    logger.info(f"{symbol} sentiment: {sentiment_data['sent_24h']:.2f} "
                               f"(24h) / {sentiment_data.get('sent_7d', 0):.2f} (7d) | "
                               f"Trend: {sentiment_data.get('sent_trend', 0):.2f} | {reasons_str}")
                else:
                    logger.info(f"{symbol} sentiment: {sentiment_data['sent_24h']:.2f} "
                               f"(24h) / {sentiment_data.get('sent_7d', 0):.2f} (7d) | "
                               f"Trend: {sentiment_data.get('sent_trend', 0):.2f}")
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

                # Log cached sentiment usage
                await self.db.log_event('INFO', ['SENTIMENT', 'CACHE'],
                                      symbol=symbol, action='SENTIMENT_CACHED',
                                      decision_id=decision_id,
                                      payload={'sent_24h': sentiment_data['sent_24h']})
        
        positions = await self.db.get_positions()
        current_position = next((p for p in positions if p['symbol'] == symbol), None)
        
        if current_position:
            await self.check_exits(symbol, current_position, df, decision_id, regime, sentiment_data)
        else:
            if regime == 'trend':
                entry_signal = self.signal_engine.check_entry_long(df)
                
                # Get proposal with consultant review
                llm_proposal, consultant_review = await self.llm_advisor.get_trade_proposal_with_consultant(
                    symbol, regime, entry_signal, sentiment_data, current_position
                )

                if llm_proposal:
                    # Enhanced LLM proposal logging
                    proposal_metadata = llm_proposal.get('_metadata', {})
                    proposal_summary = {
                        'side': llm_proposal['side'],
                        'confidence': llm_proposal['confidence'],
                        'model_used': proposal_metadata.get('model_used', 'unknown'),
                        'response_time_ms': proposal_metadata.get('response_time_ms', 0),
                        'fallback_used': proposal_metadata.get('fallback_used', False),
                        'reasons': llm_proposal.get('reasons', [])[:3],  # First 3 reasons
                        'entry_price': llm_proposal.get('entry', 'market'),
                        'stop_loss': llm_proposal.get('stop', {}),
                        'take_profit': llm_proposal.get('take_profit', {})
                    }

                    await self.db.log_event('INFO', ['PROPOSAL', 'LLM'],
                                          symbol=symbol, action='LLM_PROPOSAL_GENERATED',
                                          decision_id=decision_id,
                                          payload=proposal_summary)

                    logger.info(f"{symbol} LLM proposal: {llm_proposal['side']} ({llm_proposal['confidence']}%) "
                               f"Model: {proposal_metadata.get('model_used', 'unknown')} "
                               f"Response: {proposal_metadata.get('response_time_ms', 0)}ms")

                    # Log consultant review if available
                    if consultant_review:
                        consultant_summary = {
                            'decision': consultant_review['decision'],
                            'confidence': consultant_review['confidence'],
                            'rationale': consultant_review['rationale'],
                            'modifications': consultant_review.get('modifications', {}),
                            'final_side': llm_proposal['side'],  # After potential modifications
                            'final_confidence': llm_proposal['confidence']
                        }

                        await self.db.log_event('INFO', ['PROPOSAL', 'CONSULTANT'],
                                              symbol=symbol, action=f"CONSULTANT_{consultant_review['decision'].upper()}",
                                              decision_id=decision_id,
                                              payload=consultant_summary)

                        logger.info(f"{symbol} Consultant: {consultant_review['decision']} "
                                   f"({consultant_review['confidence']}%) - {consultant_review['rationale']}")

                        # Log if consultant modified the proposal
                        if consultant_review['decision'] == 'modify':
                            modifications = consultant_review.get('modifications', {})
                            if modifications:
                                logger.info(f"{symbol} Consultant modifications: {modifications}")
                    else:
                        logger.info(f"{symbol} No consultant review available")

                    # Only proceed with trading logic for long proposals above confidence threshold
                    if llm_proposal['side'] == 'long' and llm_proposal['confidence'] >= 50:
                        await self.db.log_event('INFO', ['PROPOSAL', 'EXECUTION'],
                                              symbol=symbol, action='PROPOSAL_APPROVED_FOR_TRADING',
                                              decision_id=decision_id,
                                              payload={'confidence': llm_proposal['confidence']})
                        await self.check_entries(symbol, nav, df, decision_id, llm_proposal, consultant_review, regime, sentiment_data, current_position)
                else:
                    # Log when no proposal is generated
                    await self.db.log_event('INFO', ['PROPOSAL', 'LLM'],
                                          symbol=symbol, action='LLM_NO_PROPOSAL',
                                          decision_id=decision_id,
                                          payload={'reason': 'No proposal generated or API failure'})
                    logger.info(f"{symbol} No LLM proposal generated")
                    await self.check_entries(symbol, nav, df, decision_id, None, None, regime, sentiment_data, current_position)
    
    async def check_entries(self, symbol: str, nav: float, df: pd.DataFrame, decision_id: str,
                           llm_proposal=None, consultant_review=None, regime=None, sentiment_data=None, current_position=None):
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
                
                # Serialize decision context for trade record
                decision_rationale = None
                if llm_proposal:
                    decision_rationale = self.llm_advisor.serialize_decision_context(
                        symbol, regime, entry_signal, sentiment_data, current_position,
                        llm_proposal, consultant_review
                    )

                trade_id = await self.db.create_trade(
                    symbol, entry_signal['side'], qty, fill['entry_price'],
                    entry_fees=fill['fees'], slippage_bps=fill['slippage_bps'],
                    decision_rationale=decision_rationale
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
    
    async def check_exits(self, symbol: str, position: Dict, df: pd.DataFrame, decision_id: str,
                         regime=None, sentiment_data=None):
        adapter = self.get_adapter_for_symbol(symbol)
        current_price = adapter.get_latest_price(symbol)
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
                
                # Serialize exit decision context
                exit_rationale = self.llm_advisor.serialize_decision_context(
                    symbol, regime, {}, sentiment_data, pos_clean,
                    {'exit_signal': exit_check}, None  # No consultant review for exits
                )

                await self.db.close_trade(
                    trade_id, fill['exit_price'], fill['fees'],
                    fill['slippage_bps'], total_pnl, reason=exit_check['reason'],
                    decision_rationale=exit_rationale
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
                adapter = self.get_adapter_for_symbol(pos['symbol'])
                current_price = adapter.get_latest_price(pos['symbol'])
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
    
    async def show_logs(self, limit: int = 50, level: str = None, tag: str = None,
                       symbol: str = None, decision_id: str = None, action: str = None):
        logs = await self.db.get_logs(limit=limit, level=level, tag=tag)
        
        if not logs:
            print("No logs found.")
            return
        
        print(f"\nShowing {len(logs)} recent events:")
        print("=" * 100)
        
        for log in reversed(logs):
            ts = log['ts'].strftime('%Y-%m-%d %H:%M:%S')
            level_str = log['level']
            tags = log.get('tags', [])
            tags_str = ','.join(tags) if tags else ''
            action = log.get('action', '')
            symbol = log.get('symbol', '')
            decision_id = log.get('decision_id', '')[:8] if log.get('decision_id') else ''

            # Enhanced formatting based on log type
            line = f"[{ts}] {level_str:5s} [{tags_str:15s}]"

            if action:
                line += f" {action:20s}"
            if symbol:
                line += f" {symbol:10s}"
            if decision_id:
                line += f" ({decision_id})"

            print(line)

            # Enhanced payload formatting based on tags
            payload = log.get('payload')
            if payload:
                if isinstance(payload, dict):
                    # Format different types of payloads
                    if 'regime' in payload:
                        # Signal/regime payload
                        print(f"  └─ Regime: {payload['regime']} (ADX: {payload['indicators']['adx14']:.2f})")
                    elif 'sent_24h' in payload:
                        # Sentiment payload
                        print(f"  └─ Sentiment: {payload['sent_24h']:.2f} (24h) / {payload.get('sent_7d', 0):.2f} (7d)")
                    elif 'side' in payload and 'confidence' in payload:
                        # Proposal payload
                        model = payload.get('model_used', 'unknown')
                        response_time = payload.get('response_time_ms', 0)
                        print(f"  └─ {payload['side']} ({payload['confidence']}%) | Model: {model} | {response_time}ms")
                    elif 'decision' in payload:
                        # Consultant review payload
                        print(f"  └─ Consultant: {payload['decision']} ({payload['confidence']}%) - {payload['rationale']}")
                    else:
                        # Generic payload formatting
                        print(f"  └─ {payload}")
                else:
                    print(f"  └─ {payload}")
