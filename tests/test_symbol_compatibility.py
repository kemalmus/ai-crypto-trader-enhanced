import pytest
from adapters.ccxt_public import CCXTAdapter


class TestSymbolCompatibility:
    """Test compatibility of expanded symbol universe with CCXT exchanges"""

    @pytest.fixture
    def coinbase_adapter(self):
        """Create Coinbase CCXT adapter for testing"""
        return CCXTAdapter('coinbase')

    @pytest.fixture
    def binance_adapter(self):
        """Create Binance CCXT adapter for testing"""
        return CCXTAdapter('binance')

    @pytest.fixture
    def kraken_adapter(self):
        """Create Kraken CCXT adapter for testing"""
        return CCXTAdapter('kraken')

    def test_coinbase_supported_symbols(self, coinbase_adapter):
        """Test which symbols are supported on Coinbase"""
        supported_symbols = [
            'BTC/USD', 'ETH/USD', 'SOL/USD', 'AVAX/USD',
            'MATIC/USD', 'LINK/USD', 'UNI/USD', 'AAVE/USD'
        ]

        results = {}
        for symbol in supported_symbols:
            try:
                # Try to fetch just 1 candle to test availability
                candles = coinbase_adapter.fetch_ohlcv(symbol, '1d', limit=1)
                results[symbol] = len(candles) > 0
            except Exception as e:
                results[symbol] = f"Error: {e}"

        print("\nCoinbase Symbol Compatibility:")
        for symbol, result in results.items():
            status = "✓" if result is True else "✗" if isinstance(result, str) else "?"
            print(f"  {status} {symbol}: {result}")

        return results

    def test_binance_supported_symbols(self, binance_adapter):
        """Test which symbols are supported on Binance"""
        supported_symbols = [
            'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'AVAX/USDT',
            'MATIC/USDT', 'LINK/USDT', 'UNI/USDT', 'AAVE/USDT'
        ]

        results = {}
        for symbol in supported_symbols:
            try:
                # Try to fetch just 1 candle to test availability
                candles = binance_adapter.fetch_ohlcv(symbol, '1d', limit=1)
                results[symbol] = len(candles) > 0
            except Exception as e:
                results[symbol] = f"Error: {e}"

        print("\nBinance Symbol Compatibility (USDT pairs):")
        for symbol, result in results.items():
            status = "✓" if result is True else "✗" if isinstance(result, str) else "?"
            print(f"  {status} {symbol}: {result}")

        return results

    def test_kraken_supported_symbols(self, kraken_adapter):
        """Test which symbols are supported on Kraken"""
        supported_symbols = [
            'BTC/USD', 'ETH/USD', 'SOL/USD', 'AVAX/USD',
            'MATIC/USD', 'LINK/USD', 'UNI/USD', 'AAVE/USD'
        ]

        results = {}
        for symbol in supported_symbols:
            try:
                # Try to fetch just 1 candle to test availability
                candles = kraken_adapter.fetch_ohlcv(symbol, '1d', limit=1)
                results[symbol] = len(candles) > 0
            except Exception as e:
                results[symbol] = f"Error: {e}"

        print("\nKraken Symbol Compatibility:")
        for symbol, result in results.items():
            status = "✓" if result is True else "✗" if isinstance(result, str) else "?"
            print(f"  {status} {symbol}: {result}")

        return results

    def test_optimal_exchange_selection(self):
        """Determine the best exchange for each symbol"""
        symbols = ['BTC/USD', 'ETH/USD', 'SOL/USD', 'AVAX/USD', 'MATIC/USD', 'LINK/USD', 'UNI/USD', 'AAVE/USD']
        exchanges = {
            'coinbase': CCXTAdapter('coinbase'),
            'binance': CCXTAdapter('binance'),
            'kraken': CCXTAdapter('kraken')
        }

        recommendations = {}

        for symbol in symbols:
            best_exchange = None
            best_availability = False

            for exchange_name, adapter in exchanges.items():
                try:
                    candles = adapter.fetch_ohlcv(symbol, '1d', limit=1)
                    if len(candles) > 0:
                        best_exchange = exchange_name
                        best_availability = True
                        break  # Take first available exchange
                except Exception:
                    continue

            if best_exchange:
                # For Binance, recommend USDT pairs if USD pairs don't work
                if best_exchange == 'binance':
                    usdt_symbol = symbol.replace('/USD', '/USDT')
                    try:
                        candles = exchanges['binance'].fetch_ohlcv(usdt_symbol, '1d', limit=1)
                        if len(candles) > 0:
                            recommendations[symbol] = f"binance:{usdt_symbol}"
                        else:
                            recommendations[symbol] = f"binance:{symbol}"
                    except Exception:
                        recommendations[symbol] = f"binance:{symbol}"
                else:
                    recommendations[symbol] = f"{best_exchange}:{symbol}"
            else:
                recommendations[symbol] = "unavailable"

        print("\nOptimal Exchange Recommendations:")
        for symbol, recommendation in recommendations.items():
            print(f"  {symbol}: {recommendation}")

        return recommendations

    def run_compatibility_analysis(self):
        """Run full compatibility analysis and return recommendations"""
        print("Running Symbol Compatibility Analysis...")

        coinbase_results = self.test_coinbase_supported_symbols(CCXTAdapter('coinbase'))
        binance_results = self.test_binance_supported_symbols(CCXTAdapter('binance'))
        kraken_results = self.test_kraken_supported_symbols(CCXTAdapter('kraken'))
        recommendations = self.test_optimal_exchange_selection()

        return {
            'coinbase': coinbase_results,
            'binance': binance_results,
            'kraken': kraken_results,
            'recommendations': recommendations
        }
