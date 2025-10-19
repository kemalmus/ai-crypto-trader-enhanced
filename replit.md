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
   - Configured for Coinbase by default
   - Easy to switch to Kraken, Binance, Bybit, etc.
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
   - 90-second cycles (configurable via configs/app.yaml)
   - Flow: ingest → features → signals → execute → persist → update NAV → log
   - Proper error handling with structured logging

7. **CLI Interface** (`cli/__main__.py`, `agent.py`)
   - `agent init --nav 1000` - Initialize database and starting NAV
   - `agent status` - View current NAV, positions, PnL
   - `agent run --cycle 90` - Start trading daemon (default 90s from config)
   - `agent logs [--limit N] [--level LEVEL] [--tag TAG]` - View recent event logs

9. **Sentiment Analyzer** (`analysis/sentiment.py`) - Perplexity Sonar Pro
   - Real-time market sentiment from news and social media
   - Stores sent_24h, sent_trend, and sources in database
   - Scores range from -1 (bearish) to +1 (bullish)

10. **LLM Advisor** (`analysis/llm_advisor.py`) - OpenRouter integration
    - Primary model: DeepSeek Chat v3
    - Fallback model: Grok Beta
    - Generates trade proposals based on signals + sentiment
    - PRD-compliant JSON schema with confidence, reasons, stop, take_profit

11. **Reflection Engine** (`analysis/reflection.py`) - Market commentary
    - Generates analytical notes every 4 hours
    - Stored in reflections table with NAV, positions, and regime data
    - No forecasts or invented data - facts only

8. **Database Layer** (`storage/db.py`) - AsyncPG persistence
   - Event logging with tags and decision tracing
   - Trade lifecycle: create_trade → close_trade
   - NAV tracking with realized/unrealized PnL and drawdown

## Current State

### What's Working ✓

- ✓ Neon Postgres database with full schema
- ✓ CCXT integration for multi-exchange support (Coinbase)
- ✓ Complete TA engine with all indicators
- ✓ Signal generation with regime detection
- ✓ Paper trading execution with realistic fees/slippage
- ✓ Trade lifecycle tracking (entry fees + exit fees)
- ✓ NAV calculation: starting_cash + realized_pnl + unrealized_pnl
- ✓ Drawdown tracking from peak NAV
- ✓ Comprehensive logging (console + JSONL file + database)
- ✓ CLI interface (init, status, run, logs)
- ✓ Trading Daemon workflow running on 90s cycles (configurable)
- ✓ **Perplexity API integration** - Real-time sentiment analysis (sonar-pro model)
- ✓ **OpenRouter LLM integration** - Trade proposals with DeepSeek/Grok
- ✓ **Reflection engine** - Periodic market commentary every 4 hours
- ✓ **Sentiment persistence** - PRD-compliant schema (sent_24h, sent_7d, sent_trend, burst, sources)

### What's Pending

- ⏳ Additional CLI commands (fund, withdraw, trades, reflect, ask)
- ⏳ 7-day sentiment aggregation (currently storing 24h snapshots)
- ⏳ Sentiment burst detection

### Recent Updates (Discrepancy Resolution)

**✓ PRD Alignment Completed (Oct 19, 2025)**

All major discrepancies between the PRD and implementation have been resolved:

1. **✓ .env.example Fixed** - Now includes required DATABASE_URL and PERPLEXITY_API_KEY; removed unnecessary Binance keys (PRD specifies CCXT public, no auth needed)

2. **✓ JSONL Logging Implemented** - Created `logging/setup.py` with:
   - Rotating JSONL file writer (`logs/events.jsonl`)
   - Console + File dual logging (Database logging remains in storage/db.py)
   - 10MB rotation with 5 backup files
   - Full event tagging support

3. **✓ Configuration System** - Created `configs/app.yaml` with:
   - Trading universe and timeframe settings
   - All technical indicator parameters
   - Signal rules and risk management
   - LLM and sentiment configuration
   - Paper broker settings

4. **✓ Test Infrastructure** - Created `tests/` directory with:
   - `conftest.py` with pytest fixtures (sample/trending candles)
   - `test_indicators.py` with 10 unit tests for TA engine
   - `test_signals.py` with 8 unit tests for signal logic
   - Tests validate: RSI bounds, ATR positivity, Donchian/Bollinger ordering, etc.

5. **✓ Documentation Updated** - Both AGENTS.md and replit.md now reflect:
   - Actual file structure (`analysis/` instead of `sentiment/`, `advisor/`)
   - Schema includes `trade_id` in positions table
   - All components properly documented

## Known Issues & Solutions

### Exchange Configuration

**Current:** System uses **Coinbase** for market data (switched from Binance due to location restrictions)

**Symbols:** BTC/USD, ETH/USD

**To switch exchanges:**
```python
# In runner/daemon.py, line 22
self.ccxt = CCXTAdapter('kraken')  # or 'bybit', 'binance', etc.
```

Note: Different exchanges use different symbol formats (e.g., BTC/USDT vs BTC/USD)

## Database Schema

Key tables:
- `nav` - NAV snapshots with realized/unrealized PnL and drawdown
- `candles` - OHLCV market data
- `features` - Computed technical indicators
- `positions` - Active positions with stops and linked trade_id (note: trade_id added vs PRD)
- `trades` - Full trade history with entry/exit and PnL
- `event_log` - Structured audit trail with tags and decision_id

## Configuration

Default settings (configurable via configs/app.yaml):
- **Exchange:** Coinbase
- **Symbols:** BTC/USD, ETH/USD  
- **Timeframe:** 5m primary
- **Cycle:** 90 seconds (configurable)
- **Risk per trade:** 0.5% of NAV
- **Max exposure:** 2% of NAV per symbol
- **Fees:** 2 bps
- **Slippage:** max(3bps, 15% of HL range)

## Usage

### First Time Setup
```bash
# Initialize database and set starting NAV
python agent.py init --nav 1000
```

### Running the Daemon
```bash
# Start paper trading (default 90s cycle from config)
python agent.py run

# Or specify custom cycle time
python agent.py run --cycle 120
```

### Check Status
```bash
# View current NAV and positions
python agent.py status

# View recent event logs
python agent.py logs --limit 20

# Filter logs by level
python agent.py logs --level ERROR

# Filter logs by tag
python agent.py logs --tag TRADE
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

See **REMAINING_TASKS.md** for detailed implementation guide.

**Remaining (6 tasks):**
1. **ConsultantAgent module** - Grok-fast model for trade proposal review
2. **Two-agent workflow** - Main agent proposes → Consultant reviews → Final decision
3. **Expand symbols** - Add SOL, AVAX, MATIC, LINK, UNI, AAVE (8 total)
4. **Decision rationale** - Store full reasoning in trades table
5. **Enhanced logging** - Show signals, sentiment, consultant feedback, decisions
6. **End-to-end testing** - Comprehensive validation of all features

**Future Enhancements:**
- Backtest mode with historical simulations
- Additional CLI commands (fund, withdraw, trades, reflect, ask)

## Dependencies

Core packages:
- `ccxt` - Exchange connectivity
- `pandas-ta` - Technical indicators  
- `asyncpg` - Async Postgres driver
- `pandas` - Data manipulation
- `aiohttp` - Async HTTP client for APIs

API Services:
- **Perplexity** (PERPLEXITY_API_KEY) - Sentiment analysis via sonar-pro model
- **OpenRouter** (OPENROUTER_API_KEY) - LLM advisor via DeepSeek/Grok

See `pyproject.toml` for full list.

## File Structure

```
/adapters/              # Exchange adapters (CCXT)
  ccxt_public.py        # Public OHLCV data fetcher
/analysis/              # AI/ML analysis components
  sentiment.py          # Perplexity + DuckDuckGo sentiment
  llm_advisor.py        # OpenRouter LLM trade proposals
  reflection.py         # Market commentary engine
  ddg_search.py         # DuckDuckGo search fallback
/ta/                    # Technical analysis engine
  indicators.py         # All TA indicators
/signals/               # Signal generation rules
  rules.py              # Entry/exit logic, regime detection
/execution/             # Paper trading execution
  paper.py              # Paper broker with fees/slippage
/storage/               # Database layer
  db.py                 # AsyncPG persistence layer
/runner/                # Daemon orchestration
  daemon.py             # Trading loop orchestrator
/cli/                   # Command-line interface
  __main__.py           # CLI commands
/logging/               # Logging infrastructure
  setup.py              # JSONL + console + DB logging
/configs/               # Configuration files
  app.yaml              # Trading parameters and settings
/tests/                 # Unit and integration tests
  conftest.py           # Pytest fixtures
  test_indicators.py    # TA engine tests
  test_signals.py       # Signal logic tests
agent.py                # CLI entry point
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
8. Sleeps for configured cycle time (default 90s) and repeats

## User Preferences

- System uses Python 3.12 with UV for dependency management
- Prefer async/await patterns for database and I/O operations
- Database schema changes via direct SQL (no migrations framework)
- Comprehensive logging for auditability
- PRD-driven development approach
