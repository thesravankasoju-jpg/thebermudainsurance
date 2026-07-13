"""
Backtest CLI.

Examples (run on a machine with market-data access):
    python -m backtest.run --source yfinance                # last ~60 days
    python -m backtest.run --source csv --path data/nifty_5m.csv
    python -m backtest.run --source kite --from 2026-05-01 --to 2026-07-11
    python -m backtest.run --source synthetic                # engine demo only
    python -m backtest.run --source yfinance --detail 2026-06-10   # per-bar log

Environment for --source kite: KITE_API_KEY, KITE_ACCESS_TOKEN.
Output: reports/backtest_report.md (+ per-bar decision log with --detail).
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest.engine import run_backtest, report            # noqa: E402
from backtest import data_loader, synthetic                 # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Nifty intraday system backtest")
    ap.add_argument("--source", choices=["yfinance", "csv", "kite", "synthetic"],
                    default="yfinance")
    ap.add_argument("--path", help="CSV path for --source csv")
    ap.add_argument("--symbol", default="^NSEI")
    ap.add_argument("--period", default="60d", help="yfinance lookback")
    ap.add_argument("--from", dest="from_date", help="kite start YYYY-MM-DD")
    ap.add_argument("--to", dest="to_date", help="kite end YYYY-MM-DD")
    ap.add_argument("--detail", metavar="DATE",
                    help="print per-bar decision log for one session")
    ap.add_argument("--out", default="reports/backtest_report.md")
    args = ap.parse_args()

    if args.source == "yfinance":
        sessions = data_loader.load_yfinance(args.symbol, args.period)
        label = f"REAL DATA - yfinance {args.symbol} {args.period}"
    elif args.source == "csv":
        if not args.path:
            ap.error("--source csv requires --path")
        sessions = data_loader.load_csv(args.path)
        label = f"REAL DATA - csv {args.path}"
    elif args.source == "kite":
        api_key = os.environ.get("KITE_API_KEY", "")
        token = os.environ.get("KITE_ACCESS_TOKEN", "")
        if not (api_key and token and args.from_date and args.to_date):
            ap.error("--source kite needs KITE_API_KEY, KITE_ACCESS_TOKEN, --from, --to")
        sessions = data_loader.load_kite(api_key, token, args.from_date, args.to_date)
        label = f"REAL DATA - kite {args.from_date}..{args.to_date}"
    else:
        sessions = synthetic.demo_sessions()
        label = "SYNTHETIC ENGINE-VALIDATION DATA - not a performance claim"

    results = run_backtest(sessions, collect_log=bool(args.detail))
    text = report(results, data_label=label)

    if args.detail:
        match = [r for r in results if r.date == args.detail]
        if match:
            text += f"\n\n## Per-bar decision log - {args.detail}\n"
            text += "\n".join("- " + line for line in match[0].decision_log)
        else:
            text += f"\n\n(no session found for --detail {args.detail})"

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        f.write(text + "\n")
    print(text)
    print(f"\nreport written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
