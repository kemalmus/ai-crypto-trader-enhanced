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

if __name__ == '__main__':
    main()
