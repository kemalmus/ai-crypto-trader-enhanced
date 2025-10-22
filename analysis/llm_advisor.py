import os
import aiohttp
import time
from typing import Dict, Optional, Tuple
import logging
import json

logger = logging.getLogger(__name__)

class LLMAdvisor:
    def __init__(self, consultant_agent=None):
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        self.base_url = 'https://openrouter.ai/api/v1/chat/completions'
        self.primary_model = 'deepseek/deepseek-chat-v3-0324'
        self.fallback_model = 'x-ai/grok-beta'
        self.consultant_agent = consultant_agent
    
    async def get_trade_proposal(self, symbol: str, regime: str, signals: Dict,
                                 sentiment: Optional[Dict] = None,
                                 current_position: Optional[Dict] = None) -> Optional[Dict]:
        """Legacy method for backward compatibility - use get_trade_proposal_with_consultant for full workflow"""
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY not set, skipping LLM advisor")
            return None

        prompt = self._build_prompt(symbol, regime, signals, sentiment, current_position)

        proposal = await self._call_model(self.primary_model, prompt)
        if proposal:
            return proposal

        logger.warning(f"Primary model {self.primary_model} failed, trying fallback")
        proposal = await self._call_model(self.fallback_model, prompt)
        return proposal

    async def get_trade_proposal_with_consultant(self, symbol: str, regime: str, signals: Dict,
                                                sentiment: Optional[Dict] = None,
                                                current_position: Optional[Dict] = None) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        Get trading proposal with consultant review.

        Returns:
            Tuple of (final_proposal, consultant_review) where final_proposal may be modified
            based on consultant feedback, and consultant_review contains the consultant's decision.
        """
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY not set, skipping LLM advisor")
            return None, None

        # Get initial proposal from main LLM
        start_time = time.time()
        prompt = self._build_prompt(symbol, regime, signals, sentiment, current_position)

        proposal = await self._call_model(self.primary_model, prompt)
        model_used = self.primary_model

        if not proposal:
            logger.warning(f"Primary model {self.primary_model} failed, trying fallback")
            proposal = await self._call_model(self.fallback_model, prompt)
            model_used = self.fallback_model

        if not proposal:
            logger.error("Both primary and fallback models failed")
            return None, None

        # Add metadata to proposal
        proposal['_metadata'] = {
            'model_used': model_used,
            'response_time_ms': int((time.time() - start_time) * 1000),
            'primary_model_attempted': self.primary_model,
            'fallback_used': model_used != self.primary_model
        }

        # If no consultant agent, return proposal as-is
        if not self.consultant_agent:
            logger.info("No consultant agent configured, returning proposal without review")
            return proposal, None

        # Get consultant review
        consultant_review = await self.consultant_agent.review_proposal(
            symbol, regime, signals, sentiment, current_position, proposal
        )

        if not consultant_review:
            logger.warning("Consultant review failed, proceeding with original proposal")
            return proposal, None

        # Apply consultant modifications if decision is 'modify'
        final_proposal = proposal.copy()
        if consultant_review['decision'] == 'modify':
            modifications = consultant_review.get('modifications', {})
            for field, value in modifications.items():
                if field in final_proposal:
                    logger.info(f"Consultant modifying {field}: {final_proposal[field]} -> {value}")
                    final_proposal[field] = value
                else:
                    logger.warning(f"Consultant tried to modify non-existent field: {field}")
            final_proposal['_consultant_modifications'] = modifications

        # Add consultant review metadata
        final_proposal['_consultant_review'] = consultant_review

        logger.info(f"Consultant {consultant_review['decision']} for {symbol} "
                   f"(confidence: {consultant_review['confidence']}%)")

        return final_proposal, consultant_review

    def serialize_decision_context(self, symbol: str, regime: str, signals: Dict,
                                  sentiment: Optional[Dict] = None,
                                  current_position: Optional[Dict] = None,
                                  proposal: Dict = None,
                                  consultant_review: Dict = None) -> str:
        """
        Serialize the complete decision context for storage in the database.

        Args:
            symbol: Trading pair symbol
            regime: Market regime (trend/chop)
            signals: Technical signals data
            sentiment: Sentiment analysis data
            current_position: Current position if any
            proposal: LLM trading proposal
            consultant_review: Consultant review decision

        Returns:
            JSON string containing all decision context
        """
        context = {
            'symbol': symbol,
            'regime': regime,
            'timestamp': time.time(),
            'technical_signals': signals,
            'sentiment_analysis': sentiment,
            'current_position': current_position,
            'llm_proposal': proposal,
            'consultant_review': consultant_review,
            'metadata': {
                'serialized_by': 'LLMAdvisor.serialize_decision_context',
                'version': '1.0'
            }
        }

        return json.dumps(context, indent=2, default=str)
    
    async def _call_model(self, model: str, prompt: str) -> Optional[Dict]:
        """Call OpenRouter API with specified model"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json',
                    'HTTP-Referer': 'https://replit.com',
                    'X-Title': 'AI Crypto Trading Agent'
                }
                
                payload = {
                    'model': model,
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
                    'max_tokens': 400
                }
                
                response = await session.post(self.base_url, headers=headers, json=payload)
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"OpenRouter API error {response.status} for {model}: {error_text}")
                    return None

                data = await response.json()
                return self._parse_response(data)
        
        except Exception as e:
            logger.error(f"LLM advisor failed for {model}: {e}")
            return None
    
    def _get_system_prompt(self) -> str:
        return (
            "System: You may only propose trades as JSON. No prose.\n"
            "Fields:\n"
            "- symbol: string (e.g., 'BTC/USD')\n"
            "- side: 'long' | 'short' | 'flat'\n"
            "- confidence: number (0-100)\n"
            "- reasons: string[] (max 3)\n"
            "- entry: {type: 'market'}\n"
            "- stop: {type: 'atr', multiplier: number}\n"
            "- take_profit: {rr: number}\n"
            "- max_hold_bars: number\n\n"
            "Respond with JSON only."
        )
    
    def _build_prompt(self, symbol: str, regime: str, signals: Dict, 
                     sentiment: Optional[Dict], current_position: Optional[Dict]) -> str:
        parts = [
            f"Symbol: {symbol}",
            f"Market Regime: {regime}",
            f"\nTechnical Signals: {json.dumps(signals, indent=2)}"
        ]
        
        if sentiment:
            parts.append("\nSentiment Analysis:")
            parts.append(f"  Score: {sentiment.get('score', 0):.2f} (-1 to +1)")
            parts.append(f"  Summary: {sentiment.get('summary', 'N/A')[:200]}")
        
        if current_position:
            parts.append("\nCurrent Position:")
            parts.append(f"  Side: {current_position.get('side')}")
            parts.append(f"  Quantity: {current_position.get('qty')}")
            parts.append(f"  Avg Price: ${current_position.get('avg_price', 0):.2f}")
        else:
            parts.append("\nCurrent Position: None")
        
        parts.append("\nProvide your trading recommendation as JSON.")
        
        return '\n'.join(parts)
    
    def _parse_response(self, data: Dict) -> Dict:
        try:
            content = data['choices'][0]['message']['content'].strip()
            
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
                content = content.strip()
            
            proposal = json.loads(content)
            
            required_fields = ['symbol', 'side', 'confidence', 'reasons']
            for field in required_fields:
                if field not in proposal:
                    logger.warning(f"Missing field in LLM response: {field}")
                    return self._get_default_proposal(f"Incomplete response: missing {field}")
            
            valid_sides = ['long', 'short', 'flat']
            if proposal['side'] not in valid_sides:
                proposal['side'] = 'flat'
            
            proposal['confidence'] = max(0, min(100, int(proposal['confidence'])))
            
            if not isinstance(proposal.get('reasons'), list):
                proposal['reasons'] = [str(proposal.get('reasons', 'No reason provided'))]
            
            return proposal
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return self._get_default_proposal("Invalid JSON response")
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return self._get_default_proposal(str(e))
    
    def _get_default_proposal(self, reason: str, symbol: str = '') -> Dict:
        return {
            'symbol': symbol,
            'side': 'flat',
            'confidence': 0,
            'reasons': [f"LLM advisor unavailable: {reason}"],
            'entry': 'market',
            'stop': {'type': 'atr', 'multiplier': 2},
            'take_profit': {'rr': 2},
            'max_hold_bars': 100
        }
