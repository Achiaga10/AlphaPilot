# AlphaPilot UI

React/TypeScript research dashboard for AlphaPilot's advisory Portfolio Plan
API. It does not calculate strategies, RS20, ATR, sizing, or decision reasons
and it does not execute trades.

## Prerequisites

- Node.js 20.19+ (the project was validated with Node 24)
- npm
- the AlphaPilot FastAPI backend and PostgreSQL development database

## Install and configure

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local
```

Set `VITE_API_BASE_URL` to the backend origin. The example uses
`http://localhost:8000`. Never put database credentials, market-provider keys,
or broker secrets in frontend environment files.

## Run locally

Backend, from `backend/`:

```powershell
$env:DEBUG='false'
uv run uvicorn alphapilot.main:app --host 127.0.0.1 --port 8000
```

Frontend, from `frontend/`:

```powershell
npm run dev
```

Open `http://localhost:5173`.

## Quality commands

```powershell
npm run lint
npm run test
npm run build
```

## API dependency

The required workflow consumes:

- `GET /api/v1/health/`
- `GET /api/v1/portfolio/risk-config`
- `POST /api/v1/portfolio/plan`
- `GET /api/v1/admin/data/capability`

The `/evaluate` screen reuses the Portfolio Plan endpoint with a one-ticker
scope. It does not calculate strategy or technical facts in the browser.

Research-admin routes under `/api/v1/admin/data` are shown only when backend
`ADMIN_TOOLS_ENABLED=true`. The safe default is false. This is a development
feature gate, not authentication or authorization. Sync operations reuse the
backend's existing providers and services; provider credentials never belong in
the frontend.

The current portfolio is entered manually because AlphaPilot has no broker
synchronization or authenticated account persistence. The backend uses stored
daily candles and may return an actual analysis date earlier than the requested
date. Results are research/advisory outputs, not live orders or production-
validated recommendations.

## Known limitations

No authentication, saved cloud portfolio, broker state, live quotes, order
execution, arbitrary custom-ticker metadata discovery, or backtest explorer is
included. Browser storage is only a local convenience for the editable research
form. Full-sync job state is process-local and is not a durable job queue.
