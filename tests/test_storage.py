import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from storage.db import Database


class TestDecisionRationale:
    """Test decision rationale storage and retrieval"""

    @pytest.mark.asyncio
    async def test_create_trade_with_rationale(self):
        """Test creating a trade with decision rationale"""
        db = Database()
        db.pool = MagicMock()

        # Mock the database connection and response
        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=123)
        db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        # Test data
        decision_rationale = json.dumps({
            'symbol': 'BTC/USD',
            'regime': 'trend',
            'technical_signals': {'ema20': 50000},
            'llm_proposal': {'side': 'long', 'confidence': 75}
        })

        # Create trade with rationale
        trade_id = await db.create_trade(
            symbol='BTC/USD',
            side='long',
            qty=0.1,
            entry_px=50000,
            decision_rationale=decision_rationale
        )

        # Verify the call
        assert trade_id == 123
        mock_conn.fetchval.assert_called_once()
        # Check that decision_rationale was passed as the 8th positional argument (after SQL query)
        call_args = mock_conn.fetchval.call_args[0]
        assert len(call_args) == 9  # SQL query + 8 parameters
        assert call_args[8] == decision_rationale  # decision_rationale should be the last argument

    @pytest.mark.asyncio
    async def test_close_trade_with_rationale(self):
        """Test closing a trade with decision rationale"""
        db = Database()
        db.pool = MagicMock()

        # Mock the database connection
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock()
        db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        # Test data
        exit_rationale = json.dumps({
            'symbol': 'BTC/USD',
            'regime': 'trend',
            'exit_signal': {'reason': 'stop_loss'}
        })

        # Close trade with rationale
        await db.close_trade(
            trade_id=123,
            exit_px=49000,
            exit_fees=1.0,
            exit_slippage_bps=0.5,
            pnl=-100.0,
            reason='stop_loss',
            decision_rationale=exit_rationale
        )

        # Verify the call was made with rationale
        mock_conn.execute.assert_called_once()
        # Check that decision_rationale was passed as a positional parameter
        call_args = mock_conn.execute.call_args[0]
        # The SQL query should include decision_rationale and the parameter should be passed
        assert exit_rationale in call_args

    @pytest.mark.asyncio
    async def test_close_trade_without_rationale(self):
        """Test closing a trade without decision rationale (backward compatibility)"""
        db = Database()
        db.pool = MagicMock()

        # Mock the database connection
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock()
        db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        # Close trade without rationale
        await db.close_trade(
            trade_id=123,
            exit_px=49000,
            exit_fees=1.0,
            exit_slippage_bps=0.5,
            pnl=-100.0,
            reason='stop_loss'
        )

        # Verify the call was made without rationale
        mock_conn.execute.assert_called_once()
        # Should use the version without decision_rationale parameter
        call_args = mock_conn.execute.call_args[0]
        # Check that the SQL query doesn't include decision_rationale
        sql_query = call_args[0]
        assert 'decision_rationale' not in sql_query

    @pytest.mark.asyncio
    async def test_get_trade_with_rationale(self):
        """Test retrieving a trade with its decision rationale"""
        db = Database()
        db.pool = MagicMock()

        # Mock trade data with rationale
        mock_trade = {
            'id': 123,
            'symbol': 'BTC/USD',
            'side': 'long',
            'qty': 0.1,
            'entry_px': 50000,
            'decision_rationale': json.dumps({'test': 'rationale'})
        }

        # Mock the database connection and response
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_trade)
        db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        # Get trade with rationale
        trade = await db.get_trade_with_rationale(123)

        # Verify the result
        assert trade is not None
        assert trade['id'] == 123
        assert 'decision_rationale' in trade
        assert trade['decision_rationale'] is not None

    @pytest.mark.asyncio
    async def test_get_trades_with_rationale(self):
        """Test retrieving multiple trades with decision rationale"""
        db = Database()
        db.pool = MagicMock()

        # Mock trades data with rationale
        mock_trades = [
            {
                'id': 123,
                'symbol': 'BTC/USD',
                'side': 'long',
                'decision_rationale': json.dumps({'test': 'rationale1'})
            },
            {
                'id': 124,
                'symbol': 'ETH/USD',
                'side': 'short',
                'decision_rationale': json.dumps({'test': 'rationale2'})
            }
        ]

        # Mock the database connection and response
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=mock_trades)
        db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        # Get trades with rationale
        trades = await db.get_trades_with_rationale(limit=10)

        # Verify the results
        assert len(trades) == 2
        assert all('decision_rationale' in trade for trade in trades)
        assert all(trade['decision_rationale'] is not None for trade in trades)

    @pytest.mark.asyncio
    async def test_get_trades_with_rationale_filtered_by_symbol(self):
        """Test retrieving trades with rationale filtered by symbol"""
        db = Database()
        db.pool = MagicMock()

        # Mock filtered trades data
        mock_trades = [
            {
                'id': 123,
                'symbol': 'BTC/USD',
                'side': 'long',
                'decision_rationale': json.dumps({'test': 'rationale1'})
            }
        ]

        # Mock the database connection and response
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=mock_trades)
        db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        # Get trades with rationale filtered by symbol
        trades = await db.get_trades_with_rationale(limit=10, symbol='BTC/USD')

        # Verify the results
        assert len(trades) == 1
        assert trades[0]['symbol'] == 'BTC/USD'

        # Verify the query included the symbol filter
        mock_conn.fetch.assert_called_once()
        # Check that the symbol parameter was passed correctly as a positional argument
        call_args = mock_conn.fetch.call_args[0]
        assert 'BTC/USD' in call_args
