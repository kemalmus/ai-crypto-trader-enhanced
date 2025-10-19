import os
import aiohttp
from typing import Dict, Optional, List
import logging
import json

logger = logging.getLogger(__name__)

class LLMAdvisor:
    def __init__(self):
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        self.base_url = 'https://openrouter.ai/api/v1/chat/completions'
        self.primary_model = 'deepseek/deepseek-chat-v3-0324'
        self.fallback_model = 'x-ai/grok-beta'
    
    async def get_trade_proposal(self, symbol: str, regime: str, signals: Dict, 
                                 sentiment: Optional[Dict] = None,
                                 current_position: Optional[Dict] = None) -> Optional[Dict]:
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
    
    async def _call_model(self, model: str, prompt: str) -> Optional[Dict]:
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
                
                async with session.post(self.base_url, headers=headers, json=payload) as response:
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
            "You are an expert cryptocurrency trading advisor. Analyze the provided market data "
            "and provide a concise trading recommendation. Format your response as JSON with these fields:\n"
            "- symbol: the trading pair symbol\n"
            "- side: 'long', 'short', or 'none'\n"
            "- confidence: 0-100 (percentage confidence in the trade)\n"
            "- reasons: array of brief reasons (max 3)\n"
            "- entry: suggested entry price or 'market'\n"
            "- stop: object with {type: 'atr', multiplier: number}\n"
            "- take_profit: object with {rr: risk-reward ratio}\n"
            "- max_hold_bars: maximum bars to hold position\n\n"
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
            
            required_fields = ['symbol', 'side', 'confidence', 'reasons']
            for field in required_fields:
                if field not in proposal:
                    logger.warning(f"Missing field in LLM response: {field}")
                    return self._get_default_proposal(f"Incomplete response: missing {field}")
            
            valid_sides = ['long', 'short', 'none']
            if proposal['side'] not in valid_sides:
                proposal['side'] = 'none'
            
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
    
    def _get_default_proposal(self, reason: str) -> Dict:
        return {
            'symbol': '',
            'side': 'none',
            'confidence': 0,
            'reasons': [f"LLM advisor unavailable: {reason}"],
            'entry': 'market',
            'stop': {'type': 'atr', 'multiplier': 2},
            'take_profit': {'rr': 2},
            'max_hold_bars': 100
        }
