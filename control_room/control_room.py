"""
Control Room - The HEART of the system
Ultra-fast institutional move detection with fake move filtering
<70ms response time required
"""

import time
from datetime import datetime
from collections import deque
from utils.logger import setup_logger
from config.settings import (LONG_SCORE_THRESHOLD, SHORT_SCORE_THRESHOLD,
                             GENERAL_WEIGHTS)

logger = setup_logger(__name__)

class ControlRoom:
    """
    Ultra-fast institutional move detector & fake move filter

    Entry Window: 9:30 AM - 10:00 AM (filter opening noise)
    Trading Window: 10:00 AM - 3:15 PM (manage positions)
    Auto-Close: 3:15 PM (exit ALL positions)

    Response Time: <70 milliseconds
    """

    def __init__(self):
        self.last_decision = None
        self.decision_history = deque(maxlen=100)  # Keep last 100 decisions
        self.price_history = deque(maxlen=50)  # Keep last 50 prices
        self.volume_history = deque(maxlen=50)

        # Opening session filter
        self.opening_noise_buffer = deque(maxlen=20)  # First 20 ticks (9:30-9:35)
        self.is_opening_phase = True
        self.opening_phase_end = None

        # Institutional move detection
        self.bid_ask_history = deque(maxlen=100)  # Track order flow
        self.large_order_detected = False
        self.smart_money_direction = None

        # Fake move detection
        self.volatility_spike_detector = VolatilityDetector()
        self.reversal_detector = ReversalDetector()

        logger.info("ControlRoom initialized (Ultra-Fast Mode, <70ms response)")

    def process_tick(self, tick_data):
        """
        Process single tick with ultra-low latency

        tick_data = {
            'price': current_price,
            'bid': bid_price,
            'ask': ask_price,
            'bid_volume': bid_qty,
            'ask_volume': ask_qty,
            'volume': trade_volume,
            'timestamp': timestamp
        }

        Returns: {
            'action': 'BUY' / 'SELL' / 'HOLD' / 'CLOSE_ALL',
            'confidence': 0-100,
            'reason': explanation,
            'response_time_ms': milliseconds
        }
        """
        start_time = time.time()

        # Step 1: Check if market is closing (3:15 PM)
        current_time = datetime.now()
        if current_time.hour == 15 and current_time.minute >= 15:
            return {
                'action': 'CLOSE_ALL',
                'confidence': 100,
                'reason': 'Auto-close at 3:15 PM',
                'response_time_ms': (time.time() - start_time) * 1000
            }

        # Step 2: Detect institutional moves
        institutional_signal = self._detect_institutional_move(tick_data)

        # Step 3: Filter fake moves
        is_fake_move = self._is_fake_move(tick_data, institutional_signal)

        # Step 4: Check opening session (9:30-10:00 AM)
        if self.is_opening_phase:
            action = self._handle_opening_phase(tick_data, institutional_signal, is_fake_move)
        else:
            # Regular trading phase (10:00 AM - 3:15 PM)
            action = self._handle_trading_phase(tick_data, institutional_signal, is_fake_move)

        # Record decision
        action['response_time_ms'] = (time.time() - start_time) * 1000
        if action['response_time_ms'] > 70:
            logger.warning(f"SLOW RESPONSE: {action['response_time_ms']:.2f}ms (>70ms limit)")

        self.decision_history.append(action)
        self.last_decision = action

        return action

    def _detect_institutional_move(self, tick_data):
        """
        Detect institutional money movement BEFORE it appears on retail charts

        Signals:
        1. Order book imbalance (bid/ask ratio)
        2. Large volume spike
        3. Volatility increase
        4. Order flow direction
        """

        bid_vol = tick_data.get('bid_volume', 0)
        ask_vol = tick_data.get('ask_volume', 0)
        volume = tick_data.get('volume', 0)

        # Calculate bid-ask imbalance
        total_vol = bid_vol + ask_vol
        if total_vol > 0:
            imbalance = (bid_vol - ask_vol) / total_vol  # -1 to +1
        else:
            imbalance = 0

        # Check for unusual volume (institutional buying/selling)
        avg_volume = sum(self.volume_history) / len(self.volume_history) if self.volume_history else 1
        volume_spike = volume / (avg_volume + 1)

        # Determine direction
        if imbalance > 0.3 and volume_spike > 1.5:
            direction = 'BULLISH'
            confidence = min(int(imbalance * 100 + volume_spike * 20), 95)
        elif imbalance < -0.3 and volume_spike > 1.5:
            direction = 'BEARISH'
            confidence = min(int(abs(imbalance) * 100 + volume_spike * 20), 95)
        else:
            direction = 'NEUTRAL'
            confidence = 30

        # Record bid-ask data
        self.bid_ask_history.append({
            'timestamp': tick_data['timestamp'],
            'imbalance': imbalance,
            'direction': direction,
            'confidence': confidence
        })

        return {
            'direction': direction,
            'confidence': confidence,
            'imbalance': imbalance,
            'volume_spike': volume_spike,
            'is_institutional': (imbalance > 0.3 or imbalance < -0.3) and volume_spike > 1.5
        }

    def _is_fake_move(self, tick_data, institutional_signal):
        """
        Identify FAKE moves (noise, false breakouts, stop loss hunts)

        Fake move characteristics:
        1. No institutional support (low bid-ask imbalance)
        2. Quick reversal
        3. Low volume spike
        4. Doesn't sustain
        """

        price = tick_data['price']
        self.price_history.append(price)
        self.volume_history.append(tick_data.get('volume', 0))

        # Check 1: No institutional support
        if not institutional_signal['is_institutional']:
            return True  # Likely fake

        # Check 2: Quick reversal detection
        if len(self.price_history) >= 5:
            recent_prices = list(self.price_history)[-5:]
            if self.reversal_detector.detect_quick_reversal(recent_prices):
                return True  # Likely fake

        # Check 3: Volatility spike without continuation
        if self.volatility_spike_detector.is_isolated_spike(self.price_history):
            return True  # Likely fake

        return False  # Real move

    def _handle_opening_phase(self, tick_data, institutional_signal, is_fake_move):
        """
        Handle 9:30 AM - 10:00 AM opening phase
        Filter out opening noise, identify real direction
        """

        current_time = datetime.now()

        # Check if we're past 10:00 AM
        if current_time.hour == 10 and current_time.minute >= 0:
            self.is_opening_phase = False
            # Make opening phase decision
            return self._make_opening_decision()

        # Buffer opening ticks
        self.opening_noise_buffer.append({
            'timestamp': tick_data['timestamp'],
            'signal': institutional_signal,
            'is_fake': is_fake_move
        })

        # Don't trade during opening noise (9:30-9:45)
        if current_time.hour == 9 and current_time.minute < 45:
            return {
                'action': 'HOLD',
                'confidence': 0,
                'reason': 'Opening noise period (9:30-9:45), not trading yet'
            }

        # Prepare to make opening decision (9:45-10:00)
        return {
            'action': 'HOLD',
            'confidence': 0,
            'reason': 'Analyzing opening (9:45-10:00), preparing to enter'
        }

    def _make_opening_decision(self):
        """
        Make final opening decision at 10:00 AM
        Aggregate opening phase signals and filter noise
        """

        if not self.opening_noise_buffer:
            return {
                'action': 'HOLD',
                'confidence': 0,
                'reason': 'Insufficient opening data'
            }

        # Analyze opening buffer
        real_signals = [s for s in self.opening_noise_buffer if not s['is_fake']]

        if not real_signals:
            return {
                'action': 'HOLD',
                'confidence': 0,
                'reason': 'All opening moves were fake, no clear direction'
            }

        # Count direction consensus
        bullish_count = sum(1 for s in real_signals if s['signal']['direction'] == 'BULLISH')
        bearish_count = sum(1 for s in real_signals if s['signal']['direction'] == 'BEARISH')

        total_real = len(real_signals)
        if bullish_count > total_real * 0.6:
            return {
                'action': 'BUY',
                'confidence': int((bullish_count / total_real) * 100),
                'reason': f'Opening consensus: {bullish_count}/{total_real} signals bullish (institutional buying detected)'
            }
        elif bearish_count > total_real * 0.6:
            return {
                'action': 'SELL',
                'confidence': int((bearish_count / total_real) * 100),
                'reason': f'Opening consensus: {bearish_count}/{total_real} signals bearish (institutional selling detected)'
            }
        else:
            return {
                'action': 'HOLD',
                'confidence': 50,
                'reason': 'Opening consensus unclear, waiting for stronger signal'
            }

    def _handle_trading_phase(self, tick_data, institutional_signal, is_fake_move):
        """
        Handle 10:00 AM - 3:15 PM trading phase
        Manage position, detect reversals, follow institutional money
        """

        # Filter out fake moves
        if is_fake_move:
            return {
                'action': 'HOLD',
                'confidence': 0,
                'reason': 'Fake move detected (no institutional support), ignoring'
            }

        # Only act on strong institutional signals
        if institutional_signal['confidence'] < 70:
            return {
                'action': 'HOLD',
                'confidence': institutional_signal['confidence'],
                'reason': f'Signal confidence {institutional_signal["confidence"]}% < 70% threshold'
            }

        # Handle sudden news events (Nirmala Sitharaman moves)
        if institutional_signal['is_institutional'] and institutional_signal['volume_spike'] > 3.0:
            logger.critical(f"SUDDEN INSTITUTIONAL MOVE DETECTED: {institutional_signal['direction']} "
                           f"(Confidence: {institutional_signal['confidence']}%)")

            return {
                'action': 'BUY' if institutional_signal['direction'] == 'BULLISH' else 'SELL',
                'confidence': institutional_signal['confidence'],
                'reason': (f"Sudden institutional move ({institutional_signal['direction']}) - "
                           f"likely news event, confidence: {institutional_signal['confidence']}%")
            }

        return {
            'action': 'HOLD',
            'confidence': institutional_signal['confidence'],
            'reason': f'Monitoring institutional flow ({institutional_signal["direction"]})'
        }

    def _generate_reasoning(self, direction, confidence, bullish, bearish, neutral, total):
        """Generate human-readable reasoning for decision"""
        reasoning = f"{direction} signal ({confidence}% confidence) based on: "
        reasoning += f"{bullish} bullish, {bearish} bearish, {neutral} neutral out of {total} generals"
        return reasoning

    def _log_decision(self, decision):
        """Log the control room decision"""
        logger.info(f"Control Room Decision: {decision['direction']} "
                   f"({decision['confidence']}% confidence) | "
                   f"Response: {decision.get('response_time_ms', 0):.2f}ms")

    def get_last_decision(self):
        """Get the last control room decision"""
        return self.last_decision


class VolatilityDetector:
    """Detects isolated volatility spikes (fake moves)"""

    def is_isolated_spike(self, price_history):
        """Check if volatility spike is isolated (not sustained)"""
        if len(price_history) < 10:
            return False

        recent = list(price_history)[-5:]
        older = list(price_history)[-10:-5]

        # Calculate volatility
        recent_vol = self._calculate_volatility(recent)
        older_vol = self._calculate_volatility(older)

        # If recent volatility is much higher but not sustained, it's fake
        if recent_vol > older_vol * 2:
            return True
        return False

    def _calculate_volatility(self, prices):
        """Calculate simple volatility (std dev of returns)"""
        if len(prices) < 2:
            return 0
        returns = [(prices[i+1] - prices[i]) / prices[i] for i in range(len(prices)-1)]
        variance = sum(r**2 for r in returns) / len(returns)
        return variance ** 0.5


class ReversalDetector:
    """Detects quick reversals (sign of fake moves)"""

    def detect_quick_reversal(self, recent_prices):
        """
        Detect if price quickly reverses after a move
        This indicates a fake move or stop-loss hunt
        """
        if len(recent_prices) < 3:
            return False

        # Check if direction changes within last 3 ticks
        p0, p1, p2 = recent_prices[-3], recent_prices[-2], recent_prices[-1]

        # Move up then down, or down then up
        up_then_down = (p1 > p0) and (p2 < p1)
        down_then_up = (p1 < p0) and (p2 > p1)

        if (up_then_down or down_then_up) and abs(p2 - p0) / p0 < 0.01:  # <1% reversal
            return True

        return False
