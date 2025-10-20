import pandas as pd
from typing import Dict

class SignalEngine:
    def __init__(self, max_risk_per_trade: float = 0.005, max_exposure_per_symbol: float = 0.02):
        self.max_risk_per_trade = max_risk_per_trade
        self.max_exposure_per_symbol = max_exposure_per_symbol
    
    def detect_regime(self, df: pd.DataFrame) -> str:
        if df.empty or len(df) < 200:
            return 'chop'
        
        last_row = df.iloc[-1]
        
        adx = last_row.get('adx14', 0)
        ema50 = last_row.get('ema50', 0)
        ema200 = last_row.get('ema200', 0)
        
        if pd.isna(adx) or pd.isna(ema50) or pd.isna(ema200):
            return 'chop'
        
        if adx > 20 and ema50 > ema200:
            return 'trend'
        return 'chop'
    
    def check_entry_long(self, df: pd.DataFrame) -> Dict:
        if df.empty or len(df) < 20:
            return {'signal': False}
        
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]
        
        close = last_row['c']
        donch_u = last_row.get('donch_u')
        cmf = last_row.get('cmf20', 0)
        rvol = last_row.get('rvol20', 0)
        atr = last_row.get('atr14', 0)
        
        if pd.isna(donch_u) or pd.isna(cmf) or pd.isna(rvol):
            return {'signal': False}
        
        breakout = close > donch_u and prev_row['c'] <= prev_row.get('donch_u', float('inf'))
        volume_surge = rvol > 1.5
        buying_pressure = cmf > 0
        
        if breakout and buying_pressure and volume_surge:
            stop = close - (2 * atr)
            return {
                'signal': True,
                'side': 'long',
                'entry': close,
                'stop': stop,
                'atr': atr,
                'confidence': 70
            }
        
        return {'signal': False}
    
    def check_exit_conditions(self, position: Dict, current_price: float, df: pd.DataFrame) -> Dict:
        if df.empty:
            return {'should_exit': False}
        
        last_row = df.iloc[-1]
        atr = last_row.get('atr14', 0)
        
        entry_price = position['avg_price']
        side = position['side']
        stop = position.get('stop', 0)
        
        if side == 'long':
            if current_price < stop:
                return {
                    'should_exit': True,
                    'reason': 'STOP_LOSS',
                    'exit_price': current_price
                }
            
            new_stop = current_price - (2 * atr)
            if new_stop > stop:
                return {
                    'should_exit': False,
                    'update_stop': new_stop
                }
        
        return {'should_exit': False}
    
    def calculate_position_size(self, nav: float, entry: float, stop: float, symbol: str) -> float:
        risk_amount = nav * self.max_risk_per_trade
        price_risk = abs(entry - stop)
        
        if price_risk == 0:
            return 0
        
        qty = risk_amount / price_risk
        
        max_qty = (nav * self.max_exposure_per_symbol) / entry
        qty = min(qty, max_qty)
        
        return round(qty, 8)
