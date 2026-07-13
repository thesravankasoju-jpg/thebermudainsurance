"""
Risk Management - Monitors positions, enforces stop loss, and manages risk
"""

from utils.logger import setup_logger
from config.settings import NIFTY_LOT_SIZE

logger = setup_logger(__name__)

class RiskManager:
    """Manages risk, positions, and enforces stop loss"""

    def __init__(self, capital, max_loss):
        self.capital = capital
        self.max_loss = max_loss  # 2% of capital
        self.initial_capital = capital
        self.current_capital = capital
        self.active_trade = None
        self.daily_pnl = 0
        self.max_daily_loss = max_loss

        logger.info(f"RiskManager initialized: Capital={capital}, MaxLoss={max_loss}")

    def set_active_trade(self, trade):
        """Set the currently active trade"""
        self.active_trade = trade
        logger.info(f"Active trade set: {trade}")

    def get_current_pnl(self, market_data):
        """
        Calculate current P&L based on market data

        Returns:
            pnl: Current unrealized P&L
        """

        if not self.active_trade or self.active_trade.get('status') != 'OPEN':
            return 0

        current_price = market_data['nifty']['last_price']
        entry_price = self.active_trade['entry_price']

        if self.active_trade['type'] == 'LONG':
            pnl = (current_price - entry_price) * self.active_trade['contracts'] * NIFTY_LOT_SIZE
        elif self.active_trade['type'] == 'SHORT':
            pnl = (entry_price - current_price) * self.active_trade['contracts'] * NIFTY_LOT_SIZE
        else:  # STRADDLE
            pnl = 0  # TODO: Calculate straddle P&L

        return pnl

    def update_pnl(self, market_data):
        """Update daily P&L tracking"""
        current_pnl = self.get_current_pnl(market_data)
        self.daily_pnl = current_pnl

        # Check if stop loss is breached
        if self.daily_pnl <= -self.max_loss:
            logger.critical(f"STOP LOSS BREACHED: {self.daily_pnl} <= -{self.max_loss}")
            return True  # Signal to stop

        # Log warning if approaching stop loss
        remaining_loss = self.max_loss + self.daily_pnl
        if remaining_loss < self.max_loss * 0.3:  # Within 30% of stop loss
            logger.warning(f"Approaching stop loss: Remaining loss tolerance = {remaining_loss}")

        return False

    def get_risk_metrics(self):
        """Get current risk metrics"""
        return {
            'capital': self.capital,
            'max_loss_allowed': self.max_loss,
            'daily_pnl': self.daily_pnl,
            'loss_percentage': (self.daily_pnl / self.capital) * 100,
            'remaining_loss_tolerance': self.max_loss + self.daily_pnl,
            'active_trade': self.active_trade is not None,
        }

    def reset(self):
        """Reset for next trading day"""
        self.active_trade = None
        self.daily_pnl = 0
        logger.info("Risk manager reset for new trading day")

    def calculate_position_size(self, risk_per_trade_percent=2):
        """
        Calculate position size based on risk management

        Args:
            risk_per_trade_percent: Risk per trade as % of capital

        Returns:
            max_contracts: Maximum contracts to trade
        """

        risk_amount = self.capital * (risk_per_trade_percent / 100)
        # For Nifty, typical stop loss = ~50-100 points
        # So max_contracts = risk_amount / (50 points * 25 shares per point)
        # This is already calculated in config as max_contracts

        return None

    def get_drawdown(self):
        """Get current drawdown"""
        loss = self.daily_pnl
        drawdown_percent = (loss / self.capital) * 100
        return {
            'loss': loss,
            'drawdown_percent': drawdown_percent,
            'within_limits': drawdown_percent >= -2,
        }

    def log_risk_status(self):
        """Log current risk status"""
        metrics = self.get_risk_metrics()
        drawdown = self.get_drawdown()

        logger.info(f"Risk Status: Daily P&L = {metrics['daily_pnl']}, "
                   f"Drawdown = {drawdown['drawdown_percent']:.2f}%, "
                   f"Remaining Loss Tolerance = {metrics['remaining_loss_tolerance']}")
