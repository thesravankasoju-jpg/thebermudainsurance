"""
Trading Engine - Executes trades based on control room decisions
"""

from utils.logger import setup_logger
from config.settings import NIFTY_LOT_SIZE, BROKERAGE_PER_ROUNDTRIP

logger = setup_logger(__name__)

class TradingEngine:
    """Executes trading decisions via Kite API"""

    def __init__(self, kite_connector):
        self.kite = kite_connector
        self.active_positions = []
        self.trade_history = []
        logger.info("TradingEngine initialized")

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

    def close_all_positions(self):
        """Close all active positions (for stop loss)"""
        nifty_data = self.kite.fetch_realtime_data()
        current_price = nifty_data['nifty']['last_price']

        for position in self.active_positions:
            if position['status'] == 'OPEN':
                self.close_position(position, current_price)

        logger.warning("All positions closed due to stop loss")

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
