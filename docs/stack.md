# Technology Stack

QuantAgents is a robust, multi-agent intelligence platform composed of a Python-based asynchronous backend and a Next.js React frontend.

## Frontend
- **Framework**: Next.js (React)
- **Styling**: TailwindCSS & Vanilla CSS (using the Exaggerated Minimalism design system)
- **Animations**: Framer Motion
- **Icons**: Lucide React
- **Data Fetching**: Native `fetch` with `useEffect` (Polling)
- **Deployment**: Vercel / Docker (Ready)

## Backend
- **Framework**: FastAPI (Python)
- **Language**: Python 3.10+
- **ORM / Database**: SQLAlchemy + Alembic (PostgreSQL)
- **Authentication**: JWT/OAuth (planned/extensible)
- **Task Orchestration**: Apache Airflow
- **LLM Integration**: LangChain / OpenAI API (GPT-4)
- **Observability**: Langfuse (for monitoring LLM traces and costs)
- **Market Data**: Alpaca API, Alpha Vantage
- **Search Engine**: Tavily API

## Infrastructure
- **Containerization**: Docker & Docker Compose
- **Database**: PostgreSQL (for both AI ledger and local Mock Trading ledger)
- **Environment Management**: `.env` and Python `config.py` using Pydantic Settings.

## Third-Party API Integrations
1. **OpenAI**: Core intelligence for all 8 agents.
2. **Alpaca**: Market data (Quotes, Historical) and real paper trading execution.
3. **Alpha Vantage**: Auxiliary market data.
4. **Tavily**: Live web searching for the Market Researcher.
5. **Langfuse**: Detailed tracing of prompt execution and token consumption.
