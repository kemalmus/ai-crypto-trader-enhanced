import os
import aiohttp
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    def __init__(self):
        self.api_key = os.getenv('PERPLEXITY_API_KEY')
        self.base_url = 'https://api.perplexity.ai/chat/completions'
        self.model = 'llama-3.1-sonar-small-128k-online'
    
    async def analyze_symbol(self, symbol: str) -> Optional[Dict]:
        if not self.api_key:
            logger.warning("PERPLEXITY_API_KEY not set, skipping sentiment analysis")
            return None
        
        query = self._build_query(symbol)
        
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
                            'content': 'You are a financial analyst. Analyze sentiment concisely with a score from -1 (very bearish) to +1 (very bullish) and brief reasoning.'
                        },
                        {
                            'role': 'user',
                            'content': query
                        }
                    ],
                    'max_tokens': 200,
                    'temperature': 0.2,
                    'search_recency_filter': 'day',
                    'return_related_questions': False,
                    'stream': False
                }
                
                async with session.post(self.base_url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Perplexity API error {response.status}: {error_text}")
                        return None
                    
                    data = await response.json()
                    return self._parse_response(symbol, data)
        
        except Exception as e:
            logger.error(f"Sentiment analysis failed for {symbol}: {e}")
            return None
    
    def _build_query(self, symbol: str) -> str:
        asset = symbol.split('/')[0]
        return (
            f"Analyze current market sentiment for {asset} cryptocurrency. "
            f"Provide: 1) sentiment score from -1 (bearish) to +1 (bullish), "
            f"2) brief summary of recent news/developments. Keep response under 100 words."
        )
    
    def _parse_response(self, symbol: str, data: Dict) -> Dict:
        try:
            content = data['choices'][0]['message']['content']
            citations = data.get('citations', [])
            
            score = self._extract_score(content)
            
            return {
                'symbol': symbol,
                'score': score,
                'summary': content,
                'citations': citations[:3],
                'model': data.get('model', self.model)
            }
        except Exception as e:
            logger.error(f"Failed to parse sentiment response: {e}")
            return {
                'symbol': symbol,
                'score': 0.0,
                'summary': 'Unable to parse sentiment',
                'citations': [],
                'model': self.model
            }
    
    def _extract_score(self, content: str) -> float:
        content_lower = content.lower()
        
        if 'bullish' in content_lower or 'positive' in content_lower:
            if 'very' in content_lower or 'strong' in content_lower:
                return 0.7
            return 0.4
        elif 'bearish' in content_lower or 'negative' in content_lower:
            if 'very' in content_lower or 'strong' in content_lower:
                return -0.7
            return -0.4
        elif 'neutral' in content_lower or 'mixed' in content_lower:
            return 0.0
        
        for line in content.split('\n'):
            if 'score' in line.lower() or 'sentiment' in line.lower():
                try:
                    for word in line.split():
                        cleaned = word.strip(',:()[]')
                        if cleaned.replace('.', '').replace('-', '').isdigit() or \
                           (cleaned.startswith('-') and cleaned[1:].replace('.', '').isdigit()):
                            score = float(cleaned)
                            if -1.0 <= score <= 1.0:
                                return score
                except ValueError:
                    continue
        
        return 0.0
