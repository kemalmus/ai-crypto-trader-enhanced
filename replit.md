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
- **Dual Interface:** The system provides both a CLI interface for functional operations and a modern React web UI for real-time monitoring and visualization.
- **React Web UI:** Built with React + Vite + TypeScript + Tailwind/DaisyUI, providing a cyberpunk-themed interface with:
  - **Overview Dashboard:** NAV, P&L, drawdown, open positions, last cycle timestamp
  - **Live Logs Stream:** Real-time event streaming with filtering (SSE-based)
  - **Sentiment Gauge:** Circular gauge showing 24h/7d sentiment and trends
  - **Ticker Grid:** Real-time price data, regime detection, and technical indicators for all symbols
  - **Trades Panel:** Complete trade history with entry/exit prices, P&L, and fees
  - **Architecture:** Vite dev server (port 5000) proxies API requests to FastAPI backend (port 8000)
- **Legacy Web UI:** FastAPI + Jinja templates available at `/` (for backward compatibility)
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
- **React Web UI:** A modern React application (`web/ui`) built with Vite, TypeScript, and Tailwind CSS:
  - Real-time data visualization with live updates
  - Server-Sent Events (SSE) for streaming logs
  - TanStack Query for efficient data fetching
  - Lightweight Charts for price visualization
  - Responsive cyberpunk-themed design
- **FastAPI Backend:** Serves REST API endpoints (`web/server.py`) for overview, symbols, trades, logs, candles, and sentiment data.
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

## Running the System in Replit

The system uses **two workflows** that run simultaneously:

### Workflows

1. **API Backend** (Port 8000)
   - FastAPI server providing REST API endpoints
   - Connects to Neon Postgres database
   - Serves data for the React UI

2. **React UI** (Port 5000) 
   - Vite development server for the React frontend
   - Proxies `/api` requests to the backend (port 8000)
   - **This is the main UI** - Replit displays it in the webview

### Starting the System

Both workflows start automatically in Replit. You can also start them manually:

```bash
# Terminal 1: Start the API backend
python -m web.server

# Terminal 2: Start the React UI (in web/ui directory)
cd web/ui && npm run dev
```

### React UI Features

The cyberpunk-themed React interface provides:

**Overview Panel** (Left):
- Current NAV and P&L breakdown
- Realized and unrealized profits
- Open positions count
- Last cycle timestamp
- Drawdown percentage

**Sentiment Gauge** (Left):
- Circular gauge showing market sentiment
- 24h sentiment score
- 7-day sentiment trend
- Visual color-coded indicators

**Key Logs Stream** (Center):
- Live streaming of system events via SSE
- Signal detection (REGIME_TREND, REGIME_CHOP)
- Proposal events (SKIP_NO_SIGNAL, etc.)
- Color-coded by event type
- Symbol highlighting

**Ticker Grid** (Bottom):
- Real-time data for all trading symbols
- Regime status (trend/chop/unknown)
- Last price and technical indicators
- RVOL, CMF, Donchian bands
- Color-coded regime badges

**Trades Panel** (Right):
- Complete trade history
- Entry/exit prices and timestamps
- P&L calculation
- Quantity and side (long/short)

### Web UI Access

- **React UI:** `http://localhost:5000` (Replit webview)
- **API Backend:** `http://localhost:8000` (internal)
- **Legacy Template UI:** `http://localhost:8000/` (available for backward compatibility)

### Architecture

```
User → Replit Webview (Port 5000) → Vite Dev Server
                                      ↓ Proxy /api requests
                                   FastAPI Backend (Port 8000)
                                      ↓
                                   Neon Postgres Database
```

The React app fetches data from the FastAPI backend via proxy, which connects to the database.