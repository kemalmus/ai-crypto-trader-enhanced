from typing import Dict, Optional
from datetime import datetime

class PaperBroker:
    def __init__(self, fee_bps: float = 2.0):
        self.fee_bps = fee_bps
    
    def calculate_slippage(self, price: float, h: float, l: float) -> float:
        hl_pct = ((h - l) / price) * 100 if price > 0 else 0
        k = 0.15
        slip_bps = max(3, k * hl_pct * 100)
        return slip_bps
    
    def execute_entry(self, symbol: str, side: str, qty: float, entry_price: float, 
                     high: float, low: float) -> Dict:
        slippage_bps = self.calculate_slippage(entry_price, high, low)
        
        slippage_amount = entry_price * (slippage_bps / 10000)
        if side == 'long':
            fill_price = entry_price + slippage_amount
        else:
            fill_price = entry_price - slippage_amount
        
        fees = fill_price * qty * (self.fee_bps / 10000)
        
        total_cost = (fill_price * qty) + fees
        
        return {
            'symbol': symbol,
            'side': side,
            'qty': qty,
            'entry_price': fill_price,
            'fees': fees,
            'slippage_bps': slippage_bps,
            'total_cost': total_cost,
            'ts': datetime.utcnow()
        }
    
    def execute_exit(self, symbol: str, side: str, qty: float, exit_price: float,
                    entry_price: float, high: float, low: float) -> Dict:
        slippage_bps = self.calculate_slippage(exit_price, high, low)
        
        slippage_amount = exit_price * (slippage_bps / 10000)
        if side == 'long':
            fill_price = exit_price - slippage_amount
        else:
            fill_price = exit_price + slippage_amount
        
        fees = fill_price * qty * (self.fee_bps / 10000)
        
        if side == 'long':
            pnl = (fill_price - entry_price) * qty - fees
        else:
            pnl = (entry_price - fill_price) * qty - fees
        
        return {
            'symbol': symbol,
            'side': side,
            'qty': qty,
            'exit_price': fill_price,
            'entry_price': entry_price,
            'pnl': pnl,
            'fees': fees,
            'slippage_bps': slippage_bps,
            'ts': datetime.utcnow()
        }
