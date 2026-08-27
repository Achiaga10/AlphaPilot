# AlphaPilot

AlphaPilot is a deterministic stock-research and portfolio-decision platform
focused on the S&P 500, with support for explicitly tracked tickers. It combines
an async FastAPI/PostgreSQL backend with a typed React/TypeScript research UI.

The backend provides market-data synchronization, completed-daily-session
strategy evaluation, no-lookahead backtesting, candidate ranking, portfolio
risk/sizing, explainable decision plans, and immutable research datasets.
Operational candles remain the latest known values for normal product use;
research runs can bind to a frozen snapshot containing exact candle versions,
an exact universe, canonical SHA-256 hashes, source-provenance status, and a Git
revision.

## Stack

- Python 3.12, FastAPI, SQLAlchemy async, Alembic, PostgreSQL, `uv`
- React, TypeScript, Vite, TanStack Query
- pytest, Ruff, mypy, Vitest, Testing Library, ESLint
- Alpaca market-data integration behind provider/service boundaries

## Local quality gates

From `backend/`:

```powershell
$env:DEBUG='false'
.\run_checks.ps1
```

From `frontend/`:

```powershell
npm run lint
npm test -- --run
npm run build
```

GitHub Actions runs clean Alembic upgrades against isolated CI databases plus
the backend and frontend gates above. Normal CI uses deterministic fakes and
does not require live market-data credentials.

## Reproducible research datasets

After applying migrations, immutable dataset manifests can be managed with:

```powershell
uv run alphapilot-research-dataset create --start 2021-08-20 --end 2026-08-20 --label research-v1
uv run alphapilot-research-dataset list
uv run alphapilot-research-dataset show <snapshot-id>
uv run alphapilot-research-dataset verify <snapshot-id>
```

Pre-Sprint 13 operational rows are frozen with honest `LEGACY_UNKNOWN`
provenance. Their values are reproducible after migration, but overwritten
historical revisions from before versioning cannot be reconstructed. A frozen
current-constituent universe also retains survivorship bias; it is not a
historical point-in-time S&P 500 universe.
