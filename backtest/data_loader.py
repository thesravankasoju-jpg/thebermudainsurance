"""
Data loaders for the backtester. Three sources:

1. yfinance  - free, ^NSEI 5-minute bars, but ONLY the last ~60 days.
               Index volume is usually 0 on Yahoo; volume-based Generals
               abstain automatically. Run on a machine with open internet.
2. Kite      - the real source. historical_data() on instrument 256265
               (NIFTY 50 index) or the current futures token gives 5-minute
               candles WITH volume (futures). Needs API key + access token.
3. CSV       - any export with columns: datetime,open,high,low,close,volume
               (datetime in IST). Use this to feed old sessions such as
               2020-03-23, which no free intraday source still serves.

All loaders return {'YYYY-MM-DD': [Bar, ...]} sorted by time.
"""

import csv as _csv
from collections import defaultdict
from typing import Dict, List

from generals.bar_generals import Bar
from config import settings as S


def _to_sessions(rows) -> Dict[str, List[Bar]]:
    """rows: iterable of (date_str, hhmm_str, o, h, l, c, v)"""
    sessions: Dict[str, List[Bar]] = defaultdict(list)
    for date, hhmm, o, h, l, c, v in rows:
        sessions[date].append(Bar(hhmm, float(o), float(h), float(l), float(c), float(v)))
    for bars in sessions.values():
        bars.sort(key=lambda b: b.ts)
    return dict(sessions)


def load_csv(path: str) -> Dict[str, List[Bar]]:
    rows = []
    with open(path, newline="") as f:
        for rec in _csv.DictReader(f):
            dt = rec["datetime"].strip()          # "2026-06-10 09:15" or ISO
            date, time_part = dt[:10], dt[11:16]
            rows.append((date, time_part, rec["open"], rec["high"], rec["low"],
                         rec["close"], rec.get("volume", 0) or 0))
    return _to_sessions(rows)


def load_yfinance(symbol: str = "^NSEI", period: str = "60d") -> Dict[str, List[Bar]]:
    """Requires internet access to Yahoo Finance. 5m data limited to ~60 days."""
    import yfinance as yf
    df = yf.download(symbol, interval="5m", period=period,
                     auto_adjust=False, progress=False)
    if df is None or len(df) == 0:
        raise RuntimeError(
            f"yfinance returned no data for {symbol}. If you are behind a "
            "restricted network, export a CSV and use --source csv instead.")
    if hasattr(df.columns, "get_level_values") and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)
    df.index = df.index.tz_convert("Asia/Kolkata")
    rows = []
    for ts, rec in df.iterrows():
        rows.append((ts.strftime("%Y-%m-%d"), ts.strftime("%H:%M"),
                     rec["Open"], rec["High"], rec["Low"], rec["Close"],
                     rec.get("Volume", 0) or 0))
    return _to_sessions(rows)


def load_kite(api_key: str, access_token: str, from_date: str, to_date: str,
              instrument_token: int = S.NIFTY_INDEX_INSTRUMENT_TOKEN
              ) -> Dict[str, List[Bar]]:
    """The production loader. For futures volume, pass the current-month
    NIFTY futures instrument token from kite.instruments('NFO')."""
    from kiteconnect import KiteConnect
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    candles = kite.historical_data(instrument_token, from_date, to_date, "5minute")
    rows = []
    for c in candles:
        dt = c["date"]  # tz-aware IST datetime
        rows.append((dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M"),
                     c["open"], c["high"], c["low"], c["close"],
                     c.get("volume", 0) or 0))
    return _to_sessions(rows)


def save_sessions_csv(sessions: Dict[str, List[Bar]], path: str) -> None:
    """Cache sessions to CSV so backtests are reproducible offline."""
    with open(path, "w", newline="") as f:
        w = _csv.writer(f)
        w.writerow(["datetime", "open", "high", "low", "close", "volume"])
        for date in sorted(sessions):
            for b in sessions[date]:
                w.writerow([f"{date} {b.ts}", b.open, b.high, b.low, b.close, b.volume])
