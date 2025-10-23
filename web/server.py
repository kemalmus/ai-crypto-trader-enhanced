"""
FastAPI server for AI Crypto Trading Agent UI
Provides cyberpunk terminal-like interface with live logs and dashboards
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Literal
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Query
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn
import json

from storage.db import Database
from configs.app import Config

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    try:
        print("Starting up database connection...")
        await init_db()
        print("Database connection established")
    except Exception as e:
        print(f"Warning: Database connection failed during startup: {e}")
        print("UI will work but API endpoints may return errors")
    yield
    # Shutdown would go here if needed


app = FastAPI(
    title="AI Crypto Trading Agent UI",
    version="1.0.0",
    lifespan=lifespan
)
templates = Jinja2Templates(directory="web/templates")

# Mount static files
app.mount("/static", StaticFiles(directory="web/static"), name="static")
app.mount("/ui", StaticFiles(directory="web/static/ui", html=True), name="ui")

# Global config and db instances
config = Config()
db = Database()


async def get_db_connection():
    """Get database connection from pool"""
    return db.pool.acquire()


async def init_db():
    """Initialize database connection"""
    await db.connect()


class OverviewData(BaseModel):
    nav_usd: float
    realized_pnl: float
    unrealized_pnl: float
    dd_pct: float
    open_positions_count: int
    last_cycle_ts: Optional[datetime]
    cycle_latency_ms: Optional[int]


class SymbolData(BaseModel):
    symbol: str
    regime: str  # "trend" or "chop"
    last_price: float
    rvol: float
    donch_upper: float
    donch_lower: float
    cmf: float


class TradeData(BaseModel):
    id: int
    symbol: str
    side: str
    qty: float
    entry_ts: datetime
    entry_px: float
    exit_ts: Optional[datetime]
    exit_px: Optional[float]
    pnl: Optional[float]
    fees: float
    slippage_bps: float
    reason: Optional[str]


class LogEvent(BaseModel):
    id: int
    ts: datetime
    level: str
    tags: list[str]
    symbol: Optional[str]
    tf: Optional[str]
    action: Optional[str]
    decision_id: Optional[str]
    trade_id: Optional[int]
    payload: Optional[dict] = None


@app.get("/")
async def index(request: Request):
    """Main UI page with tabs"""
    from datetime import datetime
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "symbols": config.symbols,
            "title": "AI Crypto Trading Agent",
            "current_time": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        }
    )


@app.get("/api/overview")
async def get_overview() -> OverviewData:
    """Get overview data"""
    if not db.pool:
        await init_db()

    try:
        async with db.pool.acquire() as conn:
            # Get latest NAV
            nav_result = await conn.fetchrow(
                "SELECT nav_usd, realized_pnl, unrealized_pnl, dd_pct, ts FROM nav ORDER BY ts DESC LIMIT 1"
            )
            if not nav_result:
                # Return defaults if no NAV data
                return OverviewData(
                    nav_usd=0.0,
                    realized_pnl=0.0,
                    unrealized_pnl=0.0,
                    dd_pct=0.0,
                    open_positions_count=0,
                    last_cycle_ts=None,
                    cycle_latency_ms=None
                )

            # Get open positions count
            positions_count = await conn.fetchval("SELECT COUNT(*) FROM positions")

            # Get last cycle timestamp and latency from event_log
            cycle_result = await conn.fetchrow(
                "SELECT ts, payload FROM event_log WHERE 'CYCLE' = ANY(tags) ORDER BY ts DESC LIMIT 1"
            )
            last_cycle_ts = cycle_result["ts"] if cycle_result else None
            cycle_latency_ms = cycle_result["payload"].get("latency_ms") if cycle_result and cycle_result["payload"] else None

            return OverviewData(
                nav_usd=float(nav_result["nav_usd"]),
                realized_pnl=float(nav_result["realized_pnl"]),
                unrealized_pnl=float(nav_result["unrealized_pnl"]),
                dd_pct=float(nav_result["dd_pct"]),
                open_positions_count=positions_count,
                last_cycle_ts=last_cycle_ts,
                cycle_latency_ms=cycle_latency_ms
            )
    except Exception as e:
        # Return default data if database fails
        return OverviewData(
            nav_usd=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            dd_pct=0.0,
            open_positions_count=0,
            last_cycle_ts=None,
            cycle_latency_ms=None
        )


@app.get("/api/symbols")
async def get_symbols() -> list[SymbolData]:
    """Get latest data for all symbols"""
    if not db.pool:
        await init_db()

    try:
        symbols_data = []
        async with db.pool.acquire() as conn:
            for symbol in config.symbols:
                # Get latest features
                features = await conn.fetchrow(
                    "SELECT * FROM features WHERE symbol = $1 AND tf = $2 ORDER BY ts DESC LIMIT 1",
                    symbol, config.timeframes[0]  # Primary timeframe
                )
                if not features:
                    # Return default data for symbols without features
                    symbols_data.append(SymbolData(
                        symbol=symbol,
                        regime="unknown",
                        last_price=0.0,
                        rvol=0.0,
                        donch_upper=0.0,
                        donch_lower=0.0,
                        cmf=0.0
                    ))
                    continue

                # Determine regime (ADX > 20 and EMA50 > EMA200 → trend)
                regime = "trend" if (features.get("adx14", 0) > 20 and
                                   features.get("ema50", 0) > features.get("ema200", 0)) else "chop"

                symbols_data.append(SymbolData(
                    symbol=symbol,
                    regime=regime,
                    last_price=float(features.get("c", 0)),
                    rvol=float(features.get("rvol20", 0)),
                    donch_upper=float(features.get("donch_u", 0)),
                    donch_lower=float(features.get("donch_l", 0)),
                    cmf=float(features.get("cmf20", 0))
                ))

            return symbols_data
    except Exception as e:
        # Return default data if database fails
        return [SymbolData(
            symbol=symbol,
            regime="unknown",
            last_price=0.0,
            rvol=0.0,
            donch_upper=0.0,
            donch_lower=0.0,
            cmf=0.0
        ) for symbol in config.symbols]


@app.get("/api/trades")
async def get_trades(
    since: Optional[str] = Query(None, description="Since timestamp (ISO format)"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    limit: int = Query(100, ge=1, le=1000)
) -> list[TradeData]:
    """Get recent trades"""
    if not db.pool:
        await init_db()

    try:
        async with db.pool.acquire() as conn:
            query = """
            SELECT id, symbol, side, qty, entry_ts, entry_px, exit_ts, exit_px,
                   pnl, fees, slippage_bps, reason
            FROM trades
            WHERE ($1::text IS NULL OR symbol = $1)
            AND ($2::timestamptz IS NULL OR entry_ts >= $2)
            ORDER BY entry_ts DESC
            LIMIT $3
            """
            since_ts = datetime.fromisoformat(since.replace('Z', '+00:00')) if since else None
            rows = await conn.fetch(query, symbol, since_ts, limit)

            return [TradeData(
                id=row["id"],
                symbol=row["symbol"],
                side=row["side"],
                qty=float(row["qty"]),
                entry_ts=row["entry_ts"],
                entry_px=float(row["entry_px"]),
                exit_ts=row["exit_ts"],
                exit_px=float(row["exit_px"]) if row["exit_px"] else None,
                pnl=float(row["pnl"]) if row["pnl"] else None,
                fees=float(row["fees"]),
                slippage_bps=float(row["slippage_bps"]),
                reason=row["reason"]
            ) for row in rows]
    except Exception as e:
        # Return empty list if database fails
        return []


@app.get("/api/logs")
async def get_logs(
    limit: int = Query(50, ge=1, le=500),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    level: Optional[str] = Query(None, description="Filter by level"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    decision_id: Optional[str] = Query(None, description="Filter by decision_id"),
    since: Optional[str] = Query(None, description="Since timestamp (ISO format)")
) -> list[LogEvent]:
    """Get filtered log events"""
    if not db.pool:
        await init_db()

    try:
        async with db.pool.acquire() as conn:
            query_parts = ["SELECT * FROM event_log WHERE 1=1"]
            params = []
            param_idx = 1

            if tags:
                tag_list = [t.strip() for t in tags.split(",")]
                query_parts.append(f"AND tags && ${param_idx}")
                params.append(tag_list)
                param_idx += 1

            if level:
                query_parts.append(f"AND level = ${param_idx}")
                params.append(level)
                param_idx += 1

            if symbol:
                query_parts.append(f"AND symbol = ${param_idx}")
                params.append(symbol)
                param_idx += 1

            if decision_id:
                query_parts.append(f"AND decision_id = ${param_idx}")
                params.append(decision_id)
                param_idx += 1

            if since:
                since_ts = datetime.fromisoformat(since.replace('Z', '+00:00'))
                query_parts.append(f"AND ts >= ${param_idx}")
                params.append(since_ts)
                param_idx += 1

            query_parts.append(f"ORDER BY ts DESC LIMIT ${param_idx}")
            params.append(limit)

            query = " ".join(query_parts)
            rows = await conn.fetch(query, *params)

            return [LogEvent(
                id=row["id"],
                ts=row["ts"],
                level=row["level"],
                tags=row["tags"],
                symbol=row["symbol"],
                tf=row["tf"],
                action=row["action"],
                decision_id=row["decision_id"],
                trade_id=row["trade_id"],
                payload=row["payload"] if row["payload"] is not None else {}
            ) for row in rows]
    except Exception as e:
        # Return empty list if database fails
        return []


@app.get("/api/logs/stream")
async def stream_logs(last_id: Optional[int] = Query(None)):
    """SSE stream for live log events"""
    async def event_generator():
        last_processed_id = last_id or 0

        while True:
            async with db.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT * FROM event_log WHERE id > $1 ORDER BY id ASC",
                    last_processed_id
                )

                for row in rows:
                    event_data = {
                        "id": row["id"],
                        "ts": row["ts"].isoformat(),
                        "level": row["level"],
                        "tags": row["tags"],
                        "symbol": row["symbol"],
                        "tf": row["tf"],
                        "action": row["action"],
                        "decision_id": row["decision_id"],
                        "trade_id": row["trade_id"],
                        "payload": row["payload"] if row["payload"] is not None else {}
                    }
                    yield f"data: {json.dumps(event_data)}\n\n"
                    last_processed_id = row["id"]

            await asyncio.sleep(1)  # Poll every second

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.get("/api/candles")
async def get_candles(symbol: str, tf: Literal["5m", "1h"] = "5m", limit: int = Query(288, ge=1, le=2000)):
    """Return recent candles for a symbol and timeframe for charts/sparklines."""
    if not db.pool:
        await init_db()
    try:
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT ts, o, h, l, c, v
                FROM candles
                WHERE symbol = $1 AND tf = $2
                ORDER BY ts DESC
                LIMIT $3
                """,
                symbol, tf, limit
            )
            data = [
                {
                    "ts": r["ts"].isoformat(),
                    "o": float(r["o"]),
                    "h": float(r["h"]),
                    "l": float(r["l"]),
                    "c": float(r["c"]),
                    "v": float(r["v"]),
                }
                for r in reversed(rows)
            ]
            return data
    except Exception:
        return []


@app.get("/api/sentiment")
async def get_latest_sentiment(symbol: str):
    """Return latest sentiment snapshot for a symbol."""
    if not db.pool:
        await init_db()
    try:
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT ts, sent_24h, sent_7d, sent_trend, burst, sources
                FROM sentiment
                WHERE symbol = $1
                ORDER BY ts DESC
                LIMIT 1
                """,
                symbol,
            )
            if not row:
                return {
                    "symbol": symbol,
                    "sent_24h": 0.0,
                    "sent_7d": 0.0,
                    "sent_trend": 0.0,
                    "burst": 0.0,
                    "sources": {},
                }
            return {
                "symbol": symbol,
                "ts": row["ts"].isoformat(),
                "sent_24h": float(row["sent_24h"] or 0),
                "sent_7d": float(row["sent_7d"] or 0),
                "sent_trend": float(row["sent_trend"] or 0),
                "burst": float(row["burst"] or 0),
                "sources": row["sources"] or {},
            }
    except Exception:
        return {
            "symbol": symbol,
            "sent_24h": 0.0,
            "sent_7d": 0.0,
            "sent_trend": 0.0,
            "burst": 0.0,
            "sources": {},
        }


if __name__ == "__main__":
    uvicorn.run(
        "web.server:app",
        host=config.ui.get('host', '0.0.0.0'),
        port=config.ui.get('port', 8000),
        reload=True,
        log_level="info"
    )
