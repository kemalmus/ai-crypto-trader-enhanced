import os
import aiohttp
from typing import Dict, Optional, List
import logging
import json

logger = logging.getLogger(__name__)

class LLMAdvisor:
    def __init__(self, provider: str = 'openai'):
        self.provider = provider
        
        if provider == 'openai':
            self.api_key = os.getenv('OPENAI_API_KEY')
            self.base_url = 'https://api.openai.com/v1/chat/completions'
            self.model = 'gpt-4o-mini'
        elif provider == 'perplexity':
            self.api_key = os.getenv('PERPLEXITY_API_KEY')
            self.base_url = 'https://api.perplexity.ai/chat/completions'
            self.model = 'llama-3.1-sonar-small-128k-chat'
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    async def get_trade_proposal(self, symbol: str, regime: str, signals: Dict, 
                                 sentiment: Optional[Dict] = None,
                                 current_position: Optional[Dict] = None) -> Optional[Dict]:
        if not self.api_key:
            logger.warning(f"{self.provider.upper()}_API_KEY not set, skipping LLM advisor")
            return None
        
        prompt = self._build_prompt(symbol, regime, signals, sentiment, current_position)
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
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
                    'temperature': 0.3,
                    'max_tokens': 300
                }
                
                async with session.post(self.base_url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"{self.provider} API error {response.status}: {error_text}")
                        return None
                    
                    data = await response.json()
                    return self._parse_response(data)
        
        except Exception as e:
            logger.error(f"LLM advisor failed: {e}")
            return None
    
    def _get_system_prompt(self) -> str:
        return (
            "You are an expert cryptocurrency trading advisor. Analyze the provided market data "
            "and provide a concise trading recommendation. Format your response as JSON with these fields:\n"
            "- action: 'buy', 'sell', 'hold', or 'skip'\n"
            "- confidence: 0-100 (percentage)\n"
            "- reasoning: brief explanation (max 100 words)\n"
            "- risk_level: 'low', 'medium', or 'high'\n\n"
            "Only respond with valid JSON, no additional text."
        )
    
    def _build_prompt(self, symbol: str, regime: str, signals: Dict, 
                     sentiment: Optional[Dict], current_position: Optional[Dict]) -> str:
        parts = [
            f"Symbol: {symbol}",
            f"Market Regime: {regime}",
            f"\nTechnical Signals: {json.dumps(signals, indent=2)}"
        ]
        
        if sentiment:
            parts.append(f"\nSentiment Analysis:")
            parts.append(f"  Score: {sentiment.get('score', 0):.2f} (-1 to +1)")
            parts.append(f"  Summary: {sentiment.get('summary', 'N/A')[:200]}")
        
        if current_position:
            parts.append(f"\nCurrent Position:")
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
            
            required_fields = ['action', 'confidence', 'reasoning', 'risk_level']
            for field in required_fields:
                if field not in proposal:
                    logger.warning(f"Missing field in LLM response: {field}")
                    return self._get_default_proposal(f"Incomplete response: missing {field}")
            
            valid_actions = ['buy', 'sell', 'hold', 'skip']
            if proposal['action'] not in valid_actions:
                proposal['action'] = 'skip'
            
            valid_risk_levels = ['low', 'medium', 'high']
            if proposal['risk_level'] not in valid_risk_levels:
                proposal['risk_level'] = 'medium'
            
            proposal['confidence'] = max(0, min(100, int(proposal['confidence'])))
            
            return proposal
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return self._get_default_proposal("Invalid JSON response")
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return self._get_default_proposal(str(e))
    
    def _get_default_proposal(self, reason: str) -> Dict:
        return {
            'action': 'skip',
            'confidence': 0,
            'reasoning': f"LLM advisor unavailable: {reason}",
            'risk_level': 'high'
        }
