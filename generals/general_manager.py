"""
General Manager - the roster of analyzing agents ("Generals").

DESIGN PRINCIPLE: a General that has no real data ABSTAINS. It never votes.
The earlier draft filled the roster with 93 placeholder agents that all voted
NEUTRAL@50 - that silently dragged every aggregate toward neutral and made
the Control Room look more certain than it was. Placeholders that vote are
worse than no placeholders.

Roster status:

ACTIVE - Price-Action Squad (9 Generals, implemented in bar_generals.py):
    gap, opening_range, failed_breakdown (trap detector), vwap, momentum,
    structure, volume_pressure, persistence, prev_day.
    Data: 5-minute OHLCV bars (Kite historical / yfinance / CSV).
    Used by BOTH the backtester and the live loop via control_room.decision.

PLANNED - Order-Flow Squad (needs live Kite WebSocket recording first):
    bid/ask imbalance, depth-withdrawal, large-order clustering, tick
    aggressor ratio. Cannot be backtested until depth ticks have been
    recorded to disk - NSE does not sell retail historical depth.

PLANNED - Options Squad (needs option-chain snapshots via Kite quote API):
    ATM IV shift, put/call OI change, straddle premium drift, max-pain drift.

PLANNED - Cross-Market Squad (needs top-20 constituent live quotes):
    top-20 breadth, weighted-leader divergence, BankNifty/Nifty spread.

PLANNED - Context Squad (EOD/pre-open only, never intraday):
    FII/DII net flows (PUBLISHED AFTER MARKET CLOSE - any "General" claiming
    to read FII flows at 09:30 is fiction), SGX/GIFT gap context, event
    calendar (budget/RBI/Fed days -> wider stops or no straddle).
"""

from utils.logger import setup_logger
from generals.bar_generals import run_squad, PRICE_ACTION_SQUAD, SessionContext

logger = setup_logger(__name__)


class GeneralManager:
    """Runs every ACTIVE General and returns their signals."""

    def __init__(self):
        self.active_squads = {"price_action": PRICE_ACTION_SQUAD}
        n = sum(len(s) for s in self.active_squads.values())
        logger.info(f"GeneralManager: {n} active Generals "
                    f"({', '.join(self.active_squads)}); "
                    "order-flow/options/cross-market squads pending data recording")

    def analyze(self, bars_today, ctx: SessionContext):
        """Return the list of Signal objects from all active Generals."""
        return run_squad(bars_today, ctx)

    def roster(self):
        return {squad: [g.__name__ for g in gens]
                for squad, gens in self.active_squads.items()}
