# Data Reality - what the system can and cannot know

This document exists so that no component of this system is ever designed
around data that does not exist. Every General must name its data source
here before it is allowed to vote.

## Verified contract specs (2026-07-13)

| Item | Value | Source |
|------|-------|--------|
| Nifty 50 futures lot size | **65** (Jan-2026 series onward) | NSE circular FAOP70616 (2025-10-03) |
| Notional per lot @ 24,200 | ~Rs 15.7 lakh | lot x spot |
| NRML margin per lot | **~Rs 1.9 lakh** (SPAN ~1.56L + Exposure ~0.32L) | Zerodha margin calculator |
| Intraday (MIS) margin | Same as NRML - **no extra intraday leverage** | peak-margin rules |
| Max lots on Rs 10L capital | **4** (Rs 7.6L margin + Rs 2.4L MTM buffer) | sizing policy |
| P&L per index point (4 lots) | Rs 260 | 4 x 65 |
| 2% stop (Rs 20,000) in points | **~77 points** | 20,000 / 260 |

Margins move with volatility. Live code must read actual margin from the
Kite margins API before sizing. Never hardcode.

## What is knowable at 09:30 IST (entry window)

| Data | Available? | Source | Latency |
|------|-----------|--------|---------|
| Nifty/futures 5-min OHLCV | YES | Kite historical/WebSocket | seconds |
| Level-1 quotes + 5-level depth | YES (live only) | Kite WebSocket | ~100-300ms ticks |
| Top-20 constituent quotes | YES (live) | Kite WebSocket (one connection, 1000 symbols) | ~100-300ms |
| Option chain quotes + OI | YES (live, snapshot) | Kite quote API | seconds |
| India VIX | YES | Kite quote | seconds |
| Previous day FII/DII net flows | YES (it is yesterday's) | NSE/NSDL, published **after market close** | EOD |
| **Today's** FII/DII flows | **NO - does not exist intraday** | - | - |
| Historical order-book depth | **NO retail source** - must self-record | own recorder | - |
| News (budget/RBI/Fed) | Partially (calendar yes, surprise no) | event calendar | - |

Consequences:

1. **Any signal descriptioned as "reads today's FII flows at 09:30" is
   fiction.** FII/DII data is an EOD context input only.
2. **Order-flow Generals cannot be backtested yet.** NSE does not sell
   retail historical depth data. The path is: run a Kite WebSocket recorder
   during live sessions, archive depth ticks, and only then build + validate
   those Generals on the recorded data.
3. **Options Generals need recorded chain snapshots** (same recorder).
4. The March 23, 2020 session cannot be replayed from free sources - free
   intraday history goes back ~60 days (yfinance). Older sessions need a
   paid data vendor (e.g. GlobalDataFeed, TrueData) or Kite historical
   (index 5-min data goes back years - use `--source kite`).

## Latency reality

| Path | Measured/typical | Verdict |
|------|-----------------|---------|
| Rule-based `decide_entry` (this repo, 75-bar session) | **0.069 ms** | 1000x inside the 70ms budget |
| Kite WebSocket tick delivery | ~100-300 ms | dominates; decision cost is negligible |
| Kite order placement round trip | ~50-300 ms | broker-side |
| Any LLM API call | 500-3000 ms | **cannot be in the tick path** |

The "<70ms Control Room" requirement is met if and only if every in-loop
General is deterministic code. LLM analysis (news digestion, morning
briefing) belongs in a PRE-MARKET step that sets the day's context, never
in the intraday loop.

## Backtest honesty rules

1. No component may read bars, ticks, or any value with a timestamp later
   than the decision time (enforced structurally in `backtest/engine.py`
   and by `tests/test_system.py::TestNoLookahead`).
2. Fills happen on the NEXT bar's open, plus slippage, plus full costs
   (brokerage, STT, exchange, stamp, GST).
3. NEUTRAL-day short straddles use a documented approximation
   (`StraddleModel`) until real option chains are recorded - treat those
   P&L numbers as rough.
4. Synthetic-data results validate the MACHINERY only. They are never
   performance claims. Only walk-forward results on real data, with
   out-of-sample separation, count as evidence.
5. Backtest results on ~60 days of data are still not enough to deploy
   capital. Minimum bar: multiple regimes (trending up, trending down,
   range-bound, event days), out-of-sample, and a paper-trading period
   whose live decisions match the backtest's on the same days.

## Expectation setting

A 2%-risk-per-day intraday futures system that reliably makes "5-10% per
day" does not exist; compounding at that rate would absorb the entire
market within months. Honest goals for a good system of this class:
positive expectancy after costs, worst day capped at -2% (plus gap risk),
and drawdowns you can survive. Judge the system on those terms after real
backtests - not on narrative walkthroughs of past charts, including the
ones in this project's own chat history.
