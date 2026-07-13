"""
Nifty 50 Trading System - live decision loop (PAPER MODE).

What this does today:
- Connects to Kite (KITE_API_KEY / KITE_ACCESS_TOKEN env vars).
- Every 5 minutes during market hours, pulls today's 5-minute bars and runs
  the SAME decision code the backtester uses (control_room.decision).
- Prints/logs what the system would do: the entry decision inside the
  09:30-10:00 window, position management, stop level, 15:15 square-off.
- Places NO orders. Order placement stays disabled until the strategy has
  a calibrated, out-of-sample backtest on real data (see docs/DATA_REALITY.md).

Run:  python main.py            (during market hours, IST)
      python main.py --replay   (after hours: replay today's bars once)
"""

import argparse
import os
import sys
import time
from datetime import datetime, date, timedelta

from config import settings as S
from generals.bar_generals import Bar, SessionContext
from control_room.decision import decide_entry
from utils.logger import setup_logger

logger = setup_logger("main")


def make_kite():
    from kiteconnect import KiteConnect
    api_key = os.environ.get("KITE_API_KEY", "")
    token = os.environ.get("KITE_ACCESS_TOKEN", "")
    if not api_key or not token:
        logger.error("Set KITE_API_KEY and KITE_ACCESS_TOKEN")
        sys.exit(1)
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(token)
    return kite


def fetch_bars(kite, day: date):
    candles = kite.historical_data(
        S.NIFTY_INDEX_INSTRUMENT_TOKEN,
        datetime.combine(day, datetime.min.time()),
        datetime.combine(day, datetime.max.time()),
        "5minute")
    return [Bar(c["date"].strftime("%H:%M"), c["open"], c["high"],
                c["low"], c["close"], c.get("volume", 0) or 0)
            for c in candles]


def fetch_context(kite, day: date) -> SessionContext:
    start = datetime.combine(day - timedelta(days=10), datetime.min.time())
    end = datetime.combine(day - timedelta(days=1), datetime.max.time())
    days = kite.historical_data(S.NIFTY_INDEX_INSTRUMENT_TOKEN, start, end, "day")
    ctx = SessionContext()
    if days:
        prev = days[-1]
        ctx.prev_open, ctx.prev_high = prev["open"], prev["high"]
        ctx.prev_low, ctx.prev_close = prev["low"], prev["close"]
    return ctx


def paper_loop(replay: bool = False):
    kite = make_kite()
    today = date.today()
    ctx = fetch_context(kite, today)
    logger.info(f"Paper mode | capital Rs {S.CAPITAL:,} | {S.MAX_CONTRACTS} lots "
                f"x {S.NIFTY_LOT_SIZE} | stop Rs {S.MAX_DAILY_LOSS:,} "
                f"(~{S.STOP_POINTS:.0f} pts) | square-off {S.SQUARE_OFF}")

    while True:
        bars = fetch_bars(kite, today)
        if bars:
            d = decide_entry(bars, ctx)
            logger.info(f"{bars[-1].ts} bars={len(bars)} -> {d.summary()}")
        if replay:
            break
        now = datetime.now().strftime("%H:%M")
        if now >= S.MARKET_CLOSE:
            logger.info("Market closed - stopping paper loop")
            break
        time.sleep(60 * S.BAR_INTERVAL_MINUTES)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay", action="store_true",
                    help="fetch today's bars once and print the decision")
    paper_loop(replay=ap.parse_args().replay)
