# Risk Assessor

**Node ID:** `risk_assessor`
**Icon:** ShieldAlert
**Color Theme:** Red

## Purpose
The Risk Assessor agent acts as the system's defensive mechanism. Once an initial trade or strategy thesis is formed, this agent critically evaluates the downside exposure.

## Responsibilities
- Calculates the Value-at-Risk (VaR) for proposed trades against the entire AI-managed portfolio.
- Scrutinizes Beta and standard deviation relative to the broader market index (SPY).
- Analyzes potential "Black Swan" geopolitical and systematic risks flagged by the Market Researcher.
- Checks proposed trades against hardcoded compliance rules (e.g., maximum 5% capital allocation to a single asset).

## Outputs
- Approves, Modifies, or Hard-Vetoes any proposed trade structure based strictly on risk models.
- Generates required hedging guidelines.
