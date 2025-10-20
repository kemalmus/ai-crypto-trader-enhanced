import aiohttp
from typing import Dict
import logging

logger = logging.getLogger(__name__)

class DuckDuckGoSearch:
    """Fallback search using DuckDuckGo Instant Answer API and news search"""
    
    def __init__(self):
        self.instant_api = 'https://api.duckduckgo.com/'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; TradingBot/1.0)'
        }
    
    async def search_news(self, symbol: str) -> Dict:
        """Search for recent news about the given cryptocurrency symbol
        
        Always returns a valid sentiment dict, never None"""
        asset = symbol.split('/')[0]
        
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    'q': f'{asset} cryptocurrency news',
                    'format': 'json',
                    'no_html': '1',
                    'skip_disambig': '1'
                }
                
                async with session.get(self.instant_api, params=params, headers=self.headers) as response:
                    if response.status != 200:
                        logger.warning(f"DuckDuckGo API error {response.status}, returning neutral sentiment")
                        return self._get_default_sentiment(symbol, f"DuckDuckGo API error: HTTP {response.status}")
                    
                    data = await response.json()
                    return self._parse_ddg_response(symbol, data, asset)
        
        except Exception as e:
            logger.warning(f"DuckDuckGo search failed for {symbol}: {e}, returning neutral sentiment")
            return self._get_default_sentiment(symbol, f"DuckDuckGo search error: {str(e)}")
    
    def _parse_ddg_response(self, symbol: str, data: Dict, asset: str) -> Dict:
        """Parse DuckDuckGo response and derive sentiment from available data"""
        try:
            # Collect text snippets for analysis
            snippets = []
            sources = []
            
            # Abstract text
            if data.get('Abstract'):
                snippets.append(data['Abstract'])
            
            # Related topics
            if data.get('RelatedTopics'):
                for topic in data['RelatedTopics'][:5]:
                    if isinstance(topic, dict) and topic.get('Text'):
                        snippets.append(topic['Text'])
                    if isinstance(topic, dict) and topic.get('FirstURL'):
                        sources.append(topic['FirstURL'])
            
            # Combine snippets
            combined_text = ' '.join(snippets).strip()
            
            # Check if we got meaningful data
            if not combined_text or len(combined_text) < 20:
                logger.warning(f"DuckDuckGo returned minimal data for {asset}")
                return self._get_default_sentiment(
                    symbol, 
                    f"No recent news found for {asset} via DuckDuckGo search. Market data unavailable from fallback source."
                )
            
            # Derive basic sentiment from keyword analysis
            score = self._analyze_keywords(combined_text)
            
            reasoning = f"DuckDuckGo search analysis for {asset} (keyword-based sentiment): {combined_text[:400]}"
            if len(combined_text) > 400:
                reasoning += "..."
            
            return {
                'symbol': symbol,
                'sent_24h': score,
                'sent_7d': None,
                'sent_trend': score,
                'burst': 0.0,
                'sources': {
                    'reasoning': reasoning,
                    'citations': sources[:5] if sources else [],
                    'model': 'duckduckgo-fallback',
                    'score_extracted': score,
                    'timestamp': None,
                    'data_quality': 'low-confidence-fallback'
                }
            }
        
        except Exception as e:
            logger.error(f"Failed to parse DuckDuckGo response: {e}")
            return self._get_default_sentiment(symbol, f"Parse error: {str(e)}")
    
    def _get_default_sentiment(self, symbol: str, reason: str) -> Dict:
        """Return a default neutral sentiment when no data is available"""
        return {
            'symbol': symbol,
            'sent_24h': 0.0,
            'sent_7d': 0.0,
            'sent_trend': 0.0,
            'burst': 0.0,
            'sources': {
                'reasoning': reason,
                'citations': [],
                'model': 'duckduckgo-fallback',
                'score_extracted': 0.0,
                'timestamp': None,
                'data_quality': 'no-data-available'
            }
        }
    
    def _analyze_keywords(self, text: str) -> float:
        """Simple keyword-based sentiment analysis"""
        text_lower = text.lower()
        
        positive_keywords = [
            'surge', 'soar', 'rally', 'gain', 'up', 'rise', 'bullish', 'growth',
            'breakthrough', 'adoption', 'institutional', 'etf', 'approval', 'milestone'
        ]
        
        negative_keywords = [
            'crash', 'plunge', 'drop', 'fall', 'down', 'bearish', 'decline',
            'hack', 'scam', 'regulation', 'ban', 'concern', 'risk', 'loss'
        ]
        
        positive_count = sum(1 for kw in positive_keywords if kw in text_lower)
        negative_count = sum(1 for kw in negative_keywords if kw in text_lower)
        
        total = positive_count + negative_count
        if total == 0:
            return 0.0
        
        # Calculate score based on keyword ratio
        net_sentiment = (positive_count - negative_count) / total
        
        # Scale to [-1, 1] range, but cap at ±0.5 for keyword-based analysis
        return max(-0.5, min(0.5, net_sentiment))
