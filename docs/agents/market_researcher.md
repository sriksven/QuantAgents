# Market Researcher

**Node ID:** `research_committee`
**Icon:** FileSearch
**Color Theme:** Blue

## Purpose
The Market Researcher agent is the project's primary data acquisition layer for fundamental and qualitative data. It relies heavily on web access to form macroscopic and microscopic overviews of equities.

## Responsibilities
- Query external APIS (Alpaca, Alpha Vantage) for earnings reports, revenue data, and corporate structure changes.
- Access the **Tavily API** to browse financial news sites, scraping the latest headlines and articles associated with a target ticker.
- Analyze general macroeconomic sentiments (e.g., inflation numbers, Federal Reserve rate announcements).
- Provide a written, qualitative brief summarizing the market positioning of the target asset.

## Outputs
- Structured JSON containing fundamental numbers.
- A natural-language macro-brief to be evaluated by the Portfolio Strategist and Risk Assessor.
