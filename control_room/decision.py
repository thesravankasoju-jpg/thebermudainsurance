"""
Control Room decision logic - pure functions, shared verbatim by the
backtester and the live loop so the backtest exercises the exact code that
would trade.

decide_entry()  - called on each bar close inside the 09:30-10:00 window
monitor()       - called on each bar close while a position is open

No I/O, no clocks, no globals: everything the function knows arrives in its
arguments, which is what makes lookahead impossible to introduce silently.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from generals.bar_generals import Bar, Signal, SessionContext, run_squad
from config.settings import (
    LONG_SCORE_THRESHOLD,
    SHORT_SCORE_THRESHOLD,
    MIN_CONFIDENCE_TO_TRADE,
    REVERSAL_EXIT_BARS,
    RANGE_FILTER_RATIO,
    GENERAL_WEIGHTS,
)

LONG, SHORT, NEUTRAL = "LONG", "SHORT", "NEUTRAL"


@dataclass
class Decision:
    direction: str               # LONG / SHORT / NEUTRAL
    score: float                 # -1..+1 weighted aggregate
    confidence: float            # 0..100
    signals: List[Signal] = field(default_factory=list)

    def summary(self) -> str:
        parts = [f"{s.name}:{s.vote:+.2f}@{s.confidence:.0f}" for s in self.signals]
        return (f"{self.direction} score={self.score:+.3f} "
                f"conf={self.confidence:.0f} [{', '.join(parts)}]")


def aggregate(signals: List[Signal]) -> Decision:
    """Weighted vote across all Generals. Abstaining Generals (conf 0)
    contribute nothing - they do not drag the score toward neutral."""
    num, den = 0.0, 0.0
    for s in signals:
        if s.confidence <= 0:
            continue
        w = GENERAL_WEIGHTS.get(s.name, GENERAL_WEIGHTS["default"])
        num += s.vote * (s.confidence / 100.0) * w
        den += w
    score = num / den if den else 0.0

    # Confidence: |score| plus agreement among non-abstaining Generals.
    voters = [s for s in signals if s.confidence > 0 and abs(s.vote) > 0.05]
    if voters:
        same_sign = sum(1 for s in voters if s.vote * score > 0)
        agreement = same_sign / len(voters)
    else:
        agreement = 0.0
    confidence = min(100.0, abs(score) * 120 + agreement * 40)

    if score >= LONG_SCORE_THRESHOLD and confidence >= MIN_CONFIDENCE_TO_TRADE:
        direction = LONG
    elif score <= SHORT_SCORE_THRESHOLD and confidence >= MIN_CONFIDENCE_TO_TRADE:
        direction = SHORT
    else:
        direction = NEUTRAL
    return Decision(direction, score, confidence, signals)


def decide_entry(bars_today: List[Bar], ctx: SessionContext) -> Decision:
    """Evaluate the session so far (bars from 09:15 up to 'now').

    Range-compression filter: when today's range is small relative to the
    recent median early range, there is no institutional intent to read -
    force NEUTRAL rather than trade oscillation noise.
    """
    d = aggregate(run_squad(bars_today, ctx))
    if (d.direction != NEUTRAL and ctx.avg_early_range
            and len(bars_today) >= 3):
        session_range = (max(b.high for b in bars_today)
                         - min(b.low for b in bars_today))
        if session_range < RANGE_FILTER_RATIO * ctx.avg_early_range:
            return Decision(NEUTRAL, d.score,
                            min(d.confidence, MIN_CONFIDENCE_TO_TRADE - 1),
                            d.signals)
    return d


def monitor(bars_today: List[Bar], ctx: SessionContext,
            position_direction: str,
            opposite_streak: int) -> tuple:
    """Called each bar while holding a position.

    Returns (action, new_opposite_streak) where action is HOLD or EXIT_REVERSAL.
    Exits only after REVERSAL_EXIT_BARS consecutive bars of a confident
    opposite signal - a single opposite bar is treated as noise.
    """
    d = decide_entry(bars_today, ctx)
    opposite = (
        (position_direction == LONG and d.direction == SHORT) or
        (position_direction == SHORT and d.direction == LONG)
    )
    streak = opposite_streak + 1 if opposite else 0
    if streak >= REVERSAL_EXIT_BARS:
        return "EXIT_REVERSAL", streak
    return "HOLD", streak
