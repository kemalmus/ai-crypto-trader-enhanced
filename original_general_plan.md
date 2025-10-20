Design it as a **single-user crypto trading daemon** with an **LLM “advisor”** on a short leash. TA and execution remain deterministic; the LLM proposes, never executes. Intraday cadence: 1–5 min.

## Architecture (single process, local-first)

* **Data adapter:** `ccxt` → fetch OHLCV for spot symbols on your exchange (Binance/Bybit/Kraken). Cache to DuckDB.
* **TA engine:** `pandas` + `pandas-ta` + a few custom (Donchian, RVOL, AVWAP). Vectorized, pure functions.
* **Feature cache:** DuckDB tables keyed by `(symbol, timeframe, asof)`.
* **Signal layer:** rule-based entries/exits (no LLM). E.g., Trend+Breakout with ATR stops.
* **Risk engine:** vol targeting, %ADV cap proxy, time stop, kill-switch.
* **Paper broker:** CCXT testnet where available; else a local ledger with FIFO fills + slippage model.
* **LLM agent:** sentiment + “risk commentary” + **JSON trade proposals**; executor validates against strict rules. No direct order rights.
* **Scheduler:** cron-like loop every 1–5 minutes per symbol/timeframe.

## Minimal TA set for intraday crypto

* **Trend:** EMA(20/50/200), HMA(55).
* **Momentum:** RSI(14), StochRSI(14,14), ROC(10).
* **Volatility:** ATR(14), Bollinger(20,2), Donchian(20).
* **Volume/price:** OBV, CMF(20), **RVOL** = Vol / mean(Vol, n).
* **VWAP/AVWAP:** session VWAP; anchored from recent breakout bar.
  All computable from free OHLCV via CCXT.

## Deterministic strategy (baseline, long/short capable)

* **Regime filter:** ADX(14) > 20 AND EMA50 > EMA200 → trend; else chop.
* **Entry (trend):** Close > DonchianUpper(20) AND CMF(20) > 0 AND RVOL > 1.5.
* **Entry (short, if allowed):** symmetric below Lower(20) with CMF < 0.
* **Stop:** initial = 2×ATR(14); **trailing** = 2×ATR(14) on new extremes.
* **Size:** target 10% annualized vol per position; clamp by max notional and a spread/range proxy.
* **Time stop:** exit after 2×lookback bars without new high/low.
* **Cooldown:** 3 bars after stop-out to avoid churn.

## Sentiment layer (free, lightweight, intraday)

* **Sources:** RSS headlines from CoinDesk/CoinTelegraph + Reddit r/CryptoCurrency Hot/Top JSON.
* **NLP:** headline-only VADER/TextBlob; compute rolling z-scores over 24h and 7d.
* **Features:** `sent_24h`, `sent_7d`, `sent_trend = sent_24h - sent_7d`, `news_burst = headlines_1h / mean(24h)`.
* **Use:** only as a **confirmation or throttle**, not a trigger. Example: require `sent_trend ≥ 0` for longs; halve size if negative.

## Safety rails for crypto intraday

* **Universe filter:** exclude perpetuals with extreme funding spikes; exclude newly listed coins (<90d history).
* **Event guard:** block trading within N minutes of major exchange incident (manual toggle).
* **Volatility kill-switch:** if realized 5-min σ > X×30d median, close to flat.
* **Slippage proxy:** apply cost = max(0.02%, HL%×k).
* **Leverage:** start 1× spot or linear perps on testnet; no compounding within a bar.

## Process loop (every 1–5 min)

1. Pull latest candles via CCXT; append to DuckDB.
2. Recompute features only for updated bars; hydrate cache.
3. Build **signal candidate** from rules.
4. Call **LLM advisor** with context (features, open positions, sentiment snapshot).
5. Receive **strict JSON proposal** → validate against policy; reject/trim if outside limits.
6. Simulate order in paper broker; persist trade + state.
7. Log metrics; emit heartbeat.

## LLM agent: tools, contract, guardrails

* **Tools exposed to LLM:**

  * `get_features(symbol, tf, asof)` → TA snapshot only.
  * `get_sentiment(symbol, window)` → sentiment features only.
  * `propose_trade(context)` → LLM returns JSON proposal; **no execution tool exposed**.
* **System rules (non-negotiable):**

  * LLM cannot invent prices, sizes, or PnL.
  * Max risk per trade = 0.5% NAV; max exposure per symbol = 2% NAV; no pyramiding within 5 bars.
  * Only one active position per symbol; only marketable limit orders with cost model.
* **Proposal JSON schema (example):**

```json
{
  "symbol": "BTC/USDT",
  "side": "long|short|flat",
  "confidence": 0.0,
  "rationale": ["trend_ok","breakout","sentiment_neutral"],
  "entry": {"type": "market"},
  "stop": {"type": "atr", "multiplier": 2.0},
  "take_profit": {"rr": 1.5},
  "max_hold_bars": 80
}
```

* **Validator:** rejects if regime/size/kill-switch violated; adjusts size to vol-target; sets concrete stops/targets from current ATR.

## Storage layout (DuckDB)

* `candles(symbol, tf, ts, o,h,l,c,v)`
* `features(symbol, tf, ts, {...columns})`
* `sentiment(ts, symbol, sent_24h, sent_7d, burst)`
* `trades(id, symbol, ts_open, ts_close, side, qty, entry, exit, fees, slippage, pnl)`
* `positions(symbol, qty, avg_price, stop, last_update)`

## Backtest parity

* Same TA code. Same costs. “As-of” joins only.
* **Walk-forward:** monthly; tune only lookbacks/multipliers within bounded ranges.
* **Labels:** triple-barrier for outcome diagnostics.
* **Report:** Expectancy, PF, Payoff, Hit%, MaxDD, Calmar, Turnover, Capacity proxy.

## Runtime parameters (sane defaults)

* Timeframe: `5m` primary; `1h` for higher-timeframe filter.
* Windows: Donchian 20, ATR 14, RSI 14, CMF 20.
* RVOL threshold: 1.5. ADX threshold: 20.
* Vol target per position: 10% annualized; portfolio cap: 30% NAV.
* Kill-switch: 5m σ > 3× 30d median → flatten.

## Implementation stack

* Python 3.11, `ccxt`, `pandas`, `pandas-ta`, `duckdb`, `uvloop`, `pydantic`, `fastapi` (optional local dashboard), `apscheduler`.
* LLM: local router or OpenRouter/OpenAI; temperature 0–0.2; **responses forced to JSON** with schema validation.

## Local dashboard (optional)

* Read-only FastAPI endpoints: `/state`, `/equity`, `/positions`, `/last_decisions`, `/logs`.
* Plot equity curve, drawdowns, hit rate by hour-of-day.

## Failure modes addressed

* **Rate limits:** per-exchange ccxt throttling + local cache.
* **Indicator warmup:** require ≥ max lookback×3 bars before enabling trades.
* **Data spikes:** winsorize volume and HL% for RVOL/spread proxies.
* **LLM drift:** unit tests compare LLM proposal vs deterministic baseline; if LLM unavailable, trade pure TA.

## Bring-up sequence (one morning)

1. Implement CCXT fetch + DuckDB append; hydrate 90 days of `5m` BTC/USDT.
2. Add TA features + cached recompute; assert deterministic outputs.
3. Implement baseline rules; run paper backtest last 60 days; print stats.
4. Add LLM advisor with JSON schema; integrate validator; prove it can’t bypass guards.
5. Start live loop on one symbol; log every decision and rejection reason.
6. Expand to 3–5 liquid pairs; monitor turnover and slippage proxy.

This gives you a fast, single-user system where TA is authoritative, sentiment is a secondary throttle, the LLM adds context and proposals but cannot hurt you, and everything runs intraday on free data.
