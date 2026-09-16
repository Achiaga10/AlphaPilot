# Sprint 28 — Production Operations, Health & Alerting

Status: **IMPLEMENTED LOCALLY — DETERMINISTIC IN-APP OBSERVATION**  
Date: 2026-09-15  
Base migration: `fa4edd0b0ef8`  
Migration: `c28a0f1b2d3e`  
Publication: **no commit, push, merge, tag or PR was performed**

## Outcome

AlphaPilot now has a persistent, backend-owned Operations domain that converts
existing operational evidence into deterministic incidents. It observes database
schema compatibility, stored market data, the Micho Forward engine, manual external
actions, Alpaca read-only sync/reconciliation, and relevant Micho/Forward position
quantities. It writes only `operational_incidents` and
`operational_incident_events`.

The monitor has no trading authority. It cannot submit, replace, cancel or close an
Alpaca order; cannot alter Micho decisions, Forward cash/equity/orders/positions/
fills/exits/allocation/P&L; and cannot change Portfolio Plan, EMA20, News,
ResearchPortfolio or Paper evidence. News and AI have no role in health evaluation.
Alert delivery is in-app only.

## Frozen operational semantics

### Lifecycle and identity

- Statuses: `OPEN`, `ACKNOWLEDGED`, `RESOLVED`.
- Severities: `INFO`, `WARNING`, `CRITICAL`.
- Stable active identity: `incident_type + source_domain + source_identity`.
- PostgreSQL uniqueness permits only one active occurrence of that identity.
- Advisory transaction lock `(2828, 1)` serializes evaluation/acknowledgement.
- Unchanged reevaluation updates `last_observed_at` but creates no duplicate row or
  audit-event spam.
- A material severity/summary/evidence change appends `UPDATED`.
- Acknowledgement appends `ACKNOWLEDGED` and does not resolve or suppress reevaluation.
- Clearing appends `RESOLVED`, nulls only the active key, and retains history.
- Recurrence creates a new row and increments `occurrence`; a resolved row is never
  silently reopened.

Database checks constrain valid statuses, severities, positive occurrence numbers,
active/resolved identity consistency, and event types.

### Overall health

| Active evidence | Overall health |
|---|---|
| One or more CRITICAL incidents | `DEGRADED` |
| No CRITICAL and one or more WARNING incidents | `ATTENTION` |
| INFO only or no incidents | `HEALTHY` |

Acknowledged incidents remain active for health calculation until their condition
clears.

### Severity policy

| Condition | Severity |
|---|---|
| Intentionally disabled Alpaca read-only sync | INFO |
| Upcoming external BUY/SELL | INFO |
| External execution awaiting record | INFO |
| Skipped execution | INFO |
| Unmatched outside activity | INFO |
| Paused Forward portfolio | INFO |
| Pending/stale/failed Forward work | WARNING |
| Missing/stale/failed market evidence | WARNING |
| Enabled but incomplete Alpaca configuration | WARNING |
| Failed/stale Alpaca read-only sync | WARNING |
| Overdue BUY | WARNING |
| Manual exit required | WARNING |
| Partial SELL execution | WARNING; partial BUY is INFO |
| Ambiguous match | WARNING |
| Entry execution conflict | WARNING |
| Ordinary position/quantity drift | WARNING |
| Meaningful price divergence (absolute difference >= 25 bps) | WARNING |
| Alpaca environment mismatch | CRITICAL |
| Overdue manual exit | CRITICAL |
| Exit/exposure execution conflict | CRITICAL |
| Execution after virtual cancellation | CRITICAL |
| Forward quantity zero but broker quantity positive for a relevant closed position | CRITICAL |

The 25 bps price threshold is an Operations noise threshold only. It does not change
Sprint 26 exact reconciliation facts or any execution economics.

### Trading-session deadlines

Manual-action overdue state is based on the latest authoritative stored completed SPY
session and the action's planned/actual virtual execution session. Wall-clock midnight,
weekends and calendar-day arithmetic do not independently make an action overdue. Once
the expected trading session is completed and no complete record, unique broker match,
or intentional skip resolves the action, a BUY becomes WARNING overdue and an exit
becomes CRITICAL overdue.

### Position drift

Drift is evaluated only when the selected Alpaca environment has a successful latest
run, that run remains within two configured polling intervals, and the most recent run
did not fail. Only symbols linked to Micho Forward positions/actions are considered.
An absent relevant symbol means broker quantity zero only within that complete fresh
snapshot. Unrelated Alpaca holdings never create drift incidents. With failed/stale/
missing broker evidence, drift is explicitly unknown/not evaluated and
`BROKER_SYNC_STALE` or the corresponding broker-health incident is authoritative.

## Incident catalog

Implemented types:

- System: `SCHEMA_MIGRATION_REQUIRED`.
- Forward: `FORWARD_ENGINE_FAILED`, `FORWARD_ENGINE_STALE`,
  `FORWARD_CYCLE_FAILED`, `FORWARD_PENDING_SESSIONS`,
  `FORWARD_PORTFOLIO_PAUSED`.
- Market: `MARKET_DATA_STALE`, `MARKET_DATA_MISSING`, `MARKET_SYNC_FAILED`.
- Broker: `BROKER_SYNC_FAILED`, `BROKER_SYNC_STALE`,
  `BROKER_SYNC_MISCONFIGURED`, `BROKER_SYNC_DISABLED`,
  `BROKER_ENVIRONMENT_MISMATCH`.
- External actions: `EXTERNAL_BUY_ACTION_UPCOMING`,
  `EXTERNAL_SELL_ACTION_UPCOMING`, `EXTERNAL_ACTION_AWAITING_RECORD`,
  `EXTERNAL_ACTION_OVERDUE`, `PARTIAL_EXTERNAL_EXECUTION`,
  `SKIPPED_EXTERNAL_EXECUTION`, `MANUAL_EXIT_ACTION_REQUIRED`,
  `MANUAL_EXIT_ACTION_OVERDUE`.
- Reconciliation: `BROKER_MATCH_AMBIGUOUS`, `BROKER_EXECUTION_CONFLICT`,
  `UNMATCHED_BROKER_ACTIVITY`, `EXECUTED_AFTER_VIRTUAL_CANCEL`,
  `QUANTITY_DIVERGENCE`, `PRICE_DIVERGENCE`.
- Position: `POSITION_QUANTITY_DRIFT`.

## Scheduling, startup and failure containment

`OperationsMonitorScheduler` starts after the market, Forward and broker schedulers,
runs immediately, then every 300 seconds by default. Its lock prevents overlapping
in-process runs; the database advisory lock protects multiple workers. A monitor
exception is contained as scheduler `FAILED` with a bounded operator message and does
not stop the other schedulers or application.

Startup/self-check facts expose:

- database reachability;
- expected and observed Alembic revision;
- schema compatibility;
- Forward scheduler initialization;
- broker configuration state;
- Operations monitor initialization.

Startup never applies migrations. If the Operations tables exist but the revision is
wrong, `SCHEMA_MIGRATION_REQUIRED` is CRITICAL. If the incident tables themselves are
absent, persistence is not possible; the contained monitor failure and structured
server log are the practical signal until deployment applies the migration.

## API

- `GET /api/v1/operations/health`
- `GET /api/v1/operations/incidents`
- `GET /api/v1/operations/incidents/{id}`
- `POST /api/v1/operations/incidents/{id}/acknowledge`
- `GET /api/v1/operations/daily-summary`
- `POST /api/v1/operations/evaluate`

Incident list filters support `status`, `severity`, `type`, and `source`. Invalid enum
filters return 422. Missing incidents return 404. Acknowledging a resolved incident
returns 409. There is no DELETE route.

The backend-owned daily summary contains overall health/counts; Forward status, cash,
equity, open positions, pending/latest sessions; expected manual BUY/SELL counts and
overdue count; broker environment/status/freshness; unmatched/ambiguous/conflict
counts; and position-drift count.

The generic `/api/v1/health/` contract is unchanged.

## User interface

The Dashboard now starts with an Operations Center. It provides:

- prominent HEALTHY/ATTENTION/DEGRADED state and severity counts;
- critical-first, then warning, then info attention ordering;
- compact Forward and Alpaca read-only health summaries;
- incident summary, source, occurrence, last-observed time and evidence;
- audited acknowledgement with a required reason;
- explicit fresh/unknown position-drift state and quantity comparison;
- retained resolved-incident history;
- an explicit observational/no-trading-authority boundary.

There are no order-entry, cancel, replace, close/liquidate, notification, or "safe to
trade" controls.

## Migration verification

Migration `c28a0f1b2d3e` descends from Sprint 27 `fa4edd0b0ef8` and adds:

- `operational_incidents`;
- `operational_incident_events`;
- supporting uniqueness, indexes and check constraints.

Verification used `ALPHAPILOT_MIGRATION_USE_TEST_DATABASE=true` only:

1. `fa4edd0b0ef8 -> c28a0f1b2d3e` upgrade passed.
2. `c28a0f1b2d3e -> fa4edd0b0ef8` downgrade passed.
3. Re-upgrade to `c28a0f1b2d3e` passed.
4. `alembic check` reported: `No new upgrade operations detected.`

The development database was not migrated.

## Verification and test hygiene

Baseline inventory before Sprint 28:

- backend: 695 tests, mypy 215 source files;
- frontend: 106 tests across 19 files.

Final focused verification:

- backend Operations/service/scheduler/API: **20 passed**;
- frontend Operations Center plus Dashboard integration: **12 passed** (3 new
  Operations tests and 9 preserved Dashboard tests).

Final full verification:

- `DEBUG=false .\run_checks.ps1`: Ruff passed; format passed; mypy passed across
  **220 source files**; **715 tests passed**.
- frontend lint: passed with zero lint warnings;
- frontend test suite: **109 tests passed across 20 files**;
- frontend production build: passed; 117 modules transformed.

No tests were deleted, consolidated, skipped, xfailed, weakened, or changed merely to
hide a failure. All 695 backend and 106 frontend baseline tests remain. Sprint 28 adds
20 backend tests and 3 frontend tests. Existing non-failing React `act(...)` and MSW
diagnostic stderr from pre-existing suites remains a known test-harness warning; it did
not fail either baseline or final suites.

Coverage exercised healthy/info health, warning/critical escalation, 20 repeated
evaluations, material update, concurrent evaluators, acknowledgement persistence,
resolution and recurrence, completed-session BUY/EXIT deadlines, awaiting/partial/
skipped/cancelled/diverged/conflict mappings, fresh-snapshot missing-symbol zero,
closed-Forward/open-broker drift, stale suppression, scheduler containment, API
filters/errors/no-delete, UI loading/health/critical/acknowledgement/drift/history.

## Real browser acceptance

A separate FastAPI server explicitly refused the development database and used only
`TEST_DATABASE_URL`; Vite ran on a separate port. Deterministic TEST-only scenario
evidence exercised the real API/persistence/UI path without contacting Alpaca or any
external provider.

Controlled Edge/Playwright acceptance passed for:

1. WARNING `BROKER_SYNC_MISCONFIGURED`;
2. CRITICAL `BROKER_ENVIRONMENT_MISMATCH` and DEGRADED health;
3. UI acknowledgement and retained ACKNOWLEDGED active state;
4. recovery to HEALTHY after a newer matching-environment observation;
5. resolved occurrence history;
6. broker-disabled INFO without health degradation;
7. unknown/not-evaluated drift when no fresh authoritative snapshot exists;
8. visible observational/no-authority boundary.

Artifacts (ignored by Git) are under `backend/backtest_reports/sprint28/`:

- `operations-degraded.png`
- `operations-acknowledged.png`
- `operations-recovered.png`
- contained backend/frontend acceptance logs

Optional real Alpaca PAPER observation was not run because it requires live account
credentials and external state. Existing Sprint 27 fake-provider tests remained in the
715-test full gate; no broker mutation was attempted.

## Acceptance examples

- Healthy: only `BROKER_SYNC_DISABLED` INFO is active; overall is HEALTHY.
- Forward stale: completed stored sessions remain pending beyond two hourly Forward
  intervals; `FORWARD_PENDING_SESSIONS` and `FORWARD_ENGINE_STALE` are WARNING. A
  successful catch-up resolves both.
- Broker stale: enabled/configured sync has no fresh successful snapshot;
  `BROKER_SYNC_STALE` is WARNING and drift is unknown. A fresh successful run resolves
  stale and re-enables drift evaluation.
- BUY upcoming: expected session is later than latest completed session; INFO.
- BUY overdue: expected session is now completed with no complete evidence/skip;
  WARNING.
- Exit required: unresolved SELL action exists; WARNING.
- Exit overdue: expected SELL session is completed without resolution; CRITICAL and
  overall DEGRADED.
- Matching fill resolves exit: linked complete broker evidence makes the external case
  recorded; the required/overdue incidents resolve on evaluation.
- Conflict: entry disagreement is WARNING; SELL/exposure disagreement is CRITICAL.
- Drift: Forward 100 / Alpaca 95 on a fresh snapshot is WARNING.
- Closed/open exposure: Forward 0 / Alpaca positive for a relevant closed symbol is
  CRITICAL.

## Exact completion answers

1. Sprint name: Production Operations, Health & Alerting.
2. Automatic trading added: **NO**.
3. Operations monitor can submit orders: **NO**.
4. Incidents can change Micho decisions: **NO**.
5. Incidents can change Forward economics: **NO**.
6. Persistence: `operational_incidents` and append-only audit events.
7. Statuses: OPEN, ACKNOWLEDGED, RESOLVED.
8. Severities: INFO, WARNING, CRITICAL.
9. Incident types: all 27 types listed in the Incident catalog above.
10. Severity mapping: frozen in the Severity policy table above.
11. Dedup key: incident type + source domain + source identity.
12. Recurrence: new row with incremented occurrence.
13. Resolution: condition absent on authoritative reevaluation.
14. Acknowledgement: audited active status; it does not resolve.
15. Health states: HEALTHY, ATTENTION, DEGRADED.
16. Calculation: CRITICAL -> DEGRADED; else WARNING -> ATTENTION; else HEALTHY.
17. Forward stale: pending stored sessions plus no success within two scheduler intervals.
18. Broker stale: no authoritative success within two broker intervals, or latest run failed.
19. BUY overdue: expected trading session completed and action remains unresolved.
20. EXIT overdue: same deadline, CRITICAL.
21. Drift: exact relevant-symbol Forward quantity versus fresh Alpaca snapshot quantity.
22. Stale broker drift: unknown/not evaluated.
23. Conflict: entry WARNING; exit/exposure CRITICAL.
24. Ambiguous match: WARNING.
25. Unmatched activity: INFO by default.
26. Disabled broker critical/noise: **NO**; one deduplicated INFO occurrence.
27. News contributes to health authority: **NO**.
28. EMA20 operational trade alerts added: **NO**.
29. Alpaca remains read-only: **YES**.
30. Alpaca non-GET network operations added: **NO**.
31. Credentials exposed: **NO**.
32. Daily summary fields: health/counts, Forward operations, manual actions, broker
    health, reconciliation counts, drift and latest sessions.
33. Startup check: database/schema/Forward scheduler/broker configuration/monitor.
34. Automatic migrations: **NO**.
35. Scheduler frequency: immediate startup then every 300 seconds.
36. Concurrency: in-process lock, PostgreSQL advisory lock and unique active key.
37. Repeated evaluation: one row; no unchanged event spam.
38. Restart: incidents/history are database durable; evaluation resumes idempotently.
39. Healthy example: disabled broker INFO only.
40. Forward stale example: pending session plus old/no successful Forward cycle.
41. Broker stale example: enabled broker snapshot older than 600 seconds at defaults.
42. BUY upcoming example: expected session after latest completed session.
43. BUY overdue example: expected session completed, no complete record/match/skip.
44. Exit-required example: unresolved Forward SELL external case.
45. Exit-overdue example: unresolved SELL after completed expected session -> CRITICAL.
46. Matching-fill recovery: complete unique match makes case recorded; exit alerts resolve.
47. Conflict example: manual and Alpaca execution facts differ.
48. Position-drift example: Forward 100 versus Alpaca 95 -> WARNING.
49. Forward closed/broker open: Forward 0 versus Alpaca positive -> CRITICAL.
50. Focused backend: **20 passed**.
51. Full backend: **715 passed**, Ruff/format and mypy passed.
52. Focused frontend: **12 passed**.
53. Full frontend: **109 passed across 20 files**.
54. Build: **passed**.
55. Browser: **passed** for DEGRADED/WARNING/ack/recovery/history/INFO.
56. Optional real PAPER observation: **not run**; external credentials/state avoided.
57. Migration created: **YES**.
58. Revision: `c28a0f1b2d3e`, down revision `fa4edd0b0ef8`.
59. Development database migrated: **NO**.
60. ResearchPortfolio mutated: **NO**.
61. Paper mutated: **NO**.
62. Forward economic acceptance mutation: **NO**.
63. Broker mutations/network writes: **NO**.
64. Test-hygiene audit completed: **YES**.
65. Obsolete tests deleted: **0**.
66. Tests consolidated: **0**.
67. Backend before/after: 695 -> 715 tests; 215 -> 220 mypy source files.
68. Frontend before/after: 106/19 files -> 109/20 files.
69. New skips/xfails: **0**.
70. Weakened assertions: **0**.
71. Created files: listed in Files changed below.
72. Modified files: listed in Files changed below.
73. Branch/HEAD: `research/ema20-loss-control` at
    `3991fbb10a2e23c79c8bb45d3d96a77ea8c9c305`.
74. Git status: intentionally dirty with Sprint 28 modified/untracked files; ready for
    user review and commit.
75. Sprint 28 commit performed: **NO**.
76. Sprint 28 push performed: **NO**.
77. Known limitations: listed below.
78. Next step: user reviews, commits/pushes if desired; Sprint 29 requires a new request.

## Files changed

Created and ready to commit:

- `backend/migrations/versions/c28a0f1b2d3e_add_production_operations_incidents.py`
- `backend/scripts/run_sprint28_acceptance_server.py`
- `backend/scripts/sprint28_acceptance_scenario.py`
- `backend/src/alphapilot/api/routes/operations.py`
- `backend/src/alphapilot/database/models/operations.py`
- `backend/src/alphapilot/schemas/operations.py`
- `backend/src/alphapilot/services/operations_monitor.py`
- `backend/src/alphapilot/services/operations_scheduler.py`
- `backend/tests/api/test_operations.py`
- `backend/tests/services/test_operations_monitor.py`
- `backend/tests/services/test_operations_scheduler.py`
- `frontend/scripts/sprint28-operations-real-smoke.mjs`
- `frontend/src/api/operations.ts`
- `frontend/src/features/dashboard/OperationsCenter.tsx`
- `frontend/src/features/dashboard/OperationsCenter.test.tsx`
- `frontend/src/hooks/useOperationsApi.ts`
- `frontend/src/types/operations.ts`
- `docs/sprints/SPRINT_28_PRODUCTION_OPERATIONS.md`

Modified and ready to commit:

- `AGENTS.md`
- `backend/.env.example`
- `backend/migrations/env.py`
- `backend/src/alphapilot/api/router.py`
- `backend/src/alphapilot/core/config.py`
- `backend/src/alphapilot/core/lifespan.py`
- `backend/src/alphapilot/database/models/__init__.py`
- `backend/tests/conftest.py`
- `docs/DECISIONS.md`
- `docs/PROJECT_STATE.md`
- `frontend/package.json`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/styles.css`
- `frontend/src/test/server.ts`

Ignored acceptance artifacts are not ready to commit and remain under
`backend/backtest_reports/sprint28/`.

Recommended commit message:

```text
feat(operations): add deterministic production health monitoring
```

## Known limitations

- Alerts are in-app only; there is no email, SMS, push, webhook or paging integration.
- Polling is five-minute scheduled evaluation, not streaming or websocket monitoring.
- Daily summary is generated from current durable facts; it is not a separate historical
  daily-snapshot table.
- A missing Operations table cannot persist its own migration-required incident; startup
  failure/logging is the fallback until deployment applies the migration.
- Acknowledgement records a reason and generic `USER` source because authentication/user
  identity is not yet a project domain.
- Price-divergence incident noise suppression is fixed at 25 bps while exact Sprint 26
  reconciliation remains visible at every nonzero difference.
- Market staleness requires authoritative scheduler evidence of a newer completed
  session, avoiding weekend/holiday inference without adding an exchange calendar.
- Incident history has no retention/archive policy yet.
- Real Alpaca PAPER observation was intentionally not performed in Sprint 28 acceptance.

## Final boundary

Sprint 28 is complete locally. No Git publication was performed. Sprint 29 was not
started.
