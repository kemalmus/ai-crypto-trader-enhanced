import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timezone
import json

from web.server import app, get_db_connection, init_db
from configs.app import Config


class TestWebUIAPI:
    """Test Web UI API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def mock_config(self):
        """Mock config"""
        config = MagicMock(spec=Config)
        config.symbols = ['BTC/USD', 'ETH/USD']
        config.timeframes = ['5m']
        config.ui = {'enabled': True, 'host': '0.0.0.0', 'port': 8000}
        return config

    @pytest.fixture
    def mock_db_connection(self):
        """Mock database connection"""
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock()
        mock_conn.fetchval = AsyncMock()
        mock_conn.fetch = AsyncMock()
        return mock_conn

    @pytest.mark.asyncio
    async def test_overview_endpoint(self, client, mock_config, mock_db_connection):
        """Test overview API endpoint"""
        # Mock NAV data
        nav_data = {
            'nav_usd': 10500.0,
            'realized_pnl': 500.0,
            'unrealized_pnl': -100.0,
            'dd_pct': -2.5,
            'ts': datetime.now(timezone.utc)
        }
        mock_db_connection.fetchrow.return_value = nav_data
        mock_db_connection.fetchval.return_value = 2  # open positions

        # Mock cycle data
        cycle_data = {
            'ts': datetime.now(timezone.utc),
            'payload': {'latency_ms': 1500}
        }
        mock_db_connection.fetchrow.side_effect = [nav_data, cycle_data]

        # Mock the pool.acquire() context manager
        mock_db_connection.__aenter__ = AsyncMock(return_value=mock_db_connection)
        mock_db_connection.__aexit__ = AsyncMock(return_value=None)

        # Mock the database pool
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_db_connection

        with patch('web.server.config', mock_config), \
             patch('web.server.db.pool', mock_pool):

            response = client.get('/api/overview')

            assert response.status_code == 200
            data = response.json()
            assert data['nav_usd'] == 10500.0
            assert data['realized_pnl'] == 500.0
            assert data['unrealized_pnl'] == -100.0
            assert data['dd_pct'] == -2.5
            assert data['open_positions_count'] == 2
            assert data['cycle_latency_ms'] == 1500

    @pytest.mark.asyncio
    async def test_overview_endpoint_no_data(self, client, mock_config, mock_db_connection):
        """Test overview API endpoint with no data"""
        mock_db_connection.fetchrow.return_value = None
        mock_db_connection.fetchval.return_value = 0

        # Mock the pool.acquire() context manager
        mock_db_connection.__aenter__ = AsyncMock(return_value=mock_db_connection)
        mock_db_connection.__aexit__ = AsyncMock(return_value=None)

        # Mock the database pool
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_db_connection

        with patch('web.server.config', mock_config), \
             patch('web.server.db.pool', mock_pool):

            response = client.get('/api/overview')

            assert response.status_code == 200
            data = response.json()
            assert data['nav_usd'] == 0.0
            assert data['realized_pnl'] == 0.0
            assert data['open_positions_count'] == 0

    @pytest.mark.asyncio
    async def test_symbols_endpoint(self, client, mock_config, mock_db_connection):
        """Test symbols API endpoint"""
        # Mock features data
        features_data = {
            'symbol': 'BTC/USD',
            'tf': '5m',
            'c': 50000.0,
            'rvol20': 1.8,
            'donch_u': 51000.0,
            'donch_l': 49000.0,
            'cmf20': 0.3,
            'adx14': 25.0,
            'ema50': 49500.0,
            'ema200': 48000.0
        }
        mock_db_connection.fetchrow.return_value = features_data

        # Mock the pool.acquire() context manager
        mock_db_connection.__aenter__ = AsyncMock(return_value=mock_db_connection)
        mock_db_connection.__aexit__ = AsyncMock(return_value=None)

        # Mock the database pool
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_db_connection

        with patch('web.server.config', mock_config), \
             patch('web.server.db.pool', mock_pool):

            response = client.get('/api/symbols')

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2  # Two symbols configured
            symbol_data = data[0]
            assert symbol_data['symbol'] == 'BTC/USD'
            assert symbol_data['regime'] == 'trend'  # ADX > 20 and EMA50 > EMA200
            assert symbol_data['last_price'] == 50000.0
            assert symbol_data['rvol'] == 1.8

    @pytest.mark.asyncio
    async def test_trades_endpoint(self, client, mock_config, mock_db_connection):
        """Test trades API endpoint"""
        # Mock trades data
        trades_data = [{
            'id': 1,
            'symbol': 'BTC/USD',
            'side': 'long',
            'qty': 0.1,
            'entry_ts': datetime.now(timezone.utc),
            'entry_px': 50000.0,
            'exit_ts': None,
            'exit_px': None,
            'pnl': None,
            'fees': 5.0,
            'slippage_bps': 3.0,
            'reason': 'Test trade'
        }]
        mock_db_connection.fetch.return_value = trades_data

        # Mock the pool.acquire() context manager
        mock_db_connection.__aenter__ = AsyncMock(return_value=mock_db_connection)
        mock_db_connection.__aexit__ = AsyncMock(return_value=None)

        # Mock the database pool
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_db_connection

        with patch('web.server.config', mock_config), \
             patch('web.server.db.pool', mock_pool):

            response = client.get('/api/trades')

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            trade = data[0]
            assert trade['id'] == 1
            assert trade['symbol'] == 'BTC/USD'
            assert trade['side'] == 'long'
            assert trade['qty'] == 0.1
            assert trade['fees'] == 5.0

    @pytest.mark.asyncio
    async def test_logs_endpoint(self, client, mock_config, mock_db_connection):
        """Test logs API endpoint"""
        # Mock logs data as row-like objects
        mock_row = MagicMock()
        mock_row.__getitem__.side_effect = lambda key: {
            'id': 1,
            'ts': datetime.now(timezone.utc),
            'level': 'INFO',
            'tags': ['CYCLE', 'SIGNAL'],
            'symbol': 'BTC/USD',
            'tf': '5m',
            'action': 'ENTER_LONG',
            'decision_id': 'test-decision-123',
            'trade_id': 1,
            'payload': {'confidence': 0.8}
        }[key]
        logs_data = [mock_row]
        mock_db_connection.fetch.return_value = logs_data

        # Mock the pool.acquire() context manager
        mock_db_connection.__aenter__ = AsyncMock(return_value=mock_db_connection)
        mock_db_connection.__aexit__ = AsyncMock(return_value=None)

        # Mock the database pool
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_db_connection

        with patch('web.server.config', mock_config), \
             patch('web.server.db.pool', mock_pool):

            response = client.get('/api/logs')

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            log_entry = data[0]
            assert log_entry['id'] == 1
            assert log_entry['level'] == 'INFO'
            assert 'CYCLE' in log_entry['tags']
            assert log_entry['symbol'] == 'BTC/USD'
            assert log_entry['decision_id'] == 'test-decision-123'

    @pytest.mark.asyncio
    async def test_logs_endpoint_with_filters(self, client, mock_config, mock_db_connection):
        """Test logs API endpoint with filters"""
        # Mock filtered logs data as row-like objects
        mock_row = MagicMock()
        mock_row.__getitem__.side_effect = lambda key: {
            'id': 2,
            'ts': datetime.now(timezone.utc),
            'level': 'ERROR',
            'tags': ['TRADE', 'EXIT'],
            'symbol': 'ETH/USD',
            'tf': '5m',
            'action': 'EXIT_STOP',
            'decision_id': 'test-decision-456',
            'trade_id': None,
            'payload': {}
        }[key]
        logs_data = [mock_row]
        mock_db_connection.fetch.return_value = logs_data

        # Mock the pool.acquire() context manager
        mock_db_connection.__aenter__ = AsyncMock(return_value=mock_db_connection)
        mock_db_connection.__aexit__ = AsyncMock(return_value=None)

        # Mock the database pool
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_db_connection

        with patch('web.server.config', mock_config), \
             patch('web.server.db.pool', mock_pool):

            response = client.get('/api/logs?level=ERROR&symbol=ETH/USD&decision_id=test-decision-456')

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            log_entry = data[0]
            assert log_entry['level'] == 'ERROR'
            assert log_entry['symbol'] == 'ETH/USD'
            assert log_entry['decision_id'] == 'test-decision-456'

    def test_index_page(self, client, mock_config):
        """Test main index page renders"""
        with patch('web.server.config', mock_config):
            response = client.get('/')

            assert response.status_code == 200
            assert 'AI Crypto Trading Agent' in response.text
            assert 'Overview' in response.text
            assert 'Symbols' in response.text
            assert 'Trades' in response.text
            assert 'Logs' in response.text

    @pytest.mark.asyncio
    async def test_sse_stream_setup(self, client, mock_config, mock_db_connection):
        """Test SSE stream endpoint setup (without full streaming)"""
        # This test verifies the endpoint exists and handles initial setup
        # Full streaming tests would require more complex async testing

        # Mock the pool.acquire() context manager
        mock_db_connection.__aenter__ = AsyncMock(return_value=mock_db_connection)
        mock_db_connection.__aexit__ = AsyncMock(return_value=None)

        # Mock the database pool
        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_db_connection

        with patch('web.server.config', mock_config), \
             patch('web.server.db.pool', mock_pool):

            # Mock empty initial query
            mock_db_connection.fetch.return_value = []

            # Test that endpoint accepts request (streaming will start but we won't wait)
            response = client.get('/api/logs/stream')

            assert response.status_code == 200
            assert 'text/event-stream' in response.headers.get('content-type', '')
            assert 'no-cache' in response.headers.get('cache-control', '')
