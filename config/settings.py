"""
Configuration settings for the Nifty Trading System
"""

# ============================================================================
# CAPITAL AND RISK MANAGEMENT
# ============================================================================
CAPITAL = 1000000  # ₹10 lakh starting capital
STOP_LOSS_PERCENT = 2  # 2% hard stop loss = ₹20,000
MAX_LOSS = CAPITAL * STOP_LOSS_PERCENT / 100

# ============================================================================
# NIFTY FUTURES SPECIFICATIONS (Corrected)
# ============================================================================
NIFTY_LOT_SIZE = 25  # shares per contract
NIFTY_TICK_SIZE = 0.05  # ₹0.05
MARGIN_PER_LOT = 70000  # ₹70,000 average SPAN margin
BROKERAGE_PER_ROUNDTRIP = 40  # ₹40 per round trip
SLIPPAGE_PAISE = 3  # 3 paise average slippage

# Calculate max contracts based on capital
MAX_CONTRACTS = int(CAPITAL / MARGIN_PER_LOT)  # ~14 contracts for 10L capital

# ============================================================================
# TRADING STRATEGY
# ============================================================================
TRADING_START_TIME = "09:30"  # Market open time (always enter)
TRADING_END_TIME = "15:30"  # Market close time
SIGNAL_UPDATE_INTERVAL_MINUTES = 5  # Update control room every 5 minutes
MIN_CONFIDENCE_TO_TRADE = 70  # Minimum 70% confidence to execute

# Thresholds for direction classification
BULLISH_THRESHOLD = 0.6
BEARISH_THRESHOLD = -0.6
# Between these thresholds = NEUTRAL (use straddle/strangle)

# ============================================================================
# GENERAL PARAMETERS
# ============================================================================
TOTAL_GENERALS = 100  # Number of analyzing agents
HIGH_IMPACT_GENERALS = [
    "order_flow",
    "options_greeks",
    "fii_dii",
    "top_20_correlation"
]

GENERAL_WEIGHTS = {
    "order_flow": 4.0,  # Most important
    "options_greeks": 3.0,
    "fii_dii": 3.0,
    "top_20_correlation": 3.0,
    "volume": 2.0,
    "technical": 2.0,
    "sentiment": 1.5,
    "default": 1.0  # Other generals
}

# ============================================================================
# DATA SOURCES
# ============================================================================
KITE_API_KEY = "your_kite_api_key"  # Will be set from environment
KITE_ACCESS_TOKEN = "your_access_token"  # Will be set from environment

# FII/DII data source (external)
NSE_FIIDII_URL = "https://www.nseindia.com/api/fiidii"

# Top 20 Nifty stocks (by weight)
TOP_20_NIFTY_STOCKS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFOSY", "ICICIBANK",
    "HINDUNILVR", "LT", "SBIN", "MARUTI", "BAJAJFINSV",
    "WIPRO", "ASIANPAINT", "SUNPHARMA", "KOTAKBANK", "ITC",
    "AXISBANK", "M&M", "TITAN", "HDFC", "JSWSTEEL"
]

# ============================================================================
# POSITION MANAGEMENT
# ============================================================================
POSITION_UPDATE_INTERVAL = 1  # Update P&L every 1 minute
MONITORING_LOOP_SLEEP = 5  # Check positions every 5 seconds

# ============================================================================
# LOGGING
# ============================================================================
LOG_LEVEL = "INFO"
LOG_FILE = "logs/trading_system.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# ============================================================================
# BACKTESTING
# ============================================================================
BACKTEST_CAPITAL = 1000000
BACKTEST_INITIAL_CASH = 1000000
BACKTEST_COMMISSION = BROKERAGE_PER_ROUNDTRIP / 100  # In percentage

# ============================================================================
# STRATEGY MODES
# ============================================================================
MODE_BULLISH = "LONG"  # Go long on bullish signal
MODE_BEARISH = "SHORT"  # Go short on bearish signal
MODE_NEUTRAL = "STRADDLE"  # Short straddle on neutral signal
