"""
Configuration loader for AI Crypto Trading Agent
"""
import yaml
from typing import Dict, Any, List


class Config:
    """Configuration class that loads from YAML"""

    def __init__(self, config_path: str = 'configs/app.yaml'):
        self._config = self._load_config(config_path)
        self.config_path = config_path

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                return config if config is not None else {}
        except Exception as e:
            # Return empty dict if config fails to load
            return {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key"""
        return self._config.get(key, default)

    @property
    def symbols(self) -> List[str]:
        """Get list of symbols"""
        return self._config.get('symbols', ['BTC/USD', 'ETH/USD'])

    @property
    def timeframes(self) -> List[str]:
        """Get list of timeframes"""
        return [
            self._config.get('primary_timeframe', '5m'),
            self._config.get('higher_timeframe', '1h')
        ]

    @property
    def exchange(self) -> str:
        """Get default exchange"""
        return self._config.get('exchange', 'coinbase')

    @property
    def cycle_seconds(self) -> int:
        """Get cycle interval"""
        return self._config.get('cycle_seconds', 90)

    @property
    def ui(self) -> Dict[str, Any]:
        """Get UI configuration"""
        return self._config.get('ui', {
            'enabled': True,
            'host': '0.0.0.0',
            'port': 8000,
            'sse_poll_ms': 1000,
            'logs_limit': 50
        })

    @property
    def llm(self) -> Dict[str, Any]:
        """Get LLM configuration"""
        return self._config.get('llm', {})

    @property
    def sentiment(self) -> Dict[str, Any]:
        """Get sentiment configuration"""
        return self._config.get('sentiment', {})

    @property
    def indicators(self) -> Dict[str, Any]:
        """Get indicators configuration"""
        return self._config.get('indicators', {})

    @property
    def signals(self) -> Dict[str, Any]:
        """Get signals configuration"""
        return self._config.get('signals', {})

    @property
    def risk(self) -> Dict[str, Any]:
        """Get risk configuration"""
        return self._config.get('risk', {})

    @property
    def logging(self) -> Dict[str, Any]:
        """Get logging configuration"""
        return self._config.get('logging', {})

