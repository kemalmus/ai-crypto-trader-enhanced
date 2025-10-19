import os
import aiohttp
from typing import Dict, Optional
import logging
from analysis.ddg_search import DuckDuckGoSearch

logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    def __init__(self):
        self.api_key = os.getenv('PERPLEXITY_API_KEY')
        self.base_url = 'https://api.perplexity.ai/chat/completions'
        self.model = 'sonar-pro'
        self.ddg_fallback = DuckDuckGoSearch()
    
    async def analyze_symbol(self, symbol: str) -> Optional[Dict]:
        # Try Perplexity first if API key is available
        if self.api_key:
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
                                'content': 'You are a financial analyst specializing in cryptocurrency markets. Provide data-driven sentiment analysis with clear numerical scores and specific supporting evidence.'
                            },
                            {
                                'role': 'user',
                                'content': query
                            }
                        ],
                        'max_tokens': 300,
                        'temperature': 0.1,
                        'search_recency_filter': 'day',
                        'return_related_questions': False,
                        'return_images': False,
                        'stream': False
                    }
                    
                    async with session.post(self.base_url, headers=headers, json=payload) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.warning(f"Perplexity API error {response.status}: {error_text}, falling back to DuckDuckGo")
                        else:
                            data = await response.json()
                            result = self._parse_response(symbol, data)
                            if result:
                                return result
            
            except Exception as e:
                logger.warning(f"Perplexity API failed for {symbol}: {e}, falling back to DuckDuckGo")
        else:
            logger.info("PERPLEXITY_API_KEY not set, using DuckDuckGo fallback")
        
        # Fallback to DuckDuckGo
        logger.info(f"Using DuckDuckGo fallback for {symbol} sentiment")
        return await self.ddg_fallback.search_news(symbol)
    
    def _build_query(self, symbol: str) -> str:
        asset = symbol.split('/')[0]
        return (
            f"Analyze current market sentiment for {asset} cryptocurrency in the last 24 hours. "
            f"Provide:\n"
            f"1) Sentiment Score: A single number from -1.0 (very bearish) to +1.0 (very bullish)\n"
            f"2) Key Reasons: List 2-3 specific factors driving this sentiment (news, technical developments, market events)\n"
            f"3) Source Quality: Brief mention of whether news is from major outlets or social media\n"
            f"Format your response clearly with the score on the first line."
        )
    
    def _parse_response(self, symbol: str, data: Dict) -> Dict:
        try:
            content = data['choices'][0]['message']['content']
            citations = data.get('citations', [])
            
            score = self._extract_score(content)
            
            return {
                'symbol': symbol,
                'sent_24h': score,
                'sent_7d': None,
                'sent_trend': score,
                'burst': 0.0,
                'sources': {
                    'reasoning': content,  # Full response with detailed reasoning
                    'citations': citations[:5] if citations else [],
                    'model': data.get('model', self.model),
                    'score_extracted': score,
                    'timestamp': data.get('created', None)
                }
            }
        except Exception as e:
            logger.error(f"Failed to parse sentiment response: {e}")
            return {
                'symbol': symbol,
                'sent_24h': 0.0,
                'sent_7d': 0.0,
                'sent_trend': 0.0,
                'burst': 0.0,
                'sources': {'error': str(e)}
            }
    
    def _extract_score(self, content: str) -> float:
        """Extract sentiment score, prioritizing explicit numbers over keywords"""
        import re
        
        lines = content.split('\n')
        
        # Strategy 1: Check lines with "score" or "sentiment" keywords FIRST
        for line in lines:
            line_lower = line.lower()
            if 'score' in line_lower or 'sentiment' in line_lower:
                # Remove parenthetical content to avoid capturing range descriptors
                # e.g., "Score (-1 to +1 scale): 0.4" becomes "Score : 0.4"
                cleaned_line = re.sub(r'\([^)]*\)', '', line_lower)
                
                # Use targeted regex to capture number after "score" or "sentiment"
                # Matches: "score: 0.4", "sentiment 0.25", "score = -0.3"
                pattern = r'(?:score|sentiment)[^\d\-+]*([-+]?\d*\.?\d+)'
                match = re.search(pattern, cleaned_line)
                if match:
                    try:
                        score = float(match.group(1))
                        if -1.0 <= score <= 1.0:
                            return score
                    except ValueError:
                        pass
                
                # Fallback: Find non-boundary values on the original line
                matches = re.findall(r'[-+]?\d*\.?\d+', line)
                for m in matches:
                    try:
                        score = float(m)
                        # Prefer values that aren't exact boundaries (-1, 1) which are likely ranges
                        if -1.0 < score < 1.0:
                            return score
                    except ValueError:
                        continue
        
        # Strategy 2: Check first 5 lines, but SKIP bullet patterns
        bullet_pattern = re.compile(r'^\s*[0-9]+[).\-]\s')
        
        for i, line in enumerate(lines[:5]):
            # Skip lines that start with bullet patterns like "1)", "2.", etc.
            if bullet_pattern.match(line):
                continue
            
            # Extract numeric values from non-bullet lines
            matches = re.findall(r'[-+]?\d*\.?\d+', line)
            for match in matches:
                try:
                    score = float(match)
                    if -1.0 <= score <= 1.0:
                        return score
                except ValueError:
                    continue
        
        # Fallback: keyword-based heuristic if no numeric score found
        content_lower = content.lower()
        
        if 'very bullish' in content_lower or 'strongly bullish' in content_lower:
            return 0.7
        elif 'very bearish' in content_lower or 'strongly bearish' in content_lower:
            return -0.7
        elif 'bullish' in content_lower or 'positive' in content_lower:
            return 0.4
        elif 'bearish' in content_lower or 'negative' in content_lower:
            return -0.4
        elif 'neutral' in content_lower or 'mixed' in content_lower:
            return 0.0
        
        return 0.0
