# Backtest Report  (SYNTHETIC ENGINE-VALIDATION DATA - not a performance claim)

Capital Rs 1,000,000 | 4 lots x 65 = 260 qty | stop Rs 20,000 (~77 pts) | square-off 15:15

| Date | Dir | Entry | Exit | Reason | Gross | Costs | Net | Worst MTM |
|------|-----|-------|------|--------|-------|-------|-----|-----------|
| SYN-1-crash | SHORT | 09:50 @ 24,234.6 | 15:10 @ 23,806.5 | SQUARE_OFF_1515 | +111,306 | 1,686 | +109,620 | 0 |
| SYN-2-trap-reversal | LONG | 10:00 @ 23,983.8 | 15:10 @ 24,115.6 | SQUARE_OFF_1515 | +34,268 | 1,681 | +32,587 | 0 |
| SYN-3-chop | STRADDLE | 10:00 @ 24,191.4 | 15:10 @ 24,211.9 | SQUARE_OFF_1515 | +15,171 | 250 | +14,921 | -1,955 |
| SYN-4-rally | LONG | 09:50 @ 24,190.2 | 15:10 @ 24,578.6 | SQUARE_OFF_1515 | +100,984 | 1,710 | +99,274 | 0 |
| SYN-5-adverse-reversal | LONG | 09:50 @ 24,210.6 | 10:35 @ 24,132.7 | STOP_LOSS | -20,260 | 1,688 | -21,948 | -20,260 |
| SYN-6-flash-crash-stop | LONG | 09:50 @ 24,212.5 | 10:05 @ 24,134.6 | STOP_LOSS | -20,260 | 1,688 | -21,948 | -20,260 |

## Summary
- Sessions traded: 6 | wins 4 | losses 2 | win rate 67%
- Gross P&L: Rs +221,209 | costs Rs 8,704 | **Net P&L: Rs +212,506 (+21.25%)**
- Worst single day: Rs -21,948 (hard cap Rs -20,000 + slippage/costs/gap risk)
- Max equity drawdown: Rs 43,897

Straddle days use the documented approximation in `backtest/engine.py:StraddleModel` - validate against real option chains before trusting NEUTRAL-day P&L.

## Per-bar decision log - SYN-2-trap-reversal
- 09:25+5m SHORT score=-0.386 conf=86 [gap:-0.50@45, opening_range:+0.00@0, failed_breakdown:+0.00@0, vwap:-0.23@34, momentum:+0.00@0, structure:+0.00@0, volume_pressure:-1.00@85, persistence:+0.00@0, prev_day:-0.97@40]
- 09:30+5m SHORT score=-0.450 conf=94 [gap:-0.50@45, opening_range:-1.00@46, failed_breakdown:+0.00@0, vwap:-0.34@40, momentum:-0.73@51, structure:-1.00@75, volume_pressure:-1.00@85, persistence:+0.00@0, prev_day:-0.97@40]
- 09:35+5m SHORT score=-0.429 conf=91 [gap:-0.50@45, opening_range:-1.00@53, failed_breakdown:+0.00@25, vwap:-0.44@46, momentum:-0.82@56, structure:-1.00@75, volume_pressure:-1.00@85, persistence:-1.00@80, prev_day:-0.97@40]
- 09:40+5m NEUTRAL score=-0.095 conf=46 [gap:-0.50@45, opening_range:+0.00@30, failed_breakdown:+1.00@59, vwap:-0.01@21, momentum:-0.40@35, structure:-0.80@74, volume_pressure:-0.72@53, persistence:-0.67@67, prev_day:-0.97@40]
- 09:45+5m NEUTRAL score=+0.019 conf=14 [gap:-0.50@45, opening_range:+0.00@30, failed_breakdown:+1.00@59, vwap:+0.25@35, momentum:-0.00@15, structure:-0.50@50, volume_pressure:-0.26@26, persistence:-0.43@43, prev_day:-0.97@40]
- 09:50+5m NEUTRAL score=+0.223 conf=52 [gap:+1.00@50, opening_range:+1.00@45, failed_breakdown:+1.00@59, vwap:+0.45@47, momentum:+0.32@31, structure:-0.29@33, volume_pressure:+0.04@12, persistence:-0.25@25, prev_day:-0.97@40]
- 09:55+5m LONG score=+0.294 conf=62 [gap:+1.00@50, opening_range:+1.00@55, failed_breakdown:+1.00@59, vwap:+0.61@57, momentum:+0.65@47, structure:-0.12@20, volume_pressure:+0.25@25, persistence:-0.11@11, prev_day:-0.97@40]
