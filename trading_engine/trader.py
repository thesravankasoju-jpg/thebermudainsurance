"""
Trading Engine - Executes trades based on control room decisions
"""

from utils.logger import setup_logger
from config.settings import NIFTY_LOT_SIZE, BROKERAGE_PER_ROUNDTRIP

logger = setup_logger(__name__)

class TradingEngine:
    """
    Executes trading decisions via Kite API
    INTRADAY ONLY - Auto-closes ALL positions at 3:15 PM
    """

    def __init__(self, kite_connector):
        self.kite = kite_connector
        self.active_positions = []
        self.trade_history = []
        self.entry_window_open = False  # 9:30 AM - 10:00 AM
        self.trading_active = False  # 10:00 AM - 3:15 PM
        logger.info("TradingEngine initialized (INTRADAY MODE - All positions close at 3:15 PM)")

    def execute_trade(self, control_signal, max_contracts):
        """
        Execute trade based on control room signal

        Args:
            control_signal: Decision from control room {'direction', 'confidence', ...}
            max_contracts: Maximum number of contracts to trade

        Returns:
            trade: Executed trade details
        """

        direction = control_signal['direction']
        confidence = control_signal['confidence']

        # Skip if confidence too low
        if confidence < 70:
            logger.warning(f"Confidence too low ({confidence}%), skipping trade")
            return None

        try:
            # Get current Nifty price
            nifty_data = self.kite.fetch_realtime_data()
            current_price = nifty_data['nifty']['last_price']

            # Execute based on direction
            if direction == 'BULLISH':
                trade = self._execute_long(current_price, max_contracts, confidence)
            elif direction == 'BEARISH':
                trade = self._execute_short(current_price, max_contracts, confidence)
            else:  # NEUTRAL
                trade = self._execute_straddle(current_price, max_contracts, confidence)

            # Record trade
            self.active_positions.append(trade)
            self.trade_history.append(trade)

            logger.info(f"Trade executed: {trade}")
            return trade

        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            return None

    def _execute_long(self, entry_price, max_contracts, confidence):
        """Execute LONG Nifty Futures trade"""
        trade = {
            'type': 'LONG',
            'direction': 'LONG',
            'entry_price': entry_price,
            'contracts': max_contracts,
            'quantity': max_contracts * NIFTY_LOT_SIZE,
            'entry_value': entry_price * max_contracts * NIFTY_LOT_SIZE,
            'confidence': confidence,
            'status': 'OPEN',
            'entry_time': self._get_timestamp(),
            'brokerage': BROKERAGE_PER_ROUNDTRIP
        }
        logger.info(f"Executing LONG: {max_contracts} contracts at {entry_price}")
        return trade

    def _execute_short(self, entry_price, max_contracts, confidence):
        """Execute SHORT Nifty Futures trade"""
        trade = {
            'type': 'SHORT',
            'direction': 'SHORT',
            'entry_price': entry_price,
            'contracts': max_contracts,
            'quantity': max_contracts * NIFTY_LOT_SIZE,
            'entry_value': entry_price * max_contracts * NIFTY_LOT_SIZE,
            'confidence': confidence,
            'status': 'OPEN',
            'entry_time': self._get_timestamp(),
            'brokerage': BROKERAGE_PER_ROUNDTRIP
        }
        logger.info(f"Executing SHORT: {max_contracts} contracts at {entry_price}")
        return trade

    def _execute_straddle(self, entry_price, max_contracts, confidence):
        """Execute SHORT STRADDLE (sell call + sell put at ATM)"""
        # For straddle, sell 1 call and 1 put at entry price
        trade = {
            'type': 'STRADDLE',
            'direction': 'NEUTRAL',
            'entry_price': entry_price,
            'contracts': 1,  # 1 straddle = 1 call + 1 put
            'confidence': confidence,
            'status': 'OPEN',
            'entry_time': self._get_timestamp(),
            'brokerage': BROKERAGE_PER_ROUNDTRIP,
            'strategy': 'SHORT_STRADDLE',
            'call_strike': entry_price,
            'put_strike': entry_price
        }
        logger.info(f"Executing SHORT STRADDLE at {entry_price}")
        return trade

    def close_position(self, position, exit_price):
        """Close an open position"""
        if position['type'] == 'LONG':
            pnl = (exit_price - position['entry_price']) * position['contracts'] * NIFTY_LOT_SIZE
        elif position['type'] == 'SHORT':
            pnl = (position['entry_price'] - exit_price) * position['contracts'] * NIFTY_LOT_SIZE
        else:  # STRADDLE
            pnl = 0  # TODO: Calculate straddle P&L

        position['exit_price'] = exit_price
        position['exit_time'] = self._get_timestamp()
        position['pnl'] = pnl - (2 * position.get('brokerage', 0))
        position['status'] = 'CLOSED'

        logger.info(f"Position closed: P&L = {position['pnl']}")
        return position

    def close_all_positions(self, reason="STOP_LOSS"):
        """Close all active positions (for stop loss or market close)"""
        nifty_data = self.kite.fetch_realtime_data()
        current_price = nifty_data['nifty']['last_price']

        closed_count = 0
        for position in self.active_positions:
            if position['status'] == 'OPEN':
                self.close_position(position, current_price)
                closed_count += 1

        if reason == "MARKET_CLOSE":
            logger.warning(f"AUTO-CLOSED all {closed_count} positions at 3:15 PM (Market close)")
        else:
            logger.warning(f"CLOSED all {closed_count} positions due to {reason}")

    def check_and_auto_close_at_market_close(self):
        """
        Check if it's 3:15 PM and auto-close ALL positions
        This runs every tick to ensure positions are closed
        """
        from datetime import datetime

        current_time = datetime.now()

        # Auto-close at 3:15 PM
        if current_time.hour == 15 and current_time.minute >= 15:
            active_positions = self.get_active_positions()
            if active_positions:
                logger.critical(f"MARKET CLOSE (3:15 PM): AUTO-CLOSING {len(active_positions)} positions")
                self.close_all_positions(reason="MARKET_CLOSE")
                return True  # Positions were closed

        return False  # Not time to close yet

    def get_entry_window_status(self):
        """Check if we're in entry window (9:30 AM - 10:00 AM)"""
        from datetime import datetime

        current_time = datetime.now()

        # Entry window: 9:30 AM to 10:00 AM
        if current_time.hour == 9 and current_time.minute >= 30:
            return True
        elif current_time.hour == 10 and current_time.minute < 0:
            return True
        elif current_time.hour == 10 and current_time.minute == 0:
            return True

        return False

    def get_trading_window_status(self):
        """Check if we're in active trading window (10:00 AM - 3:15 PM)"""
        from datetime import datetime

        current_time = datetime.now()

        # Trading window: 10:00 AM to 3:15 PM
        if current_time.hour == 10 and current_time.minute >= 0:
            return True
        elif current_time.hour > 10 and current_time.hour < 15:
            return True
        elif current_time.hour == 15 and current_time.minute < 15:
            return True

        return False

    def get_active_positions(self):
        """Get all active positions"""
        return [p for p in self.active_positions if p['status'] == 'OPEN']

    def get_position_pnl(self, position, current_price):
        """Calculate current P&L for a position"""
        if position['type'] == 'LONG':
            pnl = (current_price - position['entry_price']) * position['contracts'] * NIFTY_LOT_SIZE
        elif position['type'] == 'SHORT':
            pnl = (position['entry_price'] - current_price) * position['contracts'] * NIFTY_LOT_SIZE
        else:
            pnl = 0

        return pnl

    def _get_timestamp(self):
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().isoformat()
