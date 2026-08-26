# AlphaPilot Sprint 11 Completion Report

## 1. Sprint Goal and Outcome

Sprint 11 built AlphaPilot's first frontend: a strict, typed, production-
structured research decision dashboard that consumes the merged backend
Portfolio Plan contract. Sprint 11 completed successfully.

The UI remains presentation-only. It does not calculate EMA/SMA indicators,
strategy signals, RS20, ATR14, stop distance, modeled risk, sizing, portfolio
constraints, or BUY/HOLD/SELL/SKIP decisions. Those facts come from FastAPI.

The required Dashboard, Portfolio Plan, and Research Settings screens are
implemented. Frontend lint, 17 frontend tests, the strict TypeScript production
build, 142 backend tests, and a real Edge/Vite/FastAPI/stored-database browser
smoke test all passed. No broker execution, authentication, Sprint 12 work, Git
commit, push, PR, merge, force-push, or tag operation was performed.

## 2. UI Architecture

```text
React pages and feature components
  -> Portfolio workspace context for editable local form/latest plan
  -> TanStack Query hooks for server state and plan mutation
  -> centralized typed API modules
  -> FastAPI /api/v1 endpoints
  -> backend orchestration, strategy, RS20, ATR, sizing, and decisions
```

The main boundaries are:

- `src/api`: base URL, JSON behavior, cancellation, typed errors, response
  validation, and endpoint calls.
- `src/types`: TypeScript representations of the actual Pydantic contract.
- `src/hooks`: TanStack Query health, risk-config, and plan hooks.
- `src/features/portfolio`: form/workspace, backend-result summaries,
  positions, decisions, data status, risk context, and evidence labels.
- `src/features/dashboard`: the latest generated plan overview.
- `src/components`: reusable status, metric, loading, error, and empty states.
- `src/layouts`, `src/pages`, and `App.tsx`: navigation and route composition.
- `styles.css`: project-owned responsive visual system; no large UI framework.

Editable form state and the latest response are shared across routes through a
React provider. High-level form inputs are stored locally for refresh
convenience. This is explicitly browser-local research state, not an account or
cloud portfolio.

## 3. Frontend Stack

- React 19.2.8
- TypeScript 6.0.3 with strict checking
- Vite 8.2.2
- React Router 7.18.2
- TanStack Query 5.102.3
- project-owned responsive CSS
- Vitest 4.1.11
- React Testing Library 16.3.2
- MSW 2.15.0
- Playwright Core 1.62.1 using the installed Microsoft Edge browser for the
  real integration smoke
- npm with committed `package-lock.json`

The initially discovered TypeScript 7 / typed-ESLint peer incompatibility was
resolved before implementation validation by using the newest compatible
TypeScript 6 release. The final install reported zero vulnerabilities.

## 4. Files Created

Documentation:

- `docs/SPRINT11_PLAN.md`
- `docs/SPRINT11_COMPLETION_REPORT.md`

Frontend root/configuration:

- `frontend/.env.example`
- `frontend/README.md`
- `frontend/eslint.config.js`
- `frontend/index.html`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/tsconfig.json`
- `frontend/tsconfig.app.json`
- `frontend/tsconfig.node.json`
- `frontend/vite.config.ts`

Frontend application and API:

- `frontend/src/App.tsx`
- `frontend/src/main.tsx`
- `frontend/src/styles.css`
- `frontend/src/vite-env.d.ts`
- `frontend/src/api/client.ts`
- `frontend/src/api/portfolio.ts`
- `frontend/src/hooks/usePortfolioApi.ts`
- `frontend/src/types/portfolio.ts`
- `frontend/src/utils/format.ts`

Frontend components/features/pages:

- `frontend/src/components/AsyncState.tsx`
- `frontend/src/components/MetricCard.tsx`
- `frontend/src/components/StatusBadge.tsx`
- `frontend/src/layouts/AppLayout.tsx`
- `frontend/src/features/dashboard/PlanOverview.tsx`
- `frontend/src/features/portfolio/CandidateStatuses.tsx`
- `frontend/src/features/portfolio/DecisionTable.tsx`
- `frontend/src/features/portfolio/PlanForm.tsx`
- `frontend/src/features/portfolio/PortfolioSummary.tsx`
- `frontend/src/features/portfolio/PortfolioWorkspace.tsx`
- `frontend/src/features/portfolio/PositionsTable.tsx`
- `frontend/src/features/portfolio/RiskSummary.tsx`
- `frontend/src/features/portfolio/policyClassifications.ts`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/pages/PortfolioPage.tsx`
- `frontend/src/pages/SettingsPage.tsx`

Frontend tests and integration tooling:

- `frontend/src/features/portfolio/PlanForm.test.tsx`
- `frontend/src/pages/DashboardPage.test.tsx`
- `frontend/src/pages/PortfolioPage.test.tsx`
- `frontend/src/pages/SettingsPage.test.tsx`
- `frontend/src/utils/format.test.ts`
- `frontend/src/test/fixtures.ts`
- `frontend/src/test/renderApp.tsx`
- `frontend/src/test/server.ts`
- `frontend/src/test/setup.ts`
- `frontend/scripts/real-smoke.mjs`

The integration screenshot was generated at the Git-ignored path:

`backend/backtest_reports/sprint11/ui-demo.png`

## 5. Files Modified

- `.gitignore`
- `AGENTS.md`
- `backend/.env.example`
- `backend/src/alphapilot/api/routes/portfolio.py`
- `backend/src/alphapilot/core/config.py`
- `backend/src/alphapilot/main.py`
- `backend/src/alphapilot/schemas/portfolio.py`
- `backend/tests/api/test_health.py`
- `backend/tests/api/test_portfolio_decisions.py`
- `docs/DECISIONS.md`
- `docs/PROJECT_STATE.md`

No strategy, ranking, ATR formula, sizing formula, portfolio accounting, or
backtest implementation changed.

## 6. Backend Changes Required for the UI

Two targeted backend presentation improvements were necessary.

First, configurable local CORS support was added. `CORS_ORIGINS` defaults to the
explicit Vite development origins:

```text
http://localhost:5173,http://127.0.0.1:5173
```

FastAPI permits only those configured origins, `GET`, `POST`, and `OPTIONS`, and
the `Accept`/`Content-Type` headers. Credentials are disabled. No unrestricted
wildcard was introduced.

Second, the portfolio response now supplies display-ready current-state facts:

- cash and cash percentage
- invested value and invested percentage/exposure
- current and available modeled-risk percentages
- current-position ticker, shares, reference price, market value, portfolio
  weight, cost basis, sector, and modeled risk
- `modeled_risk_complete`

These fields keep portfolio/equity/weight calculations out of React.
`modeled_risk_complete` prevents the UI from implying accuracy when manually
entered existing positions lack their frozen entry-risk facts. The UI displays
an explicit warning instead of fabricating modeled risk.

## 7. API Endpoints Consumed

- `GET /api/v1/health/`
- `GET /api/v1/portfolio/risk-config`
- `POST /api/v1/portfolio/plan`

The UI is aware that lower-level `POST /api/v1/portfolio/decisions` exists but
does not use it for the normal workflow because it requires enriched candidate
facts. Existing lower-level behavior remains compatible and tested.

## 8. Main Screens Implemented

Required routes completed:

- `/` — Dashboard
- `/portfolio` — Portfolio Plan / Decisions
- `/settings` — Settings / Research Configuration

Company detail and backtest-summary pages were not added. Existing endpoints do
not provide a single clean combined company analysis/backtest-summary contract,
and adding that backend project was outside the required MVP.

## 9. Dashboard Behavior

The Dashboard provides:

- AlphaPilot research/development framing
- backend connectivity status
- requested and actual analysis dates after a plan exists
- current equity, cash/cash percentage, invested value/exposure, modeled risk,
  available modeled risk, and open-position count
- current positions from backend display-ready fields
- complete BUY/HOLD/SELL/SKIP decision output
- backend risk configuration
- a clear empty state linking to Portfolio Plan before analysis

It does not claim that data, portfolios, or decisions are live.

## 10. Portfolio Plan Behavior

The user can edit:

- cash
- ticker, whole shares, required current reference price, and optional cost
  basis for current positions
- EMA20 Pullback or Micho 150
- RS20 or ticker-ascending research control
- equal-slot, ATR-risk, or ATR-volatility-normalized sizing
- requested as-of date
- optional comma/space-separated ticker scope

The form never requests ATR, RS20, sector, stop distance, modeled risk budget,
strategy signal, or decision reason. It submits one high-level typed request to
`/portfolio/plan`.

EMA is fixed in the request to HYBRID 2%. Micho is fixed to BOTH. No research
tuning slider was added. The primary CTA is `Generate Portfolio Plan`, is
disabled during submission, and never represents trade execution.

## 11. Settings Behavior

Settings loads the real backend defaults from `/portfolio/risk-config` and
labels them `Session / Research Configuration`. It displays ATR period/multiple,
position and portfolio risk, position/sector caps, cash reserve, and maximum
positions. Values are not persisted to an authenticated account.

It also displays the reviewed Sprint 10B evidence classifications:

| Strategy | Equal slot | ATR risk | ATR volatility normalized |
|---|---|---|---|
| EMA HYBRID 2% | PROMISING_RESEARCH_BASELINE | RESEARCH_ONLY | RESEARCH_ONLY |
| Micho BOTH | PROMISING_RESEARCH_BASELINE | RESEARCH_ONLY | PROMISING_RESEARCH_BASELINE |

No policy is labeled production-ready.

## 12. Decision Rendering

Every returned decision remains visible, including rejections. The compact row
shows rank/order, ticker, sector, strategy signal, portfolio decision, RS20
score, proposed allocation, human-readable reason, and original machine code.

Native expandable details show returned reference price, ATR, stop proxy,
shares, target weight, modeled position risk, risk budget, sector before/after,
current shares, and estimated proceeds. BUY, SELL, HOLD, and SKIP have distinct
badges with text in addition to color. SKIP is treated as research information,
not an application error.

## 13. Data-Status Behavior

The per-ticker table exposes the actual orchestration states:

- `READY`
- `NO_ACTION`
- `COMPANY_NOT_FOUND`
- `NO_DATA`
- `STALE_DATA`
- `INSUFFICIENT_HISTORY`

Each row includes ticker, data date, signal when present, and backend reason.
Backend unavailable, invalid global request, per-ticker missing data, a
legitimate HOLD/NO_ACTION, and portfolio SKIP are presented as distinct states.

## 14. Requested Versus Actual As-of Handling

The form labels the input `Requested analysis date` and explains the stored SPY
semantics. Results separately display `Requested analysis date` and `Actual
analysis date`. The real demo requested August 25, 2026 and visibly reported
August 20, 2026 as the actual stored analysis date.

## 15. Error, Loading, and Empty States

Implemented states include:

- connectivity check / connected / backend unavailable
- `Cannot reach AlphaPilot backend.` for network failure
- detailed safe FastAPI 422 validation messages
- safe generic/invalid-response error without raw tracebacks
- retry controls for query failures
- risk-config loading
- portfolio-plan loading with duplicate submission disabled
- no current positions
- no plan yet
- no portfolio decisions
- no approved BUY decisions
- inline stale/insufficient/no-data statuses

The API client centralizes base URL, headers, parsing, non-2xx handling,
AbortSignal usage, and lightweight runtime response validation.

## 16. Accessibility Work

- semantic `aside`, `nav`, `header`, `main`, `footer`, sections, headings,
  tables, fieldsets, lists, definition lists, and native `details`
- skip link to main content
- input/select labels and accessible position group legends
- error relationships and alert/status live regions
- keyboard-native controls
- visible focus outlines
- text status labels in addition to color
- restrained high-contrast palette
- reduced-motion media handling

## 17. Responsive Behavior

The UI is desktop-first. At narrower widths:

- fixed sidebar becomes a compact horizontal navigation region
- summary and analysis grids reduce columns
- form fields and position editor collapse to one/two columns
- decision rows stack without removing information
- detail/risk grids collapse
- dense position/status tables retain horizontally scrollable containers
- actions become full-width on mobile

The real screenshot used a 1440 × 1000 browser viewport and captured the full
2,828-pixel page height. Component tests verify responsive-safe wrapper
structure; this is not native-mobile polish.

## 18. Test Coverage

The 17 frontend tests cover the requested behaviors across 5 files, including:

- Dashboard rendering and empty state
- backend-unavailable state
- required-route navigation
- backend risk defaults and research classifications
- portfolio form validation
- position add/remove
- exact high-level request serialization
- absence of ATR/RS20/stop/signal inputs in the request builder
- frozen EMA HYBRID 2% and Micho BOTH behavior
- strategy and sizing selection
- BUY, SELL, HOLD, and SKIP rendering
- reason-code human label and retained raw code
- money, percentage, date, allocation, risk, and RS20 formatting
- requested versus actual date
- stale and insufficient-history status
- plan loading and disabled duplicate submission
- empty/no-opportunity behavior
- invalid response safety
- FastAPI 422 detail presentation
- responsive scroll/container structure

MSW intercepts HTTP at the API boundary, so component tests do not require a
real FastAPI process. The separate Playwright smoke uses the real backend.

## 19. Exact Frontend Commands and Results

From `frontend/`:

```powershell
npm install
```

Final result: 289 packages audited, zero vulnerabilities. The final dependency
install succeeded. npm printed its informational MSW install-script approval
notice; no package script was manually approved or required for the tests.

```powershell
npm run lint
```

Final result: passed with zero warnings/errors.

```powershell
npm run test
```

Final result:

```text
Test Files  5 passed (5)
Tests       17 passed (17)
Duration    5.70s
```

```powershell
npm run build
```

Final result: strict TypeScript and Vite production build passed; 89 modules
transformed. Final bundle output was approximately 0.49 kB HTML, 12.98 kB CSS
(3.70 kB gzip), and 293.48 kB JavaScript (90.92 kB gzip).

## 20. Backend Focused Tests and Full Checks

Focused commands from `backend/` included:

```powershell
$env:DEBUG='false'
uv run pytest tests/api/test_portfolio_decisions.py tests/api/test_health.py tests/portfolio/test_orchestration.py
```

Result: 8 passed before the final completeness-status test was added.

Final focused command:

```powershell
$env:DEBUG='false'
uv run pytest tests/api/test_portfolio_decisions.py tests/api/test_health.py
```

Result: 7 passed in 0.46s.

Final full command:

```powershell
$env:DEBUG='false'
.\run_checks.ps1
```

Final result: passed.

- Ruff check and formatting: passed
- mypy strict: no issues in 111 source files
- pytest: 142 passed in 11.52s

`DEBUG=false` was scoped to child processes. Application configuration was not
changed to accommodate a Codex-host-only environment value.

## 21. Real Frontend-to-Backend Integration Validation

The local backend was already running on `127.0.0.1:8000` through the user's
existing Uvicorn development process. It was health-checked but not stopped or
otherwise modified. The frontend was started with:

```powershell
npm run dev -- --host 127.0.0.1 --port 5173
```

The real browser automation command was:

```powershell
npm run smoke:real
```

`frontend/scripts/real-smoke.mjs` launched the installed Microsoft Edge in
headless mode, opened the real Vite page, waited for backend connectivity,
filled the requested date and ticker scope, clicked `Generate Portfolio Plan`,
waited up to 120 seconds for the real result, inspected the rendered DOM, and
captured a full-page screenshot.

Verified end to end:

1. Browser reached Vite.
2. Vite page reached FastAPI through configured CORS.
3. Risk configuration loaded.
4. High-level portfolio state and strategy/policies serialized correctly.
5. `/api/v1/portfolio/plan` evaluated stored database candles.
6. Requested and actual dates rendered separately.
7. Actual decisions, allocations, scores, statuses, and reasons rendered.
8. Navigation and reload-safe application routing remained available.

The final smoke passed twice after the smoke-reporting helper itself was fixed.
The browser and Vite process were closed; the pre-existing user backend process
was left running.

## 22. Actual Demonstration Scenario and Rendered Result

Input:

```text
Cash:                 $100,000
Positions:            none
Strategy:             EMA20 Pullback, HYBRID 2%
Selection:            relative-strength-20
Sizing:               equal-slot
Requested as-of:      2026-08-25
Ticker scope:         AAPL, MSFT, NVDA
```

Actual backend date: `2026-08-20`.

Rendered portfolio summary:

```text
Equity:                       $100,000.00
Cash:                         $100,000.00 / 100.00%
Invested value:               $0.00 / 0.00%
Current modeled risk:         $0.00 / 0.00%
Available modeled risk:       $8,000.00 / 8.00%
Open positions:               0
```

Actual decisions:

| Ticker | Strategy signal | Decision | Reason | RS20 | Reference | ATR14 | Shares | Allocation | Weight |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| AAPL | SELL | SKIP | `NO_POSITION_TO_SELL` | unscored | $311.30 | — | 0 | $0.00 | 0.00% |
| NVDA | BUY | BUY | `BUY_APPROVED` | 0.0057 | $216.85 | $6.30 | 46 | $9,975.10 | 9.98% |

Actual per-ticker statuses:

- AAPL: `READY`, SELL, EMA20 trend breakdown
- MSFT: `NO_ACTION`, HOLD, no pullback
- NVDA: `READY`, BUY, EMA20 pullback reclaim

The UI did not fabricate an approved AAPL trade: the backend strategy produced
SELL, while the portfolio correctly returned SKIP because the user held no AAPL
position. This demonstrated the strategy-signal versus portfolio-decision
separation in the real product surface.

## 23. Screenshot

The full-page screenshot is available locally at:

`backend/backtest_reports/sprint11/ui-demo.png`

It is intentionally Git-ignored with the research artifacts. Visual inspection
confirmed a restrained desktop financial/research layout, readable hierarchy,
clear research/non-live language, distinct decision badges, visible reason
codes, responsive-safe sections, and no fake trading controls.

## 24. What Sprint 11 Proved

- The high-level backend orchestration contract is usable by a real typed UI.
- The frontend can remain presentation-only without implementing financial
  domain logic.
- Current portfolio input, frozen strategy choices, ranking, and three sizing
  policies can be expressed in a clean workflow.
- Requested/actual stored-data semantics are understandable when rendered.
- Strategy signals and portfolio decisions remain visibly distinct.
- Backend reason/data-status codes are sufficient for useful research UX.
- The React structure supports loading/error/empty states, accessibility, and
  responsive presentation without a heavy UI framework.
- Minimal additive backend presentation fields can prevent duplicated browser
  calculations while preserving research behavior.

## 25. What Sprint 11 Did Not Prove

- No UI or policy is production/live-trading ready.
- No broker account, real-time quote, fill, or order path was tested.
- No authentication, authorization, portfolio ownership, persistence, or plan
  history exists.
- Browser-local form state is not durable account state.
- The single real smoke scenario does not prove exhaustive browser/device
  compatibility or production deployment behavior.
- No company analysis page, backtest explorer, charting, or live scanner UI was
  built.
- Sprint 11 did not validate strategy profitability or alter any Sprint 6–10B
  research conclusion.

## 26. Known UI Limitations

- A current holding requires a manually entered current reference price because
  the merged request schema requires it.
- Form state is local to one browser; the generated response is retained only in
  the active React session.
- No OpenAPI type generation is installed; TypeScript contracts are reviewed
  mirrors of Pydantic schemas with lightweight runtime guards.
- The optional blank ticker scope evaluates the current active S&P 500 and may
  take materially longer than a small custom scope.
- Dense decision details are textual; advanced charts and historical analytics
  are deferred.
- Automated visual regression and multi-browser CI are not yet present.

## 27. Known Backend Limitations Exposed by the UI

The largest limitation is current portfolio-state sourcing.

There is no broker/account adapter or authenticated persisted position record.
For manually entered holdings, the backend receives shares, current reference
price, and optional cost basis, but it does not possess the original frozen ATR
entry-risk facts. The UI deliberately does not ask the user to invent those
facts. Consequently current/available modeled risk can be understated. The new
`modeled_risk_complete` field makes that limitation visible.

Other exposed limitations:

- no automatic repricing/sector/risk enrichment of the submitted current
  portfolio state
- no authenticated account ownership or saved plans
- no live/current provider fetch inside plan domain logic; stored candles only
- no explicit staleness tolerance beyond same-analysis-date orchestration status
- no dedicated combined company analysis endpoint
- no backtest-summary API suitable for browser visualization
- current active S&P 500 constituents are not a point-in-time historical
  universe; historical research still contains survivorship bias
- RS20 remains a research baseline, not universal/production alpha

## 28. API Contract Improvements Discovered

The UI caused three useful additive contract improvements:

1. Display-ready portfolio percentages and current-position facts now come from
   FastAPI, eliminating browser-side portfolio calculations.
2. `modeled_risk_complete` explicitly distinguishes a real zero from missing
   existing-position entry-risk facts.
3. Local-development CORS is explicit and configurable rather than relying on a
   wildcard or same-origin assumption.

The existing endpoint paths, decision/reason enums, orchestration statuses,
strategy behavior, and lower-level decisions endpoint remain compatible.

## 29. Security and Product Language

- No frontend secrets exist.
- `frontend/.env.example` contains only the public backend origin.
- No database, provider, broker, or private contact data was copied or printed.
- API strings render as React text, not arbitrary HTML.
- No `Trade Now`, broker execution, live portfolio, or submitted-order controls
  were added.
- The UI repeatedly identifies results as stored-data research/advisory output.

## 30. Sprint 12 Recommendation

Do not implement Sprint 12 until user/ChatGPT review.

The evidence-driven next direction should be a backend account/portfolio-state
adapter phase before adding execution language. Priorities:

1. typed broker/account or persisted research-portfolio adapter
2. authenticated ownership and saved portfolio/plan history
3. backend enrichment/repricing of current positions
4. durable recovery of frozen entry-risk facts and complete risk status
5. explicit current-data/staleness policy

After those foundations, a later UI increment can add company analysis and
backtest summaries using dedicated backend contracts. The frontend should
continue consuming backend facts rather than duplicating domain logic.

## 31. Git Status

Branch: `feature/ui-mvp`.

All Sprint 11 work remains local and uncommitted. The working tree contains 11
modified tracked files and 47 untracked source/document files after including
this completion report. `frontend/node_modules/`, `frontend/dist/`, and
`backend/backtest_reports/sprint11/` are Git-ignored.

Modified tracked files:

```text
 M .gitignore
 M AGENTS.md
 M backend/.env.example
 M backend/src/alphapilot/api/routes/portfolio.py
 M backend/src/alphapilot/core/config.py
 M backend/src/alphapilot/main.py
 M backend/src/alphapilot/schemas/portfolio.py
 M backend/tests/api/test_health.py
 M backend/tests/api/test_portfolio_decisions.py
 M docs/DECISIONS.md
 M docs/PROJECT_STATE.md
```

Untracked files are the two Sprint 11 documents and all explicitly listed
frontend files in Section 4. No unrelated user file is included.

No commit, push, PR, merge, force-push, or tag operation was performed by
Codex.

## 32. Git Diff Stat

Tracked files only; Git does not include untracked frontend files in this stat:

```text
 .gitignore                                     |  2 +
 AGENTS.md                                      | 34 ++++--------
 backend/.env.example                           |  3 +-
 backend/src/alphapilot/api/routes/portfolio.py | 71 +++++++++++++++++++++-----
 backend/src/alphapilot/core/config.py          |  2 +
 backend/src/alphapilot/main.py                 |  9 ++++
 backend/src/alphapilot/schemas/portfolio.py    | 18 +++++++
 backend/tests/api/test_health.py               | 14 +++++
 backend/tests/api/test_portfolio_decisions.py  | 36 +++++++++++++
 docs/DECISIONS.md                              | 35 ++++++++++++-
 docs/PROJECT_STATE.md                          | 21 ++++----
 11 files changed, 196 insertions(+), 49 deletions(-)
```

`git diff --check` passed. Git emitted only normal Windows LF-to-CRLF working-
copy warnings.

## 33. Recommended Commit Message

```text
feat(ui): add research portfolio decision dashboard
```

## 34. Final Conclusion

Sprint 11 is complete. AlphaPilot now has a clean, typed, responsive research
UI that consumes the real Portfolio Plan API end to end and keeps all financial
domain logic in the backend. The API required only additive presentation and
CORS improvements. The product is ready for review as a UI MVP, not for live
trading.

The primary next constraint is no longer the React surface: it is trustworthy,
durable current portfolio state. Existing-position risk completeness, broker or
persisted account state, authentication, and current-data policy should be
addressed before AlphaPilot presents itself as an operational portfolio tool.

STOP: Sprint 12 was not started.
