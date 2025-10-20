#!/usr/bin/env python3
import asyncio
import sys
import argparse
from runner.daemon import TradingDaemon

async def cmd_init(args):
    daemon = TradingDaemon()
    await daemon.init(args.nav)
    print(f"✓ Initialized with NAV ${args.nav:,.2f}")

async def cmd_status(args):
    daemon = TradingDaemon()
    await daemon.db.connect()
    await daemon.status()
    await daemon.db.close()

async def cmd_run(args):
    daemon = TradingDaemon()
    await daemon.db.connect()
    await daemon.run_daemon(cycle_seconds=args.cycle or 90)

async def cmd_logs(args):
    daemon = TradingDaemon()
    await daemon.db.connect()
    await daemon.show_logs(limit=args.limit or 50, level=args.level, tag=args.tag)
    await daemon.db.close()

async def cmd_rationale(args):
    daemon = TradingDaemon()
    await daemon.db.connect()

    if args.trade_id:
        # Show specific trade
        trade = await daemon.db.get_trade_with_rationale(args.trade_id)
        if trade:
            print(f"\nTrade {args.trade_id} Decision Rationale:")
            print("=" * 60)
            print(f"Symbol: {trade['symbol']}")
            print(f"Side: {trade['side']}")
            print(f"Quantity: {trade['qty']}")
            print(f"Entry: ${trade['entry_px']:.2f} on {trade['entry_ts']}")
            if trade.get('exit_px'):
                print(f"Exit: ${trade['exit_px']:.2f} on {trade['exit_ts']}")
                print(f"PnL: ${trade['pnl']:.2f}")
            print(f"\nDecision Rationale:")
            if trade.get('decision_rationale'):
                import json
                try:
                    rationale = json.loads(trade['decision_rationale'])
                    print(json.dumps(rationale, indent=2))
                except json.JSONDecodeError:
                    print(trade['decision_rationale'])
            else:
                print("No decision rationale available")
        else:
            print(f"Trade {args.trade_id} not found")
    else:
        # Show recent trades with rationale
        trades = await daemon.db.get_trades_with_rationale(limit=args.limit, symbol=args.symbol)
        if not trades:
            print("No trades with decision rationale found.")
            await daemon.db.close()
            return

        print(f"\nRecent Trades with Decision Rationale ({len(trades)}):")
        print("=" * 100)

        for trade in trades:
            exit_info = f"Exit: ${trade['exit_px']:7.2f}" if trade.get('exit_px') else 'Open      '
            pnl_info = f"PnL: ${trade['pnl']:7.2f}" if trade.get('pnl') else 'PnL: N/A  '
            print(f"ID: {trade['id']:3d} | {trade['symbol']:8s} | {trade['side']:4s} | "
                  f"Qty: {trade['qty']:6.4f} | Entry: ${trade['entry_px']:7.2f} | "
                  f"{exit_info} | {pnl_info}")

        print(f"\nUse 'agent rationale --trade-id <id>' to see detailed rationale for a specific trade.")

    await daemon.db.close()

async def cmd_validate(args):
    daemon = TradingDaemon()
    daemon.config = daemon._load_config('configs/app.yaml')

    if args.dry_run:
        print("\nSymbol Validation (Dry Run)")
        print("=" * 50)
        symbols_to_check = args.symbols or daemon.config.get('symbols', [])
        print(f"Would validate {len(symbols_to_check)} symbols:")
        for symbol in symbols_to_check:
            exchange = daemon.config.get('symbol_exchanges', {}).get(symbol, daemon.config.get('exchange', 'coinbase'))
            print(f"  {symbol} -> {exchange}")
        print(f"\nConfigured exchanges: {list(daemon._initialize_exchanges().keys())}")
        return

    # Run actual validation
    symbols_to_validate = args.symbols if args.symbols else None
    availability = daemon.validate_symbol_availability(symbols_to_validate)

    print(f"\nSymbol Availability Validation Results ({len(availability)} symbols):")
    print("=" * 70)

    available = 0
    unavailable = 0

    for symbol, is_available in availability.items():
        exchange = daemon.config.get('symbol_exchanges', {}).get(symbol, daemon.config.get('exchange', 'coinbase'))
        status = "✓ Available" if is_available else "✗ Unavailable"
        print(f"  {symbol:10s} | {exchange:10s} | {status}")
        if is_available:
            available += 1
        else:
            unavailable += 1

    print("-" * 70)
    print(f"Available: {available}, Unavailable: {unavailable}")

    if unavailable > 0:
        print("\nRecommendations:")
        print("- Some symbols may not be available on the configured exchange")
        print("- Consider updating symbol_exchanges in configs/app.yaml")
        print("- Alternative exchanges: binance (USDT pairs), kraken (USD pairs)")

def main():
    parser = argparse.ArgumentParser(description='AI Crypto Trading Agent')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    init_parser = subparsers.add_parser('init', help='Initialize database and NAV')
    init_parser.add_argument('--nav', type=float, required=True, help='Starting NAV in USD')
    
    status_parser = subparsers.add_parser('status', help='Show current status')
    
    run_parser = subparsers.add_parser('run', help='Run trading daemon')
    run_parser.add_argument('--cycle', type=int, help='Cycle time in seconds (default: 90)')
    
    logs_parser = subparsers.add_parser('logs', help='Show recent event logs')
    logs_parser.add_argument('--limit', type=int, help='Number of logs to show (default: 50)')
    logs_parser.add_argument('--level', type=str, help='Filter by level (INFO, ERROR, etc.)')
    logs_parser.add_argument('--tag', type=str, help='Filter by tag (CYCLE, TRADE, etc.)')

    rationale_parser = subparsers.add_parser('rationale', help='Show trades with decision rationale')
    rationale_parser.add_argument('--limit', type=int, default=10, help='Number of trades to show (default: 10)')
    rationale_parser.add_argument('--symbol', type=str, help='Filter by symbol')
    rationale_parser.add_argument('--trade-id', type=int, help='Show specific trade by ID')

    validate_parser = subparsers.add_parser('validate', help='Validate symbol availability across exchanges')
    validate_parser.add_argument('--symbols', nargs='*', help='Specific symbols to validate (default: all configured)')
    validate_parser.add_argument('--dry-run', action='store_true', help='Show what would be validated without making API calls')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if args.command == 'init':
        asyncio.run(cmd_init(args))
    elif args.command == 'status':
        asyncio.run(cmd_status(args))
    elif args.command == 'run':
        asyncio.run(cmd_run(args))
    elif args.command == 'logs':
        asyncio.run(cmd_logs(args))
    elif args.command == 'rationale':
        asyncio.run(cmd_rationale(args))
    elif args.command == 'validate':
        asyncio.run(cmd_validate(args))

if __name__ == '__main__':
    main()
