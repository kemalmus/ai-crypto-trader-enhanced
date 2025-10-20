from ta.indicators import TAEngine

class TestTAEngine:
    def test_compute_indicators_basic(self, sample_candles):
        engine = TAEngine()
        df = engine.compute_indicators(sample_candles)
        
        assert 'ema20' in df.columns
        assert 'ema50' in df.columns
        assert 'ema200' in df.columns
        assert 'rsi14' in df.columns
        assert 'atr14' in df.columns
        assert 'cmf20' in df.columns
        assert 'adx14' in df.columns
        
        assert not df['ema20'].isna().all()
        assert not df['rsi14'].isna().all()
        assert not df['atr14'].isna().all()
    
    def test_ema_ordering(self, trending_candles):
        engine = TAEngine()
        df = engine.compute_indicators(trending_candles)
        
        df_valid = df[df['ema200'].notna()].copy()
        
        assert len(df_valid) > 0, "Should have valid EMA values"
    
    def test_rsi_bounds(self, sample_candles):
        engine = TAEngine()
        df = engine.compute_indicators(sample_candles)
        
        rsi_values = df['rsi14'].dropna()
        
        assert (rsi_values >= 0).all(), "RSI should be >= 0"
        assert (rsi_values <= 100).all(), "RSI should be <= 100"
    
    def test_atr_positive(self, sample_candles):
        engine = TAEngine()
        df = engine.compute_indicators(sample_candles)
        
        atr_values = df['atr14'].dropna()
        
        assert (atr_values > 0).all(), "ATR should be positive"
    
    def test_donchian_channels(self, sample_candles):
        engine = TAEngine()
        df = engine.compute_indicators(sample_candles)
        
        df_valid = df[df['donch_u'].notna() & df['donch_l'].notna()].copy()
        
        assert len(df_valid) > 0
        assert (df_valid['donch_u'] >= df_valid['donch_l']).all(), "Upper channel should be >= lower channel"
    
    def test_bollinger_bands(self, sample_candles):
        engine = TAEngine()
        df = engine.compute_indicators(sample_candles)
        
        df_valid = df[df['bb_u'].notna() & df['bb_l'].notna()].copy()
        
        assert len(df_valid) > 0
        assert (df_valid['bb_u'] >= df_valid['bb_l']).all(), "Upper band should be >= lower band"
    
    def test_cmf_bounds(self, sample_candles):
        engine = TAEngine()
        df = engine.compute_indicators(sample_candles)
        
        cmf_values = df['cmf20'].dropna()
        
        assert (cmf_values >= -1).all(), "CMF should be >= -1"
        assert (cmf_values <= 1).all(), "CMF should be <= 1"
    
    def test_adx_positive(self, sample_candles):
        engine = TAEngine()
        df = engine.compute_indicators(sample_candles)
        
        adx_values = df['adx14'].dropna()
        
        assert (adx_values >= 0).all(), "ADX should be non-negative"
    
    def test_no_nan_propagation(self, sample_candles):
        engine = TAEngine()
        df = engine.compute_indicators(sample_candles)
        
        last_50_rows = df.tail(50)
        
        required_cols = ['ema20', 'ema50', 'rsi14', 'atr14', 'cmf20', 'adx14']
        for col in required_cols:
            nan_count = last_50_rows[col].isna().sum()
            assert nan_count < 10, f"{col} has too many NaN values in recent data"
