# AI Crypto Trading Agent

**Status:** Core system operational with paper trading daemon running successfully

## Overview

This project is an AI-powered cryptocurrency paper trading system built on Replit. It uses deterministic technical analysis for entry/exit signals while maintaining comprehensive audit trails in a Neon Postgres database.

**Last Updated:** October 19, 2025

## Architecture

### Core Components

1. **Database (Neon Postgres)** - Single source of truth for all trading data
   - 10 tables: nav, candles, features, sentiment, positions, trades, reflections, qa, config, event_log
   - Full audit trail with decision_id tracing
   - Proper trade lifecycle tracking (entry → exit)

2. **CCXT Adapter** (`adapters/ccxt_public.py`) - Multi-exchange market data
   - Configured for Binance by default
   - Easy to switch to Kraken, Bybit, etc.
   - Public OHLCV data only (no API keys for data)

3. **TA Engine** (`ta/indicators.py`) - Technical analysis with pandas-ta
   - Indicators: EMA(20/50/200), HMA(55), RSI(14), StochRSI, ATR(14), Bollinger, Donchian, OBV, CMF, ADX, RVOL, VWAP

4. **Signal Engine** (`signals/rules.py`) - Regime-based trading logic
   - Regime detection (trend vs chop using ADX)
   - Breakout/pullback entries with volume confirmation
   - ATR-based stops with trailing
   - Position sizing: 0.5% risk per trade, 2% max exposure per symbol

5. **Paper Broker** (`execution/paper.py`) - Realistic simulation
   - Slippage model: max(3bps, 0.15 * HL%)
   - Fees: 2 bps default
   - Full round-trip cost accounting (entry + exit fees)

6. **Daemon Runner** (`runner/daemon.py`) - Async trading loop
   - 120-second cycles
   - Flow: ingest → features → signals → execute → persist → update NAV → log
   - Proper error handling with structured logging

7. **CLI Interface** (`cli/__main__.py`, `agent.py`)
   - `agent init --nav 10000` - Initialize database and starting NAV
   - `agent status` - View current NAV, positions, PnL
   - `agent run --cycle 120` - Start trading daemon

8. **Database Layer** (`storage/db.py`) - AsyncPG persistence
   - Event logging with tags and decision tracing
   - Trade lifecycle: create_trade → close_trade
   - NAV tracking with realized/unrealized PnL and drawdown

## Current State

### What's Working ✓

- ✓ Neon Postgres database with full schema
- ✓ CCXT integration for multi-exchange support
- ✓ Complete TA engine with all indicators
- ✓ Signal generation with regime detection
- ✓ Paper trading execution with realistic fees/slippage
- ✓ Trade lifecycle tracking (entry fees + exit fees)
- ✓ NAV calculation: starting_cash + realized_pnl + unrealized_pnl
- ✓ Drawdown tracking from peak NAV
- ✓ Comprehensive logging (console + database)
- ✓ CLI interface (init, status, run)
- ✓ Trading Daemon workflow running on 120s cycles

### What's Pending

- ⏳ Perplexity API integration for sentiment analysis
- ⏳ OpenRouter LLM integration for trade proposals
- ⏳ Reflection engine for periodic commentary
- ⏳ Additional CLI commands (fund, withdraw, logs, trades, reflect, ask)
- ⏳ JSONL file logging (currently only console + DB)

## Known Issues & Solutions

### Binance Location Restriction

**Issue:** Binance API returns 451 error: "Service unavailable from a restricted location"

**Solutions:**
1. Use a VPN to access Binance
2. Switch to a different exchange:
   ```python
   # In runner/daemon.py
   self.ccxt = CCXTAdapter('kraken')  # or 'bybit', 'coinbase', etc.
   ```
3. Configure exchange via environment variable (feature to be added)

## Database Schema

Key tables:
- `nav` - NAV snapshots with realized/unrealized PnL and drawdown
- `candles` - OHLCV market data
- `features` - Computed technical indicators
- `positions` - Active positions with stops and linked trade_id
- `trades` - Full trade history with entry/exit and PnL
- `event_log` - Structured audit trail with tags and decision_id

## Configuration

Default settings (can be modified in code):
- **Symbols:** BTC/USDT, ETH/USDT
- **Timeframe:** 5m primary
- **Cycle:** 120 seconds
- **Risk per trade:** 0.5% of NAV
- **Max exposure:** 2% of NAV per symbol
- **Fees:** 2 bps
- **Slippage:** max(3bps, 15% of HL range)

## Usage

### First Time Setup
```bash
# Initialize database and set starting NAV
python agent.py init --nav 10000
```

### Running the Daemon
```bash
# Start paper trading
python agent.py run --cycle 120
```

### Check Status
```bash
# View current NAV and positions
python agent.py status
```

## Development Notes

### Critical Bug Fixes Applied

1. **Trade Lifecycle** - Fixed to use create_trade/close_trade pattern instead of always inserting new records
2. **Fee Accounting** - Entry and exit fees now both subtracted from PnL
3. **NAV Calculation** - Properly sums realized PnL from trades and unrealized from positions
4. **Error Handling** - CCXT errors now raise exceptions and log properly

### Code Quality

- Architect-reviewed and approved
- Proper async/await patterns with asyncpg
- Structured error handling with logging
- Database-first design (Postgres is source of truth)
- Type hints throughout

## Next Steps

1. **Add Perplexity sentiment** - Enhance signals with news/social sentiment
2. **Add OpenRouter LLM** - Get AI trade proposals (advisor mode)
3. **Add reflection engine** - Periodic market commentary
4. **Extend CLI** - Additional commands for fund management and querying
5. **Add JSONL logging** - File-based logs for external analysis
6. **Backtest mode** - Run historical simulations

## Dependencies

Core packages:
- `ccxt` - Exchange connectivity
- `pandas-ta` - Technical indicators  
- `asyncpg` - Async Postgres driver
- `pandas` - Data manipulation

See `pyproject.toml` for full list.

## File Structure

```
/adapters/         # Exchange adapters (CCXT)
/ta/              # Technical analysis engine
/signals/         # Signal generation rules
/execution/       # Paper trading execution
/storage/         # Database layer
/runner/          # Daemon orchestration
/cli/             # Command-line interface
/logging/         # Logging setup (placeholder)
/configs/         # Configuration files (placeholder)
agent.py          # CLI entry point
```

## Workflow

The **Trading Daemon** workflow runs continuously:
1. Fetches latest market data via CCXT
2. Computes technical indicators
3. Detects market regime (trend/chop)
4. Generates entry/exit signals
5. Executes paper trades
6. Updates positions and NAV
7. Logs all events to database
8. Sleeps for 120 seconds and repeats

## User Preferences

- System uses Python 3.12 with UV for dependency management
- Prefer async/await patterns for database and I/O operations
- Database schema changes via direct SQL (no migrations framework)
- Comprehensive logging for auditability
- PRD-driven development approach
