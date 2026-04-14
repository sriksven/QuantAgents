# Information & Execution Flow

QuantAgents operates on a pipeline flow, where an initial trigger trickles down through an assembly of 8 AI agents, arriving finally at the Trade Executor.

## 1. Triggers
The flow begins via scheduled chron jobs in **Airflow** or manual user overrides in the front-end dashboard. A ticker or general market query is presented to the initial nodes.

## 2. Research Phase (Data Ingestion)
- **Market Researcher**: Queries real-time APIs (Alpaca, Alpha Vantage) and scrapes news using the Tavily API to gather fundamental macro + micro data.
- **Technical Analyst**: Simultaneously gathers historical price action, moving averages, and technical indicators (RSI, MACD, Support/Resistance lines).

## 3. Analysis & Debate Phase
- **Portfolio Strategist**: Takes the fundamental and technical readouts and formulates an overarching bullish, bearish, or neutral thesis for the portfolio's general allocation mechanism.
- **Options Analyst**: Looks for specific asymmetric hedging or leveraging opportunities associated with the symbol based on Implied Volatility.
- **Risk Assessor**: Vetoes or scales down proposed positions by weighing the overall portfolio Beta and Value-At-Risk.

## 4. Optimization Phase
- **Quantum Optimizer**: Performs simulated annealing against the accepted strategy to identify the mathematical apex of capital allocation weighting (e.g., maximizing the Sharpe ratio).
- **Backtest Engine**: Validates the proposed quantum allocation dynamically over the past 5 years of historical Alpaca market data to ensure the strategy is robust against drawdowns.

## 5. Execution Phase
- **Trade Executor**: Formulates the final API payloads (Buy/Sell, Limit/Market) and dispatches them securely to the Alpaca Brokerage account. It logs the completion into the PostgreSQL database ledger.

## Auxiliary Feature: Mock Trading
A completely separate flow exists for User Mock Trading (`/api/mock-trade`):
1. User clicks "Place Order" on the `TradingTerminal` component.
2. Mock API checks real-time price using the proxy method.
3. Balance is adjusted locally in the `MockPortfolio` Postgres schema.
4. Agents are entirely unaware of this internal local sub-ledger.
