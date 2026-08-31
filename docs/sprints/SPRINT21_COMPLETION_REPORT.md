# AlphaPilot Sprint 21 Completion Report

## Outcome

Sprint 21 — Daily Portfolio Manager / Trading Command Center — completed successfully
on local branch `feature/daily-portfolio-manager`. Dashboard is now a read-only,
backend-owned workflow over existing portfolio and research authorities. No strategy
rule, research parameter, portfolio constraint, database schema, or broker behavior
changed. Sprint 22 was not started.

## Architecture

`DailyPortfolioBriefService` is a derived orchestration/projection boundary:

```text
Research portfolio valuation + revision
  + Position Intelligence / stored monitoring / sticky SELL
  + StopExitGuidance
  + completed-session freshness and scheduler status
  + frozen Strategy Profiles through PortfolioDecisionOrchestrator
  + existing ExecutionReadiness
  -> typed DailyPortfolioBrief
  -> read-only API
  -> Dashboard / deterministic Copilot explanation
```

No financial logic is duplicated in React or a new daily calculation engine. The
service delegates valuation, indicators, strategy signals, RS20, ranking, ATR, sizing,
constraints, exit monitoring, and execution readiness to existing backend owners. It
stores no new daily state.

The narrow `PortfolioDecisionOrchestrator` extension is the default-preserving
`evaluate_existing_position_exits` option. Normal Portfolio Plan calls retain `True`.
Daily opportunity projections pass `False`, so one profile's opportunity scan cannot
reinterpret holdings entered under another profile or use simulated SELL proceeds.
Actual held-position exits remain sourced from Position Intelligence and sticky state.

## Daily Brief endpoint

`GET /api/v1/portfolio/{portfolio_id}/daily-brief`

- optional query parameter: `as_of_date`
- typed response: `DailyPortfolioBriefResponse`
- performs no portfolio write, sync, paper event, or broker action
- returns portfolio ID/revision, generated time, readiness and dates, workflow state,
  valuation summary, blockers, and severity-partitioned positions/opportunities
- opportunity provenance includes profile/version, source plan ID, revision, ranking,
  sizing, decision, readiness, loss-control evidence, analysis date, and action ID

Performance hardening split this read contract into two typed stages:

- `GET /api/v1/portfolio/{portfolio_id}/daily-brief` returns the fast core only:
  valuation, readiness, required actions, ATTENTION, HOLD, and UNAVAILABLE.
- `GET /api/v1/portfolio/{portfolio_id}/daily-brief/opportunities` independently runs
  opportunity discovery. `research_only_limit` is bounded from 1 through 100 and
  defaults to 10. The response includes authoritative actionable/research/deferred total
  counts and ordered candidates.

The compatibility `build()` composition remains available internally for deterministic
Copilot grounding and returns the same combined facts.

## Services reused and no duplicated financial logic

- `ResearchPortfolioService.value()` — cash, valuation, actual holdings, revision
- `PositionIntelligenceService` — completed-session SELL/ATTENTION/HOLD/UNAVAILABLE
- stored monitoring snapshots — sticky SELL latch and actual trigger session
- `StopExitGuidanceService` — active loss-control policy and strategy references
- `PortfolioDecisionOrchestrator` — profile evaluation, RS20, sizing, constraints
- `ExecutionReadiness` / `classify_new_buy()` — canonical actionability
- `ResearchDataSummaryService` — stored SPY and tracked-ticker freshness
- `DailySchedulerStatus` — latest scheduler result
- existing Paper Validation and portfolio-action routes — linked, not duplicated

## Completed-session and readiness semantics

The brief uses stored completed daily candles and latest stored completed SPY session;
it never uses the browser clock as market truth. It separately exposes expected,
synchronized, brief, and each position's actual guidance session.

- `READY`: stored facts align and no tracked-data degradation is reported.
- `DEGRADED`: tracked ticker facts or position guidance are incomplete/stale; the UI
  displays the warning and actual as-of sessions.
- `BLOCKED`: no completed SPY session, latest scheduled sync failed, or portfolio
  valuation is incomplete. New actionable entries are moved out of ACTIONABLE.

Last-known position guidance remains visible with its real as-of date. Missing values
remain unavailable/null, never fabricated zero. Refresh only refetches the brief.

Expected-session hardening now compares latest stored SPY with the latest possible
completed U.S. weekday derived from the existing `CompletedDailySessionPolicy` clock and
16:15 ET boundary. Weekends roll back to Friday. If a newer weekday should be complete
but is absent, readiness is `BLOCKED` with
`EXPECTED_COMPLETED_SESSION_NOT_STORED`. `NEVER_RUN` after process restart does not block
demonstrably current stored data, but it can no longer allow stale SPY data to appear
READY. Without a new exchange-calendar framework, holidays are intentionally
conservative: the view may stay blocked until a later stored SPY session proves currency.

## Position status and opportunity behavior

Fixed response/UI priority:

1. sticky SELL / Action Required
2. ATTENTION
3. actionable opportunities
4. research-only and workflow-deferred opportunities
5. HOLD / no action
6. unavailable guidance

Sticky SELL remains authoritative even if later computation would say HOLD. ATTENTION
is never promoted to SELL. HOLD is lower priority. Unknown-profile positions without
governed guidance are UNAVAILABLE. Cards retain reason, quantity, completed close, P&L,
profile, actual session, loss-control facts, and links to Position Intelligence,
Copilot, and Portfolio/Paper Validation.

Both frozen Strategy Profiles use existing plan orchestration and profile-owned RS20
and sizing policies:

- Micho may be ACTIONABLE only with existing ACTIONABLE readiness, a positive numeric
  SMA150 boundary, and `COMPLETED_DAILY_CLOSE_BELOW`. It is explicitly not a broker stop.
- EMA BUY signals are `RESEARCH_ONLY` with canonical
  `NO_APPROVED_LOSS_CONTROL_POLICY`. EMA20/EMA50 are strategy references, not invented
  protective stops.
- An ACTIONABLE candidate without positive numeric loss-control evidence fails closed.

No stop was invented, no Sprint 20 research was rerun, and no result changed.

## Exit-first workflow, cash, and revision

With a required SELL, workflow becomes `WAITING_FOR_REQUIRED_EXITS`.
Otherwise-actionable entries remain visible as deferred with their evidence retained.
The service does not execute the SELL, mutate the portfolio, assume proceeds,
recalculate cash from a hypothetical exit, or claim a deferred quantity remains
executable after an unknown fill.

The response carries current portfolio revision and source plan/action identity.
Existing preview/apply APIs remain the only mutation path with revision/fingerprint
revalidation. Paper Validation remains observational and separate.

## Copilot and frontend

Unified chat gained typed internal `DAILY_BRIEF` intent. “What requires action today?”
and “Why isn't this EMA opportunity actionable?” are answered deterministically from
the same brief. Facts/counts are server-owned. Copilot cannot create or execute actions.

Dashboard was evolved in place into **Daily Portfolio Manager**. It includes completed
session/readiness, responsive summary cards, explicit exit-first warning, severity-first
cards and empty states, loss-control/broker-stop distinctions, workflow handoffs, and a
query-only Refresh. React only formats backend facts; it calculates no indicators,
signals, status, risk, ranking, sizing, or constraints.

## Performance and Daily UX Hardening

### Original measurement and profiling

The original real full-universe Daily Brief took approximately **42.6 seconds**. A
subsequent instrumented warm run took 10.572 seconds and isolated the same structural
bottleneck:

| Phase | Calls | Time |
|---|---:|---:|
| top-level portfolio valuation | 1 | 0.048s |
| per-position intelligence | 10 | 0.351s |
| freshness | 1 | 1.724s |
| EMA plan | 1 | 4.479s |
| Micho plan | 1 | 3.966s |
| company lookups | 1,006 | 1.422s |
| candle-history loads | 1,006 | 5.404s cumulative |
| universe loads | 2 | 0.015s |
| schema serialization | 1 | 0.002s |

The request issued **2,325 SELECT statements**. The two profiles independently loaded
the same universe, SPY, companies, and histories. Position Intelligence also re-valued
the complete portfolio for every held position. Freshness repeated several aggregate
scans. The bottleneck was therefore N+1/repeated data access, not RS20 arithmetic,
stop/exit guidance, or serialization.

### Exact optimization

- Split core position management from opportunity discovery, so the Dashboard never
  waits for a universe scan before showing valuation, SELL, ATTENTION, and HOLD.
- Added one bulk immutable `PortfolioMarketSnapshot`: one company list, one active
  universe list, one completed candle-history query, one SPY history, reused by both
  frozen profile evaluations.
- Added bulk latest-candle/company valuation loading.
- Added bulk Portfolio Intelligence assembly over one valuation, one company load, one
  monitoring-history load, and portfolio event/reconciliation loads.
- Consolidated freshness metrics into one aggregate database round trip.
- Preserved the legacy single-plan path and proved the bulk snapshot produces equal
  plan/status facts for identical input.

No strategy evaluation, signal, RS20 score/order, sizing, readiness, loss-control,
provenance, action identity, cash, or exit-first semantics changed.

### Final real timings and call reductions

Final measurement through the real local HTTP endpoints on the current portfolio:

| Read | Before | After | SQL statements |
|---|---:|---:|---:|
| position-management core | blocked behind ~42.6s combined request | **0.942s** | **11** |
| opportunity discovery | part of ~42.6s combined request | **5.470s** | **18**, including independent core revalidation |

The direct service measurement was 0.356s for core and 5.931s for opportunities. The
minor HTTP/run variance is expected; no fragile wall-clock CI assertion was added.
Most importantly, existing positions render in under one second and do not wait for the
separate full-universe scan. The opportunity result is also materially below the former
42.6-second request and uses a fixed number of bulk data loads rather than per-ticker
queries.

### Research-only shortlist

The backend preserves authoritative RS20 order and total count. It returns all relevant
ACTIONABLE candidates, while the primary Dashboard requests only the top **10**
research-only candidates. With the real total of **89**, the heading displays
`Research-only Opportunities (89)` and offers `View all 89`; expanding requests a larger
backend-ordered page. React performs no ranking or financial eligibility filtering.

Opportunity loading has an explicit “Scanning today's opportunities…” state. A scan
error leaves the already-rendered SELL/ATTENTION/HOLD content intact rather than
replacing it with an empty or whole-page error.

## Files created

- `backend/src/alphapilot/portfolio/daily_brief.py`
- `backend/src/alphapilot/schemas/daily_brief.py`
- `backend/src/alphapilot/services/daily_portfolio_brief.py`
- `backend/tests/portfolio/test_daily_portfolio_brief.py`
- `frontend/src/features/dashboard/DailyPortfolioManager.tsx`
- `frontend/scripts/sprint21-daily-manager-smoke.mjs`
- `docs/sprints/SPRINT21_PLAN.md`
- `docs/sprints/SPRINT21_COMPLETION_REPORT.md`

## Files modified

- `AGENTS.md`
- `docs/PROJECT_STATE.md`
- `docs/DECISIONS.md`
- `backend/src/alphapilot/api/routes/portfolio.py`
- `backend/src/alphapilot/api/routes/copilot.py`
- `backend/src/alphapilot/copilot/intent.py`
- `backend/src/alphapilot/copilot/orchestrator.py`
- `backend/src/alphapilot/portfolio/orchestration.py`
- `backend/src/alphapilot/repositories/company.py`
- `backend/src/alphapilot/repositories/daily_candle.py`
- `backend/src/alphapilot/repositories/research_data.py`
- `backend/src/alphapilot/repositories/research_portfolio.py`
- `backend/src/alphapilot/services/admin_data.py`
- `backend/src/alphapilot/services/daily_candle.py`
- `backend/src/alphapilot/services/position_intelligence.py`
- `backend/src/alphapilot/services/research_portfolio.py`
- `backend/tests/portfolio/test_copilot.py`
- `backend/tests/conftest.py`
- `backend/tests/portfolio/test_orchestration.py`
- `backend/tests/portfolio/test_position_intelligence.py`
- `frontend/package.json`
- `frontend/src/api/portfolio.ts`
- `frontend/src/hooks/usePortfolioApi.ts`
- `frontend/src/layouts/AppLayout.tsx`
- `frontend/src/layouts/AppLayout.test.tsx`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/pages/DashboardPage.test.tsx`
- `frontend/src/styles.css`
- `frontend/src/test/server.ts`
- `frontend/src/types/portfolio.ts`

## Migration status

No Alembic migration was created. The brief derives existing facts without new
persistence, so no database schema change is needed.

## Tests and exact commands

Focused backend:

```powershell
cd backend
$env:DEBUG='false'
uv run pytest tests/portfolio/test_daily_portfolio_brief.py tests/portfolio/test_copilot.py -q
```

Result: **37 passed in 5.96s**. Coverage includes typed/read-only API, sticky SELL
priority, status separation, failed sync and incomplete valuation, no plan on incomplete
state, EMA/Micho readiness, numeric loss control, fail-closed invalid actionability,
actual cash preservation, suppressed cross-profile held exits, and Copilot grounding.

Hardening-focused backend:

```powershell
cd backend
$env:DEBUG='false'
uv run pytest tests/portfolio/test_orchestration.py tests/portfolio/test_daily_portfolio_brief.py tests/portfolio/test_position_intelligence.py tests/portfolio/test_research_portfolio.py tests/services/test_research_admin_data.py tests/services/test_completed_daily_candles.py -q
```

Result: **41 passed in 7.68s**, with Ruff and mypy also passing. Added coverage proves
bulk market-snapshot reuse, equality with the legacy single-plan path, one snapshot for
both Daily Brief profiles, bulk Position Intelligence equality, missing expected-session
blocking, split typed endpoints, and bounded authoritative counts.

Shared-test-database concurrency hardening:

```powershell
cd backend
$env:DEBUG='false'
uv run pytest tests/portfolio/test_daily_portfolio_brief.py tests/portfolio/test_position_intelligence.py tests/portfolio/test_position_monitoring.py tests/portfolio/test_research_portfolio.py tests/research_data/test_candle_versioning.py tests/research_data/test_research_dataset.py tests/services/test_completed_daily_candles.py tests/services/test_market_batch_sync.py -q --tb=short
```

Result: **48 passed in 10.49s**. Two deliberately concurrent runs of the portfolio and
candle-versioning modules also both passed (**15/15 each**). A session-scoped PostgreSQL
advisory lock now serializes pytest processes that share `TEST_DATABASE_URL`, preventing
one process's per-test `TRUNCATE` cleanup from deleting another process's fixtures. The
lock is test infrastructure only and does not change application or research behavior.

Full backend gate:

```powershell
cd backend
$env:DEBUG='false'
.\run_checks.ps1
```

- Ruff check and format: **PASS**
- mypy: **PASS — 173 source files**
- pytest: **PASS — 360 passed in 47.30s**
- overall: **All checks passed**

The script formatted one Sprint 21 test file, then its second Ruff check passed. An
initial root-directory `.\run_checks.ps1` attempt failed only because the script is
under `backend/`; it was rerun successfully from the correct directory.

Full frontend gate:

```powershell
cd frontend
npm run lint
npm test -- --run
npm run build
```

- ESLint: **PASS**
- Vitest: **PASS — 16 files / 78 tests**
- TypeScript + Vite build: **PASS — 106 modules transformed**
- bundled AlphaPilot logo: **PASS**

Browser acceptance:

```powershell
cd frontend
npm run smoke:sprint21
```

**PASS** against real local Vite in Edge/Playwright with controlled backend responses.
It verified desktop and 390px mobile rendering, session/readiness/summary, priority,
sticky SELL, ATTENTION distinct from SELL, lower-priority HOLD, EMA canonical blocker,
Micho ACTIONABLE numeric SMA150/completed-close/broker-stop-No evidence, required-exit
deferral, unchanged cash, both required Copilot questions, and Refresh without sync.
The final hardening pass additionally verified that core position content appears before
the delayed opportunity response, the scanning state is explicit, the total 89 is
visible while only the ordered shortlist is rendered, actionable content stays
prominent, and neither request mutates portfolio state or invokes market sync.
Screenshot (Git-ignored):
`backend/backtest_reports/sprint21/daily-manager-smoke.png`.

A safe real-data endpoint inspection (no mutation) returned READY for stored session
2026-08-28 with actual cash `$955.8050`, 0 required SELL, 1 ATTENTION, 0 actionable, 89
EMA research-only (10 displayed), 0 deferred, 9 HOLD, and 0 unavailable. The real HTTP
core took 0.942s and opportunities took 5.470s. This confirmed usefulness on the current
stored portfolio while correctly refusing to make EMA actionable.

No historical stop research or portfolio experiment was run.

## Post-completion full-suite regression recovery

An external full-suite run after the initial completion flow reported **41 failed / 318
passed / 1 error**. A later overlapping run reported a different broad failure set. The
evidence is retained here because Sprint 21 was not accepted while that contradiction
remained unexplained.

There was **one actual root cause**: independent pytest processes used the same dedicated
PostgreSQL `TEST_DATABASE_URL` concurrently. The function-scoped cleanup fixture executes
`TRUNCATE ... CASCADE` before and after every test. Before recovery, nothing serialized
separate pytest processes, so one process could erase another process's committed fixtures
or rows between `commit()` and `refresh()`. Deliberately running two database-heavy pytest
groups concurrently reproduced the reported pattern: missing rows, duplicate ticker
violations, foreign-key violations, stale ORM objects, failed refreshes, and disappearing
portfolio state.

The apparent independent failures were consequences of that one race:

- companies were missing when another process truncated them after creation;
- duplicate `companies_ticker_key` inserts occurred when two processes seeded the same
  ticker into one shared database;
- candle and candle-version foreign keys failed when the corresponding company was
  removed between operations;
- `ResearchPortfolio` and `PaperValidationRecord` refreshes failed when their rows were
  truncated after commit and before refresh;
- pending-rollbacks followed earlier integrity failures in the same session;
- the deadlock was PostgreSQL lock contention between `TRUNCATE` and live test
  transactions, not a Sprint 21 production lock-order inversion.

The previous full-suite run appeared green because it ran without a competing pytest
process. The failure sets varied because their exact contents depended on which test's
fixtures were removed by the competing cleanup.

The fix is isolated to `backend/tests/conftest.py`: a session-scoped PostgreSQL advisory
lock is held for the lifetime of each pytest process. A second process targeting the same
test database waits for the first suite to finish, after which the existing per-test
cleanup proceeds unchanged. The lock is released automatically with its dedicated
connection, including process termination. No database was reset and no production code,
transaction boundary, or financial behavior was changed.

The shared persistence audit found no production transaction defect:

- Sprint 21 did **not** change existing `CompanyRepository` create, get-by-ticker, update,
  flush, or normalization semantics; it added a separate SELECT-only `get_many()` helper;
- the new candle history/latest helpers and research-portfolio bulk helpers are explicit
  read paths and perform no commit, rollback, refresh, close, mutation, or lock acquisition;
- Daily Brief snapshot reuse remains read-only and does not reuse a long-lived session or
  launch concurrent database work;
- no production write-path semantics required restoration.

Required isolated probes all passed: universe-company sync **2/2**, universe sync **2/2**,
portfolio BUY persistence **1/1**, and market sync **1/1**. Recovery groups passed as
follows: A **6/6**, B **16/16**, C **30/30**, D **4/4**, and E **17/17**. Sprint 21 focused
tests passed **37/37**; the hardening group passed **41/41**, then passed **41/41** again
with reversed module order. The broader reported-failure group passed **48/48**. Two
deliberately concurrent portfolio/candle-versioning runs both passed **15/15** after the
advisory-lock fix.

Full backend suite run #1, through `run_checks.ps1`: Ruff **PASS**, mypy **PASS — 173
source files**, pytest **360/360 passed in 47.30s**. Full backend suite run #2:
**360/360 passed in 47.26s**. Frontend gates also passed: ESLint, **16 files / 78 tests**,
and the TypeScript/Vite build with **106 modules transformed**.

The safe real-data performance recheck after recovery measured **0.415s** for the core
Daily Brief and **5.163s** for opportunities. The earlier valid measurements of 0.942s
and 5.470s remain above as historical measurements; the accidental 404 timing probe was
discarded. The recovery changed no financial result, strategy rule, portfolio accounting,
research conclusion, API contract, or frontend behavior.

## Final acceptance answers

1. **Yes.** Dashboard is the Daily Portfolio Manager.
2. `GET /api/v1/portfolio/{portfolio_id}/daily-brief` powers it.
3. **Yes.** It is read-only.
4. **Yes.** It uses stored completed-session semantics.
5. **No.** Stale data cannot masquerade as current; dates/readiness remain explicit.
6. **Yes.** SELL positions are first.
7. **Yes.** Sticky SELL is preserved.
8. **Yes.** ATTENTION is distinct from SELL.
9. **Yes.** HOLD is lower priority.
10. **Yes.** Unknown-profile guidance is UNAVAILABLE.
11. **Yes.** Existing plan/decision logic supplies opportunities.
12. **Yes.** Micho can be ACTIONABLE with valid existing SMA150 evidence.
13. **Yes.** SMA150 is numeric.
14. **Yes.** The completed-close trigger is explicit.
15. **Yes.** It is explicitly not a broker stop.
16. **No.** EMA cannot appear ACTIONABLE under current approved policies.
17. **Yes.** EMA can appear RESEARCH_ONLY.
18. **Yes.** EMA shows `NO_APPROVED_LOSS_CONTROL_POLICY`.
19. **No.** An actionable BUY cannot lack numeric loss control.
20. **Yes.** Required exits block reliance on new-entry quantities.
21. **Yes.** Hypothetical post-SELL cash is avoided.
22. **Yes.** Revision, source identity, and write-path revalidation are preserved.
23. **Yes.** Paper Validation remains separate.
24. **No.** No Alpaca API integration was added.
25. **No.** No broker execution was added.
26. **No.** No strategy/research rule changed.
27. **No.** No stop research was rerun.
28. **No.** Refresh does not trigger sync.
29. **Yes.** Copilot explains today's actions.
30. **No.** Copilot cannot create/execute actions.
31. Backend gate: **PASS — Ruff/format, mypy 173, pytest 360**.
32. Frontend gate: **PASS — ESLint, 16 files / 78 tests, build**.
33. Browser acceptance: **PASS — desktop/mobile and both Copilot questions**.
34. Migration: **No**, because no new persistence is required.
35. Git status: local uncommitted Sprint 21 changes on
    `feature/daily-portfolio-manager`; exact final status is recorded at handoff.
36. Recommended commit: `feat: add performant daily portfolio manager workflow`.

## Performance-hardening acceptance answers

1. Original bottlenecks: two complete sequential universe passes, 1,006 company queries,
   1,006 candle queries, per-position full revaluation, and repeated freshness scans.
   Strategy math was secondary and serialization was negligible.
2. **Yes.** There was both N+1 and repeated loading: 2,325 SELECTs in the profiled
   combined request. The optimized core uses 11 statements and opportunities use 18
   including independent core revalidation.
3. **Yes.** The brief was split because position management is useful independently and
   must not wait for full-universe analysis. Both reads remain typed and read-only.
4. Before: approximately **42.6s** real elapsed.
5. After: **0.942s** real HTTP core; **5.470s** separate real HTTP opportunity scan.
6. **Yes.** Position-management content renders without waiting for the scan.
7. With total 89, the primary Dashboard displays **10** research-only cards.
8. **Yes.** The authoritative total 89 remains visible and `View all 89` is available.
9. **Yes.** Actionable opportunities are returned and displayed in full, independently
   from the research-only limit.
10. **Yes.** Previously, an old internally consistent stored SPY date could appear READY
    after scheduler restart.
11. Final freshness rule: compare stored SPY to the conservative latest possible
    completed U.S. weekday from `CompletedDailySessionPolicy`; missing expected weekday
    blocks entries, while `NEVER_RUN` alone does not block current stored data.
12. Strategy/financial output changed: **No**.
13. Backend: **PASS — Ruff/format, mypy 173 files, 360 pytest tests**.
14. Frontend: **PASS — ESLint, 16 files / 78 tests, production build**.
15. Browser: **PASS** for staged loading, final results, bounded research, actionable
    priority, read-only refresh, no sync, and no mutation.
16. Git: uncommitted Sprint 21 work remains on `feature/daily-portfolio-manager`.
17. Recommended commit: `feat: add performant daily portfolio manager workflow`.

## Known limitations and technical debt

- Research/advisory software only; no live-trading validation.
- No broker/account sync, automatic orders, or authenticated multi-user persistence.
- Paper Validation is manual and separate; a decision is not an order.
- Historical current-constituent research retains survivorship bias and lacks a
  point-in-time S&P 500 universe.
- SPY is a limited benchmark/proxy, not an exchange calendar. The weekday-based missing
  session guard is deliberately conservative around U.S. market holidays.
- Opportunity evaluation still performs the two frozen strategy computations over the
  shared in-memory snapshot. At 5.470s it no longer blocks the 0.942s core, but future
  non-semantic CPU/query optimization may be useful as the universe grows.
- Scheduler status is process-local. Freshness correctness no longer depends on
  `NEVER_RUN`, though detailed operational history still disappears after restart.
- EMA lacks approved numeric pre-entry loss control and remains research-only. Sprint
  20's `NO_WINNER` conclusion is unchanged.
- Required exits deliberately defer reliance on quantities until a new plan is generated
  after the user's manual portfolio update.

## Git handoff

Branch: `feature/daily-portfolio-manager`

### Regression-recovery acceptance answers

1. The 41 failures came from concurrent pytest processes truncating one shared test
   database while the other process was using it.
2. **One** actual root cause existed.
3. Existing `CompanyRepository` semantics did not change; Sprint 21 added a separate
   SELECT-only bulk helper.
4. There was no production flush/commit/rollback/session bug.
5. Companies were missing after competing cleanup truncated them, or duplicated when
   both processes seeded the same ticker.
6. FK violations followed removal of parent Company rows by competing cleanup.
7. `refresh()` failed when competing cleanup removed a just-committed row.
8. The deadlock was `TRUNCATE` contending with another pytest process's live database
   transaction, not production lock-order inversion.
9. **Yes:** cross-process test isolation was the issue.
10. No production write-path behavior needed restoration.
11. **Yes:** Daily Brief bulk optimization remains explicit, SELECT-only read paths.
12. Financial results changed: **NO**.
13. Strategy rules changed: **NO**.
14. Focused results: isolated probes **6/6**; A–E **73/73**; Sprint 21 **37/37**;
    hardening and reversed order **41/41** each; broad affected group **48/48**.
15. Full suite #1: **360/360 in 47.30s**.
16. Full suite #2: **360/360 in 47.26s**.
17. Backend `run_checks.ps1`: **PASS** — Ruff, mypy 173, pytest 360.
18. Frontend: **PASS** — ESLint, 16 files/78 tests, 106-module build.
19. Final core Daily Brief timing: **0.415s**.
20. Final opportunity timing: **5.163s**.
21. Git status: Sprint 21 remains local; the test-harness fix and this report update
    are unstaged alongside the already staged Sprint 21 work; there are no `??`
    untracked files.
22. Recommended commit message: `feat: add performant daily portfolio manager workflow`.

All Sprint 21 source, tests, and documentation are ready for user review and commit. The
browser screenshot is Git-ignored. No commit, push, PR, merge, force-push, or tag was
performed.

Recommended commit message:

```text
feat: add performant daily portfolio manager workflow
```

Sprint 22 has not started.
