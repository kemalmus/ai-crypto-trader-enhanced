import os
import aiohttp
from typing import Dict, Optional
from datetime import datetime, timedelta
import logging
import json

logger = logging.getLogger(__name__)

class ReflectionEngine:
    def __init__(self):
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        self.base_url = 'https://openrouter.ai/api/v1/chat/completions'
        self.model = 'deepseek/deepseek-chat-v3-0324'
    
    async def generate_reflection(self, window: str, stats: Dict) -> Optional[Dict]:
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY not set, skipping reflection")
            return None
        
        prompt = self._build_reflection_prompt(window, stats)
        
        try:
            async with aiohttp.ClientSession() as session:
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
                    'temperature': 0.3,
                    'max_tokens': 600
                }
                
                async with session.post(self.base_url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OpenRouter API error {response.status}: {error_text}")
                        return None
                    
                    data = await response.json()
                    return self._parse_response(data, window, stats)
        
        except Exception as e:
            logger.error(f"Reflection generation failed: {e}")
            return None
    
    def _get_system_prompt(self) -> str:
        return (
            "You are an expert market analyst writing a concise trading performance report. "
            "Analyze the provided statistics and write an analytical commentary. "
            "Rules:\n"
            "- Base analysis ONLY on provided facts and metrics\n"
            "- Do NOT invent data or make forecasts\n"
            "- Cite which specific metrics changed or triggered observations\n"
            "- Keep response between 600-900 characters\n"
            "- Format as JSON with fields: title (brief), body (analytical note)\n"
            "Only respond with valid JSON, no additional text."
        )
    
    def _build_reflection_prompt(self, window: str, stats: Dict) -> str:
        parts = [f"Time Window: {window}\n"]
        
        parts.append("Performance Metrics:")
        parts.append(f"- Current NAV: ${stats.get('nav', 0):,.2f}")
        parts.append(f"- Realized PnL: ${stats.get('realized_pnl', 0):,.2f}")
        parts.append(f"- Unrealized PnL: ${stats.get('unrealized_pnl', 0):,.2f}")
        parts.append(f"- Drawdown: {stats.get('dd_pct', 0):.2f}%")
        
        if stats.get('trades_count'):
            parts.append(f"\nTrading Activity:")
            parts.append(f"- Trades: {stats['trades_count']}")
            parts.append(f"- Win Rate: {stats.get('win_rate', 0):.1f}%")
            parts.append(f"- Avg PnL: ${stats.get('avg_pnl', 0):.2f}")
        
        if stats.get('positions'):
            parts.append(f"\nOpen Positions: {len(stats['positions'])}")
            for pos in stats['positions']:
                parts.append(f"  - {pos['symbol']}: {pos['side']} {pos['qty']} @ ${pos['avg_price']:.2f}")
        
        if stats.get('regimes'):
            parts.append(f"\nMarket Regimes:")
            for symbol, regime in stats['regimes'].items():
                parts.append(f"  - {symbol}: {regime}")
        
        if stats.get('sentiment'):
            parts.append(f"\nSentiment Scores:")
            for symbol, score in stats['sentiment'].items():
                parts.append(f"  - {symbol}: {score:.2f}")
        
        parts.append("\nProvide analytical commentary as JSON with title and body fields.")
        
        return '\n'.join(parts)
    
    def _parse_response(self, data: Dict, window: str, stats: Dict) -> Dict:
        try:
            content = data['choices'][0]['message']['content'].strip()
            
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
                content = content.strip()
            
            reflection = json.loads(content)
            
            if 'title' not in reflection or 'body' not in reflection:
                logger.warning("Missing title or body in reflection response")
                reflection = {
                    'title': f"Market Update - {window}",
                    'body': content if content else "No reflection generated"
                }
            
            reflection['window'] = window
            reflection['stats'] = stats
            reflection['ts'] = datetime.utcnow()
            
            return reflection
        
        except json.JSONDecodeError:
            logger.error("Failed to parse reflection response as JSON")
            return {
                'title': f"Market Update - {window}",
                'body': content if 'content' in locals() else "Failed to generate reflection",
                'window': window,
                'stats': stats,
                'ts': datetime.utcnow()
            }
        except Exception as e:
            logger.error(f"Failed to parse reflection: {e}")
            return None
