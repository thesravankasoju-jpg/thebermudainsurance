"""
Control Room - Aggregates signals from 100 Generals and makes trading decisions
"""

from utils.logger import setup_logger
from config.settings import BULLISH_THRESHOLD, BEARISH_THRESHOLD, GENERAL_WEIGHTS

logger = setup_logger(__name__)

class ControlRoom:
    """Aggregates signals from all generals into final trading decision"""

    def __init__(self):
        self.last_decision = None
        logger.info("ControlRoom initialized")

    def aggregate_signals(self, general_signals):
        """
        Aggregate signals from all generals using weighted voting

        Returns: {
            'direction': 'BULLISH' / 'BEARISH' / 'NEUTRAL',
            'confidence': 0-100,
            'bullish_count': number,
            'bearish_count': number,
            'neutral_count': number,
            'weighted_score': float,
            'reasoning': explanation
        }
        """

        bullish_count = 0
        bearish_count = 0
        neutral_count = 0
        weighted_score = 0.0
        total_weight = 0.0

        # Calculate weighted voting score
        for general_name, signal in general_signals.items():
            direction = signal.get('direction', 'NEUTRAL')
            confidence = signal.get('confidence', 50)

            # Get weight for this general
            weight = GENERAL_WEIGHTS.get(general_name, GENERAL_WEIGHTS['default'])

            # Convert direction to vote
            if direction == 'BULLISH':
                vote = 1.0
                bullish_count += 1
            elif direction == 'BEARISH':
                vote = -1.0
                bearish_count += 1
            else:
                vote = 0.0
                neutral_count += 1

            # Apply confidence and weight
            weighted_score += vote * (confidence / 100.0) * weight
            total_weight += weight

        # Normalize weighted score
        if total_weight > 0:
            normalized_score = weighted_score / total_weight
        else:
            normalized_score = 0.0

        # Determine direction based on threshold
        if normalized_score > BULLISH_THRESHOLD:
            direction = 'BULLISH'
        elif normalized_score < BEARISH_THRESHOLD:
            direction = 'BEARISH'
        else:
            direction = 'NEUTRAL'

        # Calculate confidence
        total_generals = len(general_signals)
        dominant_opinion = max(bullish_count, bearish_count)
        confidence = int((dominant_opinion / total_generals) * 100)

        decision = {
            'direction': direction,
            'confidence': confidence,
            'bullish_count': bullish_count,
            'bearish_count': bearish_count,
            'neutral_count': neutral_count,
            'weighted_score': normalized_score,
            'total_generals': total_generals,
            'reasoning': self._generate_reasoning(
                direction, confidence, bullish_count, bearish_count, neutral_count, total_generals
            )
        }

        self.last_decision = decision
        self._log_decision(decision)

        return decision

    def _generate_reasoning(self, direction, confidence, bullish, bearish, neutral, total):
        """Generate human-readable reasoning for decision"""
        reasoning = f"{direction} signal ({confidence}% confidence) based on: "
        reasoning += f"{bullish} bullish, {bearish} bearish, {neutral} neutral out of {total} generals"
        return reasoning

    def _log_decision(self, decision):
        """Log the control room decision"""
        logger.info(f"Control Room Decision: {decision['direction']} "
                   f"({decision['confidence']}% confidence) | "
                   f"Bulls:{decision['bullish_count']} "
                   f"Bears:{decision['bearish_count']} "
                   f"Neutral:{decision['neutral_count']}")

    def get_last_decision(self):
        """Get the last control room decision"""
        return self.last_decision
