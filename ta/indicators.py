import pandas as pd
import pandas_ta as ta
import numpy as np

class TAEngine:
    @staticmethod
    def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        df['ema20'] = ta.ema(df['c'], length=20)
        df['ema50'] = ta.ema(df['c'], length=50)
        df['ema200'] = ta.ema(df['c'], length=200)
        
        df['hma55'] = ta.hma(df['c'], length=55)
        
        df['rsi14'] = ta.rsi(df['c'], length=14)
        
        stochrsi = ta.stochrsi(df['c'], length=14, rsi_length=14, k=3, d=3)
        if stochrsi is not None and not stochrsi.empty:
            df['stochrsi'] = stochrsi.iloc[:, 0]
        
        df['roc10'] = ta.roc(df['c'], length=10)
        
        atr = ta.atr(df['h'], df['l'], df['c'], length=14)
        df['atr14'] = atr
        
        bb = ta.bbands(df['c'], length=20, std=2)
        if bb is not None and not bb.empty:
            df['bb_u'] = bb.iloc[:, 0]
            df['bb_l'] = bb.iloc[:, 2]
        
        df['donch_u'] = df['h'].rolling(window=20).max()
        df['donch_l'] = df['l'].rolling(window=20).min()
        
        df['obv'] = ta.obv(df['c'], df['v'])
        
        df['cmf20'] = ta.cmf(df['h'], df['l'], df['c'], df['v'], length=20)
        
        adx_result = ta.adx(df['h'], df['l'], df['c'], length=14)
        if adx_result is not None and not adx_result.empty:
            df['adx14'] = adx_result.iloc[:, 0]
        
        avg_vol = df['v'].rolling(window=20).mean()
        df['rvol20'] = df['v'] / avg_vol
        
        typical_price = (df['h'] + df['l'] + df['c']) / 3
        df['vwap'] = (typical_price * df['v']).cumsum() / df['v'].cumsum()
        
        df['avwap'] = df['vwap']
        
        return df
