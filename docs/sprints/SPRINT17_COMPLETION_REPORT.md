# Sprint 17 Completion Report

Date: 2026-08-28  
Branch: `feature/position-monitoring`  
Status: COMPLETE LOCALLY — Sprint 18 NOT STARTED

## Goal and result

Sprint 17 made the persistent research portfolio actively monitorable from its
stored Strategy Profile and completed daily candles, added explicit audited
portfolio reconciliation, and added disabled-by-default weekday candle-sync
automation. It did not add broker execution, automatic BUY/SELL, AI, a new
strategy, or an active protective/trailing/profit policy.

## Monitoring architecture and readiness

`PositionMonitoringService` loads each open position, validates exact stored
profile ID/version, requires the position candle to match the latest completed
stored SPY session, evaluates the existing strategy, maps the existing exit
context to monitoring, persists one snapshot per position/session, and latches a
genuine SELL on the position. The unique `(position_id,
completed_trading_day)` constraint makes retries idempotent.

Readiness is `READY` or `UNAVAILABLE`; status is `HOLD`, `ATTENTION`, `SELL`, or
null when unavailable. Typed unavailable reasons include unknown profile,
unsupported profile version, missing/stale market data, and insufficient
history. Legacy/manual positions never receive fabricated strategy guidance.

### Exact EMA semantics

- `close >= EMA20`: HOLD / `EMA20_HELD`.
- `EMA50 <= close < EMA20` while the existing frozen HYBRID spread is at least
  2%: ATTENTION / `EMA20_LOST_STRONG_TREND_HOLD`.
- The same EMA20 loss without that existing strong-trend exception: SELL /
  `EMA20_WEAK_TREND_BREAKDOWN`.
- `close < EMA50`: SELL / `EMA50_BREAKDOWN`.

### Exact Micho semantics

- `close > SMA150` and `low >= SMA150`: HOLD / `SMA150_HELD`.
- `low < SMA150` and `close > SMA150`: ATTENTION /
  `SMA150_INTRADAY_BREACH_RECOVERED`.
- `close == SMA150`: ATTENTION / `SMA150_CLOSE_AT_SUPPORT`.
- `close < SMA150`: SELL / `SMA150_BREAKDOWN`.

No new threshold was introduced. ATTENTION is current-session metadata and may
recover to HOLD. SELL is sticky until the existing full-exit lifecycle closes
the position. Monitoring records profile identity, completed session, close,
relevant EMA/SMA facts, active exit policy, and latch state.

Current normal profile policy facts are explicit: protective stop `NONE`,
trailing stop `NONE`, and profit target `NONE`. Sprint 12 static ATR candidates
remain informational/research-only and are not live guidance.

## Reconciliation

Three revision-checked transactional mutations were added:

- signed cash deposit/withdrawal deltas; negative cash and zero deltas reject;
- external whole-share position import with `MANUAL_EXTERNAL` provenance and no
  fabricated strategy/profile/selection decision;
- existing-position quantity, average-cost/cost-basis, and optional entry-date
  correction.

Each successful mutation increments portfolio revision, preserves realized
trading P&L, and appends an immutable reconciliation event containing reason,
revision, and relevant before/after facts. Existing plan revision protection
therefore makes older plans stale. There is no destructive delete endpoint and
no tax-lot model.

APIs added:

- `GET /api/v1/portfolio/{id}/monitoring`
- `POST /api/v1/portfolio/{id}/cash-adjustments`
- `POST /api/v1/portfolio/{id}/external-positions`
- `POST /api/v1/portfolio/{id}/positions/{position_id}/reconcile`
- `GET /api/v1/portfolio/{id}/reconciliation-events`

## Daily completed-session synchronization

`DailyMarketSyncScheduler` is a lightweight FastAPI-lifespan task. Configuration
is `DAILY_MARKET_SYNC_ENABLED=false` by default. When enabled it schedules
Monday-Friday at exactly 16:30 `America/New_York`, after the unchanged 16:15
completed-session boundary. The scheduled request uses the New York calendar
date, calls the existing candle-sync operation, and never calls a broker.

The candle-sync operation is shared by manual and scheduled flows. A fully
successful sync refreshes monitoring for the current portfolio. Any reported
symbol failure prevents post-sync monitoring, preserving the prior authoritative
state. A repeated run with no newer completed SPY session reports
`NO_NEW_SESSION`; snapshot uniqueness prevents duplicates. Scheduler execution
is serialized in-process. The typed status endpoint is:

- `GET /api/v1/admin/data/scheduler`

It exposes enabled state, timezone/time, last start/completion/status, last
successful completed session, and a safe error summary. It exposes no secrets.
Market holidays naturally produce no newer SPY session and therefore a no-op.

The scheduler run status is process-local in V1; database monitoring history and
sticky exits are durable. This is intentionally not a distributed scheduler.

## UI changes

Dashboard and Portfolio Plan render the same backend-owned portfolio monitoring
panel. It displays HOLD/ATTENTION/SELL/UNAVAILABLE, typed reason, sticky trigger
date, profile identity, and explicit NONE policies without calculating any
indicator in React. `Manage Portfolio` exposes the three audited workflows and
refetches authoritative valuation/monitoring; the revision change makes old
plans stale. Data Management shows compact scheduler configuration/status and
retains existing manual sync controls.

## Schema and migration

Migration `f41c8e2067ab` is additive and creates monitoring snapshots and
reconciliation audit events, plus sticky exit fields on research positions. It
was upgraded successfully on the dedicated test database and development
database. No candle, snapshot, dataset, or trade history was destroyed.

## Files

Created:

- `backend/migrations/versions/f41c8e2067ab_add_position_monitoring_reconciliation.py`
- `backend/src/alphapilot/portfolio/monitoring.py`
- `backend/src/alphapilot/services/daily_market_scheduler.py`
- `backend/src/alphapilot/services/position_monitoring.py`
- `backend/tests/portfolio/test_position_monitoring.py`
- `backend/tests/services/test_daily_market_scheduler.py`
- `frontend/src/features/portfolio/ManageResearchPortfolio.tsx`
- `docs/sprints/SPRINT17_PLAN.md`
- `docs/sprints/SPRINT17_COMPLETION_REPORT.md`

Modified: continuity docs; backend config/lifespan, portfolio/admin models,
repositories, services, schemas and routes; research-portfolio tests; frontend
portfolio/admin API, hooks, types, test server, Dashboard-shared portfolio panel,
Portfolio page, and Data Management page. `.github/workflows/ci.yml` was inspected
and not changed: it already performs clean dev/test migrations, all backend and
frontend gates, and does not enable the default-off scheduler.

## Validation and exact commands

Focused backend:

```powershell
$env:DEBUG='false'
uv run pytest tests/portfolio/test_position_monitoring.py tests/portfolio/test_research_portfolio.py tests/services/test_daily_market_scheduler.py tests/strategy/test_exit_modes.py tests/strategy/test_micho150.py tests/api/test_portfolio_decisions.py tests/api/test_admin_data.py tests/api/test_scanner.py -q
```

Result: 57 passed. Later focused post-audit changes: 35 passed.

Full backend:

```powershell
$env:DEBUG='false'
.\run_checks.ps1
```

Result: Ruff PASS, format PASS, mypy PASS across 155 source files, pytest PASS
(302 tests).

Frontend:

```powershell
npm run lint
npm test -- --run
npm run build
```

Final result: ESLint PASS, 16 files / 64 tests PASS, production build PASS.
An intermediate full frontend rerun exposed one duplicate-alert regression after
placing monitoring on Portfolio Plan; it was fixed without weakening the
original error assertions, then the complete suite passed.

Migration/smoke:

```powershell
uv run alembic upgrade head
uv run alembic current
curl http://127.0.0.1:8000/api/v1/admin/data/scheduler
curl http://127.0.0.1:8000/api/v1/portfolio/current
curl http://127.0.0.1:8000/api/v1/portfolio/{id}/monitoring
```

Development and test databases reached `f41c8e2067ab (head)`. Scheduler/current/
monitoring endpoints returned HTTP 200. The real current legacy-imported
portfolio correctly returned UNAVAILABLE/null status with
`STRATEGY_PROFILE_UNKNOWN`, never fake HOLD.

Controlled Chrome headless browser acceptance at 1440px passed against the real
local backend: the persistent portfolio, allocation, Manage Portfolio workflow,
and Position Monitoring panel rendered stably. The current legacy positions
showed UNAVAILABLE with strategy-unknown reasons and NONE stop/trailing/target
facts. No provider or broker call occurred.

Pure controlled EMA and Micho acceptance covered every declared HOLD/ATTENTION/
SELL branch, including equality and strong-trend cases. Reconciliation acceptance
covered $10,000 + $2,000 cash, a 10-share external import, correction to 12 shares
at $102.40, three audit events, revision 3, and unchanged realized P&L. Scheduler
tests covered exact New York schedule/weekend progression and explicit no-new-
session behavior. Existing Scanner, Evaluate/identity, Strategy Profiles,
Strategy Lab, and Sprint 13 versioning/reproducibility suites passed in the full
gate.

## Product boundaries and limitations

No EMA20, HYBRID 2%, Micho BOTH/SMA150, RS20, Strategy Profile default,
portfolio sizing/risk, T+1, or Strategy Lab rule changed. No research-only stop
became active. Scheduled monitoring can latch guidance but cannot change cash or
quantity, auto-BUY/SELL, or submit a broker order.

Known limitations: no live broker/account source, no authentication/account
persistence, no tax lots, process-local scheduler status/lock, application
uptime is required, daily-candle data is not intraday/live, profile-unknown
positions cannot receive strategy guidance, and no distributed scheduling or
human SELL-latch override exists.

Sprint 17 proved deterministic backend-owned completed-session monitoring,
sticky exits, auditable reconciliation, safe shared sync orchestration, and UI
presentation work end to end. It did not prove production deployment reliability,
broker reconciliation, execution quality, or profitability.

## Git handoff

Current branch: `feature/position-monitoring`. The working tree contains only
local Sprint 17 modifications/untracked files listed above; nothing was committed
or pushed. `git diff --stat` before this report showed 23 tracked files changed,
797 insertions, and 21 deletions, plus the new files.

Recommended Sprint 18 direction: broker-integration preparation with a read-only,
authenticated account adapter and explicit reconciliation preview—still no order
submission—plus durable scheduler/run observability if deployment architecture
requires it.

Recommended commit message:

`feat: add persistent position monitoring and portfolio reconciliation`
