import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from analysis.consultant_agent import ConsultantAgent


class TestConsultantAgent:
    @pytest.fixture
    def consultant(self):
        """Create a ConsultantAgent instance with mocked API key"""
        with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test-key'}):
            return ConsultantAgent()

    @pytest.fixture
    def mock_session(self):
        """Create a mock aiohttp session"""
        response = MagicMock()
        response.status = 200
        response.text = AsyncMock(return_value='OK')
        response.json = AsyncMock(return_value={
            'choices': [{
                'message': {
                    'content': '{"decision": "approve", "confidence": 85, "rationale": "Strong technical setup", "modifications": {}}'
                }
            }]
        })

        session = MagicMock()
        session.post = AsyncMock(return_value=response)
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)
        return session

    @pytest.mark.asyncio
    async def test_successful_approval_review(self, consultant, mock_session):
        """Test successful consultant approval review"""
        with patch('aiohttp.ClientSession', return_value=mock_session):
            main_proposal = {
                'symbol': 'BTC/USD',
                'side': 'long',
                'confidence': 75,
                'reasons': ['Strong breakout', 'Good volume'],
                'entry': 'market',
                'stop': {'type': 'atr', 'multiplier': 2.0},
                'take_profit': {'rr': 2.0},
                'max_hold_bars': 100
            }

            result = await consultant.review_proposal(
                symbol='BTC/USD',
                regime='trend',
                signals={'ema20': 50000, 'rsi14': 65},
                main_proposal=main_proposal
            )

            assert result['decision'] == 'approve'
            assert result['confidence'] == 85
            assert 'Strong technical setup' in result['rationale']
            assert result['modifications'] == {}

    @pytest.mark.asyncio
    async def test_reject_review(self, consultant):
        """Test consultant rejecting a proposal"""
        response = MagicMock()
        response.status = 200
        response.text = AsyncMock(return_value='OK')
        response.json = AsyncMock(return_value={
            'choices': [{
                'message': {
                    'content': '{"decision": "reject", "confidence": 90, "rationale": "Overvalued and bearish sentiment", "modifications": {}}'
                }
            }]
        })

        session = MagicMock()
        session.post = AsyncMock(return_value=response)
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=session):
            main_proposal = {
                'symbol': 'BTC/USD',
                'side': 'long',
                'confidence': 75,
                'reasons': ['Price momentum'],
                'entry': 'market',
                'stop': {'type': 'atr', 'multiplier': 1.5},
                'take_profit': {'rr': 1.5},
                'max_hold_bars': 100
            }

            result = await consultant.review_proposal(
                symbol='BTC/USD',
                regime='trend',
                signals={'ema20': 50000, 'rsi14': 75},
                main_proposal=main_proposal
            )

            assert result['decision'] == 'reject'
            assert result['confidence'] == 90
            assert 'Overvalued' in result['rationale']

    @pytest.mark.asyncio
    async def test_modify_review(self, consultant):
        """Test consultant suggesting modifications"""
        response = MagicMock()
        response.status = 200
        response.text = AsyncMock(return_value='OK')
        response.json = AsyncMock(return_value={
            'choices': [{
                'message': {
                    'content': '{"decision": "modify", "confidence": 70, "rationale": "Reduce position size", "modifications": {"take_profit": {"rr": 1.5}}}'
                }
            }]
        })

        session = MagicMock()
        session.post = AsyncMock(return_value=response)
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=session):
            main_proposal = {
                'symbol': 'BTC/USD',
                'side': 'long',
                'confidence': 75,
                'reasons': ['Technical indicators'],
                'entry': 'market',
                'stop': {'type': 'atr', 'multiplier': 2.0},
                'take_profit': {'rr': 3.0},
                'max_hold_bars': 100
            }

            result = await consultant.review_proposal(
                symbol='BTC/USD',
                regime='trend',
                signals={'ema20': 50000, 'rsi14': 70},
                main_proposal=main_proposal
            )

            assert result['decision'] == 'modify'
            assert result['confidence'] == 70
            assert 'Reduce position size' in result['rationale']
            assert 'take_profit' in result['modifications']

    @pytest.mark.asyncio
    async def test_timeout_fallback(self, consultant):
        """Test fallback to approval on timeout"""
        response = MagicMock()
        response.status = 200
        response.text = AsyncMock(return_value='OK')
        response.json = AsyncMock(return_value={})

        session = MagicMock()
        session.post = AsyncMock(side_effect=asyncio.TimeoutError())
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=session):
            main_proposal = {
                'symbol': 'BTC/USD',
                'side': 'long',
                'confidence': 75,
                'reasons': ['Test'],
                'entry': 'market',
                'stop': {'type': 'atr', 'multiplier': 2.0},
                'take_profit': {'rr': 2.0},
                'max_hold_bars': 100
            }

            result = await consultant.review_proposal(
                symbol='BTC/USD',
                regime='trend',
                signals={'ema20': 50000},
                main_proposal=main_proposal
            )

            assert result['decision'] == 'approve'
            assert 'Auto-approved' in result['rationale']
            assert 'Consultant unavailable' in result['rationale']

    @pytest.mark.asyncio
    async def test_api_error_fallback(self, consultant):
        """Test fallback to approval on API error"""
        response = MagicMock()
        response.status = 500
        response.text = AsyncMock(return_value='Internal Server Error')
        response.json = AsyncMock(return_value={})

        session = MagicMock()
        session.post = AsyncMock(return_value=response)
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=session):
            main_proposal = {
                'symbol': 'BTC/USD',
                'side': 'long',
                'confidence': 75,
                'reasons': ['Test'],
                'entry': 'market',
                'stop': {'type': 'atr', 'multiplier': 2.0},
                'take_profit': {'rr': 2.0},
                'max_hold_bars': 100
            }

            result = await consultant.review_proposal(
                symbol='BTC/USD',
                regime='trend',
                signals={'ema20': 50000},
                main_proposal=main_proposal
            )

            assert result['decision'] == 'approve'
            assert 'Auto-approved' in result['rationale']

    @pytest.mark.asyncio
    async def test_missing_api_key_fallback(self):
        """Test fallback when API key is not configured"""
        with patch.dict('os.environ', {}, clear=True):
            consultant = ConsultantAgent()

            main_proposal = {
                'symbol': 'BTC/USD',
                'side': 'long',
                'confidence': 75,
                'reasons': ['Test'],
                'entry': 'market',
                'stop': {'type': 'atr', 'multiplier': 2.0},
                'take_profit': {'rr': 2.0},
                'max_hold_bars': 100
            }

            result = await consultant.review_proposal(
                symbol='BTC/USD',
                regime='trend',
                signals={'ema20': 50000},
                main_proposal=main_proposal
            )

            assert result['decision'] == 'approve'
            assert 'API key not configured' in result['rationale']

    @pytest.mark.asyncio
    async def test_invalid_json_fallback(self, consultant):
        """Test fallback on invalid JSON response"""
        response = MagicMock()
        response.status = 200
        response.text = AsyncMock(return_value='OK')
        response.json = AsyncMock(return_value={
            'choices': [{
                'message': {
                    'content': 'invalid json response'
                }
            }]
        })

        session = MagicMock()
        session.post = AsyncMock(return_value=response)
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=session):
            main_proposal = {
                'symbol': 'BTC/USD',
                'side': 'long',
                'confidence': 75,
                'reasons': ['Test'],
                'entry': 'market',
                'stop': {'type': 'atr', 'multiplier': 2.0},
                'take_profit': {'rr': 2.0},
                'max_hold_bars': 100
            }

            result = await consultant.review_proposal(
                symbol='BTC/USD',
                regime='trend',
                signals={'ema20': 50000},
                main_proposal=main_proposal
            )

            assert result['decision'] == 'approve'
            assert 'Invalid JSON' in result['rationale']

    @pytest.mark.asyncio
    async def test_retry_on_failure(self, consultant):
        """Test retry mechanism on transient failures"""
        # First call fails, second succeeds
        response_fail = MagicMock()
        response_fail.status = 500
        response_fail.text = AsyncMock(return_value='Server Error')
        response_fail.json = AsyncMock(return_value={})

        response_success = MagicMock()
        response_success.status = 200
        response_success.text = AsyncMock(return_value='OK')
        response_success.json = AsyncMock(return_value={
            'choices': [{
                'message': {
                    'content': '{"decision": "approve", "confidence": 80, "rationale": "Retry successful", "modifications": {}}'
                }
            }]
        })

        session = MagicMock()
        session.post = AsyncMock(side_effect=[
            Exception("Network error"),
            response_success
        ])
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession', return_value=session):
            main_proposal = {
                'symbol': 'BTC/USD',
                'side': 'long',
                'confidence': 75,
                'reasons': ['Test'],
                'entry': 'market',
                'stop': {'type': 'atr', 'multiplier': 2.0},
                'take_profit': {'rr': 2.0},
                'max_hold_bars': 100
            }

            result = await consultant.review_proposal(
                symbol='BTC/USD',
                regime='trend',
                signals={'ema20': 50000},
                main_proposal=main_proposal
            )

            assert result['decision'] == 'approve'
            assert result['confidence'] == 80
