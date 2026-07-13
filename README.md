# Nifty 50 Intraday System - "100 Generals" Control Room

An intraday Nifty 50 futures/options system: a roster of independent
analyzing agents ("Generals") feeds a Control Room that decides LONG /
SHORT / NEUTRAL between 09:30 and 10:00 IST, manages the position, and
force-closes everything at 15:15. Hard stop: 2% of capital per day.

**Status: strategy machinery complete and tested; NOT calibrated, NOT
validated on sufficient real data, order placement disabled.** Read
[docs/DATA_REALITY.md](docs/DATA_REALITY.md) before believing any number.

## The rules of the system

| Rule | Value |
|------|-------|
| Capital | Rs 10,00,000 |
| Entry window | 09:30-10:00 IST, enters every session |
| Bullish read | LONG Nifty futures |
| Bearish read | SHORT Nifty futures |
| Neutral read | Short straddle (reduced size) |
| Hard stop | 2% of capital (Rs 20,000) on MTM, all positions closed |
| Square-off | 15:15 IST, always - intraday only, no overnight risk |
| Fake-move defence | 3 consecutive agreeing bar-closes before entry (2 for flash moves); range-compression filter refuses directional calls in dead sessions |

## Verified contract specs (see docs/DATA_REALITY.md for sources)

- Lot size **65** (NSE circular FAOP70616, Jan-2026 series onward)
- Margin **~Rs 1.9L/lot** -> **4 lots max** on 10L (Rs 2.4L MTM buffer kept)
- 4 lots = 260 qty -> Rs 260/point -> the 2% stop sits **~77 points** away

## Architecture

```
                    PRE-MARKET (context, may use LLM/news)
                                  |
5-min bars ----> GENERALS (deterministic, each votes or ABSTAINS)
                     price-action squad: 9 active
                     order-flow / options / cross-market squads: pending
                     data recording (see docs/DATA_REALITY.md)
                                  |
                 CONTROL ROOM  (control_room/decision.py)
                     weighted vote -> LONG / SHORT / NEUTRAL
                     persistence gate + range filter (trap defence)
                     measured cost: 0.069 ms per decision
                                  |
            +---------------------+---------------------+
            |                                           |
     BACKTEST ENGINE                              LIVE LOOP (paper)
     backtest/engine.py                           main.py
     same decision code,                          same decision code,
     next-bar fills, costs,                       Kite 5-min bars,
     stop / reversal / 15:15                      no orders placed yet
```

The backtester and the live loop import the **same** decision functions -
the backtest exercises the exact code that would trade.

## Run it

```bash
pip install -r requirements.txt
python -m pytest tests/ -q          # 18 tests: stop, square-off, no-lookahead...

# Engine demo on synthetic regime days (machinery validation, NOT performance):
python -m backtest.run --source synthetic

# Real data (run where the network allows):
python -m backtest.run --source yfinance                       # last ~60 days
python -m backtest.run --source yfinance --detail 2026-06-10   # per-bar log
KITE_API_KEY=... KITE_ACCESS_TOKEN=... \
python -m backtest.run --source kite --from 2024-01-01 --to 2026-07-11

# Live paper mode during market hours (prints decisions, places no orders):
KITE_API_KEY=... KITE_ACCESS_TOKEN=... python main.py
```

## Layout

```
config/settings.py        specs, risk, thresholds (single source of truth)
generals/bar_generals.py  9 active price-action Generals (pure functions)
generals/general_manager.py  roster + squad status
control_room/decision.py  entry decision + position monitor (shared)
backtest/engine.py        event-driven simulator: fills, stop, costs, report
backtest/data_loader.py   kite / yfinance / csv loaders
backtest/synthetic.py     regime archetypes for engine validation
backtest/run.py           CLI
tests/test_system.py      the guarantees, as executable tests
docs/DATA_REALITY.md      what is knowable when; read this first
main.py                   live paper loop (Kite)
```

## Road to live capital (in order, no skipping)

1. Run the backtest on 1-2 YEARS of Kite 5-minute data; calibrate
   thresholds walk-forward with out-of-sample separation.
2. Build the live Kite WebSocket recorder (depth ticks + option chains +
   top-20 quotes) so the order-flow and options squads can be built and
   validated on recorded data instead of imagination.
3. Paper-trade for weeks; the live decisions must match the backtest on
   the same days.
4. Only then wire order placement, starting at 1 lot.
