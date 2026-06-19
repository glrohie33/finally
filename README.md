# FinAlly — AI Trading Workstation

A visually stunning, AI-powered trading workstation that streams live market data, supports simulated portfolio trading, and integrates an LLM chat assistant capable of analyzing positions and executing trades on your behalf. Built to look and feel like a modern Bloomberg terminal with an AI copilot.

## Features

- **Live price streaming** via Server-Sent Events — prices flash green/red on tick with sparkline mini-charts
- **Simulated portfolio** — start with $10,000 in virtual cash, execute market orders instantly
- **Portfolio heatmap** — treemap sized by position weight, colored by P&L
- **P&L chart** — portfolio value over time
- **AI chat assistant** — natural language trading: ask questions, get analysis, or say "buy 10 AAPL" and it executes
- **Watchlist management** — add/remove tickers manually or via AI chat

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js (TypeScript), Tailwind CSS, static export |
| Backend | FastAPI (Python), uv, SQLite |
| Real-time | Server-Sent Events (SSE) |
| AI | LiteLLM → OpenRouter (Cerebras inference) |
| Market data | Built-in GBM simulator (default) or Massive/Polygon.io REST API |

## Prerequisites

- Python 3.12+
- [uv](https://astral.sh/uv) — `pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Node.js 20+

## Quick Start

```bash
# 1. Clone and enter the project
git clone <repo-url> && cd finally

# 2. Configure environment
cp .env.example .env
# Edit .env and set OPENROUTER_API_KEY

# 3. Start (builds frontend, installs deps, launches on port 8000)
./scripts/start.sh
```

Open [http://localhost:8000](http://localhost:8000).

```bash
# Stop
./scripts/stop.sh
```

**Windows:** use `scripts/start_windows.ps1` / `scripts/stop_windows.ps1`.

## Environment Variables

```bash
# Required — get one at openrouter.ai
OPENROUTER_API_KEY=your-key-here

# Optional — real market data via Massive/Polygon.io; simulator used if unset
MASSIVE_API_KEY=

# Optional — deterministic mock LLM responses for testing
LLM_MOCK=false

# Optional — override the default LLM model
LLM_MODEL=
```

## Development Mode

Run backend and frontend separately for hot-reloading:

```bash
# Terminal 1 — backend (port 8000)
cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend (port 3000, proxies /api/* to backend)
cd frontend && npm install && npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Testing

```bash
# Backend unit tests
cd backend && uv run pytest

# Frontend unit tests
cd frontend && npm test

# E2E tests (requires app running with LLM_MOCK=true)
cd test && npx playwright test
```

## Resetting State

Delete `db/finally.db` to reset to the initial state ($10k cash, default watchlist).

## License

MIT
