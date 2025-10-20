import pytest
import pandas as pd
import numpy as np
from datetime import datetime

@pytest.fixture
def sample_candles():
    dates = pd.date_range(end=datetime.utcnow(), periods=200, freq='5min')
    np.random.seed(42)
    
    close_prices = 50000 + np.cumsum(np.random.randn(200) * 100)
    high_prices = close_prices + np.abs(np.random.randn(200) * 50)
    low_prices = close_prices - np.abs(np.random.randn(200) * 50)
    open_prices = close_prices + np.random.randn(200) * 30
    volumes = np.abs(np.random.randn(200) * 1000000)
    
    return pd.DataFrame({
        'ts': dates,
        'o': open_prices,
        'h': high_prices,
        'l': low_prices,
        'c': close_prices,
        'v': volumes
    })

@pytest.fixture
def trending_candles():
    dates = pd.date_range(end=datetime.utcnow(), periods=200, freq='5min')
    np.random.seed(43)
    
    trend = np.linspace(50000, 55000, 200)
    noise = np.random.randn(200) * 50
    close_prices = trend + noise
    
    high_prices = close_prices + np.abs(np.random.randn(200) * 30)
    low_prices = close_prices - np.abs(np.random.randn(200) * 30)
    open_prices = close_prices + np.random.randn(200) * 20
    volumes = np.abs(np.random.randn(200) * 1000000)
    
    return pd.DataFrame({
        'ts': dates,
        'o': open_prices,
        'h': high_prices,
        'l': low_prices,
        'c': close_prices,
        'v': volumes
    })
