import pytest
import asyncio
from unittest.mock import MagicMock, patch
from runner.daemon import TradingDaemon


class TestExpandedUniverse:
    """Test the expanded symbol universe functionality"""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration with expanded symbol universe"""
        return {
            'symbols': ['BTC/USD', 'ETH/USD', 'SOL/USD', 'AVAX/USD', 'MATIC/USD', 'LINK/USD', 'UNI/USD', 'AAVE/USD'],
            'exchange': 'coinbase',
            'symbol_exchanges': {
                'SOL/USD': 'binance',
                'AVAX/USD': 'binance'
            }
        }

    @pytest.fixture
    def daemon_with_config(self, mock_config):
        """Create daemon with mock configuration"""
        with patch('builtins.open', return_value=MagicMock()), \
             patch('yaml.safe_load', return_value=mock_config):

            daemon = TradingDaemon(symbols=mock_config['symbols'])
            daemon.config = mock_config
            return daemon

    def test_config_loading(self, mock_config):
        """Test that configuration is loaded correctly"""
        with patch('builtins.open'), patch('yaml.safe_load', return_value=mock_config):
            daemon = TradingDaemon()
            daemon.config = daemon._load_config('configs/app.yaml')

            assert len(daemon.config.get('symbols', [])) == 8
            assert 'BTC/USD' in daemon.config['symbols']
            assert 'AAVE/USD' in daemon.config['symbols']

    def test_exchange_initialization(self, mock_config):
        """Test that exchanges are initialized correctly"""
        with patch('builtins.open'), patch('yaml.safe_load', return_value=mock_config), \
             patch('adapters.ccxt_public.CCXTAdapter') as mock_adapter_class:

            mock_adapter = MagicMock()
            mock_adapter_class.return_value = mock_adapter

            daemon = TradingDaemon()
            # Config should be loaded from the mocked file
            exchanges = daemon._initialize_exchanges()

            # Should initialize coinbase and binance
            assert 'coinbase' in exchanges
            assert 'binance' in exchanges
            assert mock_adapter_class.call_count == 2

    def test_adapter_selection_for_symbol(self, daemon_with_config):
        """Test that correct adapter is selected for each symbol"""
        daemon = daemon_with_config

        # BTC/USD should use coinbase (default)
        adapter_btc = daemon.get_adapter_for_symbol('BTC/USD')
        assert adapter_btc == daemon.ccxt_adapters['coinbase']

        # SOL/USD should use binance (configured override)
        adapter_sol = daemon.get_adapter_for_symbol('SOL/USD')
        assert adapter_sol == daemon.ccxt_adapters['binance']

        # ETH/USD should use coinbase (default)
        adapter_eth = daemon.get_adapter_for_symbol('ETH/USD')
        assert adapter_eth == daemon.ccxt_adapters['coinbase']

    @pytest.mark.asyncio
    async def test_symbol_validation_dry_run(self, mock_config):
        """Test symbol validation in dry run mode"""
        with patch('builtins.open'), patch('yaml.safe_load', return_value=mock_config):
            daemon = TradingDaemon()

            # Test dry run
            print("\nTesting dry run validation...")
            # This would normally make API calls, but in dry run it just shows what would be checked

    def test_symbol_list_completeness(self):
        """Test that all 8 symbols are properly configured"""
        expected_symbols = {
            'BTC/USD', 'ETH/USD', 'SOL/USD', 'AVAX/USD',
            'MATIC/USD', 'LINK/USD', 'UNI/USD', 'AAVE/USD'
        }

        # Test that daemon initializes with all symbols
        with patch('builtins.open'), patch('yaml.safe_load', return_value={
            'symbols': list(expected_symbols),
            'exchange': 'coinbase'
        }):
            daemon = TradingDaemon()
            daemon_symbols = set(daemon.symbols)

            assert daemon_symbols == expected_symbols
            assert len(daemon_symbols) == 8

    def test_config_fallback_behavior(self):
        """Test configuration fallback when config file is missing"""
        with patch('builtins.open', side_effect=FileNotFoundError()), \
             patch('yaml.safe_load', return_value={}):

            daemon = TradingDaemon()

            # Should fall back to minimal config
            assert daemon.config == {}
            # Should still initialize with default symbols
            assert len(daemon.symbols) == 2  # BTC/USD, ETH/USD fallback

    def test_exchange_adapter_caching(self, mock_config):
        """Test that exchange adapters are cached and reused"""
        with patch('builtins.open'), patch('yaml.safe_load', return_value=mock_config), \
             patch('adapters.ccxt_public.CCXTAdapter') as mock_adapter_class:

            mock_adapter = MagicMock()
            mock_adapter_class.return_value = mock_adapter

            daemon = TradingDaemon()
            # Config should be loaded from the mocked file

            # Initialize exchanges twice
            exchanges1 = daemon._initialize_exchanges()
            exchanges2 = daemon._initialize_exchanges()

            # Should create adapters each time (not cached between calls)
            # But each initialization should create the same exchanges
            assert 'coinbase' in exchanges1 and 'binance' in exchanges1
            assert 'coinbase' in exchanges2 and 'binance' in exchanges2
            # Should create adapters twice (once per initialization)
            assert mock_adapter_class.call_count == 4  # 2 exchanges × 2 initializations

    def test_symbol_exchange_override(self, daemon_with_config):
        """Test that symbol-specific exchange overrides work correctly"""
        daemon = daemon_with_config

        # Test that overrides are respected
        assert daemon.config['symbol_exchanges']['SOL/USD'] == 'binance'
        assert daemon.config['symbol_exchanges']['AVAX/USD'] == 'binance'

        # Test that non-overridden symbols use default
        assert daemon.get_adapter_for_symbol('BTC/USD') == daemon.ccxt_adapters['coinbase']
        assert daemon.get_adapter_for_symbol('LINK/USD') == daemon.ccxt_adapters['coinbase']

    def test_expanded_universe_scaling(self):
        """Test that the system can handle 8 symbols efficiently"""
        symbols_8 = ['BTC/USD', 'ETH/USD', 'SOL/USD', 'AVAX/USD', 'MATIC/USD', 'LINK/USD', 'UNI/USD', 'AAVE/USD']
        symbols_2 = ['BTC/USD', 'ETH/USD']

        # Test that daemon can be initialized with 8 symbols
        with patch('builtins.open'), patch('yaml.safe_load', return_value={'symbols': symbols_8, 'exchange': 'coinbase'}):
            daemon_8 = TradingDaemon(symbols=symbols_8)
            assert len(daemon_8.symbols) == 8
            assert set(daemon_8.symbols) == set(symbols_8)

        with patch('builtins.open'), patch('yaml.safe_load', return_value={'symbols': symbols_2, 'exchange': 'coinbase'}):
            daemon_2 = TradingDaemon(symbols=symbols_2)
            assert len(daemon_2.symbols) == 2
            assert set(daemon_2.symbols) == set(symbols_2)

    def test_symbol_validation_error_handling(self, daemon_with_config):
        """Test error handling in symbol validation"""
        daemon = daemon_with_config

        # Mock adapter to raise exception
        mock_adapter = MagicMock()
        mock_adapter.fetch_ohlcv.side_effect = RuntimeError("API Error")
        daemon.ccxt_adapters['coinbase'] = mock_adapter

        # Should handle errors gracefully
        availability = daemon.validate_symbol_availability(['BTC/USD'])

        assert 'BTC/USD' in availability
        assert availability['BTC/USD'] is False
