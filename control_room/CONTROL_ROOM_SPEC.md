# Control Room Specification - The Heart of the System

> **STATUS: DESIGN DOCUMENT - UNVALIDATED.** Every accuracy percentage,
> P&L figure, and worked example below is a design target or illustrative
> narrative, NOT measured performance. Position sizes in older examples
> also predate the verified specs (lot 65, ~4 lots on Rs 10L capital -
> see `docs/DATA_REALITY.md`). The implemented, tested decision logic
> lives in `control_room/decision.py`; the backtest engine in
> `backtest/engine.py` is the only source of legitimate numbers.

## Executive Summary

The Control Room is the **ultra-fast, institutional move detection engine** that:
- Identifies real institutional moves BEFORE they appear on retail charts
- Filters out 90%+ of fake moves (noise, stop-loss hunts, false breakouts)
- Responds in **<70 milliseconds**
- Operates with **three distinct phases**: Opening Filter → Trading → Auto-Close

---

## Phase Architecture

### Phase 1: Opening Noise Filter (9:30 AM - 10:00 AM)
**Purpose**: Identify the REAL market direction by filtering opening noise

**What Happens**:
- Market opens at 9:30 AM with chaos (gap ups/downs, panic selling/buying)
- Retail traders enter random positions without conviction
- Institutional money hasn't fully shown its hand yet

**Our Strategy**:
```
9:30-9:45 AM: Buffer all ticks, DON'T TRADE
              (Pure noise, 80% of moves reverse by 9:45 AM)

9:45-10:00 AM: Analyze buffered data
               Filter out fake moves using:
               - Bid-ask imbalance consistency
               - Volume confirmation
               - Price reversal detection

10:00 AM: MAKE ENTRY DECISION
          Based on opening consensus
          If real institutional direction = High confidence to enter
          Else = Wait or use straddle
```

**Fake Move Signals**:
- No institutional bid-ask imbalance
- Quick reversal within 1-2 minutes
- Volume spike not sustained
- Price spike < 1% without continuation

---

### Phase 2: Active Trading (10:00 AM - 3:15 PM)
**Purpose**: Follow institutional money, maximize gains, avoid noise

**Real-Time Tick Processing (<70ms)**:

```
1. CHECK TIME (auto-close at 3:15 PM)
   ↓
2. DETECT INSTITUTIONAL MOVE
   - Bid-ask imbalance analysis
   - Volume spike detection
   - Order flow direction
   ↓
3. FILTER FAKE MOVES
   - Quick reversal check
   - Isolated volatility detection
   - Support/resistance analysis
   ↓
4. EXECUTE DECISION
   - Follow institutional flow
   - Ignore noise
   - Manage position
```

**Institutional Move Detection**:

```python
# Bid-Ask Imbalance Calculation
imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume)
# Range: -1.0 (all selling) to +1.0 (all buying)

# Volume Spike Detection
volume_spike_ratio = current_volume / average_volume
# >1.5x = significant (institutional activity)
# >3.0x = extreme (sudden news event like Nirmala Sitharaman)

# DECISION RULE:
IF imbalance > 0.3 AND volume_spike > 1.5:
    SIGNAL = BULLISH (institutional buying)
ELIF imbalance < -0.3 AND volume_spike > 1.5:
    SIGNAL = BEARISH (institutional selling)
```

**Fake Move Detection**:

```python
# Check 1: No Institutional Support
IF institutional_confidence < 70%:
    IS_FAKE = True

# Check 2: Quick Reversal
IF price moves up but reverses within 3 ticks AND reversal_size < 1%:
    IS_FAKE = True

# Check 3: Isolated Volatility
IF recent_volatility >> older_volatility BUT not sustained:
    IS_FAKE = True

# Check 4: No Volume Continuation
IF volume spike is 1-tick wonder:
    IS_FAKE = True
```

---

### Phase 3: Auto-Close (3:15 PM)
**Purpose**: All positions must close by 3:15 PM (INTRADAY ONLY)

**Implementation**:
```
Every tick after 3:15 PM:
    IF active_positions exist:
        CLOSE ALL POSITIONS at current_market_price
        LOG: "MARKET CLOSE - Auto-closed X positions"
        STOP ALL TRADING
```

---

## The 100 Generals Integration

The Control Room doesn't replace the 100 Generals - it **orchestrates** them:

```
100 Generals (Parallel Analysis):
├─ Order Flow General → Feeds bid-ask data
├─ Options Greeks General → Feeds volatility metrics
├─ FII/DII General → Feeds institutional flow direction
├─ Top 20 Correlation General → Feeds leading stock signals
├─ Volume General → Feeds unusual volume detection
└─ ... others

Control Room (Real-time Orchestration):
├─ Aggregates signals: <70ms processing
├─ Filters institutional noise
├─ Makes entry/exit decisions
├─ Manages position lifecycle
└─ Auto-closes at 3:15 PM
```

**Key Difference**:
- Generals = Passive analysis (what do you see?)
- Control Room = Active decision-making (what should we do?)

---

## Sudden News Event Handling (Nirmala Sitharaman Moves)

**Scenario**: Unexpected government announcement causes 3-5% flash move

**Our Detection**:
```
volume_spike_ratio = 5.0x normal volume
bid_ask_imbalance = 0.8 (very one-sided)
→ INSTITUTIONAL MOVE DETECTED (95%+ confidence)

Action:
1. Immediately position for the move
2. Don't question it (trust the math)
3. Ride the move until reversal
4. Exit at 3:15 PM regardless
```

**Why We Win**:
- Retail traders panic, slow to react
- Institutional money moves in 100ms
- We detect in 50ms and execute in 70ms
- We're in the move before it hits retail charts

---

## Response Time Architecture (<70ms)

### Tick Processing Pipeline

```
Tick arrives (0ms)
    ↓
1. Time check (0-2ms)
   - If 3:15 PM? Close all. Done.
   ↓
2. Institutional detection (2-15ms)
   - Bid-ask analysis
   - Volume calculation
   - Direction determination
   ↓
3. Fake move filter (15-40ms)
   - Quick reversal check
   - Volatility analysis
   - Support check
   ↓
4. Decision logic (40-60ms)
   - Aggregate signals
   - Determine action
   - Generate output
   ↓
5. Response delivery (60-70ms)
   Total: <70ms ✓
```

### Optimization Techniques

1. **Pre-computation**: Calculate rolling averages in background threads
2. **Caching**: Store last N prices/volumes in memory (not disk)
3. **Early Exit**: If fake move detected, skip remaining checks
4. **Vectorization**: Use numpy for bulk calculations
5. **Multi-threading**: Process ticks in parallel queues

---

## Confidence Scoring

The system outputs confidence scores for all decisions:

```
< 50%:  HOLD (too uncertain)
50-69%: WEAK signal (wait for confirmation)
70-79%: GOOD signal (tradeable)
80-89%: STRONG signal (high confidence)
90%+:   INSTITUTIONAL MOVE (very high conviction)
```

**Minimum to trade**: 70% confidence
**Sudden news**: 90%+ confidence (volume spike >3x)

---

## Fake Move Filtering Accuracy

Based on opening phase testing:

```
Opening Noise Characteristics:
- 80% of moves at 9:30-9:45 reverse by 9:45 AM
- Gap downs often reverse 70% of the move
- First 5 minutes = lowest signal quality
- After 10:00 AM = 85%+ signal accuracy

Our System Performance:
- False positive rate: <5% (wrongly identify fake as real)
- False negative rate: <8% (miss real moves)
- Real move detection: 92% accuracy
```

---

## Real-World Example: March 23, 2020 (COVID Crash)

**9:30 AM Opens**:
- Gap down 200 points (immediately -2%)
- Panic selling
- Retail traders shorting immediately

**9:30-9:45 AM (Opening Noise Buffer)**:
- Large sellers showing (FII exiting)
- Bid-ask imbalance = -0.7 (very bearish)
- Volume 3x normal (institutional panic)
- This is NOT noise - this is institutional selling

**Control Room Decision (9:45 AM)**:
```
Opening signals analysis:
- Imbalance: -0.7 (bearish)
- Volume: 3.5x normal (institutional)
- No reversal: Stays down
- Conviction: 95%

DECISION: SHORT NIFTY FUTURES
CONFIDENCE: 95%
REASON: Consistent institutional selling, not opening noise
```

**Result**:
- We SHORT at 8,550
- Nifty crashes to 7,511 (1,039 points)
- Profit: +₹3,63,570 (36.36%)
- Retail traders: -70% on their long positions

---

## System State Machine

```
BEFORE 9:30 AM
    ↓ [Market opens]
OPENING PHASE (9:30-10:00 AM)
├─ Action: BUFFER & ANALYZE
├─ Trade: NO entries yet
    ↓ [10:00 AM reached]
TRADING PHASE (10:00 AM - 3:15 PM)
├─ Action: EXECUTE based on opening decision
├─ Trade: ENTER, MANAGE, FOLLOW flows
    ↓ [3:15 PM reached]
CLOSE PHASE (3:15+ PM)
├─ Action: FORCE CLOSE ALL
├─ Trade: NO new positions
    ↓ [Day ends]
READY FOR NEXT DAY
```

---

## Critical Parameters

| Parameter | Value | Reason |
|-----------|-------|--------|
| Opening Buffer | 9:30-10:00 AM | Filter opening noise |
| Min Confidence | 70% | Balance trades vs false signals |
| Imbalance Threshold | ±0.3 | Significant institutional activity |
| Volume Spike | >1.5x | Unusual volume detection |
| Response Latency | <70ms | Beat retail reaction time |
| Sudden News | >3.0x volume | Institutional panic/euphoria |
| Auto-Close | 3:15 PM | Intraday exit (no carry-forward) |

---

## Future Enhancements

1. **Machine Learning**: Train on 5+ years of tick data to improve fake move detection
2. **Multi-timeframe**: Combine 1-tick, 5-tick, 1-min analysis
3. **Liquidity Depth**: Monitor order book levels 2-5 for hidden orders
4. **Cross-Asset**: Track Nifty Futures vs spot correlation
5. **News Integration**: Real-time news API for catalyst detection

---

## Summary

The Control Room is **NOT just a signal aggregator**. It's a:

✓ **Institutional Move Detector** - Catches smart money before retail
✓ **Noise Filter** - Eliminates 90%+ of false signals  
✓ **Ultra-Fast Engine** - <70ms response time
✓ **Smart Risk Manager** - Auto-closes at 3:15 PM
✓ **Intraday Specialist** - Optimized for opening and closing mechanics

This is what makes the system **DOMINANT** - we enter the moves that matter, ignore the noise, and exit cleanly every day.
