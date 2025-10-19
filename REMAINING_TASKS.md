# Remaining Implementation Tasks

**Project:** AI Crypto Trading Agent  
**Date:** October 19, 2025  
**Status:** 3/9 tasks completed

---

## Completed Tasks ✅

1. **Sentiment Scheduling** - Sentiment fetched only twice daily (00:00 & 12:00 UTC)
2. **Enhanced Perplexity Reasoning** - Full reasoning stored with accurate score extraction
3. **DuckDuckGo Fallback** - Robust fallback for sentiment when Perplexity fails

---

## Task 4: Create ConsultantAgent Module (Grok-fast)

### Objective
Build a consultant agent using OpenRouter's Grok-fast model to provide critical review and feedback on trade proposals.

### Implementation Details

**File:** `analysis/consultant_agent.py`

**Key Components:**
- Use OpenRouter API with Grok-fast model (`x-ai/grok-beta` or `x-ai/grok-2-1212`)
- Receive trade proposal from main agent (DeepSeek)
- Analyze proposal critically:
  - Review technical analysis signals
  - Evaluate sentiment alignment
  - Check risk/reward ratio
  - Identify potential issues or concerns
- Return structured feedback:
  - Approval/rejection recommendation
  - Concerns list
  - Suggested modifications (stop adjustment, size reduction, etc.)
  - Confidence level in recommendation

**Input Schema:**
```python
{
    "symbol": "BTC/USD",
    "proposal": {
        "action": "long",
        "entry": 95000,
        "stop": 94000,
        "size": 0.05,
        "reasons": ["TA breakout", "bullish sentiment"],
        "confidence": 75
    },
    "market_context": {
        "regime": "trend",
        "sentiment": 0.7,
        "volatility": "medium"
    }
}
```

**Output Schema:**
```python
{
    "recommendation": "approve" | "reject" | "modify",
    "concerns": ["Risk too high", "Stop too tight"],
    "modifications": {
        "stop": 93500,
        "size": 0.03
    },
    "confidence": 80,
    "reasoning": "Full text explanation from Grok"
}
```

**Error Handling:**
- Timeout after 10 seconds
- Fallback: Auto-approve if consultant fails (don't block trades)
- Log all consultant responses for audit

### Dependencies
- OpenRouter API (OPENROUTER_API_KEY already configured)
- Existing LLM advisor module as reference

### Expected Outcome
- Consultant agent provides independent review of trade proposals
- System can handle consultant failures gracefully
- All consultant feedback logged to database

---

## Task 5: Two-Agent Consultation Workflow

### Objective
Implement a consultation loop where Main Agent (DeepSeek) formulates trade proposals and Consultant Agent (Grok-fast) reviews them before final decision.

### Implementation Details

**Workflow:**
```
1. Main Agent analyzes TA + sentiment → formulates proposal
2. Send proposal to Consultant Agent → receive feedback
3. Main Agent considers feedback:
   - If approved: Execute trade
   - If rejected: Log and skip
   - If modified: Apply modifications and execute
4. Log full decision chain to database
```

**Integration Points:**

**File:** `runner/daemon.py` (modify `check_entries` method)

**Current Flow:**
```python
entry_signal = signal_engine.check_entry_long(df)
if entry_signal['signal']:
    execute_trade(...)
```

**New Flow:**
```python
# Step 1: Main agent formulates proposal
entry_signal = signal_engine.check_entry_long(df)
if entry_signal['signal']:
    proposal = await llm_advisor.formulate_proposal(
        symbol, entry_signal, sentiment_data, regime
    )
    
    # Step 2: Consultant reviews
    consultant_feedback = await consultant_agent.review_proposal(
        symbol, proposal, market_context
    )
    
    # Step 3: Main agent decides
    final_decision = await llm_advisor.consider_feedback(
        proposal, consultant_feedback
    )
    
    # Step 4: Execute if approved
    if final_decision['execute']:
        execute_trade(final_decision['params'])
        log_decision_chain(proposal, consultant_feedback, final_decision)
```

**Decision Logic:**
- **Approve**: Execute with original or modified parameters
- **Reject**: Skip trade, log reasoning
- **Modify**: Apply suggested changes (smaller size, wider stop, etc.)

**Database Storage:**
- Store all three stages in event_log:
  - Main agent proposal (tag: PROPOSAL_MAIN)
  - Consultant feedback (tag: PROPOSAL_CONSULTANT)  
  - Final decision (tag: DECISION_FINAL)
- Link all events via decision_id

### Dependencies
- Task 4 (ConsultantAgent module)
- Enhanced LLM advisor with `formulate_proposal()` and `consider_feedback()` methods

### Expected Outcome
- Every trade decision involves two AI agents
- Full audit trail of proposal → review → decision
- More robust trade selection with independent validation

---

## Task 6: Expand Symbol Watchlist

### Objective
Add 6 more cryptocurrency pairs to increase trading opportunities beyond BTC/ETH.

### Implementation Details

**New Symbols to Add:**
1. SOL/USD - Solana
2. AVAX/USD - Avalanche
3. MATIC/USD - Polygon (now POL)
4. LINK/USD - Chainlink
5. UNI/USD - Uniswap
6. AAVE/USD - Aave

**Changes Required:**

**File:** `runner/daemon.py`
```python
# Current
self.symbols = symbols or ['BTC/USD', 'ETH/USD']

# New
self.symbols = symbols or [
    'BTC/USD', 'ETH/USD', 'SOL/USD', 'AVAX/USD',
    'MATIC/USD', 'LINK/USD', 'UNI/USD', 'AAVE/USD'
]
```

**Considerations:**
- **Exchange compatibility**: Verify Coinbase supports all pairs
- **Data availability**: Ensure 200 candles available for TA
- **Liquidity**: All pairs should have sufficient volume
- **Correlation**: Diverse assets reduce portfolio correlation risk
- **Sentiment**: Perplexity/DDG should work for all assets

**Testing Requirements:**
- Warm up historical data for all 8 pairs
- Verify TA indicators compute correctly
- Confirm sentiment analysis works
- Check position sizing doesn't exceed 2% per symbol limit

**Alternative Exchange Setup:**
If Coinbase doesn't support some pairs, consider:
- Kraken: Better altcoin support
- Bybit: Wide crypto selection
- Update `CCXTAdapter` initialization in daemon

### Dependencies
- None (independent task)

### Expected Outcome
- 8 symbols actively monitored
- More trading opportunities
- Diversified portfolio potential
- All symbols work with sentiment + TA pipeline

---

## Task 7: Add Decision Rationale to Trades

### Objective
Extend the trades table to store comprehensive decision rationale including TA signals, sentiment reasoning, and consultant feedback.

### Implementation Details

**Database Schema Update:**

Add `decision_rationale` column to `trades` table:

```sql
ALTER TABLE trades 
ADD COLUMN decision_rationale TEXT;
```

**Rationale Structure (JSON):**
```json
{
  "ta_signals": {
    "regime": "trend",
    "signal_type": "breakout",
    "indicators": {
      "rsi": 65,
      "adx": 28,
      "volume_confirmed": true
    }
  },
  "sentiment": {
    "score": 0.7,
    "source": "perplexity",
    "summary": "Institutional buying, ETF inflows strong",
    "citations": ["url1", "url2"]
  },
  "main_agent_proposal": {
    "confidence": 75,
    "reasons": ["TA breakout", "bullish sentiment", "volume spike"],
    "model": "deepseek-chat"
  },
  "consultant_feedback": {
    "recommendation": "approve",
    "concerns": ["High volatility environment"],
    "confidence": 80,
    "model": "grok-fast"
  },
  "final_decision": {
    "execute": true,
    "modifications": null,
    "timestamp": "2025-10-19T10:30:00Z"
  }
}
```

**Code Changes:**

**File:** `storage/db.py`
```python
async def create_trade(self, symbol: str, side: str, qty: float, 
                      entry_price: float, entry_fees: float = 0, 
                      slippage_bps: float = 0, decision_rationale: dict = None):
    async with self.pool.acquire() as conn:
        row = await conn.fetchrow(
            '''INSERT INTO trades 
               (symbol, side, qty, entry_price, entry_ts, fees, slippage_bps, decision_rationale)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
               RETURNING trade_id''',
            symbol, side, qty, entry_price, datetime.utcnow(), 
            entry_fees, slippage_bps, json.dumps(decision_rationale)
        )
        return row['trade_id']
```

**File:** `runner/daemon.py`
```python
# Build rationale object
rationale = {
    "ta_signals": {...},
    "sentiment": {...},
    "main_agent_proposal": {...},
    "consultant_feedback": {...},
    "final_decision": {...}
}

# Pass to create_trade
trade_id = await self.db.create_trade(
    symbol, side, qty, entry_price,
    entry_fees=fees, slippage_bps=slippage,
    decision_rationale=rationale
)
```

### Dependencies
- Task 5 (two-agent workflow to populate consultant feedback)

### Expected Outcome
- Every trade has full provenance
- Can analyze why trades were taken
- Audit trail for compliance
- Machine learning dataset for future improvements

---

## Task 8: Enhanced Logging

### Objective
Improve daemon logging to show signals fired, sentiment reasoning, consultant feedback, and final decisions in real-time.

### Implementation Details

**Log Levels:**
- **INFO**: Normal operations (regime detection, sentiment cache hits)
- **WARNING**: Fallbacks, degraded data quality
- **ERROR**: API failures, database errors

**Enhanced Log Messages:**

**Current:**
```
INFO - BTC/USD regime: trend
INFO - BTC/USD sentiment: 0.70
```

**Enhanced:**
```
INFO - BTC/USD regime: trend (ADX: 28.5, strong momentum)
INFO - BTC/USD sentiment: 0.70 | 1) Institutional buying continues 2) ETF inflows record high 3) Mining difficulty up 5%
INFO - BTC/USD signal: BREAKOUT (entry: $95,000, stop: $94,000, R:R 3:1)
INFO - BTC/USD main agent: LONG proposal (confidence: 75%) - TA breakout + bullish sentiment
INFO - BTC/USD consultant: APPROVED (confidence: 80%) - Good setup, minor volatility concern
INFO - BTC/USD decision: EXECUTE LONG 0.05 BTC @ $95,000
```

**Exit Logging:**
```
INFO - ETH/USD exit signal: STOP_HIT (entry: $3,500, exit: $3,450, PnL: -$2.50)
INFO - ETH/USD consultant post-mortem: Stop was appropriate, market reversed quickly
```

**Sentiment Detail Logging:**
```python
# When fetching fresh sentiment
logger.info(f"{symbol} sentiment: {score:.2f} | {reasoning_summary}")
logger.info(f"{symbol} sentiment source: {model} | citations: {len(citations)}")

# When using cached sentiment
logger.info(f"{symbol} sentiment: {score:.2f} (cached from {window})")
```

**Decision Chain Logging:**
```python
logger.info(f"{symbol} proposal: {proposal['action'].upper()} {proposal['confidence']}%")
logger.info(f"{symbol} consultant: {feedback['recommendation'].upper()} {feedback['confidence']}%")
if feedback.get('concerns'):
    logger.warning(f"{symbol} concerns: {', '.join(feedback['concerns'])}")
logger.info(f"{symbol} final: {'EXECUTE' if execute else 'SKIP'}")
```

**Database Event Logging:**

Ensure all decision stages logged to `event_log` table:
```python
await self.db.log_event('INFO', ['SIGNAL', 'TA'], 
    symbol=symbol, action='BREAKOUT_DETECTED',
    decision_id=decision_id, payload=signal_details)

await self.db.log_event('INFO', ['PROPOSAL', 'MAIN'], 
    symbol=symbol, action='PROPOSE_LONG',
    decision_id=decision_id, payload=proposal)

await self.db.log_event('INFO', ['REVIEW', 'CONSULTANT'], 
    symbol=symbol, action='REVIEW_APPROVED',
    decision_id=decision_id, payload=feedback)

await self.db.log_event('INFO', ['DECISION', 'EXECUTE'], 
    symbol=symbol, action='EXECUTE_LONG',
    decision_id=decision_id, trade_id=trade_id)
```

### Dependencies
- Task 5 (two-agent workflow provides consultant feedback to log)

### Expected Outcome
- Clear, readable logs showing full decision process
- Easy to understand what agent is doing and why
- Searchable logs via `agent logs --tag PROPOSAL` etc.
- Sufficient detail for debugging and analysis

---

## Task 9: End-to-End Testing

### Objective
Verify all new features work together correctly and system operates as designed.

### Test Scenarios

**1. Sentiment Scheduling Test**
- Start daemon, note current UTC time
- Verify sentiment fetched on first cycle for each symbol
- Wait through multiple cycles (10-15 minutes)
- Confirm sentiment NOT re-fetched (using cached data)
- Check database shows only one sentiment entry per symbol per window
- Verify logs show "cached from {window}" messages

**2. Sentiment Fallback Test**
- Temporarily remove PERPLEXITY_API_KEY
- Restart daemon
- Verify DuckDuckGo fallback activates
- Check logs show "Using DuckDuckGo fallback" messages
- Verify sentiment data still saved to database
- Confirm sources.model = "duckduckgo-fallback"
- Restore PERPLEXITY_API_KEY

**3. Two-Agent Consultation Test**
- Monitor daemon for entry signal
- Verify sequence in logs:
  1. Signal detected
  2. Main agent proposes trade
  3. Consultant reviews proposal
  4. Final decision made
- Check event_log table has all stages with same decision_id
- Query trades table and verify decision_rationale populated

**4. Expanded Symbols Test**
- Verify all 8 symbols in daemon initialization
- Check historical data loaded for all symbols
- Confirm sentiment analysis works for altcoins (SOL, AVAX, etc.)
- Verify TA indicators compute for all symbols
- Check position sizing respects 2% per symbol limit

**5. Decision Rationale Test**
- Execute at least one trade
- Query database: `SELECT decision_rationale FROM trades WHERE trade_id = X`
- Verify JSON structure contains:
  - ta_signals
  - sentiment
  - main_agent_proposal
  - consultant_feedback
  - final_decision
- Confirm all fields populated correctly

**6. Enhanced Logging Test**
- Review daemon console output
- Verify detailed sentiment reasoning displayed
- Check signal details shown (entry, stop, R:R)
- Confirm consultant feedback visible in logs
- Verify final decisions clearly stated
- Test CLI: `agent logs --tag PROPOSAL` shows proposals
- Test CLI: `agent logs --tag CONSULTANT` shows reviews

**7. Error Handling Test**
- Simulate Perplexity API failure (bad API key temporarily)
- Verify DuckDuckGo fallback works
- Simulate network timeout
- Verify daemon continues operating
- Check consultant agent timeout handling (10s limit)
- Verify trades still execute if consultant fails

**8. Database Integrity Test**
- Check all tables have data:
  - sentiment (with twice-daily entries)
  - trades (with decision_rationale)
  - event_log (with full decision chains)
  - reflections (periodic commentary)
- Verify no duplicate sentiment entries in same window
- Confirm NAV calculations still accurate

**9. Performance Test**
- Run daemon for 2 hours minimum
- Monitor memory usage (should be stable)
- Check cycle execution time (<10 seconds per cycle)
- Verify no API rate limiting issues
- Confirm database connections don't leak

### Success Criteria
- ✅ All 8 symbols monitored successfully
- ✅ Sentiment fetched only twice daily
- ✅ DuckDuckGo fallback works when Perplexity unavailable
- ✅ Two-agent consultation happens for every trade
- ✅ Decision rationale stored in database
- ✅ Logs show full decision process
- ✅ No crashes or errors over 2-hour run
- ✅ NAV calculations remain accurate
- ✅ CLI commands work (status, logs with filters)

### Dependencies
- All previous tasks (4-8) completed

### Expected Outcome
- Fully operational AI trading agent with:
  - Robust sentiment analysis (Perplexity + DDG fallback)
  - Two-agent decision making (DeepSeek + Grok)
  - 8 cryptocurrency pairs monitored
  - Complete audit trail of all decisions
  - Enhanced logging for transparency
  - Production-ready stability

---

## Implementation Order

**Recommended sequence:**

1. **Task 4** (ConsultantAgent) - Foundation for two-agent system
2. **Task 5** (Two-agent workflow) - Core decision-making improvement
3. **Task 7** (Decision rationale) - Capture decisions in database
4. **Task 8** (Enhanced logging) - Visibility into system behavior
5. **Task 6** (Expand symbols) - Increase opportunities
6. **Task 9** (Testing) - Validate everything works

**Estimated Time:**
- Tasks 4-5: 60-90 minutes (consultant + workflow integration)
- Task 7: 20-30 minutes (database schema + code updates)
- Task 8: 30-40 minutes (logging enhancements)
- Task 6: 15-20 minutes (symbol expansion + testing)
- Task 9: 60-90 minutes (comprehensive testing)

**Total: 3-4 hours of focused implementation**

---

## Technical Considerations

### API Rate Limits
- **Perplexity**: Unknown limit, hence twice-daily fetching
- **OpenRouter**: Check rate limits for Grok-fast model
- **DuckDuckGo**: No API key required, but may throttle aggressive use

### Database Performance
- decision_rationale stored as TEXT (JSON)
- Consider indexing on decision_id for faster event_log queries
- Monitor database size growth with 8 symbols

### Error Recovery
- All API calls should have timeouts
- Fallback behavior for every external dependency
- Never block trades due to non-critical failures

### Production Readiness
- Add health check endpoint (optional)
- Consider Sentry or logging aggregation for production
- Set up alerting for repeated failures
- Document operational procedures

---

## Post-Implementation

After completing all tasks:

1. **Update replit.md** with new features
2. **Create example queries** for decision_rationale analysis
3. **Document consultant agent behavior** and configuration
4. **Benchmark performance** with 8 symbols vs 2
5. **Review API costs** (Perplexity + OpenRouter usage)

---

## Notes

- All features designed to be **non-blocking** - system continues even if consultant fails
- **Transparency** is key - every decision logged and explained
- **Fail-safe** architecture - multiple fallbacks at each level
- **Audit trail** - complete provenance for every trade
- **Scalable** - Can add more symbols or agents in future
