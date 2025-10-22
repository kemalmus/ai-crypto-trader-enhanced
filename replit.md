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
- The system primarily uses a CLI interface for interaction, focusing on functional output (status, logs, rationale) rather than a graphical user interface.
- Logging is structured and comprehensive, providing clear audit trails and decision contexts.

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