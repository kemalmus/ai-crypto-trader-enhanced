import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from analysis.llm_advisor import LLMAdvisor
from analysis.consultant_agent import ConsultantAgent


class TestConsultantWorkflow:
    """Integration tests for the full consultant workflow"""

    @pytest.fixture
    def mock_llm_response(self):
        """Mock successful LLM response"""
        return {
            'choices': [{
                'message': {
                    'content': '{"symbol": "BTC/USD", "side": "long", "confidence": 75, "reasons": ["Strong breakout"], "entry": "market", "stop": {"type": "atr", "multiplier": 2.0}, "take_profit": {"rr": 2.0}, "max_hold_bars": 100}'
                }
            }]
        }

    @pytest.fixture
    def mock_consultant_response(self):
        """Mock consultant approval response"""
        response = MagicMock()
        response.status = 200
        response.text = AsyncMock(return_value='OK')
        response.json = AsyncMock(return_value={
            'choices': [{
                'message': {
                    'content': '{"decision": "approve", "confidence": 85, "rationale": "Good technical setup", "modifications": {}}'
                }
            }]
        })
        return response

    @pytest.mark.asyncio
    async def test_full_approve_workflow(self, mock_llm_response, mock_consultant_response):
        """Test complete workflow where consultant approves proposal"""
        # Mock both LLM and consultant responses
        llm_response_mock = MagicMock()
        llm_response_mock.status = 200
        llm_response_mock.text = AsyncMock(return_value='OK')
        llm_response_mock.json = AsyncMock(return_value=mock_llm_response)

        llm_session = MagicMock()
        llm_session.post = AsyncMock(return_value=llm_response_mock)
        llm_session.__aenter__ = AsyncMock(return_value=llm_session)
        llm_session.__aexit__ = AsyncMock(return_value=None)

        consultant_session = MagicMock()
        consultant_session.post = AsyncMock(return_value=mock_consultant_response)
        consultant_session.__aenter__ = AsyncMock(return_value=consultant_session)
        consultant_session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession') as mock_session_class:
            # Configure side effects to return appropriate session for each call
            call_count = 0
            def session_side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return llm_session  # First call is LLM
                else:
                    return consultant_session  # Second call is consultant

            mock_session_class.side_effect = session_side_effect

            # Create advisor with consultant
            consultant_agent = ConsultantAgent()
            llm_advisor = LLMAdvisor(consultant_agent=consultant_agent)

            # Test the workflow
            proposal, review = await llm_advisor.get_trade_proposal_with_consultant(
                symbol='BTC/USD',
                regime='trend',
                signals={'ema20': 50000, 'rsi14': 65},
                sentiment={'sent_24h': 0.1},
                current_position=None
            )

            # Verify results
            assert proposal is not None
            assert proposal['side'] == 'long'
            assert proposal['confidence'] == 75
            assert '_metadata' in proposal
            assert '_consultant_review' in proposal
            assert review['decision'] == 'approve'

    @pytest.mark.asyncio
    async def test_full_modify_workflow(self, mock_llm_response, mock_consultant_response):
        """Test complete workflow where consultant modifies proposal"""
        # Modify consultant response to suggest modifications
        modify_response = MagicMock()
        modify_response.status = 200
        modify_response.text = AsyncMock(return_value='OK')
        modify_response.json = AsyncMock(return_value={
            'choices': [{
                'message': {
                    'content': '{"decision": "modify", "confidence": 70, "rationale": "Reduce position size", "modifications": {"take_profit": {"rr": 1.5}}}'
                }
            }]
        })

        # Mock sessions
        llm_response_mock = MagicMock()
        llm_response_mock.status = 200
        llm_response_mock.text = AsyncMock(return_value='OK')
        llm_response_mock.json = AsyncMock(return_value=mock_llm_response)

        llm_session = MagicMock()
        llm_session.post = AsyncMock(return_value=llm_response_mock)
        llm_session.__aenter__ = AsyncMock(return_value=llm_session)
        llm_session.__aexit__ = AsyncMock(return_value=None)

        consultant_session = MagicMock()
        consultant_session.post = AsyncMock(return_value=modify_response)
        consultant_session.__aenter__ = AsyncMock(return_value=consultant_session)
        consultant_session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession') as mock_session_class:
            call_count = 0
            def session_side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return llm_session  # First call is LLM
                else:
                    return consultant_session  # Second call is consultant

            mock_session_class.side_effect = session_side_effect

            # Create advisor with consultant
            consultant_agent = ConsultantAgent()
            llm_advisor = LLMAdvisor(consultant_agent=consultant_agent)

            # Test the workflow
            proposal, review = await llm_advisor.get_trade_proposal_with_consultant(
                symbol='BTC/USD',
                regime='trend',
                signals={'ema20': 50000, 'rsi14': 65},
                sentiment={'sent_24h': 0.1},
                current_position=None
            )

            # Verify results
            assert proposal is not None
            assert proposal['side'] == 'long'
            assert proposal['confidence'] == 75
            assert '_consultant_review' in proposal
            assert '_consultant_modifications' in proposal
            assert review['decision'] == 'modify'
            assert 'take_profit' in proposal['_consultant_modifications']

    @pytest.mark.asyncio
    async def test_full_reject_workflow(self, mock_llm_response, mock_consultant_response):
        """Test complete workflow where consultant rejects proposal"""
        # Modify consultant response to reject
        reject_response = MagicMock()
        reject_response.status = 200
        reject_response.text = AsyncMock(return_value='OK')
        reject_response.json = AsyncMock(return_value={
            'choices': [{
                'message': {
                    'content': '{"decision": "reject", "confidence": 90, "rationale": "Overvalued market conditions", "modifications": {}}'
                }
            }]
        })

        # Mock sessions
        llm_response_mock = MagicMock()
        llm_response_mock.status = 200
        llm_response_mock.text = AsyncMock(return_value='OK')
        llm_response_mock.json = AsyncMock(return_value=mock_llm_response)

        llm_session = MagicMock()
        llm_session.post = AsyncMock(return_value=llm_response_mock)
        llm_session.__aenter__ = AsyncMock(return_value=llm_session)
        llm_session.__aexit__ = AsyncMock(return_value=None)

        consultant_session = MagicMock()
        consultant_session.post = AsyncMock(return_value=reject_response)
        consultant_session.__aenter__ = AsyncMock(return_value=consultant_session)
        consultant_session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession') as mock_session_class:
            call_count = 0
            def session_side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return llm_session  # First call is LLM
                else:
                    return consultant_session  # Second call is consultant

            mock_session_class.side_effect = session_side_effect

            # Create advisor with consultant
            consultant_agent = ConsultantAgent()
            llm_advisor = LLMAdvisor(consultant_agent=consultant_agent)

            # Test the workflow
            proposal, review = await llm_advisor.get_trade_proposal_with_consultant(
                symbol='BTC/USD',
                regime='trend',
                signals={'ema20': 50000, 'rsi14': 65},
                sentiment={'sent_24h': 0.1},
                current_position=None
            )

            # Verify results
            assert proposal is not None
            assert proposal['side'] == 'long'
            assert proposal['confidence'] == 75
            assert '_consultant_review' in proposal
            assert review['decision'] == 'reject'

    @pytest.mark.asyncio
    async def test_consultant_failure_fallback(self, mock_llm_response):
        """Test workflow when consultant fails but LLM succeeds"""
        # Mock LLM success but consultant failure
        llm_response_mock = MagicMock()
        llm_response_mock.status = 200
        llm_response_mock.text = AsyncMock(return_value='OK')
        llm_response_mock.json = AsyncMock(return_value=mock_llm_response)

        llm_session = MagicMock()
        llm_session.post = AsyncMock(return_value=llm_response_mock)
        llm_session.__aenter__ = AsyncMock(return_value=llm_session)
        llm_session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession') as mock_session_class:
            call_count = 0
            def session_side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count <= 2:  # LLM calls (primary + fallback)
                    return llm_session
                else:
                    # Consultant call fails
                    raise Exception("Consultant API error")

            mock_session_class.side_effect = session_side_effect

            # Create advisor with consultant that will fail
            consultant_agent = ConsultantAgent()
            llm_advisor = LLMAdvisor(consultant_agent=consultant_agent)

            # Test the workflow
            proposal, review = await llm_advisor.get_trade_proposal_with_consultant(
                symbol='BTC/USD',
                regime='trend',
                signals={'ema20': 50000, 'rsi14': 65},
                sentiment={'sent_24h': 0.1},
                current_position=None
            )

            # Verify results - should proceed with original proposal
            assert proposal is not None
            assert proposal['side'] == 'long'
            assert proposal['confidence'] == 75
            assert '_metadata' in proposal
            # Consultant review should be a fallback approval due to the consultant agent always returning something
            assert review is not None
            assert review['decision'] == 'approve'

    @pytest.mark.asyncio
    async def test_no_consultant_configured(self, mock_llm_response):
        """Test workflow when no consultant agent is configured"""
        # Mock LLM success
        llm_response_mock = MagicMock()
        llm_response_mock.status = 200
        llm_response_mock.text = AsyncMock(return_value='OK')
        llm_response_mock.json = AsyncMock(return_value=mock_llm_response)

        llm_session = MagicMock()
        llm_session.post = AsyncMock(return_value=llm_response_mock)
        llm_session.__aenter__ = AsyncMock(return_value=llm_session)
        llm_session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session_class.return_value = llm_session

            # Create advisor without consultant
            llm_advisor = LLMAdvisor(consultant_agent=None)

            # Test the workflow
            proposal, review = await llm_advisor.get_trade_proposal_with_consultant(
                symbol='BTC/USD',
                regime='trend',
                signals={'ema20': 50000, 'rsi14': 65},
                sentiment={'sent_24h': 0.1},
                current_position=None
            )

            # Verify results - should work without consultant
            assert proposal is not None
            assert proposal['side'] == 'long'
            assert proposal['confidence'] == 75
            assert '_metadata' in proposal
            assert review is None  # No consultant review

    @pytest.mark.asyncio
    async def test_llm_failure_handling(self):
        """Test workflow when LLM fails"""
        # Mock LLM failure - both primary and fallback will fail
        failed_response = MagicMock()
        failed_response.status = 500
        failed_response.text = AsyncMock(return_value='Internal Server Error')
        failed_response.json = AsyncMock(return_value={})

        llm_session = MagicMock()
        llm_session.post = AsyncMock(return_value=failed_response)
        llm_session.__aenter__ = AsyncMock(return_value=llm_session)
        llm_session.__aexit__ = AsyncMock(return_value=None)

        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session_class.return_value = llm_session

            # Create advisor
            consultant_agent = ConsultantAgent()
            llm_advisor = LLMAdvisor(consultant_agent=consultant_agent)

            # Test the workflow
            proposal, review = await llm_advisor.get_trade_proposal_with_consultant(
                symbol='BTC/USD',
                regime='trend',
                signals={'ema20': 50000, 'rsi14': 65},
                sentiment={'sent_24h': 0.1},
                current_position=None
            )

            # Verify results - should return None for both
            assert proposal is None
            assert review is None
