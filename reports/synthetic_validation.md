# Backtest Report  (SYNTHETIC ENGINE-VALIDATION DATA - not a performance claim)

Capital Rs 1,000,000 | 4 lots x 65 = 260 qty | stop Rs 20,000 (~77 pts) | square-off 15:15

| Date | Dir | Entry | Exit | Reason | Gross | Costs | Net | Worst MTM |
|------|-----|-------|------|--------|-------|-------|-----|-----------|
| SYN-1-crash | SHORT | 09:40 @ 24,249.0 | 15:10 @ 23,806.5 | SQUARE_OFF_1515 | +115,050 | 1,687 | +113,363 | 0 |
| SYN-2-trap-reversal | SHORT | 09:40 @ 23,909.9 | 09:55 @ 23,987.8 | STOP_LOSS | -20,260 | 1,673 | -21,933 | -20,260 |
| SYN-3-chop | STRADDLE | 10:00 @ 24,191.4 | 15:10 @ 24,211.9 | SQUARE_OFF_1515 | +15,171 | 250 | +14,921 | -1,955 |
| SYN-4-rally | LONG | 09:45 @ 24,186.4 | 15:10 @ 24,578.6 | SQUARE_OFF_1515 | +101,972 | 1,710 | +100,262 | 0 |
| SYN-5-adverse-reversal | LONG | 09:40 @ 24,193.7 | 10:40 @ 24,127.1 | REVERSAL_EXIT | -17,316 | 1,687 | -19,003 | -17,316 |
| SYN-6-flash-crash-stop | LONG | 09:40 @ 24,195.3 | 10:05 @ 24,117.4 | STOP_LOSS | -20,260 | 1,687 | -21,947 | -20,260 |

## Summary
- Sessions traded: 6 | wins 3 | losses 3 | win rate 50%
- Gross P&L: Rs +174,357 | costs Rs 8,694 | **Net P&L: Rs +165,663 (+16.57%)**
- Worst single day: Rs -21,947 (hard cap Rs -20,000 + slippage/costs/gap risk)
- Max equity drawdown: Rs 40,950

Straddle days use the documented approximation in `backtest/engine.py:StraddleModel` - validate against real option chains before trusting NEUTRAL-day P&L.
