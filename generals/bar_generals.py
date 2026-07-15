"""
Price-action squad of Generals: deterministic signals computed from 5-minute
bars. Every General sees ONLY bars up to the decision time - no lookahead.

Each General returns a Signal:
    vote        -1.0 (bearish) .. +1.0 (bullish), 0 = no opinion
    confidence  0-100, how much the General trusts its own vote
    reason      one-line human-readable explanation

Squads that require data we do not yet record (order-book depth, options
greeks / OI, live cross-index correlation, news) are intentionally absent:
they can only be added honestly once a live Kite recorder has captured that
data. Do not fake them with placeholders that vote.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class Bar:
    ts: str        # "HH:MM" IST bar start time
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass(frozen=True)
class Signal:
    name: str
    vote: float          # -1..+1
    confidence: float    # 0..100
    reason: str


@dataclass
class SessionContext:
    """What is legitimately knowable before today's open."""
    prev_close: Optional[float] = None
    prev_open: Optional[float] = None
    prev_high: Optional[float] = None
    prev_low: Optional[float] = None
    avg_early_range: Optional[float] = None  # median 09:15-10:00 range, last ~10 days


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _session_vwap(bars: List[Bar]) -> float:
    """Volume-weighted average price; falls back to typical-price mean when
    the feed has no volume (index feeds often report 0 volume)."""
    num, den = 0.0, 0.0
    for b in bars:
        tp = (b.high + b.low + b.close) / 3.0
        w = b.volume if b.volume > 0 else 1.0
        num += tp * w
        den += w
    return num / den if den else bars[-1].close


def _bar_range_avg(bars: List[Bar]) -> float:
    rs = [b.high - b.low for b in bars]
    return sum(rs) / len(rs) if rs else 1.0


# ---------------------------------------------------------------------------
# Generals
# ---------------------------------------------------------------------------

def gap_general(bars: List[Bar], ctx: SessionContext) -> Signal:
    """Gap direction AND how the gap is being treated.

    A gap that HOLDS after several bars is institutional conviction in the
    gap direction. A gap that is being FILLED fast (>50% retraced) is being
    faded by stronger hands - vote with the fade, not the gap.
    """
    if ctx.prev_close is None or not bars:
        return Signal("gap", 0.0, 0.0, "no previous close available")
    open_px = bars[0].open
    gap = open_px - ctx.prev_close
    gap_pct = gap / ctx.prev_close * 100
    if abs(gap_pct) < 0.15:
        return Signal("gap", 0.0, 20.0, f"no meaningful gap ({gap_pct:+.2f}%)")

    last = bars[-1].close
    filled = (last - open_px) / (-gap) if gap != 0 else 0.0  # fraction of gap filled

    if filled > 0.5:
        # Gap aggressively faded -> vote against the gap direction
        vote = 1.0 if gap < 0 else -1.0
        conf = _clamp(40 + filled * 40, 0, 90)
        side = "bought" if gap < 0 else "sold"
        return Signal("gap", vote, conf,
                      f"gap {gap_pct:+.2f}% is {filled:.0%} filled - being {side} into")
    if (gap < 0 and last > open_px) or (gap > 0 and last < open_px):
        # Price is back across the session open: the attempt to EXTEND the
        # gap has failed. Early fade signal, weaker than a half-fill.
        # (This is what distinguishes "gap unfilled" from "gap holding".)
        vote = 0.5 if gap < 0 else -0.5
        return Signal("gap", vote, 45.0,
                      f"gap {gap_pct:+.2f}% extension failed - price back across open")
    if len(bars) >= 3:
        # Still trading beyond the open in the gap direction -> gap holding
        vote = 1.0 if gap > 0 else -1.0
        conf = _clamp(35 + abs(gap_pct) * 20, 0, 85)
        return Signal("gap", vote, conf,
                      f"gap {gap_pct:+.2f}% holding after {len(bars)} bars")
    return Signal("gap", 0.0, 30.0, f"gap {gap_pct:+.2f}% - too early to judge")


def opening_range_general(bars: List[Bar], ctx: SessionContext) -> Signal:
    """Breakout from the 09:15-09:30 opening range, confirmed on close."""
    if len(bars) < 4:
        return Signal("opening_range", 0.0, 0.0, "opening range still forming")
    orh = max(b.high for b in bars[:3])
    orl = min(b.low for b in bars[:3])
    last = bars[-1]
    width = max(orh - orl, 1e-9)
    if last.close > orh:
        depth = _clamp((last.close - orh) / width, 0, 2)
        return Signal("opening_range", 1.0, _clamp(45 + depth * 25, 0, 90),
                      f"close {last.close:.1f} above OR high {orh:.1f}")
    if last.close < orl:
        depth = _clamp((orl - last.close) / width, 0, 2)
        return Signal("opening_range", -1.0, _clamp(45 + depth * 25, 0, 90),
                      f"close {last.close:.1f} below OR low {orl:.1f}")
    return Signal("opening_range", 0.0, 30.0, "inside opening range")


def failed_breakdown_general(bars: List[Bar], ctx: SessionContext) -> Signal:
    """Trap detector (spring / upthrust).

    Spring: price breaks below the opening-range low, then RECLAIMS it on a
    close - stop-hunt absorbed by buyers (the June-10-type pattern). Bullish.
    Upthrust: mirror image above the range. Bearish.
    """
    if len(bars) < 5:
        return Signal("failed_breakdown", 0.0, 0.0, "too early")
    orh = max(b.high for b in bars[:3])
    orl = min(b.low for b in bars[:3])
    later = bars[3:]
    broke_low = any(b.low < orl for b in later)
    broke_high = any(b.high > orh for b in later)
    last = bars[-1]
    if broke_low and last.close > orl:
        depth = (orl - min(b.low for b in later)) / max(orl, 1e-9) * 100
        conf = _clamp(55 + depth * 40, 0, 92)
        return Signal("failed_breakdown", 1.0, conf,
                      f"spring: broke OR low {orl:.1f} then reclaimed ({last.close:.1f})")
    if broke_high and last.close < orh:
        depth = (max(b.high for b in later) - orh) / max(orh, 1e-9) * 100
        conf = _clamp(55 + depth * 40, 0, 92)
        return Signal("failed_breakdown", -1.0, conf,
                      f"upthrust: broke OR high {orh:.1f} then rejected ({last.close:.1f})")
    return Signal("failed_breakdown", 0.0, 25.0, "no trap pattern")


def vwap_general(bars: List[Bar], ctx: SessionContext) -> Signal:
    """Position of price relative to session VWAP, scaled by distance."""
    if len(bars) < 2:
        return Signal("vwap", 0.0, 0.0, "insufficient bars")
    vwap = _session_vwap(bars)
    last = bars[-1].close
    dist = (last - vwap) / max(_bar_range_avg(bars), 1e-9)
    vote = _clamp(dist / 2.0, -1, 1)
    conf = _clamp(abs(dist) * 30 + 20, 0, 80)
    side = "above" if dist > 0 else "below"
    return Signal("vwap", vote, conf, f"price {abs(dist):.1f} avg-ranges {side} VWAP {vwap:.1f}")


def momentum_general(bars: List[Bar], ctx: SessionContext) -> Signal:
    """Net drift over the last 6 bars, normalised by average bar range."""
    if len(bars) < 4:
        return Signal("momentum", 0.0, 0.0, "insufficient bars")
    window = bars[-6:]
    net = window[-1].close - window[0].open
    norm = net / max(_bar_range_avg(bars) * len(window) ** 0.5, 1e-9)
    vote = _clamp(norm, -1, 1)
    conf = _clamp(abs(norm) * 50 + 15, 0, 85)
    return Signal("momentum", vote, conf, f"net {net:+.1f} pts over last {len(window)} bars")


def structure_general(bars: List[Bar], ctx: SessionContext) -> Signal:
    """Higher-lows vs lower-highs across the session so far."""
    if len(bars) < 4:
        return Signal("structure", 0.0, 0.0, "insufficient bars")
    hl = sum(1 for a, b in zip(bars, bars[1:]) if b.low > a.low)
    lh = sum(1 for a, b in zip(bars, bars[1:]) if b.high < a.high)
    n = len(bars) - 1
    vote = _clamp((hl - lh) / n, -1, 1)
    conf = _clamp(abs(hl - lh) / n * 80 + 10, 0, 75)
    return Signal("structure", vote, conf, f"{hl} higher-lows vs {lh} lower-highs")


def volume_pressure_general(bars: List[Bar], ctx: SessionContext) -> Signal:
    """Volume on up-bars vs down-bars. Honest proxy for order flow when only
    bar data exists. Abstains (vote 0, conf 0) when the feed has no volume -
    the real order-flow General needs recorded Kite depth ticks."""
    vol_total = sum(b.volume for b in bars)
    if vol_total <= 0 or len(bars) < 3:
        return Signal("volume_pressure", 0.0, 0.0, "no volume in feed - abstain")
    up = sum(b.volume for b in bars if b.close >= b.open)
    down = vol_total - up
    ratio = (up - down) / vol_total
    vote = _clamp(ratio * 1.5, -1, 1)
    conf = _clamp(abs(ratio) * 90 + 10, 0, 85)
    return Signal("volume_pressure", vote, conf,
                  f"up-bar volume {up / vol_total:.0%} of total")


def persistence_general(bars: List[Bar], ctx: SessionContext) -> Signal:
    """Fraction of bars closing in the same direction - trend days persist,
    chop days alternate. Distinguishes June-8-style grinds from noise."""
    if len(bars) < 5:
        return Signal("persistence", 0.0, 0.0, "insufficient bars")
    ups = sum(1 for b in bars if b.close > b.open)
    downs = sum(1 for b in bars if b.close < b.open)
    n = max(ups + downs, 1)
    vote = _clamp((ups - downs) / n, -1, 1)
    conf = _clamp(abs(ups - downs) / n * 100, 0, 80)
    return Signal("persistence", vote, conf, f"{ups} up / {downs} down bars")


def prev_day_general(bars: List[Bar], ctx: SessionContext) -> Signal:
    """Previous day's trend and where it closed in its range."""
    if ctx.prev_close is None or ctx.prev_high is None or ctx.prev_low is None:
        return Signal("prev_day", 0.0, 0.0, "no previous day data")
    rng = max(ctx.prev_high - ctx.prev_low, 1e-9)
    loc = (ctx.prev_close - ctx.prev_low) / rng  # 0 = closed at low, 1 = at high
    vote = _clamp((loc - 0.5) * 2, -1, 1)
    return Signal("prev_day", vote, 40.0, f"prev day closed at {loc:.0%} of its range")


PRICE_ACTION_SQUAD = [
    gap_general,
    opening_range_general,
    failed_breakdown_general,
    vwap_general,
    momentum_general,
    structure_general,
    volume_pressure_general,
    persistence_general,
    prev_day_general,
]


def run_squad(bars: List[Bar], ctx: SessionContext) -> List[Signal]:
    """Run every General; a General that errors abstains rather than voting."""
    signals = []
    for gen in PRICE_ACTION_SQUAD:
        try:
            signals.append(gen(bars, ctx))
        except Exception as exc:  # abstain on failure, never guess
            signals.append(Signal(gen.__name__, 0.0, 0.0, f"error: {exc}"))
    return signals
