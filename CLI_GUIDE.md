# AI Trading Agent - CLI Guide

## Overview

Your trading agent is currently **running in the background** via the "Trading Daemon" workflow. You can interact with it using simple command-line commands.

## Available Commands

### 1. Check Current Status

```bash
python agent.py status
```

**What it shows:**
- Current NAV (Net Asset Value)
- Open positions with entry price and current P&L
- Total realized and unrealized profit/loss
- Drawdown from peak NAV

**Example output:**
```
Current NAV: $10,245.67
Realized PnL: +$45.67
Unrealized PnL: +$200.00
Drawdown: -2.3% from peak $10,485.23

Open Positions:
- BTC/USD: 0.05 @ $98,500 | Current: $99,000 | PnL: +$25.00
- ETH/USD: 1.2 @ $3,450 | Current: $3,600 | PnL: +$180.00
```

### 2. Initialize Database (First Time Only)

```bash
python agent.py init --nav 10000
```

**When to use:** Only when starting fresh or resetting the system.
**What it does:**
- Creates database tables
- Sets starting cash/NAV (e.g., $10,000)
- Downloads 120 days of historical price data

**Note:** This was already done, so you don't need to run it again unless you want to reset.

### 3. Start Trading Daemon Manually

```bash
python agent.py run --cycle 120
```

**What it does:**
- Starts the trading loop
- Fetches live market data every 120 seconds
- Analyzes technical indicators
- Generates buy/sell signals
- Executes paper trades
- Updates NAV and logs everything

**Note:** The daemon is **already running** via the workflow, so you don't need to run this manually. You can see it in the console on the right side of your screen.

## Current System Status

### What's Running Now

The "Trading Daemon" workflow is active and processing:
- **Exchange:** Coinbase (switched from Binance to avoid location restrictions)
- **Trading Pairs:** BTC/USD, ETH/USD
- **Cycle Time:** 120 seconds
- **Mode:** Paper trading only (no real money)
- **Current NAV:** $10,000.00
- **Regime:** Both pairs are in "chop" (choppy/sideways market), so no trades yet

### Where to See Activity

1. **Console (right panel):** Real-time logs of what the daemon is doing
2. **Command line:** Run `python agent.py status` anytime to check positions/NAV
3. **Database:** All trades, candles, and events are stored in Neon Postgres

## Trading Logic

### When It Trades

**Entry signals (only in TREND regime):**
- Price breaks above Donchian upper band
- Volume surge (1.5x average)
- Positive Chaikin Money Flow (buying pressure)

**Exit signals:**
- Stop loss hit (2 ATRs below entry)
- Trailing stop triggered

**Risk Management:**
- Maximum 0.5% risk per trade
- Maximum 2% exposure per symbol
- Realistic slippage and 2 bps fees

### Current Market Regime

Both BTC and ETH are in "chop" mode, which means:
- Low ADX (directionless)
- No clear trend
- System waits for trend regime before entering trades

This is normal and expected - the system is designed to avoid trading in choppy markets!

## Example Workflow

### Morning Routine
```bash
# Check your portfolio
python agent.py status

# View recent activity (daemon logs are in the console)
```

### If You See a Trade
The daemon will automatically:
1. Detect entry signal
2. Calculate position size
3. Execute paper trade
4. Set stop loss
5. Log everything to database

You'll see logs like:
```
INFO - Entry signal for BTC/USD: {'signal': True, 'side': 'long', ...}
INFO - Entered BTC/USD: 0.05 @ $99,000.00
```

### Track Progress
```bash
# Check your NAV anytime
python agent.py status

# The daemon updates NAV every cycle (120s)
```

## Technical Details

### Data Sources
- **Market Data:** Coinbase via CCXT (public API, no keys needed)
- **Storage:** Neon Postgres database
- **Indicators:** pandas-ta library

### What's Logged
- Every price candle (5-minute OHLCV)
- All technical indicators
- Entry/exit signals
- Trade executions with fees and slippage
- NAV updates with P&L breakdown
- System events and errors

### Database Tables
- `nav` - NAV snapshots
- `candles` - OHLCV market data
- `positions` - Active positions
- `trades` - Trade history
- `event_log` - Audit trail

## Troubleshooting

### "No NAV data found"
```bash
# Reinitialize (warning: resets everything)
python agent.py init --nav 10000
```

### Daemon Not Running
Check the workflow panel - it should show "Trading Daemon" as RUNNING

### No Trades Happening
This is normal! The system only trades when:
1. Market is in TREND regime (not CHOP)
2. Entry signal criteria are met
3. Risk limits allow new positions

Most of the time, the system waits patiently for good opportunities.

## Next Steps

### Want to See More Detail?
The daemon logs everything in real-time to the console. Watch for:
- `INFO - BTC/USD regime: trend` ← Trading mode activated
- `INFO - Entry signal` ← Potential trade
- `INFO - Entered` ← Trade executed

### Need Historical Analysis?
All data is in the database. You can query it directly or we can build additional CLI commands like:
- `python agent.py trades` - Show trade history
- `python agent.py logs` - Query event log
- `python agent.py reflect` - Get AI commentary

### Ready for More Features?
The system is designed to add:
- Sentiment analysis (Perplexity API)
- LLM trade proposals (OpenRouter integration)
- Periodic market reflections
- More exchanges and trading pairs

## Safety Notes

⚠️ **This is PAPER TRADING only** - No real money is at risk  
✓ Database tracks everything for full auditability  
✓ Hard risk limits prevent over-trading  
✓ Stop losses protect positions  

## Questions?

The trading agent is autonomous and will:
- Keep running 24/7 via the workflow
- Trade when conditions are right
- Update you via logs and status

Just run `python agent.py status` whenever you want to check in!
