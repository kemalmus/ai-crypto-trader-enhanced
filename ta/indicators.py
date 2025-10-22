import pandas as pd
import pandas_ta as ta

class TAEngine:
    @staticmethod
    def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # Ensure timestamp is the index for session-based calculations
        if 'ts' in df.columns and not isinstance(df.index, pd.DatetimeIndex):
            df.set_index('ts', inplace=True)

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
            df['bb_l'] = bb.iloc[:, 0]  # BBL - lower band
            df['bb_u'] = bb.iloc[:, 2]  # BBU - upper band
        
        df['donch_u'] = df['h'].rolling(window=20).max()
        df['donch_l'] = df['l'].rolling(window=20).min()
        
        df['obv'] = ta.obv(df['c'], df['v'])
        
        df['cmf20'] = ta.cmf(df['h'], df['l'], df['c'], df['v'], length=20)
        
        adx_result = ta.adx(df['h'], df['l'], df['c'], length=14)
        if adx_result is not None and not adx_result.empty:
            df['adx14'] = adx_result.iloc[:, 0]
        
        avg_vol = df['v'].rolling(window=20).mean()
        df['rvol20'] = df['v'] / avg_vol
        
        # Session-based VWAP (resets daily)
        typical_price = (df['h'] + df['l'] + df['c']) / 3
        df['session'] = df.index.date  # Group by trading day
        df['vwap'] = df.groupby('session').apply(
            lambda x: (typical_price.loc[x.index] * x['v']).cumsum() / x['v'].cumsum()
        ).explode().reset_index(level=0, drop=True)

        # Anchored AVWAP from recent breakout (last 20-bar high)
        breakout_price = df['h'].rolling(window=20).max().shift(1)  # Look back for breakout
        anchor_mask = df['h'] >= breakout_price  # Find breakout bars

        if anchor_mask.any():
            # Find the most recent breakout
            last_breakout_idx = anchor_mask.idxmax()
            # Calculate AVWAP from breakout point forward
            anchor_data = df.loc[last_breakout_idx:]
            anchor_typical = (anchor_data['h'] + anchor_data['l'] + anchor_data['c']) / 3
            df['avwap'] = (anchor_typical * anchor_data['v']).cumsum() / anchor_data['v'].cumsum()
            # Fill backward with session VWAP for bars before anchor
            pre_anchor_mask = df.index < last_breakout_idx
            if pre_anchor_mask.any():
                df.loc[pre_anchor_mask, 'avwap'] = df.loc[pre_anchor_mask, 'vwap']
        else:
            # No breakout found, use session VWAP
            df['avwap'] = df['vwap']
        
        return df
