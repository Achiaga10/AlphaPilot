# AlphaPilot Sprint 16 Completion Report

## Outcome and goal

Sprint 16 is complete locally on `feature/persistent-research-portfolio`. It
replaced browser-authoritative research cash/holdings with a single persistent,
backend-owned portfolio, preserved the position/trade lifecycle, added
completed-session mark-to-market valuation, and bound normal plans/actions to a
portfolio identity and monotonic revision. Sprint 17 was not started.

Previously, `localStorage` supplied financial state to normal plan/action APIs.
That made a browser the source of truth, could lose history, and could overwrite
current state with stale cash/positions. It now stores only strategy, selection,
requested-date, and ticker-scope preferences after migration.

## Persistent architecture

Alembic revision `d91f32a45c7b` (down revision `b7a9d4f2c613`) additively creates:

- `research_portfolios`: stable key/name, Decimal cash, cumulative realized P&L,
  monotonic revision, UUID, timestamps.
- `research_positions`: open/closed lifecycle, whole-share quantity, average
  cost, cost basis, entry price/day, modeled risk, company/ticker/sector lookup,
  strategy/selection/decision facts, profile ID/version plus canonical profile
  JSON, provenance, and close date. A partial unique PostgreSQL index prevents
  two open positions for one company in a portfolio.
- `research_trade_events`: append-only service ledger for `OPEN`,
  `PARTIAL_EXIT`, and `FULL_EXIT`, with quantity, execution price/day, cash
  effect, realized P&L, source/reason/action, and strategy/profile provenance.

All financial storage uses `Numeric`/`Decimal`; quantities/revisions are
integers. The repository never commits internally. Mutations lock the portfolio
row with `SELECT FOR UPDATE`, require the exact expected revision, validate
before writes, update aggregate/position, append one event, increment revision,
and commit once. Failed or stale mutations create no successful event. A stale
preview or apply returns HTTP 409.

## Accounting and provenance

BUY requires positive whole shares, sufficient cash, a known company, and no
open holding. Cash effect is `-(quantity × execution price)`; average cost,
cost basis, entry price/day, modeled risk, selection policy, decision/reason,
exact Strategy Profile ID/version, and its resolved canonical JSON snapshot are
preserved. It appends `OPEN` and increments revision.

SELL proceeds are `quantity × execution price`. Realized P&L is
`quantity × (execution price - stored average cost)`. A partial exit reduces
quantity and cost basis by `sold quantity × average cost`, retains the open row,
and appends `PARTIAL_EXIT`. A full exit marks the row closed without deleting
it and appends `FULL_EXIT`. Both update cash/cumulative realized P&L and preserve
complete history.

Legacy browser positions import once, only when no backend portfolio exists.
They are explicitly `LEGACY_IMPORTED`; strategy/profile/selection fields remain
unknown and no historical trade event is fabricated. If a backend portfolio
already exists, browser cash/positions are ignored and cannot override it.

## Valuation and missing data

Reads value every open position through `DailyCandleRepository.get_latest()`,
which enforces `CompletedDailySessionPolicy`. Backend responses provide latest
completed day/close, market value, portfolio weight, unrealized P&L/percentage,
cash/equity/weights, realized P&L, and valuation status. Entry facts are never
rewritten by valuation or Sync.

If any open position has no completed price, it remains visible as
`PRICE_UNAVAILABLE`; the portfolio is `PARTIAL` or `UNAVAILABLE`. Aggregate
market value, equity, and unrealized P&L are null rather than fabricated zero.
Normal plan/action loading rejects a portfolio whose required current price is
unavailable.

Primary acceptance: 10 shares with stored average/entry cost $100 and cost basis
$1,000, valued at a completed $110 close, produced market value $1,100,
unrealized P&L +$100 and +10%. Stored average cost, cost basis, and entry price
remained unchanged. An incomplete current-session $999 candle was explicitly
ignored in the focused test.

## API and frontend contract

New API operations are:

- `GET /api/v1/portfolio/current`
- `POST /api/v1/portfolio/initialize`
- `GET /api/v1/portfolio/{portfolio_id}/events`

Before Sprint 16, normal `POST /portfolio/plan`, preview/apply, and manual sell
accepted browser cash/positions. Normal Sprint 16 calls carry `portfolio_id`;
plans return `portfolio_id` and `portfolio_revision`; preview/apply/manual sell
carry both ID and expected revision. The backend reloads the aggregate and
revalidates. The revision is included in the deterministic plan fingerprint,
so an old plan becomes stale after a successful mutation. The lower-level
research `/portfolio/decisions` and compatible explicit-state path remain for
tests/research integrations, not normal UI authority.

Dashboard and Portfolio now query backend portfolio valuation, show revision,
realized/unrealized P&L, completed valuation date, average cost, cost basis,
completed close, market value, unrealized P&L/percentage, and explicit profile
or legacy provenance. Manual cash/position editors were removed. Evaluate uses
the same persistent portfolio ID while retaining exact ticker identity and
latest-request-wins protections. Successful BUY/SELL/import invalidates the
portfolio query. Successful ticker, Market Candles, or Full Sync also refetches
valuation. React performs formatting and visualization only; market value,
cost basis, P&L, equity, and financial weights come from backend fields.

## Files

Created backend files:

- `backend/migrations/versions/d91f32a45c7b_add_persistent_research_portfolio.py`
- `backend/src/alphapilot/database/models/research_portfolio.py`
- `backend/src/alphapilot/repositories/research_portfolio.py`
- `backend/src/alphapilot/services/research_portfolio.py`
- `backend/tests/portfolio/test_research_portfolio.py`

Modified backend files:

- `backend/migrations/env.py`
- `backend/src/alphapilot/api/routes/portfolio.py`
- `backend/src/alphapilot/database/models/__init__.py`
- `backend/src/alphapilot/schemas/portfolio.py`
- `backend/tests/api/test_portfolio_decisions.py`
- `backend/tests/conftest.py`

Created documentation: `docs/sprints/SPRINT16_PLAN.md` and this report. Updated
`AGENTS.md`, `docs/PROJECT_STATE.md`, and `docs/DECISIONS.md`.

Modified frontend files:

- `frontend/src/api/portfolio.ts`
- `frontend/src/types/portfolio.ts`
- `frontend/src/features/portfolio/ManualSellDialog.tsx`
- `frontend/src/features/portfolio/PlanForm.tsx`
- `frontend/src/features/portfolio/PlanForm.test.tsx`
- `frontend/src/features/portfolio/PortfolioWorkspace.tsx`
- `frontend/src/features/portfolio/ResearchPortfolioPanel.tsx`
- `frontend/src/pages/AdminDataPage.tsx`
- `frontend/src/pages/EvaluatePage.tsx`
- `frontend/src/pages/EvaluatePage.test.tsx`
- `frontend/src/pages/PlanDirtyState.test.tsx`
- `frontend/src/pages/PortfolioActions.test.tsx`
- `frontend/src/pages/PortfolioPage.tsx`
- `frontend/src/pages/PortfolioPage.test.tsx`
- `frontend/src/test/fixtures.ts`
- `frontend/src/test/server.ts`

No strategy, Strategy Profile, Strategy Lab, Sprint 13 snapshot/versioning,
ranking, stop/trailing-stop default, backtest accounting, broker execution,
scheduler, or provider integration was changed. CI required no change: it
already provisions separate PostgreSQL databases, migrates both to head, runs
backend and frontend gates, and supplies no real provider credentials.

## Verification and exact commands

Migration (dedicated test DB target was asserted different from development and
to contain `test` before downgrade):

```powershell
$env:DATABASE_URL=$testUrl
uv run alembic downgrade b7a9d4f2c613
uv run alembic upgrade head
uv run alembic current
```

Result: downgrade/upgrade PASS; `d91f32a45c7b (head)`.

Focused backend commands included:

```powershell
$env:DEBUG='false'
uv run pytest tests/portfolio/test_research_portfolio.py tests/api/test_portfolio_decisions.py -q
uv run pytest tests/api/test_scanner.py tests/strategy_lab tests/research_data tests/api/test_research_datasets.py tests/api/test_portfolio_decisions.py tests/portfolio/test_research_portfolio.py -q
```

Results: persistent/API focused set 18 passed; combined Scanner/Sprint 13-15
regression set 82 passed. Scanner passed 3/3. Strategy Profiles, Strategy Lab,
and research dataset/snapshot reproducibility remained green.

Final backend gate:

```powershell
cd backend
$env:DEBUG='false'
.\run_checks.ps1
```

Result: Ruff lint PASS; Ruff format PASS; mypy PASS (152 source files); pytest
PASS (290 passed in 33.47s); overall PASS.

Final frontend gate:

```powershell
cd frontend
npm run lint
npm test -- --run
npm run build
```

Result: ESLint PASS; Vitest PASS (16 files, 64 tests, no skips); TypeScript/Vite
production build PASS (103 modules, logo bundled).

Controlled browser acceptance used hidden Edge, Vite on localhost, and a
selector-loop backend connected only to the dedicated test database. The seeded
historical completed candle and legacy position produced the exact 10 @ $100 to
$110 facts above. Dashboard showed backend valuation/provenance/revision;
Portfolio showed backend-owned state and no cash editor. Network monitoring
observed only localhost requests—no provider or broker call. PASS. The broader
mutation, stale-plan, partial/full SELL, profile provenance, incomplete-session,
sync invalidation, migration, and Evaluate identity cases are covered by the
green automated tests.

## Conclusions and limitations

Sprint 16 proved that AlphaPilot can persist and audit a research portfolio,
preserve entry/profile facts and exits, value it deterministically from stored
completed sessions, reject stale revisions, migrate legacy state without false
provenance, and present backend-owned financial facts in the UI.

It did not prove live execution, broker/account reconciliation, tax-lot
accounting, intraday pricing, corporate-action handling, multi-user ownership,
authentication/authorization, automated daily sync, or production concurrency
at scale. The largest limitation is that the system still has one local
research portfolio with no authenticated user/account ownership or broker state;
valuation is end-of-day and depends on stored data freshness.

Recommended Sprint 17 direction only: position monitoring, profile-bound exit
guidance, and carefully governed completed-session daily sync automation. No
Sprint 17 implementation was started.

## Git handoff

Working tree: local Sprint 16 modifications and new files are uncommitted on
`feature/persistent-research-portfolio`; no commit or push was performed. See
the exact handoff below.

`git status --short` reports 25 modified tracked files and these seven untracked
files:

```text
backend/migrations/versions/d91f32a45c7b_add_persistent_research_portfolio.py
backend/src/alphapilot/database/models/research_portfolio.py
backend/src/alphapilot/repositories/research_portfolio.py
backend/src/alphapilot/services/research_portfolio.py
backend/tests/portfolio/test_research_portfolio.py
docs/sprints/SPRINT16_COMPLETION_REPORT.md
docs/sprints/SPRINT16_PLAN.md
```

The modified tracked files are `AGENTS.md`, migration environment/model exports,
portfolio route/schemas/API tests/test cleanup, continuity docs, and the 16
frontend source/test files enumerated in the Files section. `git diff --stat`
before staging reports 25 tracked files changed, 781 insertions, and 656
deletions; untracked files are not included by that Git command. `git diff
--check` passes (only expected Windows LF-to-CRLF notices are printed).

Recommended commit message:

`feat: add persistent research portfolio lifecycle`
