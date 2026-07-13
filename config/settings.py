"""
Configuration settings for the Nifty Trading System.

CONTRACT SPECS VERIFIED 2026-07-13:
- Lot size 65: NSE circular FAOP70616 (2025-10-03), effective January 2026 series
  (revised down from 75; SEBI Rs 10-15 lakh notional band).
- NRML margin ~Rs 1.9L/lot: SPAN ~1.56L + Exposure ~0.32L at spot ~24,200-24,800
  (Zerodha margin calculator). Intraday (MIS) margin for index futures is the
  same as NRML under peak-margin rules - there is NO extra intraday leverage.
- Margins move with volatility. Live code must read the actual margin from the
  Kite margins API before sizing; these constants are for backtests and sizing
  sanity checks only.
"""

# ============================================================================
# CAPITAL AND RISK MANAGEMENT
# ============================================================================
CAPITAL = 1_000_000            # Rs 10 lakh
STOP_LOSS_PERCENT = 2.0        # hard daily stop on total capital
MAX_DAILY_LOSS = CAPITAL * STOP_LOSS_PERCENT / 100   # Rs 20,000

# ============================================================================
# NIFTY FUTURES CONTRACT SPECS (Jan-2026 series onward)
# ============================================================================
NIFTY_LOT_SIZE = 65            # units per lot (NSE circular FAOP70616)
NIFTY_TICK_SIZE = 0.05
MARGIN_PER_LOT = 190_000       # SPAN + Exposure, approx; read live from Kite

# Sizing: keep a margin buffer so adverse MTM never triggers a margin call.
# 10L capital -> 8L deployable -> floor(8L / 1.9L) = 4 lots = 260 qty.
MARGIN_BUFFER_PERCENT = 20
DEPLOYABLE_CAPITAL = CAPITAL * (1 - MARGIN_BUFFER_PERCENT / 100)
MAX_CONTRACTS = int(DEPLOYABLE_CAPITAL // MARGIN_PER_LOT)      # 4 lots
TRADE_QTY = MAX_CONTRACTS * NIFTY_LOT_SIZE                     # 260 units

# Hard stop expressed in index points for the futures position:
# 20,000 / 260 = ~77 points adverse move closes everything.
STOP_POINTS = MAX_DAILY_LOSS / TRADE_QTY if TRADE_QTY else 0.0

# Neutral days trade short straddles with reduced size (margin per short
# straddle lot is higher than futures and gamma risk is unbounded).
STRADDLE_LOTS = 2

# ============================================================================
# TRANSACTION COSTS (Zerodha, futures, as of 2026)
# ============================================================================
BROKERAGE_PER_ORDER = 20.0     # flat Rs 20 or 0.03%, whichever lower
STT_SELL_PCT = 0.02            # % of sell-side notional (futures)
EXCHANGE_TXN_PCT = 0.00173     # % of notional, each side
STAMP_DUTY_BUY_PCT = 0.002     # % of buy-side notional
GST_PCT = 18.0                 # on brokerage + exchange charges
SLIPPAGE_POINTS = 1.0          # per side; index futures are liquid

# ============================================================================
# SESSION TIMINGS (IST)
# ============================================================================
MARKET_OPEN = "09:15"          # NSE cash/derivatives open (not 09:30)
ENTRY_DECISION_START = "09:30" # begin evaluating entry (user rule)
ENTRY_CUTOFF = "10:00"         # must have decided/entered by now (user rule)
SQUARE_OFF = "15:15"           # force-close everything (user rule)
MARKET_CLOSE = "15:30"

BAR_INTERVAL_MINUTES = 5

# ============================================================================
# CONTROL ROOM DECISION THRESHOLDS
# ----------------------------------------------------------------------------
# NOTE: these are engineering defaults, NOT calibrated values. They must be
# tuned on real historical data (walk-forward, out-of-sample) before any
# capital is deployed. Do not treat backtest output as validated performance
# until that calibration exists.
# ============================================================================
LONG_SCORE_THRESHOLD = 0.25    # aggregate score >= this -> LONG
SHORT_SCORE_THRESHOLD = -0.25  # aggregate score <= this -> SHORT
MIN_CONFIDENCE_TO_TRADE = 60   # 0-100; below this -> NEUTRAL handling
REVERSAL_EXIT_BARS = 2         # consecutive opposite-signal bars to exit early

# Fake-move defences (the trap filter):
# - A directional entry needs the SAME direction on ENTRY_CONFIRM_BARS
#   consecutive bar closes. Stop-hunts read directional for 1-2 bars and
#   then flip; real institutional moves persist.
# - A flash move (news shock) with extreme score+confidence may enter after
#   FLASH_CONFIRM_BARS instead.
# - No directional call at all when the session range is compressed vs the
#   recent median 09:15-10:00 range: small ranges are noise, not intent.
ENTRY_CONFIRM_BARS = 3
FLASH_CONFIRM_BARS = 2
FLASH_SCORE = 0.50
FLASH_CONFIDENCE = 85
RANGE_FILTER_RATIO = 0.5       # session range < ratio * median early range -> NEUTRAL

# Trap-detector activation gate: failed_breakdown_general needs >=5 bars of
# history before it can vote (it must see the opening range AND a
# subsequent break attempt). No directional entry may lock in before every
# General that could veto it has had a chance to speak - otherwise the
# persistence gate can be satisfied entirely from bars laid down BEFORE the
# trap detector switches on, which defeats its purpose. Found via a real
# integration-test failure (SYN-2-trap-reversal still shorted the spring
# after the persistence gate was added) - not a hypothetical concern.
MIN_BARS_FOR_DIRECTIONAL_ENTRY = 5

GENERAL_WEIGHTS = {
    # Price-action squad (computable from bar data, active today)
    "gap": 2.0,
    "opening_range": 2.5,
    "failed_breakdown": 3.0,   # trap detector (spring/upthrust)
    "vwap": 2.0,
    "momentum": 2.0,
    "structure": 1.5,
    "volume_pressure": 2.0,
    "persistence": 1.5,
    "prev_day": 1.0,
    # Squads that need live Kite recording before they can exist honestly:
    # order-book depth, options greeks/OI, cross-index correlation.
    "default": 1.0,
}

# ============================================================================
# DATA SOURCES
# ============================================================================
KITE_API_KEY = ""              # read from env KITE_API_KEY in live code
KITE_ACCESS_TOKEN = ""         # read from env KITE_ACCESS_TOKEN
NIFTY_INDEX_INSTRUMENT_TOKEN = 256265   # NSE:NIFTY 50 index token on Kite

TOP_20_NIFTY_STOCKS = [
    "RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS",
    "ITC", "LT", "BHARTIARTL", "AXISBANK", "SBIN",
    "KOTAKBANK", "M&M", "HINDUNILVR", "BAJFINANCE", "MARUTI",
    "SUNPHARMA", "NTPC", "TATAMOTORS", "TITAN", "ULTRACEMCO",
]  # refresh weights monthly from NSE indices factsheet

# ============================================================================
# LOGGING
# ============================================================================
LOG_LEVEL = "INFO"
LOG_FILE = "logs/trading_system.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
