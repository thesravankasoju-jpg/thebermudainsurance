"""
Nifty 50 Automated Trading System - 100 Generals Control Room
Main entry point for the trading system
"""

import os
import sys
from datetime import datetime
from config.settings import CAPITAL, STOP_LOSS_PERCENT, MAX_CONTRACTS
from data.kite_connector import KiteConnector
from generals.general_manager import GeneralManager
from control_room.control_room import ControlRoom
from trading_engine.trader import TradingEngine
from risk_management.risk_manager import RiskManager
from utils.logger import setup_logger

logger = setup_logger(__name__)

class NiftyTradingSystem:
    """Main trading system orchestrator"""

    def __init__(self):
        self.capital = CAPITAL
        self.stop_loss = CAPITAL * STOP_LOSS_PERCENT / 100
        self.max_contracts = MAX_CONTRACTS

        # Initialize components
        self.kite = KiteConnector()
        self.generals = GeneralManager()
        self.control_room = ControlRoom()
        self.trader = TradingEngine(self.kite)
        self.risk_manager = RiskManager(self.capital, self.stop_loss)

        logger.info(f"System initialized: Capital={self.capital}, StopLoss={self.stop_loss}, MaxContracts={self.max_contracts}")

    def run_daily_cycle(self):
        """Run the complete daily trading cycle at 9:30 AM"""
        try:
            logger.info("=" * 80)
            logger.info(f"Starting daily trading cycle at {datetime.now()}")

            # 1. Fetch market data
            logger.info("Fetching market data...")
            market_data = self.kite.fetch_realtime_data()

            # 2. Analyze with 100 Generals
            logger.info("Analyzing with 100 Generals...")
            general_signals = self.generals.analyze_all(market_data)

            # 3. Control Room decision
            logger.info("Control Room aggregating signals...")
            control_signal = self.control_room.aggregate_signals(general_signals)

            logger.info(f"Control Room Decision: {control_signal['direction']} (Confidence: {control_signal['confidence']}%)")

            # 4. Execute trade
            if control_signal['confidence'] >= 70:  # Only trade if high confidence
                logger.info(f"Executing {control_signal['direction']} trade...")
                trade = self.trader.execute_trade(control_signal, self.max_contracts)

                # 5. Risk management
                self.risk_manager.set_active_trade(trade)
                logger.info(f"Trade executed: {trade}")
            else:
                logger.warning(f"Low confidence signal ({control_signal['confidence']}%), skipping trade")

            logger.info("Daily cycle complete")

        except Exception as e:
            logger.error(f"Error in daily cycle: {e}", exc_info=True)

    def monitor_positions(self):
        """Continuously monitor active positions and risk"""
        try:
            while True:
                # Get current market data
                market_data = self.kite.fetch_realtime_data()

                # Check risk limits
                current_loss = self.risk_manager.get_current_pnl(market_data)

                if current_loss <= -self.stop_loss:
                    logger.critical(f"STOP LOSS HIT: Loss = {current_loss}, closing all positions")
                    self.trader.close_all_positions()
                    self.risk_manager.reset()

                # Update position monitoring
                self.risk_manager.update_pnl(market_data)

        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        except Exception as e:
            logger.error(f"Error in position monitoring: {e}", exc_info=True)

if __name__ == "__main__":
    system = NiftyTradingSystem()

    # For testing: run one daily cycle
    system.run_daily_cycle()

    # For production: uncomment to run continuous monitoring
    # system.monitor_positions()
