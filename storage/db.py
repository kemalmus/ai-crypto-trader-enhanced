import os
import asyncpg
from datetime import datetime
from typing import Optional, Dict, List, Any
import json

class Database:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.database_url = os.getenv('DATABASE_URL')
    
    async def connect(self):
        if not self.pool:
            self.pool = await asyncpg.create_pool(self.database_url, min_size=2, max_size=10)
    
    async def close(self):
        if self.pool:
            await self.pool.close()
    
    async def init_nav(self, nav_usd: float):
        async with self.pool.acquire() as conn:
            await conn.execute(
                '''INSERT INTO nav (ts, nav_usd, realized_pnl, unrealized_pnl, dd_pct)
                   VALUES ($1, $2, $3, $4, $5)
                   ON CONFLICT (ts) DO NOTHING''',
                datetime.utcnow(), nav_usd, 0.0, 0.0, 0.0
            )
            await conn.execute(
                '''INSERT INTO config (key, value)
                   VALUES ($1, $2)
                   ON CONFLICT (key) DO UPDATE SET value = $2''',
                'initial_nav', json.dumps({'value': nav_usd, 'ts': datetime.utcnow().isoformat()})
            )
    
    async def get_nav(self) -> Optional[Dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow('SELECT * FROM nav ORDER BY ts DESC LIMIT 1')
            if row:
                return dict(row)
            return None
    
    async def update_nav(self, nav_usd: float, realized_pnl: float, unrealized_pnl: float, dd_pct: float):
        async with self.pool.acquire() as conn:
            await conn.execute(
                '''INSERT INTO nav (ts, nav_usd, realized_pnl, unrealized_pnl, dd_pct)
                   VALUES ($1, $2, $3, $4, $5)''',
                datetime.utcnow(), nav_usd, realized_pnl, unrealized_pnl, dd_pct
            )
    
    async def log_event(self, level: str, tags: List[str], action: str = None, 
                       symbol: str = None, tf: str = None, decision_id: str = None,
                       trade_id: int = None, payload: Dict = None):
        async with self.pool.acquire() as conn:
            await conn.execute(
                '''INSERT INTO event_log (ts, level, tags, symbol, tf, action, decision_id, trade_id, payload)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)''',
                datetime.utcnow(), level, tags, symbol, tf, action, decision_id, trade_id,
                json.dumps(payload) if payload else None
            )
    
    async def save_candles(self, symbol: str, tf: str, candles: List[Dict]):
        async with self.pool.acquire() as conn:
            await conn.executemany(
                '''INSERT INTO candles (symbol, tf, ts, o, h, l, c, v)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                   ON CONFLICT (symbol, tf, ts) DO UPDATE
                   SET o = $4, h = $5, l = $6, c = $7, v = $8''',
                [(symbol, tf, c['ts'], c['o'], c['h'], c['l'], c['c'], c['v']) for c in candles]
            )
    
    async def get_candles(self, symbol: str, tf: str, limit: int = 200) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                '''SELECT * FROM candles WHERE symbol = $1 AND tf = $2
                   ORDER BY ts DESC LIMIT $3''',
                symbol, tf, limit
            )
            result = []
            for row in reversed(rows):
                d = dict(row)
                for k, v in d.items():
                    if hasattr(v, '__float__') and not isinstance(v, (int, float)):
                        d[k] = float(v)
                result.append(d)
            return result
    
    async def get_positions(self) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('SELECT * FROM positions')
            result = []
            for row in rows:
                d = dict(row)
                for k, v in d.items():
                    if hasattr(v, '__float__') and not isinstance(v, (int, float)):
                        d[k] = float(v)
                result.append(d)
            return result
    
    async def upsert_position(self, symbol: str, qty: float, avg_price: float, 
                            side: str, stop: float = None, trade_id: int = None):
        async with self.pool.acquire() as conn:
            now = datetime.utcnow()
            await conn.execute(
                '''INSERT INTO positions (symbol, qty, avg_price, side, stop, trade_id, opened_ts, last_update_ts)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                   ON CONFLICT (symbol) DO UPDATE
                   SET qty = $2, avg_price = $3, side = $4, stop = $5, trade_id = $6, last_update_ts = $8''',
                symbol, qty, avg_price, side, stop, trade_id, now, now
            )
    
    async def close_position(self, symbol: str):
        async with self.pool.acquire() as conn:
            await conn.execute('DELETE FROM positions WHERE symbol = $1', symbol)
    
    async def create_trade(self, symbol: str, side: str, qty: float, entry_px: float,
                          entry_fees: float = 0, slippage_bps: float = 0) -> int:
        async with self.pool.acquire() as conn:
            trade_id = await conn.fetchval(
                '''INSERT INTO trades (symbol, side, qty, entry_ts, entry_px, fees, slippage_bps)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
                   RETURNING id''',
                symbol, side, qty, datetime.utcnow(), entry_px, entry_fees, slippage_bps
            )
            return trade_id
    
    async def close_trade(self, trade_id: int, exit_px: float, exit_fees: float,
                         exit_slippage_bps: float, pnl: float, reason: str = None):
        async with self.pool.acquire() as conn:
            await conn.execute(
                '''UPDATE trades 
                   SET exit_ts = $1, exit_px = $2, fees = fees + $3, 
                       slippage_bps = (slippage_bps + $4) / 2, pnl = $5, reason = $6
                   WHERE id = $7''',
                datetime.utcnow(), exit_px, exit_fees, exit_slippage_bps, pnl, reason, trade_id
            )
    
    async def get_open_trade(self, symbol: str) -> Optional[Dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT * FROM trades WHERE symbol = $1 AND exit_ts IS NULL ORDER BY entry_ts DESC LIMIT 1',
                symbol
            )
            return dict(row) if row else None
    
    async def get_total_realized_pnl(self) -> float:
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(
                'SELECT COALESCE(SUM(pnl), 0) FROM trades WHERE pnl IS NOT NULL'
            )
            return float(result)
    
    async def get_config(self, key: str) -> Optional[Any]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow('SELECT value FROM config WHERE key = $1', key)
            if row:
                return json.loads(row['value'])
            return None
    
    async def set_config(self, key: str, value: Any):
        async with self.pool.acquire() as conn:
            await conn.execute(
                '''INSERT INTO config (key, value)
                   VALUES ($1, $2)
                   ON CONFLICT (key) DO UPDATE SET value = $2''',
                key, json.dumps(value)
            )
    
    async def get_logs(self, limit: int = 50, level: Optional[str] = None, tag: Optional[str] = None) -> List[Dict]:
        async with self.pool.acquire() as conn:
            query = 'SELECT * FROM event_log WHERE 1=1'
            params = []
            param_idx = 1
            
            if level:
                query += f' AND level = ${param_idx}'
                params.append(level)
                param_idx += 1
            
            if tag:
                query += f' AND ${param_idx} = ANY(tags)'
                params.append(tag)
                param_idx += 1
            
            query += f' ORDER BY ts DESC LIMIT ${param_idx}'
            params.append(limit)
            
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
    
    async def save_sentiment(self, symbol: str, score: float, summary: str, 
                            citations: List[str] = None, model: str = None):
        async with self.pool.acquire() as conn:
            await conn.execute(
                '''INSERT INTO sentiment (ts, symbol, score, summary, citations, model)
                   VALUES ($1, $2, $3, $4, $5, $6)''',
                datetime.utcnow(), symbol, score, summary, 
                citations or [], model
            )
    
    async def get_latest_sentiment(self, symbol: str) -> Optional[Dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT * FROM sentiment WHERE symbol = $1 ORDER BY ts DESC LIMIT 1',
                symbol
            )
            return dict(row) if row else None
