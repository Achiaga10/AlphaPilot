# AlphaPilot Sprint 11B Completion Report

## 1. Why Sprint 11B Was Needed

Sprint 11 produced a technically working React/TypeScript UI, but manual review
showed that it was not yet ready for handoff. The main gaps were product-level:
the opportunity view did not make recommendation priority sufficiently clear,
large-universe results were hard to browse, contextual research explanations
were sparse, a displayed plan could silently become stale after input changes,
single-stock analysis was not a dedicated workflow, stored-data maintenance was
not exposed safely, and the application still used placeholder branding.

Sprint 11B hardened that same local, uncommitted Sprint 11 working tree. It did
not change strategy rules, RS20, ATR, sizing formulas, portfolio accounting, or
backtest assumptions, and it did not start Sprint 12.

## 2. User Review Findings Addressed

- Replaced the placeholder brand mark with the official user-provided logo.
- Added concise, accessible help for strategy, ranking, sizing, scope, dates,
  risk, constraints, ordering, and research classifications.
- Made Approved Buys the immediately useful default view when approved BUYs
  exist, with visible counts for every decision category.
- Separated backend recommendation priority from alphabetical universe browsing.
- Made all evaluated tickers searchable, filterable, paginated, and directly
  evaluable.
- Added a dedicated backend-owned single-stock evaluation workflow.
- Added explicit unknown-company, missing-data, stale-data, and insufficient-
  history states without fabricating metadata or analytical facts.
- Added safely gated stored-data freshness and sync operations.
- Added plan input snapshots and a prominent stale-plan warning.
- Humanized reason codes and research policy labels while retaining their stable
  machine-readable values in detail views.

## 3. UX Architecture Changes

The browser remains a presentation and workflow layer. It submits typed,
high-level portfolio inputs and renders backend output. The backend still owns:

1. stored Company and DailyCandle loading;
2. EMA/Micho strategy evaluation;
3. RS20 and ATR14 calculation;
4. BUY candidate ranking;
5. sizing and portfolio constraints; and
6. typed portfolio decisions and reason codes.

The UI now organizes those results into a reusable workspace, plan snapshot,
opportunity explorer, universe evaluation table, one-stock evaluation page, and
research-admin page. No EMA, SMA, RS20, ATR, ranking, sizing, or constraint
formula was moved into React.

## 4. Tooltip Behavior and Content

`InfoTooltip` uses a native `details`/`summary` interaction with an accessible
button role and `aria-describedby`. The same concise content is available by
hover, keyboard focus, and click/tap; it is not hover-only.

Help is present for the frozen EMA20 HYBRID 2% and Micho BOTH strategies,
ticker-ascending control, RS20, all sizing policies and classifications,
ticker scope, requested versus actual analysis dates, modeled/available risk,
constraints, opportunity priority, and A-Z universe order. Text explicitly says
that negative RS20 is not automatically invalid and that no sizing policy is
production-ready.

## 5. Opportunities Redesign

The result view now has counted tabs for:

- Approved Buys
- Sell / Exit
- Skipped
- All Decisions
- All Evaluated

Approved Buys is selected by default whenever at least one approved BUY exists;
otherwise the view falls back to All Decisions. Approved BUY rows preserve the
backend response/priority order. Candidate rank is displayed separately from
row order. SELL, HOLD, and unscored items display `Not scored` rather than a
fabricated score.

## 6. Sorting Semantics

Two different and explicit ordering rules are retained:

- Approved BUY decisions preserve backend candidate priority. This is the
  constrained allocation order for the selected policy.
- All Evaluated is sorted ticker ascending and visibly labeled `Sorted A-Z`.
  Help text states that this is browsing order, not recommendation priority.

Ticker-ascending selection remains the deterministic, economically meaningless
control and is never described as alpha.

## 7. Search, Filter, and Pagination Behavior

Returned results can be searched by ticker or company and filtered by decision,
signal, sector, and data status. Filters operate only on the backend response;
the UI does not synthesize candidates. Decision and universe tables paginate at
25 rows, preserving usable rendering for the current S&P 500-sized universe.
Tests exercise ticker/company search, combined filters, and a 30-row two-page
universe result.

## 8. All-Evaluated Behavior

The backend orchestration status now exposes optional display-ready company
name, stored sector, RS20, ATR14, decision, decision reason, and candidate rank.
The UI displays counts for `READY`, `NO_ACTION`, `COMPANY_NOT_FOUND`, `NO_DATA`,
`STALE_DATA`, and `INSUFFICIENT_HISTORY`, plus ticker, company, sector, data
date, signal, decision, rank, human-readable reason, and an Evaluate link.
Every returned ticker remains accessible through search and pagination.

## 9. Single-Stock Evaluation Workflow

The new `/evaluate` route accepts a ticker and submits the existing high-level
`POST /api/v1/portfolio/plan` contract with a one-ticker scope and current
workspace portfolio/configuration. The client does not send ATR, RS20, signal,
ranking, or enriched risk facts. The result separates strategy signal from
portfolio decision and shows company, sector, status, actual analysis date,
rank, allocation, RS20, ATR14, human-readable reason, and the raw reason code in
details.

## 10. Custom Ticker Behavior

Ticker input is normalized and locally format-validated, but a ticker is not
treated as a real company unless it exists in stored Company data. An unknown
ticker returns the explicit `COMPANY_NOT_FOUND` status. AlphaPilot does not
fabricate a name, sector, candles, ATR, score, or decision. The existing provider
boundaries do not reliably support arbitrary company discovery, so custom-
ticker onboarding remains future work.

## 11. Admin/Data Management Architecture

The new `/admin/data` UI is backed by typed API schemas and a small research-
admin service layer:

- `ResearchDataRepository` reads stored freshness/count information.
- `ResearchDataSummaryService` produces the freshness summary.
- `ResearchTickerSyncService` syncs market history only for a known company.
- `ResearchFullSyncService` delegates universe, company metadata, benchmark,
  and constituent history work to existing provider/service boundaries.
- `AdminSyncJobManager` runs and tracks one process-local full job without
  blocking the HTTP request.

No provider API call occurs inside portfolio domain logic, and no secret or raw
traceback is included in API responses.

## 12. Sync-All Semantics

`POST /api/v1/admin/data/sync/all` starts a background full-universe research
sync and returns a typed job snapshot immediately. The operation refreshes the
current S&P 500 membership, updates stored Company metadata, and delegates SPY
and constituent market history to `UniverseMarketSyncRunner` and the existing
Alpaca bulk-sync service. Its default request range is the schema's predeclared
400-day window, with an existing batch size of 100. A checkpoint lives below
the user's `.alphapilot` directory.

The expensive real provider sync was deliberately not started during Sprint
11B validation. Delegation, progress, success/failure, polling, and duplicate
prevention were verified with controlled integration/API tests.

## 13. Single-Ticker Sync Semantics

`POST /api/v1/admin/data/sync/ticker` accepts a validated ticker and date range.
For a stored company it delegates to the existing market-sync service and
returns `SYNCED`, `SKIPPED`, or `FAILED`. If no Company record exists it returns
`COMPANY_NOT_FOUND` before invoking a market provider. This is data refresh, not
arbitrary-company onboarding.

## 14. Sync Job and Status Behavior

The job states are `QUEUED`, `RUNNING`, `SUCCEEDED`, and `FAILED`. Status includes
timestamps and deterministic attempted/synced/skipped/failed progress counts.
The UI polls a running job and displays completion and failed-ticker summaries.
A second full job is rejected while one is queued/running. Failure responses use
a safe generic message; server details remain in server logs.

Job state is process-local and is lost on restart. It is neither a durable queue
nor suitable for multi-process coordination.

## 15. Admin Feature Gate

`ADMIN_TOOLS_ENABLED` is defined in backend configuration and defaults to
`false`; `.env.example` documents the same safe default. The capability endpoint
is always readable so navigation can be hidden and the disabled page can explain
the state. Summary and mutation endpoints return HTTP 403 while disabled.

This gate is operational safety only. It is not authentication or authorization,
and admin tools must not be exposed to untrusted networks until real access
control exists.

## 16. Data Freshness Behavior

`GET /api/v1/admin/data/summary` reports active Company count, active current
S&P 500 constituent count, latest stored SPY date, the earliest and latest of
each active constituent's latest stored candle, and the latest process-local
sync job. Missing dates remain null rather than being inferred.

## 17. Dirty-Plan Behavior

A successful plan stores a canonical snapshot of every plan-affecting draft
input. Later changes to cash, positions, strategy/configuration, selection,
sizing, risk configuration, dates, or ticker scope mark the displayed result
stale. A prominent warning offers regeneration. The warning clears only after
successful regeneration records the new snapshot; changing an input back to the
snapshot also restores a clean state deterministically.

## 18. Current-Position Price Behavior

Current positions still require an explicit reference price in the high-level
request. Portfolio equity and constraints need the portfolio-state value before
candidate orchestration begins. Automatically substituting the latest candle
would also not recover frozen entry ATR/stop-distance risk for a manually entered
holding. The UI labels this requirement rather than implying broker-synchronized
or automatically enriched account state.

## 19. Backend API Changes

New endpoints under `/api/v1/admin/data`:

- `GET /capability`
- `GET /summary`
- `POST /sync/ticker`
- `POST /sync/all`
- `GET /sync/jobs/latest`
- `GET /sync/jobs/{job_id}`

The existing `POST /api/v1/portfolio/plan` response gained only optional
candidate display/decision fields, preserving compatibility. CORS/startup
configuration was extended for the local Vite client without changing financial
semantics.

## 20. Files Created

Sprint 11B-specific created files:

- `backend/src/alphapilot/api/routes/admin_data.py`
- `backend/src/alphapilot/repositories/research_data.py`
- `backend/src/alphapilot/schemas/admin_data.py`
- `backend/src/alphapilot/services/admin_data.py`
- `backend/tests/api/test_admin_data.py`
- `backend/tests/services/test_research_admin_data.py`
- `docs/SPRINT11B_PLAN.md`
- `docs/SPRINT11B_COMPLETION_REPORT.md`
- `frontend/src/api/admin.ts`
- `frontend/src/components/InfoTooltip.tsx`
- `frontend/src/components/InfoTooltip.test.tsx`
- `frontend/src/features/portfolio/helpText.ts`
- `frontend/src/features/portfolio/OpportunityExplorer.tsx`
- `frontend/src/features/portfolio/OpportunityExplorer.test.tsx`
- `frontend/src/features/portfolio/StalePlanWarning.tsx`
- `frontend/src/pages/AdminDataPage.tsx`
- `frontend/src/pages/AdminDataPage.test.tsx`
- `frontend/src/pages/EvaluatePage.tsx`
- `frontend/src/pages/EvaluatePage.test.tsx`
- `frontend/src/pages/PlanDirtyState.test.tsx`
- `frontend/src/layouts/AppLayout.test.tsx`

The source asset `frontend/src/assets/images/alphapilot-logo.png` was created and
placed by the user. It was inspected and consumed, not created or edited by
Codex. The remaining untracked frontend scaffold and Sprint 11 files are listed
in `docs/SPRINT11_COMPLETION_REPORT.md` and are part of the same combined local
handoff.

## 21. Files Modified

Sprint 11B modified:

- `AGENTS.md`
- `docs/PROJECT_STATE.md`
- `docs/DECISIONS.md`
- `backend/.env.example`
- `backend/src/alphapilot/api/router.py`
- `backend/src/alphapilot/core/config.py`
- `backend/src/alphapilot/portfolio/orchestration.py`
- `backend/src/alphapilot/schemas/portfolio.py`
- `backend/src/alphapilot/services/universe_company_sync.py`
- `backend/tests/integration/test_universe_company_sync.py`
- `backend/tests/portfolio/test_orchestration.py`
- `frontend/index.html`
- `frontend/README.md`
- `frontend/scripts/real-smoke.mjs`
- `frontend/src/App.tsx`
- `frontend/src/features/dashboard/PlanOverview.tsx`
- `frontend/src/features/portfolio/CandidateStatuses.tsx`
- `frontend/src/features/portfolio/DecisionTable.tsx`
- `frontend/src/features/portfolio/PlanForm.tsx`
- `frontend/src/features/portfolio/PlanForm.test.tsx`
- `frontend/src/features/portfolio/PortfolioWorkspace.tsx`
- `frontend/src/features/portfolio/RiskSummary.tsx`
- `frontend/src/features/portfolio/policyClassifications.ts`
- `frontend/src/hooks/usePortfolioApi.ts`
- `frontend/src/layouts/AppLayout.tsx`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/pages/DashboardPage.test.tsx`
- `frontend/src/pages/PortfolioPage.tsx`
- `frontend/src/pages/PortfolioPage.test.tsx`
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/pages/SettingsPage.test.tsx`
- `frontend/src/styles.css`
- `frontend/src/test/fixtures.ts`
- `frontend/src/test/server.ts`
- `frontend/src/types/portfolio.ts`
- `frontend/src/utils/format.ts`

The tracked working tree also contains the reviewed Sprint 11 changes in
`.gitignore`, backend CORS/health/portfolio-route integration, and the full
frontend application. None was discarded or committed during Sprint 11B.

## 22. Frontend Tests and Results

Final command:

```powershell
cd frontend
npm run test
```

Result: **PASS — 11 test files, 40 tests passed**.

Coverage includes accessible help, brand replacement, strategy/ranking/sizing
content, Approved Buys default/counts, ordering disclosure, filters, negative
RS20, unscored decisions, pagination, one-stock evaluation, unknown company,
admin disabled/enabled states, known-ticker and full-job workflows, polling,
duplicate prevention, freshness, dirty-state variants, stable machine reasons,
human classifications, and navigation.

Backend tests also prove existing plan compatibility and stored-data/no-
lookahead behavior. Existing Sprint 7-10B regression tests remained green in
the full suite.

## 23. Backend Tests and Results

Focused command:

```powershell
cd backend
$env:DEBUG='false'
uv run ruff format src tests
uv run ruff check src tests
uv run mypy src
uv run pytest tests/api/test_admin_data.py tests/services/test_research_admin_data.py tests/portfolio/test_orchestration.py tests/api/test_portfolio_decisions.py tests/integration/test_universe_company_sync.py
```

Result: **PASS — 16 focused tests passed; Ruff and mypy passed**.

Full gate:

```powershell
cd backend
$env:DEBUG='false'
.\run_checks.ps1
```

Result: **PASS — Ruff check, Ruff formatting check, mypy over 115 source files,
and 150 pytest tests passed (13.20 seconds)**. `DEBUG=false` was scoped only to
the child shell to neutralize the Codex host's invalid value; application
configuration was not weakened.

## 24. Build and Lint Results

Commands:

```powershell
cd frontend
npm run lint
npm run test
npm run build
```

Results:

- ESLint: PASS
- Vitest: PASS — 40 tests
- TypeScript/Vite production build: PASS — 97 modules transformed
- Output included `dist/assets/alphapilot-logo-Dp3JkXYr.png` (150.15 kB),
  proving that Vite bundled the imported official asset.

No TypeScript suppression was introduced.

## 25. Manual Browser Validation

A temporary local Vite process was used with the already-running real backend.
The final command was:

```powershell
cd frontend
npm run smoke:real
```

The real stored-data Edge/Playwright smoke passed at desktop and 390 × 844
mobile sizes. It generated a three-ticker AAPL/MSFT/NVDA portfolio plan, found
one approved decision card and three evaluated rows, confirmed A-Z disclosure,
changed scope to make the plan stale, regenerated and cleared the warning,
evaluated NVDA through the one-stock route, confirmed the disabled admin state,
and checked mobile navigation.

Logo facts observed in the browser:

- source URL: `/src/assets/images/alphapilot-logo.png`
- natural size: 1024 × 1024
- desktop rendered size: 148 × 148
- mobile rendered width: at most 64 px
- `object-fit: contain`
- old `.brand__mark` placeholder count: zero

The official source asset is
`frontend/src/assets/images/alphapilot-logo.png`. It appears in the sidebar
brand area with `alt="AlphaPilot"`; because the image contains the wordmark,
adjacent duplicate `AlphaPilot` text was removed and only `Research Decision
Dashboard` remains. The prior placeholder was replaced. CSS preserves the 1:1
aspect ratio, uses `height: auto` and `object-fit: contain`, and scales the image
down on mobile without cropping. The same imported path is also used as optional
favicon branding. The original PNG remained unchanged: 150,156 bytes, SHA-256
`45294393C92AF82A3859B12932507016EFA9C8065AC5634736DE551E60C501B1` before and
after implementation.

The enabled admin sync UI, safe failed-ticker display, polling, and duplicate
job behavior were validated through controlled API/component tests instead of
triggering an expensive external full-universe sync. Provider secrets were not
read or displayed.

## 26. Screenshot

The final ignored smoke-test screenshot is:

`backend/backtest_reports/sprint11b/ui-hardening-smoke.png`

It shows the restrained approved visual design, the official logo, responsive
sidebar/navigation, portfolio metadata, opportunity categories, filters, and
the universe evaluation area. Research reports remain Git-ignored.

## 27. Remaining UI Issues

- The portfolio state is still manually entered; there is no broker/account
  synchronization or saved authenticated account.
- Admin navigation is intentionally hidden when disabled; direct navigation
  explains the disabled gate.
- Pagination is client-side over the returned plan. This is appropriate for the
  current S&P 500 response, but server-side pagination may be needed for much
  larger future universes.
- The optional favicon uses the full square PNG; no dedicated small favicon
  variant was created because modifying/duplicating the official source was out
  of scope.
- The UI remains an advisory research interface, not a broker/order interface.

## 28. Remaining Backend and Product Issues

- `ADMIN_TOOLS_ENABLED` is not authentication or authorization.
- Full-sync job state and duplicate protection are process-local and not durable
  across restart or coordinated across workers.
- Arbitrary custom-ticker company discovery/onboarding is unsupported by the
  current providers; unknown metadata is never inferred.
- Current positions still require manual reference prices and may lack original
  frozen entry-risk facts.
- There is no live broker state, account persistence, order execution, or audit
  identity.
- Data freshness describes stored data; it does not guarantee exchange-real-time
  data or provider completeness.
- The current universe is the current S&P 500 constituent set, not a point-in-
  time historical universe. Research continues to contain survivorship bias.
- RS20 and all sizing policies retain research-only evidence/classifications;
  none is production-ready.

## 29. Sprint 11 Commit/Merge Readiness

**Yes.** The combined Sprint 11 and Sprint 11B local work is ready for user
review, commit, and PR. The required high-level plan workflow works with real
stored data, large-universe results are usable, backend/domain ownership is
preserved, the official branding is integrated without modification, admin
operations are disabled safely by default, frontend gates pass, all 150 backend
tests pass, and a real browser smoke passes.

This is a technical/product handoff assessment, not a claim that AlphaPilot or
its research policies are production-ready.

## 30. Recommendation for the Next Sprint

Do not start Sprint 12 until the user reviews and publishes Sprint 11/11B.
After approval, the next sprint should focus on a deliberately chosen product
boundary such as authenticated portfolio persistence/broker-state adapters or a
separate research workflow. It should not duplicate backend strategy/risk logic
in the frontend. Durable/authenticated admin jobs should precede any non-local
admin exposure.

## 31. Git Status

Branch: `feature/ui-mvp`

Working tree: **dirty by design; no commit or push was performed**.

At report creation, `git status --short` contained 16 tracked modified files and
10 untracked entries. Because Git collapses the wholly untracked frontend tree
to `?? frontend/`, that entry contains the complete Sprint 11/11B frontend,
including the user-provided logo. Other untracked entries are the new backend
admin modules/tests and Sprint 11/11B plan/completion documents. Ignored
`frontend/dist`, dependencies, environment files, and browser/report artifacts
are not commit candidates.

Untracked top-level status entries:

- `backend/src/alphapilot/api/routes/admin_data.py`
- `backend/src/alphapilot/repositories/research_data.py`
- `backend/src/alphapilot/schemas/admin_data.py`
- `backend/src/alphapilot/services/admin_data.py`
- `backend/tests/api/test_admin_data.py`
- `backend/tests/services/test_research_admin_data.py`
- `docs/SPRINT11_PLAN.md`
- `docs/SPRINT11_COMPLETION_REPORT.md`
- `docs/SPRINT11B_PLAN.md`
- `docs/SPRINT11B_COMPLETION_REPORT.md` (after this report is created)
- `frontend/`

The displayed count is 10 before this report and 11 after it is created. All
source/docs/tests listed above are ready for the user's commit review; no secret
`.env`, dependency directory, build output, screenshot, or backtest report is
included.

## 32. Git Diff Stat

Immediately before creating this untracked report, tracked changes were:

```text
16 files changed, 363 insertions(+), 127 deletions(-)
```

This native `git diff --stat` does not include any wholly untracked file or the
untracked `frontend/` tree. `git diff --check` passed; its only output was the
existing Windows LF-to-CRLF conversion warnings.

## 33. Recommended Commit Message

```text
feat(ui): add and harden research decision dashboard
```

No commit, push, PR, merge, force-push, or tag operation was performed.
