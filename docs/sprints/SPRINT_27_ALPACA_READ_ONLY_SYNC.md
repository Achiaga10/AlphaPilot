# Sprint 27 — Alpaca Read-Only Broker Synchronization

Status: **IMPLEMENTED LOCALLY — ZERO TRADING AUTHORITY**  
Date: 2026-09-15  
Base: Sprint 26 migration `f650e3a238a0`  
Migration: `fa4edd0b0ef8`  
Publication: no commit, push, merge, tag or PR was performed

## Outcome

AlphaPilot can now read an explicitly configured Alpaca account and preserve the
provider's account, position, order and fill facts as a separate observational
domain. The integration defaults to disabled and `PAPER`. Its broker adapter has
GET methods only; it has no submit, cancel, replace, close or liquidation surface.

Imported fills can populate Sprint 26 external-execution evidence without changing
the controlled Micho Forward experiment. Automatic matching is deliberately narrow:
same symbol, same BUY/SELL side, the exact expected execution date in New York,
exactly one broker-order group, and exactly one eligible external case. Ambiguous and outside-Forward activity remains
unlinked. Users can explicitly link, unlink/rematch or ignore evidence, with a reason,
request-key idempotency and immutable audit event for each action.

Alpaca observations are canonical only for reporting what the broker observed.
Existing manual records remain preserved. Matching facts are not double-counted;
different facts become a visible `CONFLICT` / `BROKER_CONFLICT`. All broker financial
facts and quantities are Decimal, including fractional shares. Unknown fees remain
null and net external-execution P&L remains unavailable until both trade sides are
complete, quantities match and all fees are known.

## Frozen safety boundary

- Real order entry remains entirely manual in Alpaca.
- The adapter's normal broker network operations use `GET` only.
- No broker mutation endpoint, method, SDK trading object or UI control exists.
- Broker snapshots never write Forward cash, equity, allocation, capacity, orders,
  positions, virtual fills, trades, exits, P&L or analytics.
- Micho signals/rules, EMA20 semantics, Portfolio Plan, News, ResearchPortfolio and
  Paper evidence are unchanged.
- EMA20 has no Sprint 25 Forward order and therefore cannot produce a Sprint 27
  automatic reconciliation case.
- Broker divergence is evidence only and cannot retune Micho or its 5 bps model.

## Configuration and scheduling

Backend-only settings:

```text
ALPACA_SYNC_ENABLED=false
ALPACA_ENVIRONMENT=PAPER
ALPACA_API_KEY=<local secret>
ALPACA_SECRET_KEY=<local secret>
ALPACA_SYNC_INTERVAL_SECONDS=300
ALPACA_SYNC_INITIAL_LOOKBACK_DAYS=14
ALPACA_SYNC_OVERLAP_MINUTES=10
ALPACA_SYNC_TIMEOUT_SECONDS=30
```

Credentials come from the existing settings/environment mechanism, are never
hardcoded, logged, returned by the API or exposed to React. `LIVE` is technically
readable only through an explicit environment setting; PAPER remains the default.

The broker scheduler is separate from the Sprint 25 Forward scheduler. When enabled,
it runs once at application startup and every 300 seconds thereafter. First sync reads
only the most recent 14 days. Later syncs start from the last successful high watermark
minus a 10-minute overlap. Database uniqueness makes the overlap replay-safe. Disabled
and misconfigured states do not prevent startup. Provider/rate-limit/network failures
produce a durable failed run, do not tight-loop, retain the last successful snapshot,
and do not affect Forward processing or manual recording.

## Persistence and identity

Migration `fa4edd0b0ef8` adds:

- `broker_sync_runs`: each attempt, environment, requested window, watermark, status,
  counts and bounded error information.
- `broker_account_snapshots`: immutable account facts per successful sync run.
- `broker_position_snapshots`: immutable current-position facts per run and symbol.
- `broker_order_observations`: current durable order observation, updated idempotently.
- `broker_executions`: immutable fill/activity fact plus current reconciliation state.
- `broker_execution_match_events`: immutable audit of link/unlink/rematch/ignore.

Orders are unique by `(environment, broker_order_id)`. Executions are unique by
`(environment, broker_activity_id)`. Account snapshots are unique per sync run,
positions per `(sync_run_id, symbol)`, and match requests per
`(execution_id, request_key)`. PostgreSQL advisory lock `(2727, 1)` serializes broker
sync with manual journal writes; existing per-Forward-portfolio locks remain intact.

## API and user interface

Read APIs:

- `GET /api/v1/broker/alpaca/status`
- `GET /api/v1/broker/alpaca/account`
- `GET /api/v1/broker/alpaca/positions`
- `GET /api/v1/broker/alpaca/orders`
- `GET /api/v1/broker/alpaca/activity`
- `GET /api/v1/broker/alpaca/unmatched`

Application-only observation/reconciliation commands:

- `POST /api/v1/broker/alpaca/sync`
- `POST /api/v1/broker/alpaca/activity/{id}/manual-match`
- `POST /api/v1/broker/alpaca/activity/{id}/rematch`
- `POST /api/v1/broker/alpaca/activity/{id}/unlink`
- `POST /api/v1/broker/alpaca/activity/{id}/ignore`

These POST routes only update AlphaPilot observation/audit state. They never send a
non-GET request to Alpaca.

The Forward operations console now shows `ALPACA — READ ONLY`, PAPER/LIVE identity,
health/freshness/error data, account snapshot, observed counts, Forward-vs-Alpaca
positions, unmatched/ambiguous activity, provenance and explicit audited resolution
controls. It contains no broker BUY, SELL, cancel, replace, close or liquidate control.
The Sprint 26 manual journal remains available and labels canonical source and match
state while retaining all user-entered history.

## Matching and reconciliation details

Imported fills start as `UNMATCHED`. Eligible cases must have the exact symbol and
BUY/SELL side and an expected date equal to the fill's `America/New_York` calendar
date. The expected date is the virtual `actual_execution_session`, falling back to
`planned_execution_session`. Exactly one broker-order group and one candidate become
`AUTO_MATCHED`; multiple same-window broker order groups or multiple Forward cases
become `AMBIGUOUS`; zero candidates become `UNMATCHED` with
`OUTSIDE_FORWARD_OR_EXECUTION_WINDOW`. No score, proximity tolerance, AI, News or
quantity guess is used.

Manual matching requires compatible ticker and side plus explicit confirmation,
reason and request key. Unlink returns the execution to `UNMATCHED`, after which it may
be rematched; ignore produces `IGNORED_EXTERNAL`. Each transition is audited.

All fills for a linked action contribute to broker quantity, notional and
quantity-weighted price. An observed order is complete only when its Alpaca order
status is `FILLED`; otherwise available fills are partial. `REJECTED` and `CANCELED`
zero-fill orders remain order observations and create no execution fact. Broker values
are canonical for external reporting whenever linked. Manual facts are retained and
compared; equality prevents double counting, while quantity or notional disagreement
surfaces a conflict and preserves both sources without blending them.

Closed-trade comparison remains complete-only: linked entry and exit must both be
complete, recorded quantities must match, and every fee must be known before net
broker-observed execution P&L is calculated. Gross facts may remain visible when fees
are unavailable, but net P&L and dependent differences are null—not fabricated zero.
These metrics are external-execution analytics, never Micho Forward performance.

## Verification

### Database and migration

- Confirmed lineage `f650e3a238a0 -> fa4edd0b0ef8`.
- Applied the migration only to `TEST_DATABASE_URL`.
- Verified downgrade to `f650e3a238a0` and upgrade back to `fa4edd0b0ef8`.
- Constraints and repeat/concurrent import behavior passed.
- Development database was not migrated or mutated.

### Backend

- Focused broker/scheduler/Forward selection: **33 passed**.
- Full `backend/run_checks.ps1`: Ruff pass, format pass, mypy pass across 215 source
  files, **695 tests passed**.
- GET-only regression exercised account, positions, orders, fills and clock and saw
  only `GET`; the adapter exposes none of the prohibited mutation method names.
- Ten repeated imports retained exactly the same two native fill identities with no
  duplicates; concurrent sync retained one execution and unchanged Forward
  cash/equity/realized P&L/revision.
- Explicit cases cover disabled/misconfigured/failure retention, full/multiple/
  partial/fractional fills, price and quantity divergence, rejected/canceled orders,
  ambiguous/outside activity, same/different manual facts, audited manual resolution,
  API contracts, scheduler isolation and Forward independence.

### Frontend and browser

- Focused Forward/external/Alpaca panels: **6 passed** across 3 files.
- Full frontend: lint pass, **106 tests passed across 19 files**, production build pass.
- Controlled Edge acceptance used real FastAPI, real Vite, a TEST-only database and a
  fake Alpaca provider. It displayed the PAPER read-only panel, account and position
  evidence, imported two broker executions, auto-matched one exact fill, left one
  outside fill unmatched, manually linked it through explicit UI confirmation, exposed
  provenance, and showed no broker mutation control. Forward cash, equity, realized
  P&L and revision were byte-for-byte unchanged before/after.
- Additional backend/API and rendered-component tests cover partial, ambiguous,
  conflict, failure retention, manual fallback and complete-only comparison states.
- Temporary acceptance server/seed/runner files were removed after the test.

### Optional real PAPER read smoke

Local credentials were configured, environment was explicitly `PAPER`, and automatic
sync remained disabled. A count-only adapter smoke succeeded using account, positions,
orders and FILL-activity GETs: `positions=10`, `orders=24`, `fills=61`. No balances,
identifiers or secrets were printed; no database write and no broker mutation occurred.

## Test suite hygiene

The audit used the Sprint 26 HEAD as the before inventory and reviewed historical News,
EMA20 approval/manual-stop, final-actionability, Portfolio/Forward, execution, Paper,
research, API, idempotency and concurrency tests against current decisions and source.
No permanent test was confirmed obsolete, unreachable or semantically duplicated.
Uncertain and still-protective research/history tests were retained as required.

| Inventory | Before | After |
|---|---:|---:|
| Backend test files | 99 | 101 |
| Backend syntactic test functions | 526 | 539 |
| Backend collected tests | 681 | 695 |
| Frontend test files | 18 | 19 |
| Frontend syntactic test declarations | 97 | 99 |
| Frontend executed tests | 104 | 106 |

- Deleted permanent test files: **0**.
- Removed backend tests: **0**.
- Removed frontend tests: **0**.
- Consolidated tests: **0**.
- Replacement tests added for deleted coverage: **0**.
- New Sprint 27 regression cases: **14 backend**, **2 frontend**.
- Production behavior changed because of hygiene deletion: **no**.

The temporary real-server/browser scaffolding and count-only PAPER smoke helper were
deleted after use because they were run-specific harnesses, not permanent tests. No
skip/xfail, weakened assertion, CI exclusion or deletion-to-green was introduced.

## Required final report — 74 answers

1. **Sprint name:** Sprint 27 — Alpaca Read-Only Broker Synchronization.
2. **Is Alpaca connected?** YES—the PAPER adapter completed a live read-only smoke;
   scheduled sync remains locally disabled by default.
3. **Is integration READ-ONLY?** YES.
4. **Can AlphaPilot submit a BUY?** NO.
5. **Can AlphaPilot submit a SELL?** NO.
6. **Can AlphaPilot cancel a broker order?** NO.
7. **Can AlphaPilot close a broker position?** NO.
8. **Broker HTTP methods:** GET only for account, positions, orders, FILL activities
   and clock.
9. **Default broker environment:** PAPER.
10. **Credential source/handling:** backend settings from local environment/`.env`;
    never hardcoded, logged, persisted in sync tables or included in reports.
11. **Credentials exposed to frontend?** NO.
12. **Does the application work with Alpaca disabled?** YES.
13. **Does Forward processing depend on Alpaca?** NO.
14. **Can Alpaca alter Forward cash?** NO.
15. **Can Alpaca alter Forward positions?** NO.
16. **Can Alpaca alter Micho decisions?** NO.
17. **Can Alpaca automatically populate external execution evidence?** YES.
18. **Is manual Sprint 26 recording preserved?** YES.
19. **Exact provenance values:** `ALPACA_READ_ONLY_SYNC` and
    `MANUAL_USER_RECORDED`; `NONE` is the typed canonical-source value when no
    execution evidence exists.
20. **Persistence design:** durable sync runs; immutable account and position snapshots;
    idempotently updated current order observations; immutable broker executions with
    match metadata; immutable match-transition events.
21. **Migration:** `fa4edd0b0ef8`, down revision `f650e3a238a0`.
22. **Deduplication identity:** order `(environment, broker_order_id)`; execution
    `(environment, broker_activity_id)`; manual transition
    `(execution_id, request_key)`.
23. **Sync frequency/default:** immediate startup run and every 300 seconds when
    enabled; disabled by default.
24. **Initial lookback:** 14 days; subsequent reads overlap the high watermark by 10
    minutes.
25. **Match rules:** exact symbol, exact BUY/SELL side, exact expected New York
    session date, and one broker-order group; deterministic and no AI/News/proximity
    score.
26. **Auto-match criteria:** exactly one broker-order group and exactly one eligible
    Sprint 26 external case under those rules, with no different broker order already
    linked to that case.
27. **Ambiguous behavior:** state `AMBIGUOUS`, reason `MULTIPLE_FORWARD_CASES`,
    `MULTIPLE_BROKER_ORDER_GROUPS` or `DISTINCT_BROKER_ORDER_ALREADY_LINKED`; no
    automatic link.
28. **Unmatched behavior:** preserve execution as `UNMATCHED` /
    `OUTSIDE_FORWARD_OR_EXECUTION_WINDOW`; create no Forward artifact.
29. **Manual link:** explicit confirmed request with compatible ticker/side, reason and
    idempotency key; result `MANUAL_MATCHED` with an audit event.
30. **Manual unlink/rematch:** explicit confirmed, reasoned, idempotent unlink returns
    to `UNMATCHED`; the same evidence may then be explicitly rematched. History remains.
31. **Manual-vs-Alpaca conflict:** retain both, use broker facts as canonical external
    facts, mark `CONFLICT` / `BROKER_CONFLICT`, never blend or overwrite.
32. **Partial fills:** preserve every native fill; aggregate Decimal quantity/notional
    and weighted price; remain partial until the associated order is `FILLED`.
33. **Rejected order:** retain `REJECTED` order observation; with zero fills, create no
    execution/reconciliation record.
34. **Canceled order:** retain `CANCELED` order observation; with zero fills, create no
    execution/reconciliation record. Any real fill activity remains separately factual.
35. **Unknown fee:** `null`, never zero.
36. **Weighted-fill authority:** linked Alpaca fills are authoritative for external
    reporting; weighted price is exact sum(quantity × price) / sum(quantity), Decimal.
37. **P&L semantics:** calculate external net only for complete linked entry and exit,
    equal quantities and fully known fees; compare it with, but never replace, Forward
    modeled P&L.
38. **Incomplete values null rather than zero?** YES.
39. **Does broker data contaminate Forward analytics?** NO.
40. **Does broker divergence retune Micho?** NO.
41. **Did Micho technical semantics change?** NO.
42. **Did Micho Forward semantics change?** NO.
43. **Did EMA20 semantics change?** NO.
44. **Does EMA20 produce Sprint 27 auto-reconciliation cases?** NO; Sprint 27 creates
    no EMA20 Forward order.
45. **Is News advisory-only?** YES.
46. **Broker API mutations during tests?** NO.
47. **Development DB migrated?** NO.
48. **ResearchPortfolio mutated?** NO.
49. **Paper evidence mutated?** NO.
50. **Current Forward evidence mutated?** NO.
51. **Focused backend:** 33 passed.
52. **Full backend:** Ruff/format/mypy passed; 695 tests passed.
53. **Focused frontend:** 6 passed across 3 files.
54. **Full frontend:** lint passed; 106 tests across 19 files passed.
55. **Build:** production TypeScript/Vite build passed.
56. **Browser acceptance:** PASS on real FastAPI + Vite + Edge + TEST DB + fake
    provider; PAPER read-only flow, auto/manual match and Forward isolation verified.
57. **Optional Alpaca PAPER smoke:** PASS; account read succeeded and count-only result
    was 10 positions, 24 recent orders and 61 recent fills.
58. **GET-only safety test:** PASS; all five read surfaces emitted GET and prohibited
    mutation method names were absent.
59. **Repeated-sync idempotency:** PASS; ten syncs retained the same two execution
    identities with no duplicates.
60. **Concurrent sync:** PASS; concurrent workers retained one execution and unchanged
    Forward economics.
61. **Example auto-match:** one AAA BUY fill on the exact expected date with one AAA
    BUY case became `AUTO_MATCHED`.
62. **Example partial fill:** a 40-share fill on a partially-filled order remained
    `PARTIALLY_RECORDED`; fractional 40.5 shares also remained exact Decimal.
63. **Example unmatched:** an AAA BUY dated outside the Forward execution window stayed
    `UNMATCHED` / `OUTSIDE_FORWARD_OR_EXECUTION_WINDOW`.
64. **Example ambiguous:** two compatible AAA BUY cases caused the imported fill to
    remain unlinked as `AMBIGUOUS`.
65. **Example conflict:** manual 100 @ 100.60 versus Alpaca 99 @ 100.70 retained both and
    surfaced `BROKER_CONFLICT` with Alpaca canonical for broker reporting.
66. **Files created:**
    `backend/migrations/versions/fa4edd0b0ef8_add_alpaca_read_only_broker_sync.py`;
    `backend/src/alphapilot/api/routes/broker_alpaca.py`;
    `backend/src/alphapilot/broker/__init__.py`;
    `backend/src/alphapilot/broker/alpaca_read_only.py`;
    `backend/src/alphapilot/database/models/broker_sync.py`;
    `backend/src/alphapilot/schemas/broker_sync.py`;
    `backend/src/alphapilot/services/broker_sync.py`;
    `backend/src/alphapilot/services/broker_sync_scheduler.py`;
    `backend/tests/broker/test_alpaca_read_only_sync.py`;
    `backend/tests/services/test_broker_sync_scheduler.py`;
    `frontend/src/features/dashboard/AlpacaReadOnlyPanel.tsx`;
    `frontend/src/features/dashboard/AlpacaReadOnlyPanel.test.tsx`;
    `docs/sprints/SPRINT_27_ALPACA_READ_ONLY_SYNC.md`.
67. **Files modified:** `AGENTS.md`; `docs/PROJECT_STATE.md`; `docs/DECISIONS.md`;
    `backend/migrations/env.py`; `backend/src/alphapilot/api/router.py`;
    `backend/src/alphapilot/core/config.py`; `backend/src/alphapilot/core/lifespan.py`;
    `backend/src/alphapilot/database/models/__init__.py`;
    `backend/src/alphapilot/database/models/external_execution.py`;
    `backend/src/alphapilot/schemas/external_execution.py`;
    `backend/src/alphapilot/services/external_execution.py`;
    `backend/tests/conftest.py`; `backend/tests/portfolio/test_forward_portfolio.py`;
    `frontend/src/api/forwardPortfolio.ts`;
    `frontend/src/features/dashboard/ExternalExecutionPanel.test.tsx`;
    `frontend/src/features/dashboard/ExternalExecutionPanel.tsx`;
    `frontend/src/features/dashboard/ForwardPortfolioPanel.test.tsx`;
    `frontend/src/features/dashboard/ForwardPortfolioPanel.tsx`;
    `frontend/src/hooks/usePortfolioApi.ts`; `frontend/src/test/server.ts`;
    `frontend/src/types/forwardPortfolio.ts`.
68. **Git branch/HEAD:** `research/ema20-loss-control` at
    `3de7d32a08542a85c2c2eb11b2a1fb614b77377d`; `origin/main` was
    `f2b94262ea15ce9eba550d5a2cc28a8e1b73bd0b` at final inspection.
69. **Git status:** dirty only with the Sprint 27 files listed in answers 66–67; no
    unrelated pre-existing change was present.
70. **Commit?** NO.
71. **Push?** NO.
72. **Known limitations:** provider availability/rate limits; five-minute rather than
    real-time polling; bounded history; fees may be absent; manual and broker facts may
    conflict; outside trades may stay unmatched; observations do not prove compliance;
    daily-candle Forward modeling may intentionally differ from broker execution;
    broker/Forward portfolios may diverge; no automatic trading or broker mutation.
73. **Safe post-review deployment:** user publishes/merges after review, pulls clean
    main, verifies the target without printing secrets, backs it up, applies migration
    `fa4edd0b0ef8`, configures PAPER credentials locally, explicitly enables sync,
    starts services, checks health, triggers/observes a read sync, then resolves any
    unmatched activity. Commands are below.
74. **Recommended next step:** review this diff and acceptance evidence, then commit and
    publish Sprint 27; deploy to PAPER read-only observation and monitor before proposing
    any Sprint 28 work.

## Safe user-run deployment runbook

Run only after reviewing, committing and publishing Sprint 27 yourself:

```powershell
# Publication (use the branch name/merge workflow you approve)
git status --short --branch
git add AGENTS.md docs backend frontend
git commit -m "feat(broker): add read-only Alpaca reconciliation"
git push -u origin HEAD

# On the deployment checkout
git switch main
git pull --ff-only
cd backend
$env:DEBUG='false'

# Print host/port/database only; never print username/password/query values
uv run python -c "from urllib.parse import urlsplit; from alphapilot.core.config import settings; u=urlsplit(str(settings.DATABASE_URL).replace('+asyncpg','')); print({'host':u.hostname,'port':u.port,'database':u.path.lstrip('/')})"

# Back up with your approved PostgreSQL credential mechanism before migration.
# Example shape only; replace the connection placeholder locally:
pg_dump --format=custom --file .\backups\alphapilot-pre-sprint27.dump --dbname "<deployment PostgreSQL URI>"

uv run alembic current
uv run alembic upgrade fa4edd0b0ef8
uv run alembic current
```

Set the following only in the backend's local secret environment (do not commit it):

```text
ALPACA_API_KEY=<paper key>
ALPACA_SECRET_KEY=<paper secret>
ALPACA_ENVIRONMENT=PAPER
ALPACA_SYNC_ENABLED=true
```

Then start the normal backend/frontend processes and verify:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/broker/alpaca/status
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/broker/alpaca/sync
Invoke-RestMethod http://127.0.0.1:8000/api/v1/broker/alpaca/status
Invoke-RestMethod http://127.0.0.1:8000/api/v1/broker/alpaca/unmatched
```

Confirm the returned environment is `PAPER`, review stale/error fields and inspect
unmatched/ambiguous activity in the UI. These application POSTs trigger a GET-only
broker read or local reconciliation; they do not place or modify orders.

## Stop boundary

Sprint 27 is complete locally. Do not start Sprint 28, automatic trading, broker
notifications, new strategy work or strategy tuning without a new reviewed request.
