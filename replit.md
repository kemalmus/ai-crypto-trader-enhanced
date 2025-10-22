# AI Crypto Trading Agent

## Overview
This project is an AI-powered cryptocurrency paper trading system built on Replit. It integrates deterministic technical analysis with an LLM-powered consultant for enhanced decision-making and maintains comprehensive audit trails in a Neon Postgres database. The system aims to provide a robust platform for algorithmic crypto trading with a focus on transparent, auditable decisions. Key capabilities include multi-exchange market data, advanced technical analysis, regime-based trading signals, and real-time sentiment analysis. The project's ambition is to demonstrate a sophisticated, AI-driven trading agent capable of making informed decisions in the cryptocurrency market.

## User Preferences
- System uses Python 3.12 with UV for dependency management
- Prefer async/await patterns for database and I/O operations
- Database schema changes via direct SQL (no migrations framework)
- Comprehensive logging for auditability
- PRD-driven development approach

## System Architecture
The system is built around a daemon runner orchestrating a continuous trading loop.
**UI/UX Decisions:**
- **Dual Interface:** The system provides both a CLI interface for functional operations and a cyberpunk-themed web UI for real-time monitoring and visualization.
- **Web UI:** Built with FastAPI + Jinja + HTMX + Tailwind/DaisyUI, providing a terminal-like interface with live logs, dashboards, and decision tracing.
- **CLI Interface:** Provides commands for initialization, status checks, running the trading daemon, viewing logs, and trade rationales.
- **Logging:** Structured and comprehensive, providing clear audit trails and decision contexts through both interfaces.

**Technical Implementations & Feature Specifications:**
- **Core Database:** Neon Postgres serves as the single source of truth, storing all trading data across 11 tables (nav, candles, features, sentiment, positions, trades, reflections, qa, config, event_log, decision_rationale) ensuring a full audit trail and proper trade lifecycle tracking.
- **Data Ingestion:** A `CCXT Adapter` fetches OHLCV data from multiple exchanges (Coinbase, Binance, Kraken), with automatic backfilling for new symbols.
- **Technical Analysis:** A `TA Engine` (using pandas-ta) computes various indicators including EMA, HMA, RSI, StochRSI, ATR, Bollinger, Donchian, OBV, CMF, ADX, RVOL, VWAP, and AVWAP.
- **Signal Generation:** A `Signal Engine` implements regime-based trading logic, including trend/chop detection, breakout/pullback entries with volume confirmation, and ATR-based stops.
- **Risk Management:** Position sizing is set at 0.5% risk per trade with a 2% maximum exposure per symbol.
- **AI Decision Making:**
    - An `LLM Advisor` generates trade proposals based on signals and sentiment using DeepSeek (primary) and Grok Beta (fallback) models, outputting PRD-compliant JSON.
    - A `Consultant Agent` (Grok-fast model) reviews these proposals, making approve/reject/modify decisions with confidence scoring and risk management validation.
- **Sentiment Analysis:** A `Sentiment Analyzer` integrates Perplexity Sonar Pro for real-time market sentiment from news and social media, storing scores and trends.
- **Execution Simulation:** A `Paper Broker` simulates trades with realistic slippage (max(3bps, 0.15 * HL%)) and fees (2 bps), accounting for full round-trip costs.
- **Reflection Engine:** Periodically generates market commentary based on current NAV, positions, and regime data.
- **Logging:** An `Enhanced Logging` system provides structured event logging to JSONL files (with rotation), console, and the database, including tags, symbols, actions, and decision_ids.
- **Web UI:** A `FastAPI-based Web Interface` provides real-time monitoring with a cyberpunk terminal theme, featuring Overview, Symbols, Trades, and Logs tabs with live SSE streaming and decision tracing.
- **CLI Interface:** Provides commands for initialization, status checks, running the trading daemon, viewing logs, and trade rationales.
- **Daemon Runner:** Orchestrates the trading cycle (configurable, default 90 seconds) which includes data ingestion, feature computation, signal generation, LLM proposal, consultant review, execution, persistence, NAV updates, and logging.

**System Design Choices:**
- **Database-first design:** Postgres is the central data store for all operations.
- **Asynchronous operations:** Utilizes `asyncpg` and `aiohttp` for non-blocking I/O.
- **Modular components:** Code is organized into logical directories (adapters, analysis, ta, signals, etc.).
- **Configuration Management:** Uses `configs/app.yaml` for centralizing trading parameters, indicators, and model settings.

## External Dependencies
- **Postgres Database:** Neon Postgres (for persistence and audit trails)
- **CCXT:** For multi-exchange market data (Coinbase, Binance, Kraken)
- **Perplexity API:** For real-time sentiment analysis (`PERPLEXITY_API_KEY`, using sonar-pro model)
- **OpenRouter API:** For LLM access (`OPENROUTER_API_KEY`, utilizing DeepSeek Chat v3 and Grok Beta models)
- **pandas-ta:** For technical analysis indicator calculations
- **asyncpg:** Asynchronous PostgreSQL driver
- **pandas:** For data manipulation
- **aiohttp:** Asynchronous HTTP client
- **uv:** For dependency management and package installation

## Web UI Usage

### Starting the Web Interface

```bash
# Start the web UI (runs on port 8000 by default)
agent ui

# Or with custom host/port
agent ui --host 0.0.0.0 --port 8080
```

### Web UI Features

The cyberpunk-themed web interface provides real-time monitoring with:

**Overview Tab:**
- Current NAV and P&L breakdown
- Open positions summary
- Cycle latency and heartbeat status
- Drawdown from peak NAV

**Symbols Tab:**
- Real-time price and indicator data for all symbols
- Regime status (trend/chop) with color coding
- Technical indicators (RVOL, CMF, Donchian bands)
- Market regime visualization

**Trades Tab:**
- Complete trade history with P&L
- Filtering by symbol and date range
- Fee and slippage details
- Entry/exit rationale

**Logs Tab:**
- Live streaming of system events via Server-Sent Events (SSE)
- Filter by level (DEBUG/INFO/WARN/ERROR), tags, symbol, decision_id
- Terminal-like display with color coding
- Raw JSON toggle for detailed debugging
- Real-time decision tracing with decision_id chains

### Web UI Access

- **URL:** `http://localhost:8000` (or configured host/port)
- **Features:** Responsive design, cyberpunk terminal theme
- **Live Updates:** Automatic refresh of data and logs
- **Decision Tracing:** Follow complete decision chains with decision_id
- **Mobile Friendly:** Works on mobile devices

### Running Both Systems

You can run the trading daemon and web UI simultaneously:

1. **Terminal 1:** `agent run` (trading daemon)
2. **Terminal 2:** `agent ui` (web interface)

The web UI connects to the same database, so you'll see live updates as the daemon processes trades.