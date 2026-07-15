"""
Event-driven intraday backtest engine.

Rules implemented (exactly the user's system):
- Evaluate entry on every 5-min bar close from 09:30 to the 10:00 cutoff.
- LONG/SHORT futures on a confident Control Room signal; fill at the NEXT
  bar's open plus slippage (we never fill at the price that generated the
  signal - that is lookahead).
- If still NEUTRAL at the 10:00 cutoff: short straddle (modelled - see
  StraddleModel docstring) because the system enters every day.
- Hard stop: Rs 20,000 (2% of capital) on MTM, checked intrabar against
  bar highs/lows. Gap-through fills at the bar open (honest gap risk).
- Early exit if the Control Room flips hard against the position for
  REVERSAL_EXIT_BARS consecutive bars.
- Everything force-closed at 15:15. No overnight positions, ever.

The engine feeds the Control Room only bars[0:i+1] at step i. Lookahead is
structurally impossible unless someone edits this file.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import math

from generals.bar_generals import Bar, SessionContext
from control_room.decision import decide_entry, monitor, Decision, LONG, SHORT, NEUTRAL
from config import settings as S


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minutes(ts: str) -> int:
    h, m = ts.split(":")
    return int(h) * 60 + int(m)

ENTRY_START_MIN = _minutes(S.ENTRY_DECISION_START)   # 09:30
ENTRY_CUTOFF_MIN = _minutes(S.ENTRY_CUTOFF)          # 10:00
SQUARE_OFF_MIN = _minutes(S.SQUARE_OFF)              # 15:15
SESSION_OPEN_MIN = _minutes(S.MARKET_OPEN)           # 09:15
SESSION_CLOSE_MIN = _minutes(S.MARKET_CLOSE)         # 15:30


def futures_roundtrip_costs(entry_px: float, exit_px: float, lots: int) -> float:
    """Brokerage + STT + exchange charges + stamp + GST for one round trip."""
    qty = lots * S.NIFTY_LOT_SIZE
    buy_notional = min(entry_px, exit_px) * qty   # one leg is a buy...
    sell_notional = max(entry_px, exit_px) * qty  # ...and one a sell; use actual sides' notionals approx
    brokerage = 2 * S.BROKERAGE_PER_ORDER
    stt = sell_notional * S.STT_SELL_PCT / 100
    exch = (buy_notional + sell_notional) * S.EXCHANGE_TXN_PCT / 100
    stamp = buy_notional * S.STAMP_DUTY_BUY_PCT / 100
    gst = (brokerage + exch) * S.GST_PCT / 100
    return brokerage + stt + exch + stamp + gst


OPTIONS_COST_FLAT = 250.0  # approx per straddle round trip (4 orders + charges)


class StraddleModel:
    """APPROXIMATION - not a real options backtest.

    Models an intraday ATM short straddle as: collect time value that decays
    with sqrt(session-time remaining), pay back intrinsic |S - K| at exit.

        premium(t) = 0.8 * S * sigma_daily * sqrt(frac_of_session_remaining)

    This is the standard expiry-style straddle approximation. It ignores IV
    changes, skew, and weekday-to-expiry term structure, so treat NEUTRAL-day
    P&L as a rough model. A real validation needs recorded option chains
    (Kite quote API) - see docs/DATA_REALITY.md.
    """

    def __init__(self, sigma_daily_pct: float):
        self.sigma = max(sigma_daily_pct, 0.2) / 100.0

    def _frac_remaining(self, minute: int) -> float:
        total = SESSION_CLOSE_MIN - SESSION_OPEN_MIN
        rem = max(SESSION_CLOSE_MIN - minute, 0)
        return rem / total

    def premium(self, spot: float, minute: int) -> float:
        return 0.8 * spot * self.sigma * math.sqrt(self._frac_remaining(minute))

    def mtm_per_unit(self, strike: float, entry_premium: float,
                     spot: float, minute: int) -> float:
        """Positive = profit for the short straddle."""
        tv = self.premium(strike, minute)
        intrinsic = abs(spot - strike)
        return entry_premium - (tv + intrinsic)


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

@dataclass
class SessionResult:
    date: str
    direction: str                    # LONG / SHORT / STRADDLE / NO_TRADE
    entry_time: Optional[str] = None
    entry_price: Optional[float] = None
    exit_time: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: str = ""
    gross_pnl: float = 0.0
    costs: float = 0.0
    net_pnl: float = 0.0
    max_adverse_mtm: float = 0.0      # worst intraday MTM (negative number)
    decision_score: float = 0.0
    decision_confidence: float = 0.0
    decision_log: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Session simulation
# ---------------------------------------------------------------------------

def run_session(date: str, bars: List[Bar], ctx: SessionContext,
                sigma_daily_pct: float = 0.9,
                collect_log: bool = False) -> SessionResult:
    res = SessionResult(date=date, direction="NO_TRADE")
    if len(bars) < 6:
        res.exit_reason = "insufficient bars"
        return res

    qty = S.TRADE_QTY
    stop_rupees = S.MAX_DAILY_LOSS

    position = None          # dict when open
    opposite_streak = 0
    entry_streak = 0         # consecutive same-direction reads pre-entry
    streak_direction = None
    total_qty_open = 0       # current quantity held (for scaled entry)

    i = 0
    while i < len(bars):
        bar = bars[i]
        start_min = _minutes(bar.ts)
        end_min = start_min + S.BAR_INTERVAL_MINUTES

        # ------------------------------------------------ open-position path
        if position is not None:
            direction = position["direction"]

            if direction in (LONG, SHORT):
                # Scaled entry: add contracts on subsequent bars in entry window
                if (ENTRY_START_MIN <= end_min <= ENTRY_CUTOFF_MIN and
                    "entry_bar_index" in position and
                    i > position["entry_bar_index"] and
                    total_qty_open < qty):
                    # Check if we should add more contracts
                    bars_since_entry = i - position["entry_bar_index"]
                    new_qty = 0
                    if bars_since_entry == 1 and total_qty_open == S.NIFTY_LOT_SIZE:
                        # First bar post-entry: add 1 more lot
                        new_qty = S.NIFTY_LOT_SIZE
                    elif bars_since_entry >= 2 and total_qty_open == 2 * S.NIFTY_LOT_SIZE:
                        # Second+ bar post-entry: add remaining 2 lots
                        new_qty = 2 * S.NIFTY_LOT_SIZE

                    if new_qty > 0:
                        # Add new contracts at this bar's open + slippage
                        slip = S.SLIPPAGE_POINTS if direction == LONG else -S.SLIPPAGE_POINTS
                        new_entry_px = bar.open + slip
                        # Update position to track weighted average entry price
                        old_cost = position["entry_price"] * total_qty_open
                        new_cost = new_entry_px * new_qty
                        total_qty_open += new_qty
                        position["entry_price"] = (old_cost + new_cost) / total_qty_open

                stop_px = position["stop_price"]
                hit = (bar.low <= stop_px) if direction == LONG else (bar.high >= stop_px)
                if hit:
                    # Gap-through: if the bar opened beyond the stop, we get the open.
                    if direction == LONG:
                        fill = min(bar.open, stop_px) - S.SLIPPAGE_POINTS
                    else:
                        fill = max(bar.open, stop_px) + S.SLIPPAGE_POINTS
                    _close_futures(res, position, fill, bar.ts, "STOP_LOSS", total_qty_open)
                    position = None
                    total_qty_open = 0
                    i += 1
                    continue

                # MTM tracking on bar close
                mtm = _futures_mtm(position, bar.close, total_qty_open)
                res.max_adverse_mtm = min(res.max_adverse_mtm, mtm)

                # Forced square-off
                if end_min >= SQUARE_OFF_MIN:
                    fill = bar.close - S.SLIPPAGE_POINTS if direction == LONG \
                        else bar.close + S.SLIPPAGE_POINTS
                    _close_futures(res, position, fill, bar.ts, "SQUARE_OFF_1515", total_qty_open)
                    position = None
                    total_qty_open = 0
                    i += 1
                    continue

                # Control-room reversal exit
                action, opposite_streak = monitor(bars[: i + 1], ctx,
                                                  direction, opposite_streak)
                if action == "EXIT_REVERSAL":
                    fill = bar.close - S.SLIPPAGE_POINTS if direction == LONG \
                        else bar.close + S.SLIPPAGE_POINTS
                    _close_futures(res, position, fill, bar.ts, "REVERSAL_EXIT", total_qty_open)
                    position = None
                    total_qty_open = 0

            else:  # STRADDLE
                model: StraddleModel = position["model"]
                sqty = S.STRADDLE_LOTS * S.NIFTY_LOT_SIZE
                # Worst intrabar excursion: check the bar extreme farther from strike
                worst_spot = bar.high if abs(bar.high - position["strike"]) > \
                    abs(bar.low - position["strike"]) else bar.low
                worst_mtm = sqty * model.mtm_per_unit(
                    position["strike"], position["entry_premium"], worst_spot, end_min)
                close_mtm = sqty * model.mtm_per_unit(
                    position["strike"], position["entry_premium"], bar.close, end_min)
                res.max_adverse_mtm = min(res.max_adverse_mtm, worst_mtm)

                if worst_mtm <= -stop_rupees:
                    _close_straddle(res, position, worst_spot, bar.ts, "STOP_LOSS",
                                    end_min, sqty)
                    position = None
                elif end_min >= SQUARE_OFF_MIN:
                    _close_straddle(res, position, bar.close, bar.ts, "SQUARE_OFF_1515",
                                    end_min, sqty)
                    position = None

            i += 1
            continue

        # ------------------------------------------------ entry-decision path
        if res.direction != "NO_TRADE":
            i += 1
            continue  # already traded and closed; done for the day

        if ENTRY_START_MIN <= end_min <= ENTRY_CUTOFF_MIN:
            d = decide_entry(bars[: i + 1], ctx)
            if collect_log:
                res.decision_log.append(f"{bar.ts}+5m {d.summary()}")

            # Trap-detector activation gate: don't let a directional read
            # count toward entry until every General - especially
            # failed_breakdown_general, which needs >=5 bars to see a
            # break-and-reclaim - has had a chance to veto it.
            trap_detector_live = (i + 1) >= S.MIN_BARS_FOR_DIRECTIONAL_ENTRY

            # Persistence gate: stop-hunts read directional for a bar or two
            # then flip; institutional moves persist. Require agreement on
            # consecutive closes before committing capital - except at the
            # 10:00 cutoff, where the rule of the system is: decide and enter.
            if d.direction in (LONG, SHORT) and trap_detector_live:
                if d.direction == streak_direction:
                    entry_streak += 1
                else:
                    streak_direction, entry_streak = d.direction, 1
            else:
                streak_direction, entry_streak = None, 0

            flash = (abs(d.score) >= S.FLASH_SCORE
                     and d.confidence >= S.FLASH_CONFIDENCE)
            confirmed = (entry_streak >= S.ENTRY_CONFIRM_BARS
                         or (flash and entry_streak >= S.FLASH_CONFIRM_BARS))
            at_cutoff = end_min >= ENTRY_CUTOFF_MIN
            enter_directional = (d.direction in (LONG, SHORT) and trap_detector_live
                                 and (confirmed or at_cutoff))

            if (enter_directional or at_cutoff) and i + 1 < len(bars):
                nxt = bars[i + 1]
                res.decision_score = d.score
                res.decision_confidence = d.confidence
                if enter_directional:
                    slip = S.SLIPPAGE_POINTS if d.direction == LONG else -S.SLIPPAGE_POINTS
                    entry_px = nxt.open + slip
                    stop_pts = stop_rupees / qty  # stop calculated on full qty for consistency
                    position = {
                        "direction": d.direction,
                        "entry_price": entry_px,
                        "stop_price": entry_px - stop_pts if d.direction == LONG
                        else entry_px + stop_pts,
                        "entry_bar_index": i + 1,  # for scaled entry tracking
                    }
                    res.direction = d.direction
                    total_qty_open = S.NIFTY_LOT_SIZE  # start with 1 lot
                else:
                    # NEUTRAL at cutoff -> short straddle (modelled)
                    model = StraddleModel(sigma_daily_pct)
                    strike = round(nxt.open / 50) * 50
                    entry_min = _minutes(nxt.ts)
                    position = {
                        "direction": "STRADDLE",
                        "model": model,
                        "strike": strike,
                        "entry_premium": model.premium(strike, entry_min),
                    }
                    res.direction = "STRADDLE"
                res.entry_time = nxt.ts
                res.entry_price = position.get("entry_price", nxt.open)
                opposite_streak = 0

        i += 1

    # Safety: position must never survive the loop (last bar closes 15:30)
    if position is not None:
        last = bars[-1]
        if position["direction"] in (LONG, SHORT):
            fill = last.close - S.SLIPPAGE_POINTS if position["direction"] == LONG \
                else last.close + S.SLIPPAGE_POINTS
            _close_futures(res, position, fill, last.ts, "EOD_FAILSAFE", total_qty_open)
        else:
            _close_straddle(res, position, last.close, last.ts, "EOD_FAILSAFE",
                            _minutes(last.ts) + S.BAR_INTERVAL_MINUTES,
                            S.STRADDLE_LOTS * S.NIFTY_LOT_SIZE)
    return res


def _futures_mtm(position: dict, price: float, qty: int) -> float:
    if position["direction"] == LONG:
        return (price - position["entry_price"]) * qty
    return (position["entry_price"] - price) * qty


def _close_futures(res: SessionResult, position: dict, fill: float,
                   ts: str, reason: str, qty: int) -> None:
    gross = _futures_mtm(position, fill, qty)
    lots = qty // S.NIFTY_LOT_SIZE  # actual number of lots entered
    costs = futures_roundtrip_costs(position["entry_price"], fill, lots)
    res.exit_time, res.exit_price, res.exit_reason = ts, fill, reason
    res.gross_pnl, res.costs, res.net_pnl = gross, costs, gross - costs
    res.max_adverse_mtm = min(res.max_adverse_mtm, gross)


def _close_straddle(res: SessionResult, position: dict, spot: float,
                    ts: str, reason: str, minute: int, sqty: int) -> None:
    gross = sqty * position["model"].mtm_per_unit(
        position["strike"], position["entry_premium"], spot, minute)
    res.exit_time, res.exit_price, res.exit_reason = ts, spot, reason
    res.gross_pnl, res.costs = gross, OPTIONS_COST_FLAT
    res.net_pnl = gross - OPTIONS_COST_FLAT
    res.max_adverse_mtm = min(res.max_adverse_mtm, gross)


# ---------------------------------------------------------------------------
# Multi-day driver
# ---------------------------------------------------------------------------

def run_backtest(sessions: Dict[str, List[Bar]],
                 collect_log: bool = False) -> List[SessionResult]:
    """sessions: {'YYYY-MM-DD': [Bar, ...]} in chronological order."""
    results = []
    dates = sorted(sessions.keys())
    prev_bars: Optional[List[Bar]] = None
    early_ranges: List[float] = []

    for date in dates:
        bars = sessions[date]
        ctx = SessionContext()
        if prev_bars:
            ctx.prev_open = prev_bars[0].open
            ctx.prev_close = prev_bars[-1].close
            ctx.prev_high = max(b.high for b in prev_bars)
            ctx.prev_low = min(b.low for b in prev_bars)
        if early_ranges:
            sr = sorted(early_ranges[-10:])
            ctx.avg_early_range = sr[len(sr) // 2]

        sigma = _recent_daily_vol_pct(results, sessions, dates, date)
        results.append(run_session(date, bars, ctx, sigma_daily_pct=sigma,
                                   collect_log=collect_log))

        early = [b for b in bars if _minutes(b.ts) < ENTRY_CUTOFF_MIN]
        if early:
            early_ranges.append(max(b.high for b in early) - min(b.low for b in early))
        prev_bars = bars
    return results


def _recent_daily_vol_pct(results, sessions, dates, current_date,
                          lookback: int = 10) -> float:
    """Realized daily close-to-close volatility (%) over recent sessions."""
    closes = []
    for d in dates:
        if d >= current_date:
            break
        closes.append(sessions[d][-1].close)
    closes = closes[-(lookback + 1):]
    if len(closes) < 3:
        return 0.9
    rets = [(b - a) / a for a, b in zip(closes, closes[1:])]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    return max(math.sqrt(var) * 100, 0.2)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def report(results: List[SessionResult], capital: float = S.CAPITAL,
           data_label: str = "REAL DATA") -> str:
    lines = [
        f"# Backtest Report  ({data_label})",
        "",
        f"Capital Rs {capital:,.0f} | {S.MAX_CONTRACTS} lots x {S.NIFTY_LOT_SIZE} "
        f"= {S.TRADE_QTY} qty | stop Rs {S.MAX_DAILY_LOSS:,.0f} "
        f"(~{S.STOP_POINTS:.0f} pts) | square-off {S.SQUARE_OFF}",
        "",
        "| Date | Dir | Entry | Exit | Reason | Gross | Costs | Net | Worst MTM |",
        "|------|-----|-------|------|--------|-------|-------|-----|-----------|",
    ]
    total = wins = losses = 0
    net_sum = gross_sum = cost_sum = 0.0
    worst_day = 0.0
    equity = capital
    peak = capital
    max_dd = 0.0
    for r in results:
        if r.direction == "NO_TRADE":
            lines.append(f"| {r.date} | - | - | - | {r.exit_reason} | - | - | - | - |")
            continue
        total += 1
        wins += r.net_pnl > 0
        losses += r.net_pnl <= 0
        net_sum += r.net_pnl
        gross_sum += r.gross_pnl
        cost_sum += r.costs
        worst_day = min(worst_day, r.net_pnl)
        equity += r.net_pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
        ep = f"{r.entry_price:,.1f}" if r.entry_price else "-"
        xp = f"{r.exit_price:,.1f}" if r.exit_price else "-"
        lines.append(
            f"| {r.date} | {r.direction} | {r.entry_time} @ {ep} "
            f"| {r.exit_time} @ {xp} | {r.exit_reason} "
            f"| {r.gross_pnl:+,.0f} | {r.costs:,.0f} | {r.net_pnl:+,.0f} "
            f"| {r.max_adverse_mtm:,.0f} |")
    lines += [
        "",
        "## Summary",
        f"- Sessions traded: {total} | wins {wins} | losses {losses}"
        f" | win rate {wins / total * 100 if total else 0:.0f}%",
        f"- Gross P&L: Rs {gross_sum:+,.0f} | costs Rs {cost_sum:,.0f}"
        f" | **Net P&L: Rs {net_sum:+,.0f} ({net_sum / capital * 100:+.2f}%)**",
        f"- Worst single day: Rs {worst_day:+,.0f}"
        f" (hard cap Rs -{S.MAX_DAILY_LOSS:,.0f} + slippage/costs/gap risk)",
        f"- Max equity drawdown: Rs {max_dd:,.0f}",
        "",
        "Straddle days use the documented approximation in "
        "`backtest/engine.py:StraddleModel` - validate against real option "
        "chains before trusting NEUTRAL-day P&L.",
    ]
    return "\n".join(lines)
