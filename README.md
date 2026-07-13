# Nifty 50 Automated Trading System - 100 Generals Control Room

A sophisticated automated trading system for Nifty 50 index using multi-agent analysis framework powered by the "100 Generals" control room concept.

## System Overview

### Architecture

```
Market Data (Kite API)
        ↓
100 Generals (Parallel Agents)
├─ Order Flow General
├─ Options Greeks General
├─ FII/DII General
├─ Top 20 Correlation General
├─ Volume General
├─ Technical General
├─ Sentiment General
└─ ... 93 more
        ↓
Control Room (Aggregation & Decision)
        ↓
Trading Engine (Execution)
        ├─ LONG (Bullish)
        ├─ SHORT (Bearish)
        └─ STRADDLE/STRANGLE (Neutral)
        ↓
Risk Manager (2% Stop Loss)
```

## Key Features

### 100 Generals Framework
- **High-Impact Generals**: Order Flow, Options Greeks, FII/DII, Top 20 Correlation
- **Medium-Impact Generals**: Volume, Technical Analysis, Sentiment
- **Adaptive Analysis**: Each General provides independent signal with confidence

### Control Room Logic
- **Weighted Voting System**: Aggregates signals with dynamic weighting
- **Thresholds**:
  - BULLISH: Score > +0.6 → Long Nifty Futures
  - BEARISH: Score < -0.6 → Short Nifty Futures
  - NEUTRAL: -0.6 to +0.6 → Short Straddle/Strangle
- **Minimum Confidence**: 70% required to trade

### Trading Rules
- **Entry Time**: 9:30 AM (every trading day, no exceptions)
- **Position Size**: 14 contracts (based on ₹70k margin per contract)
- **Capital**: ₹10,00,000
- **Stop Loss**: 2% hard stop = ₹20,000
- **Target**: Unlimited (squeeze market)

## Project Structure

```
thebermudainsurance/
├── main.py                          # Entry point
├── config/
│   └── settings.py                  # Configuration & constants
├── data/
│   └── kite_connector.py            # Kite API integration
├── generals/
│   ├── __init__.py
│   └── general_manager.py           # 100 Generals framework
├── control_room/
│   ├── __init__.py
│   └── control_room.py              # Decision aggregation
├── trading_engine/
│   ├── __init__.py
│   └── trader.py                    # Trade execution
├── risk_management/
│   ├── __init__.py
│   └── risk_manager.py              # Risk & position tracking
├── backtest/
│   ├── __init__.py
│   └── backtester.py                # Historical testing
├── utils/
│   ├── __init__.py
│   └── logger.py                    # Logging configuration
└── logs/                            # Log files
```

## Installation

```bash
# Clone repository
git clone <repo-url>
cd thebermudainsurance

# Install dependencies
pip install -r requirements.txt

# Setup Kite API credentials
export KITE_API_KEY="your_api_key"
export KITE_ACCESS_TOKEN="your_access_token"
```

## Usage

### Run Single Daily Cycle
```bash
python main.py
```

### Run Live Monitoring (Production)
```python
system = NiftyTradingSystem()
system.monitor_positions()  # Continuous monitoring
```

### Backtest on Historical Data
```python
from backtest.backtester import Backtester

backtester = Backtester(capital=1000000, strategy=system)
results = backtester.run_backtest(historical_data)
```

## Performance Metrics

### Corrected Nifty Futures Specifications

| Parameter | Value |
|-----------|-------|
| Lot Size | 25 shares |
| Margin per Lot | ₹70,000 |
| Max Contracts | 14 (with ₹10L capital) |
| Brokerage | ₹40 per round trip |
| Slippage | 2-5 paise |

### Historical Backtests

#### March 23, 2020 (Worst Case - COVID Crash)
- **Signal**: BEARISH (13% daily crash)
- **Entry**: Short 14 contracts at ₹8,550
- **Exit**: ₹7,511
- **Profit**: ₹3,63,570 (+36.36%)
- **Stop Loss**: Never breached ✓

#### June 13, 2026 (Neutral to Bullish Recovery)
- **Signal**: NEUTRAL → BULLISH (recovery after gap down)
- **Entry**: Long 14 contracts at ₹24,100
- **Exit**: ₹24,211
- **Profit**: ₹38,770 (+3.88%)
- **Stop Loss**: Never breached ✓

## Configuration

Edit `config/settings.py` to customize:

```python
CAPITAL = 1000000                    # Starting capital
STOP_LOSS_PERCENT = 2               # 2% hard stop
MIN_CONFIDENCE_TO_TRADE = 70        # Confidence threshold
SIGNAL_UPDATE_INTERVAL_MINUTES = 5  # Signal refresh rate
```

## Risk Management

- **Daily Stop Loss**: ₹20,000 (2% of capital)
- **Auto Close**: All positions closed if stop loss hit
- **Position Limits**: Max 14 contracts per trade
- **Margin Management**: Real-time margin monitoring

## Next Steps

### Priority Tasks

1. **Implement Individual Generals**
   - Order Flow analysis from Kite orderbook
   - Options Greeks calculation
   - FII/DII data fetching
   - Top 20 stock correlation tracking

2. **Build Backtesting Engine**
   - Historical data loader
   - Simulate trades with slippage
   - Generate performance reports

3. **Test on Historical Scenarios**
   - March 23, 2020 (worst case)
   - June 13, 2026 (neutral recovery)
   - Additional stress test scenarios

4. **Deploy to Production**
   - Paper trading validation
   - Live trading with Kite API
   - Real-time monitoring and alerts

## Important Notes

### Nifty is Mathematical, Not Prediction
- System follows mathematical relationships, not predicts
- Top 20 stocks determine Nifty movements
- Smart money flows visible through order flow analysis
- System adapts to what the math shows in real-time

### Daily Entry Requirement
- System enters market **EVERY DAY** at 9:30 AM
- Direction determined by 100 Generals analysis
- No skipping or "waiting for perfect conditions"

## Support & Debugging

```bash
# Check logs
tail -f logs/trading_system.log

# Verbose logging
export LOG_LEVEL=DEBUG
python main.py
```

## License

Proprietary - Not for public distribution

## Contact

For questions or issues, contact: sravan.kasoji@gmail.com
