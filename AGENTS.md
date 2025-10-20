# AGENTS.md — AI Crypto Trading Agent (Replit + Neon Postgres)

## Build & Test

* Create venv (optional): `python -m venv .venv && source .venv/bin/activate`
* Install deps: `pip install -U pip && pip install -r requirements.txt`
* Type check: `pyright`
* Lint/format: `ruff check . && ruff format .`
* Run tests: `pytest -q`
* Smoke test (dry run, 1 cycle): `agent run --once --dry-run`

## Run Locally (Replit / shell)

* Set env:

  ```
  export DATABASE_URL="postgresql://USER:PASS@HOST/DB"
  export OPENROUTER_API_KEY="..."
  export PERPLEXITY_API_KEY="..."
  ```
* Initialize DB and starting NAV: `agent init --nav 10000`
* Warm up market data (5m bars, 120d): `agent run --warmup 120d --once`
* Start daemon (5m cadence): `agent run`
* Inspect:

  * Status: `agent status`
  * Trades: `agent trades --since 7d`
  * Logs: `agent logs [--limit N] [--level LEVEL] [--tag TAG] [--symbol SYMBOL] [--decision-id ID] [--action ACTION] [--summary]`
  * Rationale: `agent rationale [--limit N] [--symbol SYMBOL] [--trade-id ID]`
  * Reflections: `agent reflect --since 7d`
  * Validation: `agent validate [--symbols LIST] [--dry-run]`
  * Q&A: `agent ask "Why did we exit BTC?"`

## Architecture Overview

Single-user, intraday crypto paper-trading daemon.
Deterministic TA → Signals → LLM Proposals → Consultant Review → Validator/Executor (paper) → Metrics/Logs.
LLM acts as advisor and commentator; Consultant Agent provides risk validation; no direct execution rights.
Data: CCXT public OHLCV. Sentiment: Perplexity search. Storage: Neon Postgres.

```
adapters/ccxt_public.py      # public OHLCV ingest (multi-exchange support)
ta/indicators.py             # EMA/HMA/RSI/ATR/Bollinger/Donchian/CMF/RVOL/VWAP/AVWAP
signals/rules.py             # regime gates + entries/exits + sizing/stops
analysis/sentiment.py        # Perplexity + DuckDuckGo fallback for news/sentiment
analysis/llm_advisor.py      # OpenRouter LLM (deepseek primary, grok fallback) + consultant integration
analysis/consultant_agent.py # Grok-fast consultant for proposal review/validation
analysis/reflection.py       # Periodic market commentary engine
analysis/ddg_search.py       # DuckDuckGo search fallback
execution/paper.py           # fills, fees+slip, ledger, NAV
storage/db.py                # Neon Postgres client + schema ops + decision rationale
runner/daemon.py             # scheduler loop, cycle orchestration (enhanced logging)
cli/__main__.py              # `agent` command (rationale, validate commands)
logging/setup.py             # JSONL + console + DB event_log (enhanced formatting)
configs/app.yaml             # universe, TFs, thresholds, models, exchanges
tests/                       # unit + integration tests (expanded coverage)
```

## External Services & Env Vars

* **CCXT** (public endpoints only) — no keys required.
* **OpenRouter** — models:

  * Primary (Advisor): `deepseek/deepseek-chat-v3-0324`
  * Fallback (Advisor): `x-ai/grok-beta`
  * Consultant: `x-ai/grok-4-fast` (separate API calls for proposal review)
  * `OPENROUTER_API_KEY` required.
* **Perplexity Search API** — sentiment/news pulse from Reddit + crypto media.

  * `PERPLEXITY_API_KEY` required.
* Optional free enrichers (non-binding):

  * CoinGecko (global cap/BTCD) — no key.
  * CryptoPanic (news pulse) — free key.
  * Fear & Greed Index — public JSON.

## Conventions & Patterns

* UTC ISO-8601 timestamps. One decision cycle = one `decision_id` spanning all log events.
* Deterministic TA is authoritative. LLM can only propose JSON trades and write reflections.
* Strict validator enforces risk caps, regime gates, kill-switches.
* No forward-fill beyond 1 bar; pause signals on gaps or stale data.
* Never store secrets in repo; env-only. No live exchange keys; paper trading only.

## Data Contracts (Postgres)

* `candles(symbol, tf, ts, o,h,l,c,v, PK(symbol,tf,ts))`
* `features(symbol, tf, ts, ema20, ema50, ema200, hma55, rsi14, stochrsi, roc10, atr14, bb_u, bb_l, donch_u, donch_l, obv, cmf20, adx14, rvol20, vwap, avwap, PK(symbol,tf,ts))`
* `sentiment(symbol, ts, sent_24h, sent_7d, sent_trend, burst, sources, PK(symbol,ts))`
* `positions(symbol, qty, avg_price, side, stop, trade_id, opened_ts, last_update_ts, PK(symbol))`
* `trades(id, symbol, side, qty, entry_ts, entry_px, exit_ts, exit_px, fees, slippage_bps, pnl, reason, decision_rationale, PK(id))`
* `nav(ts, nav_usd, realized_pnl, unrealized_pnl, dd_pct, PK(ts))`
* `reflections(id, ts, window, title, body, stats, PK(id))`
* `qa(id, ts, question, answer, PK(id))`
* `event_log(id, ts, level, tags[], symbol, tf, action, decision_id, trade_id, payload, PK(id))`

## TA & Signals (baseline)

* Regime: `ADX(14) > 20` and `EMA50 > EMA200` → trend; else chop.
* Long: `Close > DonchianUpper(20)` and `CMF(20) > 0` and `RVOL > 1.5`.
* Short: optional; symmetric below `DonchianLower(20)` and `CMF < 0`.
* Size: vol-target 10% annualized per position; cap by max notional.
* Stops: initial `2*ATR(14)`, trailing `2*ATR(14)`.
* Time stop: `2*lookback` bars without progress.
* Cooldown: 3 bars after stop-out.

## LLM Advisor Contract

* System: proposals only; no price/PnL invention; one active position per symbol; no pyramiding ≤5 bars.
* Request context: latest features, open positions, sentiment snapshot, risk caps.
* JSON schema (must validate):

  ```
  {
    "symbol": "BTC/USDT",
    "side": "long|short|flat",
    "confidence": 0.0,
    "reasons": ["..."],
    "entry": {"type": "market"},
    "stop": {"type": "atr", "multiplier": 2.0},
    "take_profit": {"rr": 1.5},
    "max_hold_bars": 80
  }
  ```

## Sentiment Features

* `sent_24h`, `sent_7d`, `sent_trend = sent_24h - sent_7d`, `burst = headlines_1h / mean(24h)`.
* Usage: throttle/confirm only. Example: halve size if `sent_trend < 0`.

## Reflection Cadence

* Every 4h and daily at 00:00 UTC.
* Inputs: PnL/DD/hit rate, regime flags, realized vol, sentiment deltas, breadth proxies.
* Output: 600–900 chars; stored in `reflections`; surfaced via `agent reflect`.

## Logging & Observability

* Console: human-readable. File: `logs/events.jsonl` (rotated). DB: `event_log`.
* Tags: `CYCLE`, `DATA`, `FEATURES`, `SIGNAL`, `SENTIMENT`, `PROPOSAL`, `CONSULTANT`, `TRADE`, `EXIT`, `RISK`, `REFLECTION`, `QA`, `ERROR`.
* Each cycle emits heartbeat, cache stats, feature compute time, LLM latency, consultant decisions, signal details, sentiment scores.
* Enhanced filtering and formatting for signal, sentiment, and consultation events.
* Filter examples:

  * `agent logs --tags SIGNAL --symbol BTC/USD --since 2h` - Signal events for specific symbol
  * `agent logs --tags PROPOSAL --decision-id abc123` - All proposal events for a decision cycle
  * `agent logs --action REGIME_TREND --summary` - Regime detection summary
  * `agent rationale --trade-id 123` - View decision context for specific trade
  * SQL: `SELECT * FROM event_log WHERE 'TRADE'=ANY(tags) AND ts>now()-interval '7 days' ORDER BY ts DESC;`

## Allowed Edit Surface (agents)

* OK: `adapters/`, `ta/`, `signals/`, `analysis/`, `execution/`, `storage/`, `runner/`, `cli/`, `logging/`, `tests/`, `configs/app.yaml` (keys only).
* Do not touch: secrets, deployment files outside this repo, live-exchange integrations, non-declared dependencies.
* Add dependencies only if justified in PR description and covered by tests.

## Verification Gate

* Required to pass before merge:

  * `pytest -q` green (20+ consultant tests)
  * `ruff check .` clean
  * `pyright` no new errors
  * Dry-run cycle prints `CYCLE`→`SIGNAL`→`SENTIMENT`→`PROPOSAL`→`CONSULTANT`→`VALIDATION` heartbeat with a `decision_id`
  * `agent validate --dry-run` shows configured exchanges and symbols

## Gotchas

* CCXT rate limits: use built-in throttling; cache candles; never hammer endpoints.
* Stale bars: if last bar age > 2× timeframe, pause trading and log `RISK`.
* Indicator warm-up: require ≥ 3× max lookback before enabling signals.
* No forward-filling across maintenance gaps.
* Reflection/QA must cite metrics used; no speculative claims.

## Quick Tasks For Agents

* ✅ **COMPLETED**: Implement consultant agent with LLM-powered proposal review
* ✅ **COMPLETED**: Add 8-symbol universe (BTC, ETH, SOL, AVAX, MATIC, LINK, UNI, AAVE)
* ✅ **COMPLETED**: Enhanced logging with signal, sentiment, and consultation details
* ✅ **COMPLETED**: Decision rationale storage with complete audit trails
* ⏳ Implement missing unit tests for indicators and validator edges.
* ⏳ Optimize RVOL and AVWAP computations; cache-aware.
* ⏳ Extend CLI with `agent portfolio` (weights, exposure, VaR proxy).
* ⏳ Add backtest command reusing live TA path and costs.
* ⏳ Verify CCXT adapter compatibility for expanded symbol universe.

## Proof Artifacts

* Unit test diffs for logic changes (20+ consultant tests added).
* JSONL snippet showing consultant proposal review workflow with approve/reject/modify decisions.
* SQL snapshot: last 20 trades with PnL, fees, and decision rationale.
* CLI output: `agent validate --dry-run` showing configured exchanges and symbols.
* CLI output: `agent rationale --trade-id 123` showing complete decision context.
* Reflection sample stored and retrievable via CLI.
