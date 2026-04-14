# Trade Executor

**Node ID:** `trade_executor`
**Icon:** Brain
**Color Theme:** Slate

## Purpose
The Trade Executor is the terminal node of the QuantAgents committee. It relies entirely on the upstream vetting processes and does no cognitive analysis itself. It simply interfaces with the actual brokerages.

## Responsibilities
- Receives the final validated, mathematically optimized, and rigorously backtested JSON logic structure from the preceding agents.
- Converts the internal platform logic into proper Brokerage API standard formats.
- Dispatches buy, sell, limit, and trailing-stop orders over established WebSockets/REST APIs linked to Alpaca.

## Outputs
- API payloads fired directly into the stock market structure.
- Ingestion of the immediate execution receipts from the broker, looping them back into the main PostgreSQL `Portfolio` ledger to ensure the frontend reflects accurate cash-on-hand.
