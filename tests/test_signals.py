import pytest
import pandas as pd
import numpy as np
from ta.indicators import TAEngine
from signals.rules import SignalEngine

class TestSignalEngine:
    def test_detect_regime_trend(self, trending_candles):
        ta_engine = TAEngine()
        signal_engine = SignalEngine()
        
        df = ta_engine.compute_indicators(trending_candles)
        regime = signal_engine.detect_regime(df)
        
        assert regime in ['trend', 'chop']
    
    def test_detect_regime_requires_indicators(self, sample_candles):
        signal_engine = SignalEngine()
        df = sample_candles.copy()
        
        regime = signal_engine.detect_regime(df)
        assert regime == 'chop'
    
    def test_entry_signal_structure(self, sample_candles):
        ta_engine = TAEngine()
        signal_engine = SignalEngine()
        
        df = ta_engine.compute_indicators(sample_candles)
        signal = signal_engine.check_entry_long(df)
        
        assert 'signal' in signal
        assert 'side' in signal
        assert 'entry' in signal
        assert 'stop' in signal
        assert 'reasons' in signal
        
        assert isinstance(signal['signal'], bool)
        assert signal['side'] in ['long', 'flat']
    
    def test_entry_no_signal_on_insufficient_data(self):
        signal_engine = SignalEngine()
        df = pd.DataFrame({
            'c': [100],
            'h': [101],
            'l': [99]
        })
        
        signal = signal_engine.check_entry_long(df)
        assert signal['signal'] is False
    
    def test_position_sizing_positive(self):
        signal_engine = SignalEngine()
        
        nav = 10000
        entry_price = 50000
        stop_price = 49000
        
        qty = signal_engine.calculate_position_size(nav, entry_price, stop_price, 'BTC/USD')
        
        assert qty >= 0
    
    def test_position_sizing_zero_on_no_risk(self):
        signal_engine = SignalEngine()
        
        nav = 10000
        entry_price = 50000
        stop_price = 50000
        
        qty = signal_engine.calculate_position_size(nav, entry_price, stop_price, 'BTC/USD')
        
        assert qty == 0
    
    def test_exit_signal_structure(self, sample_candles):
        ta_engine = TAEngine()
        signal_engine = SignalEngine()
        
        df = ta_engine.compute_indicators(sample_candles)
        
        position = {
            'side': 'long',
            'avg_price': 50000,
            'stop': 49000,
            'qty': 0.1
        }
        
        exit_signal = signal_engine.check_exit(df, position)
        
        assert 'exit' in exit_signal
        assert 'reason' in exit_signal
        assert isinstance(exit_signal['exit'], bool)
    
    def test_stop_loss_trigger(self):
        signal_engine = SignalEngine()
        
        df = pd.DataFrame({
            'c': [48000],
            'l': [47500],
            'atr14': [500]
        })
        
        position = {
            'side': 'long',
            'avg_price': 50000,
            'stop': 49000,
            'qty': 0.1
        }
        
        exit_signal = signal_engine.check_exit(df, position)
        
        assert exit_signal['exit'] is True
        assert 'stop' in exit_signal['reason'].lower()
