# PRD — AI Crypto Trading Agent (Replit + Neon Postgres, CCXT public, OpenRouter, Perplexity)

## Objective

Single-user, intraday crypto paper-trading daemon running on Replit.
Deterministic TA drives entries/exits; LLM acts as advisor and commentator.
Data: CCXT public OHLCV only.
LLM: OpenRouter (`deepseek/deepseek-chat-v3-0324` primary; `x-ai/grok-4-fast` fallback).
Sentiment/news: Perplexity Search API.
Storage: **Replit Postgres (Neon)** as the single source of truth.
Interface: minimal CLI + optional local HTTP endpoints.
Auditability: comprehensive JSONL logs + structured Postgres logs.
Reflection: periodic agent market/portfolio write-ups persisted and viewable.

---

## Non-Goals

Live trading, private keys, leverage, paid data feeds, social APIs requiring elevated access.

---

## System Overview

### Runtime cadence

* Primary timeframe: 5m. Higher timeframe: 1h. Cycle every 60–120s.
* Sequence per cycle: ingest → features → signals → sentiment snapshot → LLM proposal → validate/execute (paper) → persist → reflect on cadence → log.

### Components

1. **Data adapter** — `ccxt` public OHLCV, exchange default `binance` (configurable to `kraken`, `bybit`, etc.).
2. **TA engine** — `pandas`/`pandas-ta` + custom (Donchian, RVOL, AVWAP).
3. **Signals** — regime-gated breakout/pullback with ATR stops and vol-target sizing.
4. **Sentiment** — Perplexity Search API; features: 24h/7d polarity and news burst.
5. **LLM advisor** — OpenRouter; proposal JSON only; executor enforces policy.
6. **Paper broker** — fills at next bar close ± slippage proxy; fees configurable.
7. **Storage** — Neon Postgres via `psycopg`/`asyncpg`.
8. **CLI** — user funds the agent NAV, inspects status/logs/reflections, asks queries.
9. **Reflection engine** — scheduled market/portfolio commentary written by LLM from facts only.
10. **Logging** — human-readable console + JSONL + Postgres `event_log` table with tags/flags.

---

## Data & Indicators

### Free sources

* **Market data**: CCXT public OHLCV (no keys), paginated history warm-up.
* **Aux sentiment/news**: Perplexity API (Reddit + crypto media via search).
* **Market breadth (optional)**: CoinGecko free API for global market cap/BTCD; CryptoPanic free key for news pulse; Alternative.me Crypto Fear & Greed (free JSON). Use as non-binding features.

### TA set (intraday crypto)

* Trend: EMA(20/50/200), HMA(55)
* Momentum: RSI(14), StochRSI(14,14,3), ROC(10)
* Volatility: ATR(14), Bollinger(20,2), Donchian(20)
* Volume/price: OBV, CMF(20), **RVOL(20)**
* VWAP/AVWAP: session VWAP; Anchored from recent breakout bar

### Signals (baseline)

* **Regime**: ADX(14)>20 and EMA50>EMA200 → trend; else chop.
* **Long**: Close>DonchianUpper(20) AND CMF>0 AND RVOL>1.5.
* **Short**: optional; symmetric below Lower(20) with CMF<0.
* **Size**: target 10% annualized vol per position; clamp by max notional.
* **Stops**: initial 2×ATR; trailing 2×ATR on new extremes.
* **Time stop**: 2×lookback bars without progress.
* **Cooldown**: 3 bars after stop.

---

## LLM Integration

### Advisor (proposal only)

* Provider: **OpenRouter**.
* Primary model: `deepseek/deepseek-chat-v3-0324`.
* Fallback: `x-ai/grok-4-fast`.
* Temperature: 0.1.
* Contract: valid JSON with fields: `symbol`, `side`, `confidence`, `reasons[]`, `entry`, `stop{type,multiplier}`, `take_profit{rr}`, `max_hold_bars`.

### Reflection (commentary)

* Every 4 hours and at 00:00 UTC.
* Inputs: aggregated stats (PnL, DD, hit rate), regime markers (ADX buckets, realized vol), sentiment trend, breadth proxies.
* Output: 600–900 chars analytical note; stored in `reflections` and printed on CLI command.
* Guardrails: no invented data; cite which metrics switched.

---

## CLI Interface (Replit console or shell)

Binary: `agent`

Commands:

* `agent init --nav 10000`
  Initialize Postgres schema if absent; set starting NAV.
* `agent status`
  Print NAV, open positions, unrealized PnL, last cycle ts, heartbeat latency.
* `agent fund --add 2500`
  Increase paper NAV.
* `agent withdraw --amount 1000`
  Decrease paper NAV (floor 0; error if insufficient).
* `agent run`
  Start daemon loop (blocking). Ctrl-C to stop.
* `agent logs --since 6h --level info --tags TRADE,SIGNAL`
  Stream filtered logs.
* `agent trades --since 7d`
  Table of fills with PnL, fees, slip.
* `agent reflect --since 7d`
  Show stored reflections.
* `agent ask "Why did we cut ETH?"`
  Query LLM with bounded context from logs/positions; answer printed; stored as `qa` event.
* `agent config get|set key value`
  Read/modify runtime config (persisted).

Optional TUI (Textual) later; not required.

---

## Local HTTP (optional)

* `GET /state` → NAV, positions, symbols watched, last cycle
* `GET /trades?since=...`
* `GET /logs?level=...&tags=...&limit=...`
* `GET /reflections?since=...`
* `POST /ask` → `{question}` returns `{answer, sources}`

Loopback-only by default.

---

## Storage (Neon Postgres schema)

```sql
-- Core
CREATE TABLE nav (
  ts TIMESTAMPTZ PRIMARY KEY,
  nav_usd NUMERIC NOT NULL,
  realized_pnl NUMERIC NOT NULL,
  unrealized_pnl NUMERIC NOT NULL,
  dd_pct NUMERIC NOT NULL
);

CREATE TABLE candles (
  symbol TEXT NOT NULL,
  tf TEXT NOT NULL,
  ts TIMESTAMPTZ NOT NULL,
  o NUMERIC NOT NULL, h NUMERIC NOT NULL, l NUMERIC NOT NULL, c NUMERIC NOT NULL, v NUMERIC NOT NULL,
  PRIMARY KEY (symbol, tf, ts)
);

CREATE TABLE features (
  symbol TEXT NOT NULL, tf TEXT NOT NULL, ts TIMESTAMPTZ NOT NULL,
  ema20 NUMERIC, ema50 NUMERIC, ema200 NUMERIC,
  hma55 NUMERIC, rsi14 NUMERIC, stochrsi NUMERIC, roc10 NUMERIC,
  atr14 NUMERIC, bb_u NUMERIC, bb_l NUMERIC, donch_u NUMERIC, donch_l NUMERIC,
  obv NUMERIC, cmf20 NUMERIC, adx14 NUMERIC, rvol20 NUMERIC,
  vwap NUMERIC, avwap NUMERIC,
  PRIMARY KEY (symbol, tf, ts)
);

CREATE TABLE sentiment (
  ts TIMESTAMPTZ NOT NULL, symbol TEXT NOT NULL,
  sent_24h NUMERIC, sent_7d NUMERIC, sent_trend NUMERIC,
  burst NUMERIC, sources JSONB,
  PRIMARY KEY (symbol, ts)
);

CREATE TABLE positions (
  symbol TEXT PRIMARY KEY,
  qty NUMERIC NOT NULL, avg_price NUMERIC NOT NULL,
  side TEXT NOT NULL, stop NUMERIC, opened_ts TIMESTAMPTZ NOT NULL,
  last_update_ts TIMESTAMPTZ NOT NULL
);

CREATE TABLE trades (
  id BIGSERIAL PRIMARY KEY,
  symbol TEXT NOT NULL, side TEXT NOT NULL,
  qty NUMERIC NOT NULL, entry_ts TIMESTAMPTZ NOT NULL, entry_px NUMERIC NOT NULL,
  exit_ts TIMESTAMPTZ, exit_px NUMERIC,
  fees NUMERIC DEFAULT 0, slippage_bps NUMERIC DEFAULT 0,
  pnl NUMERIC, reason TEXT
);

CREATE TABLE reflections (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL, window TEXT NOT NULL,
  title TEXT, body TEXT NOT NULL,
  stats JSONB NOT NULL
);

CREATE TABLE qa (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL, question TEXT NOT NULL, answer TEXT NOT NULL
);

CREATE TABLE config (
  key TEXT PRIMARY KEY, value JSONB NOT NULL
);

-- Structured event log
CREATE TABLE event_log (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL,
  level TEXT NOT NULL,            -- DEBUG/INFO/WARN/ERROR
  tags TEXT[] NOT NULL,           -- e.g., {CYCLE,DATA,SIGNAL,PROPOSAL,TRADE,EXIT,REFLECTION,QA}
  symbol TEXT,
  tf TEXT,
  action TEXT,                    -- verb, e.g., "ENTER_LONG","EXIT_STOP","REJECT_PROPOSAL"
  decision_id TEXT,               -- uuid for end-to-end trace
  trade_id BIGINT,
  payload JSONB                   -- full details, features snapshot hash, thresholds, LLM rationale
);

-- Indices
CREATE INDEX event_log_ts_idx ON event_log(ts);
CREATE INDEX event_log_tags_idx ON event_log USING GIN(tags);
CREATE INDEX features_symbol_ts_idx ON features(symbol, tf, ts);
CREATE INDEX sentiment_symbol_ts_idx ON sentiment(symbol, ts);
```

**Logs (dual-path):**

* Console: human-readable.
* File: `logs/events.jsonl` (rotated).
* DB: `event_log` for queryable history.

**Tagging discipline:**

* `CYCLE`, `DATA`, `FEATURES`, `SIGNAL`, `PROPOSAL`, `VALIDATION`, `TRADE`, `EXIT`, `RISK`, `SENTIMENT`, `REFLECTION`, `QA`, `ERROR`.

**Decision tracing:**

* Generate `decision_id` at cycle start; propagate to all events until next cycle.

---

## External APIs and Keys

* **OpenRouter**: `OPENROUTER_API_KEY`. Models set in config.
* **Perplexity**: `PERPLEXITY_API_KEY`.
* **CoinGecko** (optional breadth): no key.
* **CryptoPanic** (optional news): free key.
* **Alternative.me Fear&Greed** (optional): no key.

`.env.example`

```
DATABASE_URL=postgresql://user:pass@host/db
OPENROUTER_API_KEY=...
PERPLEXITY_API_KEY=...
```

---

## Validator Rules (hard)

* Max risk per trade = 0.5% NAV equivalent.
* Max exposure per symbol = 2% NAV.
* One active position per symbol.
* No pyramiding ≤5 bars from last entry.
* Kill-switch: 5m realized σ > 3× 30d median → flatten and pause N bars.
* Reject any LLM proposal missing mandatory fields or violating regime/size.

---

## Replit Considerations

* Use Poetry or pip with a `replit.nix` for reproducible env.
* Keep memory low: fetch only latest N bars per cycle; backfill on init.
* Async IO with `uvloop` + `asyncpg` to keep cycles under cadence.
* Periodic VACUUM/partitioning optional; acceptable as is for single user.

---

## Acceptance Criteria

* `agent init --nav X` creates schema and stores NAV.
* CCXT public ingest warms up 120 days of 5m candles for BTC/USDT, ETH/USDT.
* Features computed deterministically; no NaN leakage into signals; warm-up respected.
* Paper trades produced with ATR stops and trailing; ledger persisted.
* Logs: console + JSONL + `event_log` populated with correct tags and `decision_id`.
* Perplexity sentiment stored; negative `sent_trend` halves position size.
* OpenRouter advisor returns valid JSON; fallback fires on primary failure; proposals stored in `event_log` with `PROPOSAL` tag and rationale.
* Reflections written every 4h and daily; `agent reflect --since 7d` renders text.
* `agent ask` answers stored in `qa` and logged.
* 8-hour daemon run without crash, cycle time < cadence.

---

## Milestones

1. **M1 Data/DB (1d)**: Neon Postgres schema; CCXT ingest; warm-up; persistence.
2. **M2 TA/Signals (1d)**: features, regime, entries/exits, sizing, stops.
3. **M3 Paper Exec (0.5d)**: fills, fees/slip, ledger, NAV updates.
4. **M4 Logging (0.5d)**: JSONL + DB `event_log`, tags, decision tracing.
5. **M5 Sentiment (0.5d)**: Perplexity integration, scoring, throttle.
6. **M6 LLM Advisor (0.5d)**: OpenRouter primary/fallback, JSON schema, validator.
7. **M7 Reflection/CLI (1d)**: periodic write-ups, CLI commands, status/logs/trades/reflections/ask.
8. **M8 Backtest (nice-to-have 1d)**: rolling backtest using same TA path with costs.

---

## File Layout

```
/adapters/ccxt_public.py
/ta/indicators.py
/signals/rules.py
/sentiment/perplexity.py
/advisor/openrouter.py
/execution/paper.py
/storage/db.py
/runner/daemon.py
/cli/__main__.py
/logging/setup.py
/configs/app.yaml
/tests/...
```

---

## Reflection Template (LLM prompt skeleton, system side)

* Inputs: last 4h stats, regime flags, sentiment deltas, breadth proxies.
* Output fields: `title`, `body`, `stats_used[]`.
* Constraints: no forecasts, no invented data, cite which metrics flipped.

---

## Cost/Slippage Model

* Fees default 2 bps; slippage = max(3 bps, k * HL%) with k=0.15. Configurable.

---

## Safeguards

* Stop trading on schema migration error, missing data, or stale candles > 2× timeframe.
* Retries with exponential backoff for network; circuit breaker for APIs.
* Unit tests for indicators (fixed vectors), signal gates, validator, JSON schema.

Done.
