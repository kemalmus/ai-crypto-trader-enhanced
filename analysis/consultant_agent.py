import os
import asyncio
import aiohttp
from typing import Dict, Optional
import logging
import json

logger = logging.getLogger(__name__)

class ConsultantAgent:
    def __init__(self):
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        self.base_url = 'https://openrouter.ai/api/v1/chat/completions'
        self.model = 'x-ai/grok-4-fast'
        self.timeout_seconds = 30
        self.max_retries = 2

    async def review_proposal(self, symbol: str, regime: str, signals: Dict,
                             main_proposal: Dict,
                             sentiment: Optional[Dict] = None,
                             current_position: Optional[Dict] = None) -> Optional[Dict]:
        """
        Review a trading proposal from the main LLM advisor.

        Args:
            symbol: Trading pair symbol
            regime: Market regime (trend/chop)
            signals: Technical signals data
            sentiment: Sentiment analysis data
            current_position: Current position if any
            main_proposal: Proposal from main LLM advisor

        Returns:
            Dict with decision (approve/reject/modify) and rationale
        """
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY not set, auto-approving proposal")
            return self._get_fallback_approval(main_proposal, "API key not configured")

        prompt = self._build_review_prompt(symbol, regime, signals, sentiment, current_position, main_proposal)

        for attempt in range(self.max_retries + 1):
            try:
                review = await self._call_model(prompt)
                if review:
                    logger.info(f"Consultant review for {symbol}: {review['decision']} ({review['confidence']}%)")
                    return review
            except Exception as e:
                logger.warning(f"Consultant review attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(1)  # Brief delay before retry
                    continue

        logger.error(f"Consultant review failed after {self.max_retries + 1} attempts, auto-approving")
        return self._get_fallback_approval(main_proposal, "Consultant unavailable")

    async def _call_model(self, prompt: str) -> Optional[Dict]:
        """Call OpenRouter API with Grok-fast model"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)) as session:
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json',
                    'HTTP-Referer': 'https://replit.com',
                    'X-Title': 'AI Crypto Trading Agent'
                }

                payload = {
                    'model': self.model,
                    'messages': [
                        {
                            'role': 'system',
                            'content': self._get_system_prompt()
                        },
                        {
                            'role': 'user',
                            'content': prompt
                        }
                    ],
                    'temperature': 0.1,
                    'max_tokens': 500
                }

                response = await session.post(self.base_url, headers=headers, json=payload)
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"OpenRouter API error {response.status}: {error_text}")
                    return None

                data = await response.json()
                return self._parse_response(data)

        except asyncio.TimeoutError:
            logger.error(f"Consultant API call timed out after {self.timeout_seconds}s")
            return None
        except Exception as e:
            logger.error(f"Consultant API call failed: {e}")
            return None

    def _get_system_prompt(self) -> str:
        return (
            "You are a senior trading consultant reviewing cryptocurrency trading proposals. "
            "Your role is to approve, reject, or modify proposals based on risk management principles.\n\n"
            "Response format (valid JSON only):\n"
            "{\n"
            '  "decision": "approve|reject|modify",\n'
            '  "confidence": 0-100,\n'
            '  "rationale": "brief explanation (1-2 sentences)",\n'
            '  "modifications": {"field": "new_value"}  // only if decision is "modify"\n'
            "}\n\n"
            "Decision guidelines:\n"
            "- APPROVE: Strong technical alignment, appropriate risk/reward, no red flags\n"
            "- REJECT: Clear risk violations, poor timing, or major concerns\n"
            "- MODIFY: Minor adjustments needed for sizing, stops, or targets\n\n"
            "Only respond with valid JSON, no additional text."
        )

    def _build_review_prompt(self, symbol: str, regime: str, signals: Dict,
                           sentiment: Optional[Dict], current_position: Optional[Dict],
                           main_proposal: Dict) -> str:
        """Build the review prompt with all context"""
        parts = [
            f"Symbol: {symbol}",
            f"Market Regime: {regime}",
            f"\nMain Proposal to Review:"
            f"Side: {main_proposal.get('side', 'N/A')}",
            f"Confidence: {main_proposal.get('confidence', 0)}%",
            f"Entry: {main_proposal.get('entry', 'market')}",
            f"Stop Loss: {main_proposal.get('stop', {}).get('type', 'N/A')} {main_proposal.get('stop', {}).get('multiplier', 'N/A')}",
            f"Take Profit: RR {main_proposal.get('take_profit', {}).get('rr', 'N/A')}",
            f"Max Hold: {main_proposal.get('max_hold_bars', 'N/A')} bars",
            f"Reasons: {'; '.join(main_proposal.get('reasons', []))}",
            f"\nTechnical Signals: {json.dumps(signals, indent=2)}"
        ]

        if sentiment:
            parts.append("\nSentiment Analysis:")
            parts.append(f"  Score (24h): {sentiment.get('sent_24h', 0):.2f}")
            parts.append(f"  Trend: {sentiment.get('sent_trend', 0):.2f}")
            parts.append(f"  Burst: {sentiment.get('burst', 0):.2f}")

        if current_position:
            parts.append("\nCurrent Position:")
            parts.append(f"  Side: {current_position.get('side')}")
            parts.append(f"  Quantity: {current_position.get('qty')}")
            parts.append(f"  Avg Price: ${current_position.get('avg_price', 0):.2f}")
        else:
            parts.append("\nCurrent Position: None")

        parts.append("\nReview this proposal. Approve, reject, or suggest modifications based on:")
        parts.append("- Risk/reward alignment")
        parts.append("- Market conditions vs proposal")
        parts.append("- Position sizing appropriateness")
        parts.append("- Stop loss and take profit logic")

        return '\n'.join(parts)

    def _parse_response(self, data: Dict) -> Dict:
        """Parse and validate consultant response"""
        try:
            content = data['choices'][0]['message']['content'].strip()

            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
                content = content.strip()

            review = json.loads(content)

            # Validate required fields
            required_fields = ['decision', 'confidence', 'rationale']
            for field in required_fields:
                if field not in review:
                    logger.warning(f"Missing field in consultant response: {field}")
                    return self._get_fallback_approval({}, f"Incomplete response: missing {field}")

            # Validate decision values
            valid_decisions = ['approve', 'reject', 'modify']
            if review['decision'] not in valid_decisions:
                logger.warning(f"Invalid decision in consultant response: {review['decision']}")
                review['decision'] = 'approve'  # Default to approve on error

            # Validate confidence
            review['confidence'] = max(0, min(100, int(review.get('confidence', 50))))

            # Ensure rationale is a string
            if not isinstance(review.get('rationale'), str):
                review['rationale'] = str(review.get('rationale', 'No rationale provided'))

            # If modify, ensure modifications dict exists
            if review['decision'] == 'modify':
                if 'modifications' not in review or not isinstance(review['modifications'], dict):
                    logger.warning("Modify decision missing modifications dict")
                    review['decision'] = 'approve'
                    review['modifications'] = {}

            return review

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse consultant response as JSON: {e}")
            return self._get_fallback_approval({}, "Invalid JSON response")
        except Exception as e:
            logger.error(f"Failed to parse consultant response: {e}")
            return self._get_fallback_approval({}, str(e))

    def _get_fallback_approval(self, main_proposal: Dict, reason: str) -> Dict:
        """Return a fallback approval when consultant is unavailable"""
        return {
            'decision': 'approve',
            'confidence': 50,
            'rationale': f"Auto-approved due to consultant unavailable: {reason}",
            'modifications': {}
        }
