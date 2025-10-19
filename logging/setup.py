import logging
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

class JSONLFileHandler(logging.Handler):
    def __init__(self, log_dir: str = 'logs', max_bytes: int = 10_000_000, backup_count: int = 5):
        super().__init__()
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.current_file = self.log_dir / 'events.jsonl'
        self._rotate_if_needed()
    
    def _rotate_if_needed(self):
        if self.current_file.exists() and self.current_file.stat().st_size >= self.max_bytes:
            for i in range(self.backup_count - 1, 0, -1):
                old_file = self.log_dir / f'events.jsonl.{i}'
                new_file = self.log_dir / f'events.jsonl.{i + 1}'
                if old_file.exists():
                    if new_file.exists():
                        new_file.unlink()
                    old_file.rename(new_file)
            
            backup = self.log_dir / 'events.jsonl.1'
            if backup.exists():
                backup.unlink()
            self.current_file.rename(backup)
    
    def emit(self, record: logging.LogRecord):
        try:
            self._rotate_if_needed()
            
            log_entry = {
                'ts': datetime.utcnow().isoformat() + 'Z',
                'level': record.levelname,
                'message': record.getMessage(),
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno
            }
            
            if hasattr(record, 'tags'):
                log_entry['tags'] = record.tags
            if hasattr(record, 'symbol'):
                log_entry['symbol'] = record.symbol
            if hasattr(record, 'tf'):
                log_entry['tf'] = record.tf
            if hasattr(record, 'action'):
                log_entry['action'] = record.action
            if hasattr(record, 'decision_id'):
                log_entry['decision_id'] = record.decision_id
            if hasattr(record, 'trade_id'):
                log_entry['trade_id'] = record.trade_id
            if hasattr(record, 'payload'):
                log_entry['payload'] = record.payload
            
            with open(self.current_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        
        except Exception:
            self.handleError(record)

class TradingLogger:
    def __init__(self, name: str = 'trading_agent'):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)
            
            jsonl_handler = JSONLFileHandler()
            jsonl_handler.setLevel(logging.INFO)
            self.logger.addHandler(jsonl_handler)
    
    def log_event(self, level: str, message: str, tags: List[str] = None,
                  symbol: str = None, tf: str = None, action: str = None,
                  decision_id: str = None, trade_id: int = None, payload: Dict = None):
        log_level = getattr(logging, level.upper(), logging.INFO)
        
        extra = {}
        if tags:
            extra['tags'] = tags
        if symbol:
            extra['symbol'] = symbol
        if tf:
            extra['tf'] = tf
        if action:
            extra['action'] = action
        if decision_id:
            extra['decision_id'] = decision_id
        if trade_id:
            extra['trade_id'] = trade_id
        if payload:
            extra['payload'] = payload
        
        self.logger.log(log_level, message, extra=extra)
    
    def info(self, message: str, **kwargs):
        self.log_event('INFO', message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self.log_event('WARNING', message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self.log_event('ERROR', message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        self.log_event('DEBUG', message, **kwargs)

def get_logger(name: str = 'trading_agent') -> TradingLogger:
    return TradingLogger(name)
