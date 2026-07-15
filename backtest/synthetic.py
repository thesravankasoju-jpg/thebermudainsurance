"""
Synthetic regime days for ENGINE VALIDATION ONLY.

These are deterministic, hand-shaped sessions used by the test suite to prove
the machinery (decision logic, stop enforcement, square-off, accounting)
behaves correctly in each market regime. Numbers produced from synthetic data
are NOT performance claims - never quote them as expected returns.

Regimes:
- crash_day():    June-8 style - steady institutional selling all day.
- trap_day():     June-10 style - gap down, stop-hunt below the opening
                  range, then reclaimed and grinds up (spring).
- chop_day():     range-bound noise around the open; correct answer NEUTRAL.
- rally_day():    mirror of crash_day.
- adverse_after_entry_day(): looks bullish till 10:00, then dumps hard -
                  exists to prove the stop loss caps the damage at 2%.
"""

import math
import random
from typing import List

from generals.bar_generals import Bar
from config import settings as S


def _times() -> List[str]:
    """09:15 .. 15:25 start times (75 five-minute bars, last closes 15:30)."""
    out, minute = [], 9 * 60 + 15
    while minute <= 15 * 60 + 25:
        out.append(f"{minute // 60:02d}:{minute % 60:02d}")
        minute += 5
    return out


def _mk_bars(path, volumes, seed=7) -> List[Bar]:
    rng = random.Random(seed)
    bars = []
    for ts, (o, c), v in zip(_times(), path, volumes):
        wick = abs(c - o) * 0.4 + 3 + rng.random() * 2
        bars.append(Bar(ts, round(o, 1), round(max(o, c) + wick, 1),
                        round(min(o, c) - wick, 1), round(c, 1), v))
    return bars


def _drift_path(open_px: float, per_bar: float, n: int, noise: float, seed: int):
    rng = random.Random(seed)
    path, px = [], open_px
    for i in range(n):
        o = px
        c = o + per_bar + rng.uniform(-noise, noise)
        path.append((o, c))
        px = c
    return path


def crash_day(open_px: float = 24280.0) -> List[Bar]:
    """Persistent selling: ~-6.5 pts/bar, volume swelling as it falls."""
    n = len(_times())
    path = _drift_path(open_px, -6.5, n, noise=3.0, seed=11)
    volumes = [1000 + i * 40 for i in range(n)]
    return _mk_bars(path, volumes, seed=11)


def rally_day(open_px: float = 24150.0) -> List[Bar]:
    n = len(_times())
    path = _drift_path(open_px, +6.0, n, noise=3.0, seed=13)
    volumes = [1000 + i * 35 for i in range(n)]
    return _mk_bars(path, volumes, seed=13)


def trap_day(prev_close: float = 24200.0) -> List[Bar]:
    """Gap down ~1%, breaks the opening-range low by 09:40, reclaims by
    09:55 on heavy volume, then grinds up for the rest of the day."""
    n = len(_times())
    open_px = prev_close * 0.99          # ~23,958
    path, volumes = [], []
    px = open_px
    for i in range(n):
        if i < 3:        # 09:15-09:30: drifting down (opening range forms)
            step, vol = -8, 1400
        elif i < 5:      # 09:30-09:40: stop-hunt below the OR low
            step, vol = -12, 1600
        elif i < 9:      # 09:40-10:00: aggressive reclaim, volume expands
            step, vol = +18, 2600
        elif i < 40:     # grind up
            step, vol = +3.5, 1500
        else:            # afternoon drift
            step, vol = +0.8, 1100
        o = px
        c = o + step + random.Random(100 + i).uniform(-1.5, 1.5)
        path.append((o, c))
        volumes.append(vol)
        px = c
    return _mk_bars(path, volumes, seed=17)


def chop_day(center: float = 24200.0) -> List[Bar]:
    """Directionless oscillation in a compressed range; correct answer is
    NEUTRAL (the range filter must refuse a directional call)."""
    n = len(_times())
    path, volumes = [], []
    for i in range(n):
        o = center + 14 * math.sin(i / 1.6)
        c = center + 14 * math.sin((i + 1) / 1.6)
        path.append((o, c))
        volumes.append(1000 + (i % 4) * 60)
    return _mk_bars(path, volumes, seed=19)


def flash_crash_after_entry_day(open_px: float = 24150.0) -> List[Bar]:
    """Bullish till 10:00, then a violent -55 pts/bar collapse. The dump is
    too fast for the 2-bar reversal exit - this day exists to prove the
    HARD STOP path fires and caps the loss."""
    n = len(_times())
    path, volumes = [], []
    px = open_px
    for i in range(n):
        if i < 9:
            step, vol = +9, 2000
        else:
            step, vol = -55, 4000
        o = px
        c = o + step + random.Random(300 + i).uniform(-1.0, 1.0)
        path.append((o, c))
        volumes.append(vol)
        px = c
    return _mk_bars(path, volumes, seed=29)


def adverse_after_entry_day(open_px: float = 24150.0) -> List[Bar]:
    """Bullish-looking first 45 min, then a hard dump - stop-loss test."""
    n = len(_times())
    path, volumes = [], []
    px = open_px
    for i in range(n):
        if i < 9:        # look strongly bullish till 10:00
            step, vol = +9, 2000
        else:            # then collapse
            step, vol = -11, 2600
        o = px
        c = o + step + random.Random(200 + i).uniform(-1.0, 1.0)
        path.append((o, c))
        volumes.append(vol)
        px = c
    return _mk_bars(path, volumes, seed=23)


def demo_sessions() -> dict:
    """A labelled week of archetypes for the demo report."""
    return {
        "SYN-1-crash": crash_day(),
        "SYN-2-trap-reversal": trap_day(),
        "SYN-3-chop": chop_day(),
        "SYN-4-rally": rally_day(),
        "SYN-5-adverse-reversal": adverse_after_entry_day(),
        "SYN-6-flash-crash-stop": flash_crash_after_entry_day(),
    }
