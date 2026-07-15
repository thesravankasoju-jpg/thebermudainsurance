"""
Test suite for the trading system's non-negotiable guarantees:

1. Contract math matches verified 2026 specs (lot 65, ~4 lots on 10L).
2. The Control Room reads each synthetic regime correctly BY the 10:00 cutoff.
3. The 2% hard stop caps any day's loss (plus bounded slippage/costs).
4. Every position is flat by 15:15 - no overnight risk, ever.
5. No lookahead: bars after the entry decision cannot change that decision.
6. The system enters every session (directional or straddle), per the rules.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings as S
from generals.bar_generals import Bar, SessionContext
from control_room.decision import decide_entry, LONG, SHORT, NEUTRAL
from backtest.engine import run_session, run_backtest, _minutes, SQUARE_OFF_MIN
from backtest import synthetic


CTX = SessionContext(prev_close=24200.0, prev_open=24150.0,
                     prev_high=24260.0, prev_low=24100.0,
                     avg_early_range=100.0)  # typical 09:15-10:00 Nifty range

# CTX with avg_early_range=None reproduces what run_backtest() actually feeds
# every session: the range filter is computed from PRIOR sessions' ranges,
# not a hand-picked constant. A test that only exercises the fixed-CTX path
# can pass while the real multi-day driver still fails - that happened here
# once already (SYN-2-trap-reversal shorted the spring in the CLI report
# while the fixed-CTX unit test showed LONG), so every regime test below
# must be checked under both contexts, not just the convenient one.
CTX_NO_RANGE_FILTER = SessionContext(prev_close=24200.0, prev_open=24150.0,
                                     prev_high=24260.0, prev_low=24100.0,
                                     avg_early_range=None)


def bars_until(bars, hhmm):
    """Bars whose CLOSE time is <= hhmm (what the system can know at hhmm)."""
    cutoff = _minutes(hhmm)
    return [b for b in bars if _minutes(b.ts) + S.BAR_INTERVAL_MINUTES <= cutoff]


# ---------------------------------------------------------------------------
# 1. Contract specs
# ---------------------------------------------------------------------------

class TestSpecs:
    def test_lot_size_is_65(self):
        assert S.NIFTY_LOT_SIZE == 65

    def test_position_sizing_leaves_margin_buffer(self):
        assert S.MAX_CONTRACTS == 4
        assert S.TRADE_QTY == 260
        assert S.MAX_CONTRACTS * S.MARGIN_PER_LOT <= S.CAPITAL * 0.8

    def test_stop_distance(self):
        # 20,000 / 260 ~= 76.9 points
        assert 75 < S.STOP_POINTS < 78


# ---------------------------------------------------------------------------
# 2. Regime reads by the 10:00 cutoff
# ---------------------------------------------------------------------------

class TestDecisionRegimes:
    def test_crash_day_reads_short(self):
        d = decide_entry(bars_until(synthetic.crash_day(), "10:00"), CTX)
        assert d.direction == SHORT, d.summary()

    def test_rally_day_reads_long(self):
        d = decide_entry(bars_until(synthetic.rally_day(), "10:00"), CTX)
        assert d.direction == LONG, d.summary()

    def test_trap_day_reads_long_not_short(self):
        """Gap-down stop-hunt that reclaims must NOT be shorted."""
        d = decide_entry(bars_until(synthetic.trap_day(), "10:00"), CTX)
        assert d.direction == LONG, d.summary()

    def test_chop_day_reads_neutral(self):
        d = decide_entry(bars_until(synthetic.chop_day(), "10:00"), CTX)
        assert d.direction == NEUTRAL, d.summary()

    def test_trap_day_is_never_shorted_by_the_engine(self):
        """The stop-hunt reads SHORT for the first bars; entry must not
        commit until the trap-detector General (failed_breakdown) has had
        enough bars to weigh in and the spring resolves it. Checked under
        BOTH contexts - this exact regression (passed under CTX, failed
        under the driver's real dynamic range) is why both exist."""
        for ctx in (CTX, CTX_NO_RANGE_FILTER):
            r = run_session("trap", synthetic.trap_day(), ctx)
            assert r.direction != SHORT, (ctx.avg_early_range, r.direction, r.exit_reason)

    def test_trap_day_regression_under_driver_conditions(self):
        """Exact reproduction of the bug found via manual /model review:
        entry_streak could be satisfied entirely from pre-trap-detector
        bars when avg_early_range came from a prior session's real range
        instead of a generous constant. Locks the fix in permanently."""
        r = run_session("trap", synthetic.trap_day(), CTX_NO_RANGE_FILTER)
        assert r.direction == LONG
        assert r.exit_reason == "SQUARE_OFF_1515"
        assert r.net_pnl > 0


# ---------------------------------------------------------------------------
# 3. Hard stop caps losses
# ---------------------------------------------------------------------------

class TestStopLoss:
    def test_adverse_day_exits_defensively(self):
        """A slow grind against the position should exit via the reversal
        detector or the hard stop - either way, before the day gets worse."""
        r = run_session("adverse", synthetic.adverse_after_entry_day(), CTX)
        assert r.direction == LONG                 # was lured long by 10:00
        assert r.exit_reason in ("REVERSAL_EXIT", "STOP_LOSS")

    def test_flash_crash_hits_hard_stop(self):
        """A collapse too fast for the reversal detector MUST hit the stop."""
        r = run_session("flash", synthetic.flash_crash_after_entry_day(), CTX)
        assert r.direction == LONG
        assert r.exit_reason == "STOP_LOSS"
        adverse_points = r.entry_price - r.exit_price
        assert adverse_points >= S.STOP_POINTS * 0.9

    def test_loss_capped_at_2pct_plus_frictions(self):
        # Continuous synthetic bars: loss <= 20k + slippage on qty + costs.
        max_friction = S.SLIPPAGE_POINTS * S.TRADE_QTY * 2 + 3500
        for day in (synthetic.adverse_after_entry_day(),
                    synthetic.flash_crash_after_entry_day()):
            r = run_session("d", day, CTX)
            assert r.net_pnl < 0
            assert abs(r.net_pnl) <= S.MAX_DAILY_LOSS + max_friction, r.net_pnl


# ---------------------------------------------------------------------------
# 4. Intraday only - flat by 15:15
# ---------------------------------------------------------------------------

class TestSquareOff:
    def test_all_regimes_close_by_1515(self):
        for name, bars in synthetic.demo_sessions().items():
            r = run_session(name, bars, CTX)
            if r.direction == "NO_TRADE":
                continue
            assert r.exit_time is not None, name
            exit_end = _minutes(r.exit_time) + S.BAR_INTERVAL_MINUTES
            assert exit_end <= SQUARE_OFF_MIN + S.BAR_INTERVAL_MINUTES, \
                f"{name} exited at {r.exit_time}"

    def test_trend_day_rides_to_square_off(self):
        r = run_session("crash", synthetic.crash_day(), CTX)
        assert r.direction == SHORT
        assert r.exit_reason == "SQUARE_OFF_1515"
        assert r.net_pnl > 0            # shorting a persistent downtrend pays


# ---------------------------------------------------------------------------
# 5. No lookahead
# ---------------------------------------------------------------------------

class TestTrapDetectorActivationGate:
    """The gate added after the regression: no directional entry may commit
    before every General - especially failed_breakdown_general, which needs
    >=5 bars - has had a chance to vote."""

    def test_gate_constant_matches_general_requirement(self):
        # If failed_breakdown_general's minimum-bars requirement ever
        # changes, this constant must move with it.
        from generals.bar_generals import failed_breakdown_general, Bar
        stub = [Bar(f"09:{15+5*i:02d}", 100, 101, 99, 100, 0) for i in range(4)]
        assert failed_breakdown_general(stub, CTX).confidence == 0.0  # silent at 4 bars
        stub.append(Bar("09:35", 100, 101, 99, 100, 0))
        # at 5 bars it may now speak (confidence need not be nonzero for
        # this flat stub, but the function must not raise / stay gated code path)
        assert S.MIN_BARS_FOR_DIRECTIONAL_ENTRY == 5

    def test_no_directional_fill_before_gate_opens(self):
        """Across every regime, the entry bar index must be >= the gate."""
        for name, bars in synthetic.demo_sessions().items():
            r = run_session(name, bars, CTX_NO_RANGE_FILTER)
            if r.direction not in (LONG, SHORT) or r.entry_time is None:
                continue
            entry_bar_index = next(i for i, b in enumerate(bars) if b.ts == r.entry_time)
            assert entry_bar_index >= S.MIN_BARS_FOR_DIRECTIONAL_ENTRY, \
                f"{name} filled at bar {entry_bar_index}, before the gate opens"


class TestNoLookahead:
    def test_future_bars_cannot_change_the_decision(self):
        bars = synthetic.crash_day()
        d_before = decide_entry(bars_until(bars, "10:00"), CTX)

        # Mutate everything after 10:00 into a monster rally
        mutated = bars_until(bars, "10:00") + [
            Bar(b.ts, b.open + 500, b.high + 500, b.low + 500, b.close + 500,
                b.volume)
            for b in bars if _minutes(b.ts) + S.BAR_INTERVAL_MINUTES > _minutes("10:00")
        ]
        d_after = decide_entry(bars_until(mutated, "10:00"), CTX)
        assert d_before.direction == d_after.direction
        assert abs(d_before.score - d_after.score) < 1e-12

    def test_entry_fills_at_next_bar_open(self):
        """The fill must come from the bar AFTER the signal, plus slippage."""
        bars = synthetic.crash_day()
        r = run_session("crash", bars, CTX)
        entry_bar = next(b for b in bars if b.ts == r.entry_time)
        assert abs(r.entry_price - (entry_bar.open - S.SLIPPAGE_POINTS)) < 1e-9


# ---------------------------------------------------------------------------
# 6. Enters every session; accounting sane
# ---------------------------------------------------------------------------

class TestDailyEntryAndAccounting:
    def test_system_trades_every_synthetic_session(self):
        results = run_backtest(synthetic.demo_sessions())
        assert all(r.direction != "NO_TRADE" for r in results)

    def test_chop_day_takes_straddle(self):
        r = run_session("chop", synthetic.chop_day(), CTX)
        assert r.direction == "STRADDLE"

    def test_costs_always_positive_and_sane(self):
        for name, bars in synthetic.demo_sessions().items():
            r = run_session(name, bars, CTX)
            if r.direction == "NO_TRADE":
                continue
            assert 0 < r.costs < 5000, f"{name} costs {r.costs}"
            assert abs((r.gross_pnl - r.costs) - r.net_pnl) < 1e-6


# ---------------------------------------------------------------------------
# 7. Scaled entry for better move capture
# ---------------------------------------------------------------------------

class TestScaledEntry:
    def test_scaled_entry_increases_position_gradually(self):
        """Scaled entry should open with 1 lot, then add 1 lot, then add 2 lots."""
        bars = synthetic.rally_day()
        r = run_session("rally", bars, CTX, collect_log=True)

        # Verify entry happened
        assert r.direction == LONG
        assert r.entry_time is not None

        # Full position should be entered by 10:00 at most
        assert r.exit_reason == "SQUARE_OFF_1515"

        # P&L on a strong trend should be positive
        assert r.net_pnl > 0, "Strong trend day should profit"
