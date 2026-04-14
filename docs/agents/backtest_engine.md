# Backtest Engine

**Node ID:** `backtester`
**Icon:** Zap
**Color Theme:** Indigo

## Purpose
The Backtest Engine acts as a reality check mechanism before any real money is committed. It runs the Quantum Optimizer's mathematical models backwards through historical market data to measure resilience.

## Responsibilities
- Connects to Alpaca's historical ticker APIs to retrieve past 1, 3, and 5-year data structures.
- Simulates executing the Strategist's proposed criteria continuously over historical timelines.
- Factorizes slippage, fees, and general market drag into the testing environment.

## Outputs
- Maximum drawdown statistics.
- Win-rate probabilities.
- Rejects a model if the simulated drawdown exceeds the hard limit established by the Risk Assessor.
