import ccxt
from datetime import datetime, timedelta
from typing import List, Dict
import pandas as pd

class CCXTAdapter:
    def __init__(self, exchange_id: str = 'binance'):
        self.exchange_class = getattr(ccxt, exchange_id)
        self.exchange = self.exchange_class({
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
    
    def fetch_ohlcv(self, symbol: str, timeframe: str, since: datetime = None, limit: int = 200) -> List[Dict]:
        since_ms = int(since.timestamp() * 1000) if since else None
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, since=since_ms, limit=limit)
            candles = []
            for bar in ohlcv:
                candles.append({
                    'ts': datetime.fromtimestamp(bar[0] / 1000),
                    'o': float(bar[1]),
                    'h': float(bar[2]),
                    'l': float(bar[3]),
                    'c': float(bar[4]),
                    'v': float(bar[5])
                })
            return candles
        except Exception as e:
            raise RuntimeError(f"Failed to fetch OHLCV for {symbol} on {timeframe}: {e}")
    
    def warm_up_data(self, symbol: str, timeframe: str, days: int = 120) -> List[Dict]:
        since = datetime.utcnow() - timedelta(days=days)
        try:
            return self.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
        except RuntimeError:
            return []
    
    def get_latest_price(self, symbol: str) -> float:
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return float(ticker['last'])
        except Exception as e:
            raise RuntimeError(f"Failed to fetch price for {symbol}: {e}")
