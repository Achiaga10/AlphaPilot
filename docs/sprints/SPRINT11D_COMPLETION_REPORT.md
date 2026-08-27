# AlphaPilot Sprint 11D Completion Report

## 1. Root cause of the observed 502 `STALE_DATA` result

The 502-stock stale result was a real stored-session mismatch, not a strategy
result and not a calendar/weekend bug. Sprint 11C had advanced SPY with a
lightweight benchmark-oriented operation while deliberately avoiding an
expensive full constituent candle refresh. The expected analysis session was
therefore later than the newest stored candle for all 502 current S&P 500
stocks. Strict freshness correctly excluded every constituent before strategy
evaluation.

Sprint 11D did not weaken this rule, forward-fill missing data, or tune a
strategy to make BUY cards appear.

## 2. Exact freshness semantics before and after Sprint 11D

The core freshness rule is preserved and now documented and surfaced clearly:

1. Let `R` be the requested calendar date.
2. Load the newest stored SPY trading session `S` such that `S <= R`.
3. Filter every stock and benchmark history to information through `S` only.
4. A stock is fresh when its newest candle through `S` is exactly `S`.
5. A stock is stale when its newest candle is earlier than `S`.
6. A stock has no data when no stored candle exists through `S`.
7. Stale/no-data stocks do not enter strategy, RS20, ATR, ranking, sizing, or
   portfolio evaluation.

Before Sprint 11D, candidate rows exposed statuses but the plan response did
not provide a first-class readiness conclusion, so an all-stale result could
look superficially like “no opportunities.” After Sprint 11D, the backend
returns typed readiness, coverage, data-status counts, signal/approval counts,
and rejection attribution. Admin freshness also separates null/no-data rows
from genuinely lagging rows instead of counting both as stale.

## 3. Trading-session, weekend, and closure behavior

Freshness is trading-session aware through the stored SPY calendar. A Sunday or
market-closure request resolves to the newest prior stored SPY session and does
not become stale merely because there is no candle on the requested calendar
day. The response and UI preserve both dates:

- requested calendar date;
- actual SPY analysis session;
- latest returned ticker-data date.

Focused tests prove a Sunday request uses Friday and that future stock candles
cannot bypass the session filter.

## 4. Plan readiness model

`PortfolioPlanReadiness` adds four stable states:

- `READY`: usable evaluation with at least one approved BUY/SELL action;
- `NO_ACTION`: normally evaluated data with no approved action;
- `PARTIAL_DATA`: some tickers were normally evaluated while others were
  unavailable, stale, missing, or history-insufficient;
- `DATA_NOT_READY`: no ticker received a normal evaluation because data was
  unusable.

Returned facts include requested, normally evaluated, fresh/session-aligned,
stale, no-data, insufficient-history, company-not-found, BUY signals, approved
BUYs, approved SELLs, actionable decisions, latest ticker-data date, and BUY
rejections by stable reason code. Requested coverage reconciles as:

`requested = fresh + stale + no_data + company_not_found`

where `fresh = normally_evaluated + insufficient_history` because an aligned
session can still lack enough lookback history for research calculations.

## 5. Zero-BUY explanation behavior

The UI now distinguishes these economically different outcomes:

- zero approved BUYs after full normal evaluation: a legitimate current
  strategy/portfolio result;
- zero BUY analysis because every ticker was stale/no-data: **Data refresh
  required**, not strategy rejection;
- zero approved BUYs within a partial result: usable coverage and excluded
  counts are both disclosed;
- BUY signals rejected by portfolio constraints: returned reason counts are
  shown without fabricating attribution.

The Approved Buys tab retains its default position even when empty and provides
context-specific copy from backend readiness facts.

## 6. Analysis coverage behavior

Plan metadata displays normally evaluated/requested coverage beside requested
and actual analysis dates. The readiness banner separately shows session-
aligned, stale, and no-data counts. This avoids treating insufficient-history
stocks as normally evaluated and avoids treating a later requested calendar
date as a nonexistent trading candle.

## 7. Data-recovery workflow

Blocked/partial readiness provides **Go to Data Management**. Data Management
shows the stored SPY session, fresh/stale/no-data coverage, configured provider
and feed, progress for the selected sync, a persistent completion/failure
summary, and **Return to Portfolio Plan** after candle/full-sync success. Active
jobs disable conflicting expensive sync buttons and state that a sync is
already running.

## 8. Dashboard portfolio-allocation donut

Dashboard now begins with a reactive **Research Portfolio Draft** section. It
contains a compact SVG donut, legend, backend-valued equity, cash, and current
managed positions. The **Latest Portfolio Plan** remains a separate frozen
analysis snapshot below it.

The donut updates immediately after an approved BUY, approved SELL, manual
position edit, partial manual sale, or full manual sale. No plan regeneration is
required for basic current-portfolio visualization.

## 9. Exact chart data source

React calls `POST /api/v1/portfolio/state-summary` for the canonical draft. The
backend calculates position market values from the draft’s stored reference
prices, shares, and cash and returns value/weight fields. React uses those exact
returned `market_value`, `portfolio_weight_pct`, `cash`, and `cash_pct` values;
it performs only SVG circumference/offset rendering. The chart is stored-data
research bookkeeping, not live brokerage valuation.

## 10. Color and accessibility behavior

Position slices are ticker-sorted and receive deterministic distinct colors
from a fixed palette; Cash uses a neutral gray. The original backend amounts
and percentages appear in the matching legend. Each SVG slice is keyboard
focusable and has an accessible ticker/cash, value, and percentage label plus a
native title. The all-cash state is explicit. Responsive CSS stacks chart and
legend on smaller screens without changing financial values.

## 11. Sync progress architecture

`AdminSyncProgress` now includes a safe stage and current ticker in addition to
total/attempted/synced/skipped/failed counts and failed ticker identifiers.
Process-local jobs expose determinate progress only when a meaningful total is
known and otherwise use an accessible indeterminate progress bar. Final job
snapshots retain `stage=complete` rather than losing stage information.

## 12. Universe progress behavior

Universe Sync reports:

1. `universe_discovery`;
2. per-company `company_metadata` with current ticker and counts;
3. `membership_sync`;
4. `complete`, including created/updated/unchanged companies, membership
   additions/removals, and active constituent count.

## 13. Candle progress behavior

Market Candles Sync reports SPY `benchmark` first, then `stock_candles` batch
progress with current batch/ticker context, accumulated successes/skips/
failures, and final `complete`. A benchmark failure or configured-feed
authorization failure remains explicit and does not silently fall back feeds.

## 14. Full-sync progress behavior

Full Sync preserves the existing Universe-then-Candles architecture and renders
the two phases separately. Universe completion remains visible when candle
progress begins. Final totals, provider/feed, timestamps, constituent changes,
and failures remain visible after completion.

## 15. Ticker and custom-ticker progress behavior

Fast one-ticker and Add & Sync mutations display explicit staged progress
surfaces. Custom onboarding lists ticker validation, metadata, company
persistence, and historical candles; known-ticker sync lists queue, candle
request, persistence, and completion. Their terminal typed results determine
success/failure—no fake timed progress is used.

## 16. Data-freshness dashboard changes

Dashboard and Data Management now show latest SPY session, fresh tracked,
stale tracked, no-data, S&P/custom scope, and last successful candle-sync facts.
Warnings are based on actual stale/no-data counts. The feed is explicitly IEX
in the validated local environment.

## 17. Backend files changed for Sprint 11D

Created:

- `backend/src/alphapilot/portfolio/actions.py`
- `backend/tests/portfolio/test_actions.py`

Modified:

- `backend/src/alphapilot/api/routes/portfolio.py`
- `backend/src/alphapilot/portfolio/decisions.py`
- `backend/src/alphapilot/portfolio/orchestration.py`
- `backend/src/alphapilot/repositories/daily_candle.py`
- `backend/src/alphapilot/repositories/research_data.py`
- `backend/src/alphapilot/schemas/admin_data.py`
- `backend/src/alphapilot/schemas/portfolio.py`
- `backend/src/alphapilot/services/admin_data.py`
- `backend/src/alphapilot/services/daily_candle.py`
- `backend/tests/api/test_admin_data.py`
- `backend/tests/api/test_portfolio_decisions.py`
- `backend/tests/portfolio/test_decisions.py`
- `backend/tests/portfolio/test_orchestration.py`
- `backend/tests/services/test_research_admin_data.py`

These are Sprint 11D changes inside the larger still-uncommitted Sprint
11/11B/11C/11D working tree. Earlier Sprint 11C admin/custom-provider files are
also untracked because the user has intentionally not committed the combined UI
work yet.

## 18. Frontend files changed for Sprint 11D

Created:

- `frontend/src/components/SyncProgress.tsx`
- `frontend/src/components/SyncProgress.test.tsx`
- `frontend/src/features/portfolio/ManualSellDialog.tsx`
- `frontend/src/features/portfolio/PlanReadinessBanner.tsx`
- `frontend/src/features/portfolio/PlanReadinessBanner.test.tsx`
- `frontend/src/features/portfolio/PortfolioAllocationDonut.tsx`
- `frontend/src/features/portfolio/PortfolioAllocationDonut.test.tsx`
- `frontend/src/features/portfolio/ResearchPortfolioPanel.tsx`
- `frontend/src/pages/PortfolioActions.test.tsx`

Modified:

- `frontend/scripts/real-smoke.mjs`
- `frontend/src/api/portfolio.ts`
- `frontend/src/features/dashboard/PlanOverview.tsx`
- `frontend/src/features/portfolio/DecisionTable.tsx`
- `frontend/src/features/portfolio/OpportunityExplorer.tsx`
- `frontend/src/features/portfolio/PlanForm.tsx`
- `frontend/src/features/portfolio/PortfolioSummary.tsx`
- `frontend/src/features/portfolio/PortfolioWorkspace.tsx`
- `frontend/src/features/portfolio/PositionsTable.tsx`
- `frontend/src/hooks/usePortfolioApi.ts`
- `frontend/src/pages/AdminDataPage.tsx`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/pages/PortfolioPage.tsx`
- `frontend/src/pages/AdminDataPage.test.tsx`
- `frontend/src/pages/DashboardPage.test.tsx`
- `frontend/src/pages/PortfolioPage.test.tsx`
- `frontend/src/test/fixtures.ts`
- `frontend/src/test/server.ts`
- `frontend/src/types/portfolio.ts`
- `frontend/src/styles.css`

The official logo source
`frontend/src/assets/images/alphapilot-logo.png` remained unchanged (SHA-256
`45294393C92AF82A3859B12932507016EFA9C8065AC5634736DE551E60C501B1`).

## 19. Tests added or changed

Backend coverage includes:

- all-fresh BUY and all-fresh zero-action readiness;
- all-stale data-not-ready behavior;
- partial stale coverage and weekend-to-prior-session mapping;
- future-candle exclusion and no stale strategy bypass;
- readiness/count serialization;
- deterministic action IDs, dependency order, duplicate rejection, current
  cash revalidation, sequential BUYs, and approved full SELL;
- manual preview, partial/full sale, proportional modeled-risk remainder,
  stored price/date, explicit override, missing price, and invalid shares;
- backend-owned state summary and action/manual API contracts;
- admin fresh/stale/no-data counts and progress stage/current ticker.

Frontend coverage includes all-stale, partial, and fully fresh zero-opportunity
copy; recovery link; constraint outcomes; donut backend values, colors, cash,
all-cash, keyboard access; queued/indeterminate/0/partial/100/failure/full/
universe/inline progress; same-plan three-action application, dependency lock,
duplicate prevention, cash sequence, stale manual change, regeneration reset,
Dashboard/donut reactivity, partial/full manual sale, stored price/date,
override, missing price, invalid shares, and canonical persisted workspace.

## 20. Frontend commands and results

Commands executed:

```powershell
cd frontend
npm test -- src/features/portfolio/PlanReadinessBanner.test.tsx src/features/portfolio/PortfolioAllocationDonut.test.tsx src/components/SyncProgress.test.tsx src/pages/PortfolioActions.test.tsx --reporter=dot
npm test -- --reporter=dot
npm run lint
npm run build
npm run smoke:real
```

Results:

- focused Sprint 11D frontend: **14 passed**;
- full frontend: **59 passed in 15 files**;
- ESLint: **passed with zero warnings**;
- TypeScript/Vite production build: **passed**, 103 modules transformed;
- official logo bundled as a hashed Vite asset;
- controlled real-browser acceptance: **passed**.

## 21. Backend commands and `run_checks` result

Commands executed:

```powershell
cd backend
$env:DEBUG='false'
uv run pytest tests/portfolio/test_orchestration.py tests/portfolio/test_actions.py tests/services/test_research_admin_data.py tests/api/test_portfolio_decisions.py -q
$env:DEBUG='false'
.\run_checks.ps1
```

Results:

- focused Sprint 11D backend: **19 passed**;
- Ruff check/format: **passed**;
- mypy: **passed, 119 source files**;
- full pytest: **170 passed**;
- overall `run_checks.ps1`: **All checks passed**.

`DEBUG=false` was scoped only to child validation processes because the Codex
host can inject an invalid value; application configuration was not weakened.

## 22. Real-browser validation

Headless Microsoft Edge loaded the actual Vite app and exercised a controlled,
safe portfolio workflow through the real React UI and typed HTTP boundaries:

- official 1024×1024 logo rendered at equal width/height with `object-fit:
  contain`;
- three dependent approved BUYs applied without regeneration;
- exact cash sequence was `$30,000 -> $29,000 -> $28,000 -> $27,000`;
- three action cards became **Applied** and could not be repeated;
- Dashboard immediately showed NVDA, AMD, AAPL, cash, position counts, and the
  updated donut;
- manual input made the plan stale and regeneration reset the session;
- JNJ defaulted to all 200 shares at latest stored `$150`, dated Aug 25, 2026;
- a 40-share partial sale left 160 shares and updated cash/donut;
- the subsequent full sale removed JNJ and updated cash/donut;
- no broker/order/trade endpoint was requested;
- responsive, visually coherent output was captured at
  `backend/backtest_reports/sprint11d/ui-smoke.png` (Git-ignored).

## 23. Real and controlled sync validation

The local backend reported configured provider/feed `Alpaca / iex`. Real stored
data was already fully aligned when validation resumed:

- active companies: 505;
- active S&P 500: 502;
- active custom tracked: 2;
- SPY: 2026-08-25;
- oldest/newest tracked latest session: 2026-08-25 / 2026-08-25;
- fresh tracked: 504;
- stale: 0;
- no data: 0.

Because a new expensive provider call was unnecessary, Sprint 11D did not
repeat the real market-candle sync. The prior real persisted outcome was
verified from the database summary. The browser then completed a controlled
Market Candles Sync from 0 through 250/503 to 503/503 and verified completion,
100% accessible progress, provider/feed, and persistent summary behavior.
Process-local last-sync timestamps were null after server restart; this is an
honestly retained limitation, not evidence that stored candles are absent.

## 24. Post-sync real Portfolio Plan result

Exact request:

```text
POST /api/v1/portfolio/plan
strategy=ema20-pullback
exit_mode=hybrid
hybrid_trend_threshold_pct=2
selection_policy=relative-strength-20
sizing_policy=equal-slot
as_of_date=2026-08-26
portfolio.cash=100000
portfolio.positions=[]
tickers omitted (current active S&P 500)
```

The backend resolved requested Aug 26 to the latest stored trading session Aug
25 and produced plan `a8db920a43d0ed45f9ec2bab`.

## 25. Fresh/evaluated/BUY/approved-BUY counts

| Fact | Count |
|---|---:|
| Requested current S&P 500 tickers | 502 |
| Session-aligned/fresh | 502 |
| Normally evaluated | 501 |
| Insufficient history | 1 |
| Stale | 0 |
| No data | 0 |
| Company not found | 0 |
| BUY signals | 61 |
| Approved BUYs | 10 |
| BUY rejections: `MAX_POSITIONS` | 51 |
| Approved SELLs | 0 |
| Returned decisions | 293 |

Readiness was `PARTIAL_DATA` solely because one session-aligned ticker had
insufficient history. The 10 approved BUYs are legitimate frozen-strategy
output after fresh evaluation; no strategy/ranking/risk parameter was changed.

## 26. Remaining limitations

- Current S&P historical work retains survivorship bias and is not a
  point-in-time constituent universe.
- Prices are stored daily-candle/reference values, not live broker quotes.
- Research portfolio state is browser-local; no authenticated account,
  server-side portfolio persistence, or broker synchronization exists.
- Apply-action endpoints are stateless research-draft transformations, not
  durable transactional commands or broker orders.
- Applied action IDs are session-local; refresh restores the updated draft but
  not the active recommendation-application session.
- Process-local sync job history/timestamps do not survive backend restart.
- Batch progress reports the current batch boundary/ticker, not streaming
  provider-level progress for every individual HTTP request.
- Manual sale uses gross proceeds with no commission/slippage and is research
  bookkeeping, not execution accounting.
- User-provided manual execution prices cannot be independently verified; they
  are explicitly labeled and have no stored candle date.
- The latest stored close may be stale for a manually held ticker; its exact
  stored date is disclosed.
- The chart uses at most ten predefined distinct position colors, matching the
  current max-position research baseline.
- RS20 remains a research baseline, not universally production-ready.
- No authentication or authorization protects enabled local Admin tools; the
  configuration gate remains an explicit development-only safety boundary.

## 27. Sprint 11 commit-readiness conclusion

Sprint 11D is complete successfully. The combined Sprint 11/11B/11C/11D
working tree now has backend-owned readiness, recovery, decision application,
manual sale bookkeeping, a reactive portfolio workspace, observable admin
sync, and complete UI explanation. Frontend and backend gates and controlled
browser acceptance pass. The real current-universe plan evaluated fresh data
and returned traceable signals/approvals.

The work is ready for the user’s review and then a user-controlled commit/PR.
It is not production trading software, does not send broker orders, and Sprint
12 has not started.

## 28. Git status

- Branch: `feature/ui-mvp`
- Working tree: dirty by design; all Sprint 11 through Sprint 11D work remains
  local and uncommitted.
- No commit, push, PR, merge, force-push, or tag operation was performed.
- Modified tracked areas include root instructions/ignore rules, backend source
  and tests, and continuity docs.
- Untracked areas include the complete `frontend/`, Sprint 11/11B/11C/11D
  plans/reports, the custom-company migration, and new backend admin/action/
  provider/repository/service/test modules.

Run `git status --short` before committing; `.env` files and Git-ignored browser
artifacts are not intended for commit.

## 29. Git diff summary

Tracked-file diff before this completion report:

```text
35 tracked files changed, 1,491 insertions(+), 269 deletions(-)
```

`git diff --stat` does not include untracked files, notably the full frontend
tree and newly created backend/docs files. The final user staging review must
include those intended source, test, migration, and documentation files while
excluding `.env`, dependencies, build output, and report artifacts.

## 30. Recommended commit message

```text
feat: complete Sprint 11 research UI and data readiness workflow
```

## 31. Same-plan multi-action application semantics

Approved BUY/SELL decisions carry a deterministic `action_id` and advisory
`application_order`. Candidate rank and response order do not create action
dependencies: the engine emits empty `depends_on_action_ids` unless a future
decision has a genuine operational dependency. Before an action is applied,
the backend previews or revalidates it against the current draft, selected
quantity, sizing policy, and risk configuration. A successful response updates
the canonical draft with exact backend-returned shares, cash, sector, and
modeled risk while the remaining recommendations stay available for their own
current-state validation.

## 32. How plan validity is preserved across approved actions

An exact approved action is part of the active plan’s prescribed state
transition. After success, the workspace advances both the persisted draft and
its expected plan snapshot to the backend-returned state. The analysis remains
active, applied cards remain visible as **Applied**, and a notice clarifies that
risk/analysis metrics describe the original snapshot. Arbitrary manual edits
do not advance the expected snapshot and therefore make the plan stale.

## 33. Current draft cash revalidation

The backend ignores the plan’s old display-only `cash_after_decision` when
deciding whether the action is still feasible. For a BUY it verifies current
draft cash is at least the frozen approved outlay, subtracts that outlay, and
returns the exact new state. Insufficient cash returns
`INSUFFICIENT_CURRENT_DRAFT_CASH` without mutation. Cash cannot become negative.

## 34. Decision dependency and order behavior

The portfolio engine’s response order remains SELLs first, then ranked BUYs,
then non-actions, but that sequence is advisory rather than a required click
order. A user may review and apply any currently valid approved candidate. The
backend revalidates that chosen action against current cash, holdings, position
count, reserve, position-weight, portfolio-risk, and sector constraints. Empty
dependency lists do not produce `PRIOR_ACTION_REQUIRED`; that code is retained
only for a future genuine dependency. SELL application also verifies the
position still exists with the same full share count, and BUY verifies the
ticker is not already held.

## 35. Reactive Research Portfolio Draft architecture

`PortfolioWorkspaceProvider` is the single client owner of cash, positions,
plan, expected snapshot, applied IDs, pending action, and user message. It
persists one `alphapilot.plan-draft.v1` value and listens for cross-tab storage
events. Dashboard, Portfolio Plan, forms, current holdings, and donut all consume
the same context. No Redux or second portfolio copy was introduced.

## 36. Immediate Dashboard synchronization behavior

Every backend-applied action or manual sale updates the provider state and
localStorage immediately. Dashboard current holdings, cash, equity, position
count, and donut rerender without refresh or plan regeneration. The latest plan
section remains visibly labeled as an analysis snapshot, preventing current
bookkeeping from being confused with frozen plan metrics.

## 37. Manual Sell Position workflow

Current-position rows expose **Sell Position**. The modal clearly states
“Research bookkeeping · no broker order,” loads the latest stored price/date,
defaults quantity to all held shares, validates whole shares, previews the
backend result, and requires a second **Update Research Portfolio** confirmation.
No endpoint or label says “Execute Sell.”

## 38. Default stored-price behavior and exact source

`GET /api/v1/portfolio/latest-price/{ticker}` loads the latest stored
`DailyCandle.close` and trading day through repository/service boundaries. If
used, responses identify `LATEST_STORED_CANDLE` and display “not a live price.”
If no stored price exists, the UI requires an explicit manual price and the
backend returns `STORED_PRICE_UNAVAILABLE` rather than fabricating one.

## 39. Partial versus full sell behavior

A partial sale adds `whole_shares_sold * execution_price` to cash, keeps cost
basis/reference price, and scales modeled risk proportionally to remaining
shares. A full sale adds gross proceeds and removes the position. Both return a
complete backend-calculated state/summary; cash and donut update immediately.

## 40. Manual execution-price override

A user may replace the stored default for bookkeeping. The backend labels the
source `USER_PROVIDED`; `price_date` is null so the external value is not
misrepresented as a stored candle. Positive Decimal validation remains typed.

## 41. Portfolio-state persistence behavior

Approved actions and manual sales persist the same canonical local draft used
by both main pages. Reload restores updated cash/positions. Cross-tab storage
events refresh another open AlphaPilot tab when straightforward browser events
are delivered. There is still no authenticated server-side portfolio account.

## 42. Updated real-browser multi-action acceptance result

The earlier controlled browser scenario completed all three then-ordered BUYs without
regeneration, prevented duplicates, updated Dashboard/donut instantly, marked a
manual cash edit stale, reset after regeneration, verified stored price/date,
performed partial then full manual sale, reconciled final cash, and observed no
broker/order/trade request. The separate controlled candle-sync UI progressed
to 503/503 and retained its completion summary. Acceptance result: **PASS**.

Sprint 12 was not started.

## 43. Final manual-review addendum

Synthetic BUY-rank dependencies were removed. Candidate rank remains visible
with the exact explanation that it is
AlphaPilot recommendation priority and does not require applying positions in
order. A user can ignore rank 1 and review/apply rank 4 first. Applied IDs still
prevent duplicate application, and the current research draft is revalidated
for every selected action.

Each approved BUY card defaults **Shares to add** to backend
`proposed_shares`. `POST /api/v1/portfolio/preview-action` returns backend-owned
cash/outlay, resulting position and sector weights, cash reserve, modeled risk,
and portfolio risk where applicable. The confirmation distinguishes the
AlphaPilot recommendation from the user selection. Values are never silently
clamped.

Exact quantity is `SAME_PLAN_ACTION`. A different quantity is
`USER_QUANTITY_OVERRIDE`; after application the UI states that the draft is
`DEVIATED_FROM_PLAN` and that remaining recommendations will be revalidated.
It does not force a 502-stock regeneration solely for a quantity change.

Current-draft BUY validation covers duplicate holding, max positions, whole
shares, cash, max position weight, sector limit, and for risk-aware sizing the
minimum reserve, valid ATR distance, and portfolio modeled-risk limit. Stable
rejection codes identify the actual failing constraint.

## 44. Frozen strategy exit guidance

New typed backend `StrategyExitContext` is calculated from the same strategy
evaluation and candles already filtered through the analysis day. It is carried
to BUY, HOLD, SELL, and SKIP decision details, including held positions.

EMA20 Pullback HYBRID 2% exposes close, EMA20, EMA50, their spread, the frozen
2% threshold, signed distances, signal reason, and exact state:

- close below EMA50: hard `EMA50_BREAKDOWN` SELL state;
- close at/above EMA20: trend held;
- close between the averages with spread at least 2%: strong-trend HOLD;
- close between the averages with weaker spread: EMA20 breakdown SELL state.

Micho V1 exposes close, SMA150, signed distance, and its exact close-below-
SMA150 exit state. No strategy was changed.

The UI explicitly displays **Fixed take-profit policy: None in current
strategy**. It explains that the frozen strategies stay in a trend until their
strategy exit condition and that a fixed target has not been validated. Any
2×ATR14 level is labeled a research risk reference only—not an active stop,
order, alert, or live monitor. Every context displays `Data as of YYYY-MM-DD`.
Fixed R-multiple, ATR trailing, peak-drawdown trailing, partial-profit, and
strategy-exit control comparisons remain possible future research requiring
separate development/validation discipline; none was implemented here.

## 45. Not-applicable metrics and sector regression

Equal-slot does not use ATR stop distance, modeled position risk, or risk budget
for sizing. Those decision-detail fields now display **Not used by Equal-slot**
instead of `$0.00`; non-BUY contexts display **Not applicable**. This prevents a
zero proxy from being mistaken for zero financial risk.

The reviewed `Sector before 0.00% / Sector after 0.00%` BUY was a genuine
Equal-slot reporting defect. `EqualSlotPositionSizer` had hard-coded both output
fields to zero. It now reports:

```text
sector_before = current sector market value / portfolio equity
sector_after = (current sector market value + proposed allocation) / portfolio equity
```

Its existing equal-slot share formula was not changed. A regression test
verifies a 10% current sector plus 10% proposed allocation reports 10% before
and 20% after.

## 46. Addendum files and focused validation

Created:

- `backend/src/alphapilot/portfolio/exit_guidance.py`
- `backend/tests/portfolio/test_exit_guidance.py`
- `frontend/src/features/portfolio/BuyActionPreviewDialog.tsx`
- `frontend/src/features/portfolio/DecisionTable.test.tsx`

Modified for the addendum: continuity docs; backend actions, decisions,
orchestration, sizing, schemas, routes, and focused tests; frontend API, types,
workspace, decision/explorer/dashboard/page styling, fixtures, and tests.

Focused evidence before the final repository gate:

```text
backend focused pytest: 24 passed
backend Ruff: passed
backend mypy: passed across 120 source files
frontend Vitest: 62 passed across 16 files
frontend production build: passed; official PNG bundled
```

The final repository-wide gate and final Git state are recorded in the closing
sections after validation. Sprint 12 was not started.

## 47. Final quality gate after Parts X/Y/Z/AA

Commands:

```powershell
cd frontend
npm run lint
npm test -- --run
npm run build

cd ..\backend
$env:DEBUG='false'
.\run_checks.ps1
```

Results:

```text
frontend ESLint: passed with zero warnings
frontend Vitest: 66 passed across 16 files
frontend TypeScript/Vite production build: passed
backend Ruff: passed
backend mypy: passed across 120 source files
backend pytest: 176 passed
run_checks.ps1: All checks passed
```

The official user-provided
`frontend/src/assets/images/alphapilot-logo.png` remained unchanged. Its final
SHA-256 is
`45294393C92AF82A3859B12932507016EFA9C8065AC5634736DE551E60C501B1`, and the
Vite build bundled that source asset.

## 48. Final Git state

Branch:

```text
feature/ui-mvp
```

The working tree remains intentionally dirty with the combined uncommitted
Sprint 11/11B/11C/11D work. `git status --porcelain` reports 60 top-level status
entries: 36 tracked modified paths and 24 untracked paths/directories. The
tracked-only summary is:

```text
36 files changed, 1,807 insertions(+), 273 deletions(-)
```

Untracked source/test/documentation includes the full `frontend/` tree, the
Sprint 11 through Sprint 11D plans/reports, the existing Sprint 11C admin/action
modules and migration, plus the new exit-guidance/action tests. `.env` files,
`node_modules`, `dist`, and browser artifacts remain excluded and are not
intended for commit. `git diff --check` passed apart from informational Windows
LF-to-CRLF notices.

Recommended commit message remains:

```text
feat: complete Sprint 11 research UI and data readiness workflow
```

Sprint 11D, including Parts X/Y/Z/AA, is complete locally. Sprint 12 was not
started. No commit, push, PR, merge, force-push, or tag operation was performed.

## 49. Single-stock identity bug root cause

The high-level plan intentionally expands an explicit ticker scope with current
holdings so exits and portfolio constraints have complete context. It then
iterates the combined set in ticker order. `EvaluatePage` incorrectly selected
`plan.candidate_statuses[0]`, then found a decision for that first status. This
was a positional UI assumption, not a strategy or Company-data corruption.

The exact reproduced class was a Research Portfolio holding LDOS plus an
explicit SBET request. The backend correctly returned both LDOS and SBET for
context, in that order. The old page therefore rendered LDOS.

## 50. Why SBET displayed LDOS

LDOS sorts before SBET. Because the old page treated the first status as the
single-stock target, it displayed the authoritative LDOS tuple—Leidos / LDOS /
its portfolio state—even though the explicit request scope was SBET. Existing
holdings remain necessary portfolio context and were not removed to mask the
bug.

## 51. Exact frontend/backend fix

Backend:

- `PortfolioOrchestrationResult` and `PortfolioPlanSchema` now expose
  `evaluation_target_ticker` when exactly one explicit ticker was requested;
- the target is trimmed and normalized to uppercase before held positions are
  added to the analysis scope;
- each known `CandidateOrchestrationStatus` exposes the authoritative stored
  `company_id` alongside ticker, Company name, sector, and tracking status;
- unknown targets retain their own normalized status and null Company identity.

Frontend:

- `EvaluatePage` no longer indexes any response array;
- it requires the normalized submitted ticker to equal
  `evaluation_target_ticker` and selects exactly one matching candidate status;
- it finds a matching decision by normalized ticker only;
- a known Company status must include its authoritative Company ID;
- a missing, duplicate, or mismatched target clears the result and displays
  `AlphaPilot could not match the evaluation response to TICKER.`;
- development diagnostics log only target/status identity, not secrets.

The API runtime guard and TypeScript types require the new target field. No
strategy, ranking, risk, portfolio-context, or no-lookahead semantics changed.

## 52. How evaluation target identity is now guaranteed

The enforced invariant is:

```text
normalized(requested_ticker) == normalized(returned_target_ticker)
normalized(requested_ticker) == normalized(rendered_result.ticker)
```

Rendering occurs only from the exact matching status. Company name, Company ID,
sector, stored-data date, signal, and decision all come from that matched backend
identity. If the invariant cannot be satisfied, the page renders an error and
never another ticker's result.

## 53. Old-result/input-draft behavior

The editable input and successful evaluation are separate state snapshots.
Changing LDOS input to SBET does not relabel the LDOS card. Until a new request
succeeds, the UI states:

```text
Showing previous evaluation for LDOS. Evaluate SBET to update.
```

A matching successful response replaces the prior snapshot. An unknown ticker
replaces the previous Company with its own typed `COMPANY_NOT_FOUND` result.

## 54. Race-condition handling

Each submission receives a monotonically increasing local request ID. Only the
latest active request may set the evaluation, error, or pending state. A focused
test holds an SBET response, completes a later AAPL request, then releases SBET;
the displayed result remains AAPL.

## 55. Regression tests and final checks

Focused commands and results:

```text
backend:
$env:DEBUG='false'
uv run pytest tests/portfolio/test_orchestration.py tests/api/test_portfolio_decisions.py -q
14 passed

frontend:
npm test -- --run src/pages/EvaluatePage.test.tsx
9 passed
```

Coverage includes LDOS-held/SBET-target ordering, target-last responses,
lowercase normalization, custom tracking independent of S&P membership,
authoritative Company identity, unknown targets, safe mismatch errors, input
draft versus evaluated snapshot, and latest-request-wins behavior. Existing
orchestration no-lookahead coverage remains green.

Final quality gate:

```text
frontend npm run lint: passed with zero warnings
frontend npm test: 66 passed across 16 files
frontend npm run build: passed
backend .\run_checks.ps1:
  Ruff passed
  mypy passed across 120 source files
  pytest 176 passed
  All checks passed
```

## 56. Real-browser SBET-with-existing-holdings result

A reusable Edge/Playwright acceptance command was added:

```text
cd frontend
npm run smoke:identity
```

It used the real current stored database through a freshly loaded FastAPI/Vite
pair and a browser-local Research Portfolio containing LDOS. Exact observations:

```text
Held ticker: LDOS
Evaluate SBET heading: Sharplink Inc
Evaluate SBET identity: SBET · Hotels, Restaurants & Leisure
Data as of: Aug 26, 2026
LDOS/Leidos rendered as target: no

After editing, before submitting:
Showing previous evaluation for SBET. Evaluate AAPL to update.

Evaluate AAPL heading: Apple Inc.
Evaluate AAPL identity: AAPL · Information Technology
```

Acceptance result: **PASS**. The final correctness blocker is resolved locally.
Sprint 12 was not started, and no Git publishing operation was performed.

## 57. Whether Alpaca exposes an in-progress current-day 1Day bar

Part AB closes a real completed-daily-candle integrity defect. During the open
U.S. session on August 26, 2026, the configured Alpaca IEX daily-bars endpoint
returned a same-day aggregate for both SPY and SBET:

```text
SPY: 2026-08-26 close 764.82, volume 385959
SBET: 2026-08-26 close 8.215, volume 221583
```

Those values were still changing intraday. Therefore: **yes, Alpaca can expose
an in-progress current-day 1Day aggregate while the U.S. session remains open**.

## 58. Whether AlphaPilot previously persisted or used such a bar

Before this fix, Alpaca mapped the timestamp to `trading_day` without
completion metadata, both single and bulk sync paths persisted every returned
bar, and repository latest/history queries had no completed-session cutoff. The
database consequently contained partial August 26 rows (SPY close 765.4500 and
SBET close 8.2200), proving that a daily decision could consume an unfinished
bar.

The affected downstream paths were strategy candles, EMA/SMA evaluation, RS20,
ATR14, ranking, portfolio decisions, exit guidance, latest stored price, and
Admin freshness. Backtest historical semantics remain unchanged because past
sessions are already before the completion cutoff.

## 59. Exact completed-session rule

`backend/src/alphapilot/market/session.py` adds the backend-owned
`CompletedDailySessionPolicy`. It uses the IANA `America/New_York` time zone and
a conservative 16:15 New York completion boundary:

```text
before 16:15 ET: completed_through = previous calendar date
at/after 16:15 ET: completed_through = current New York date
```

The extra 15 minutes avoids treating the official close instant as proof that a
provider's daily aggregate has finalized. Early-close sessions are
conservatively unavailable until 16:15 rather than guessed. Weekends and market
holidays do not rely on weekday arithmetic: orchestration chooses the newest
stored completed SPY session on or before the request cutoff, making stored SPY
dates the effective exchange-session calendar. No browser clock participates.

For a request on August 26 while the U.S. market is open, metadata therefore
remains truthful:

```text
requested date: 2026-08-26
completed analysis session: 2026-08-25
data as of: 2026-08-25
```

## 60. Persistence and upsert changes

New incomplete same-day provider bars are filtered before persistence in both
`MarketSyncService` and `AlpacaBulkMarketSyncService`, with a second defensive
filter in `DailyCandleRepository.upsert_many`. Direct DailyCandle creation also
rejects an incomplete session.

Existing partial rows are not destructively deleted. Every normal repository,
orchestration, latest-price, and research-admin read quarantines rows after the
completed cutoff. Once the session is complete, the existing unique
`(company_id, trading_day)` upsert replaces any legacy partial row with the
provider's final OHLCV. This required no schema change or cleanup migration.

## 61. Stock Evaluation current-day behavior

When today is requested before completion, Single Stock Evaluation preserves
the requested date but resolves and displays the prior stored completed SPY
session as both `Completed analysis session` and `Data as of`. Its stock history,
strategy facts, RS20, and ATR14 are all cut off at that completed date. At or
after the backend completion boundary, a synchronized final current-day bar may
become the analysis session. The frontend does not infer this from local time.

## 62. Portfolio Plan current-day behavior

The portfolio orchestrator independently filters benchmark and stock histories
through the same completed boundary before selecting the SPY analysis session.
All tickers are evaluated against that one completed benchmark session. Strategy
signals, EMA/SMA values, RS20, ATR14, ranking, constraints, decisions, and exit
guidance therefore cannot observe T's unfinished daily candle. Future and T+1
execution guarantees remain intact.

Focused regression coverage proves that changing partial T data cannot change a
decision based on T-1, future SPY data cannot advance the analysis session, a
completed T bar becomes eligible after the boundary, and the July 3, 2026 U.S.
holiday correctly resolves to the stored July 2 SPY session.

## 63. Latest-price completed-close semantics

Repository latest-history reads and research-admin aggregate queries now apply
the completed-session cutoff. The UI labels are explicit:

- Dashboard shows `Stored completed daily data - not live` and `Latest stored
  completed SPY session`.
- Admin reports oldest/newest tracked completed close and completed SPY session.
- Manual Sell uses `Latest stored completed close`, including its source date.

No React component calculates exchange-session completion. It renders dates and
status supplied by the backend. The wording avoids presenting a stored completed
close as a live quote.

## 64. Regression tests and quality-gate results

Focused backend command:

```powershell
cd backend
$env:DEBUG='false'
uv run pytest tests/market/test_session.py tests/services/test_completed_daily_candles.py tests/services/test_alpaca_bulk_market_sync.py tests/integration/test_market_sync.py tests/portfolio/test_orchestration.py tests/api/test_portfolio_decisions.py -q
```

Result: **30 passed**.

Final backend gate:

```powershell
cd backend
$env:DEBUG='false'
.\run_checks.ps1
```

Result: Ruff and formatting passed; mypy passed across 121 source files; all
**187 tests passed**; the script reported `All checks passed!`.

Final frontend gate:

```powershell
cd frontend
npm run lint
npm test -- --run
npm run build
```

Result: ESLint passed with zero warnings; **67 tests passed across 16 files**;
TypeScript and the Vite production build passed. The official unmodified
AlphaPilot PNG was bundled successfully.

## 65. Real and controlled validation result

Validation used the configured provider and current development database without
printing credentials. A freshly loaded FastAPI/Vite pair was used so no stale
server process could mask the implementation. While Alpaca demonstrably exposed
August 26 partial daily bars, the corrected API returned:

```text
SPY latest stored completed session: 2026-08-25, close 765.7900
SBET latest stored completed session: 2026-08-25, close 8.3400
```

Browser acceptance with an existing LDOS holding and explicit SBET evaluation
showed the authoritative SBET identity, `Requested Aug 26, 2026`, `Completed
analysis session Aug 25, 2026`, and `Data as of Aug 25, 2026`. Manual Sell also
displayed the latest stored completed close dated August 25. Temporary validation
backend processes were stopped afterward; the existing local Vite development
listener was left untouched.

This is direct evidence that provider availability of a partial T bar no longer
advances the decision, benchmark, latest-price, or displayed data session.

## 66. Files changed for Part AB

Source files created:

- `backend/src/alphapilot/market/session.py`

Source files modified:

- `backend/src/alphapilot/repositories/daily_candle.py`
- `backend/src/alphapilot/repositories/research_data.py`
- `backend/src/alphapilot/services/daily_candle.py`
- `backend/src/alphapilot/services/market_sync.py`
- `backend/src/alphapilot/services/alpaca_bulk_market_sync.py`
- `backend/src/alphapilot/portfolio/orchestration.py`
- Evaluate, Dashboard, Portfolio Plan, Admin Data, and Manual Sell frontend
  presentation components and their shared types/tests
- `frontend/scripts/single-stock-identity-smoke.mjs`

Tests created or extended:

- `backend/tests/market/test_session.py`
- `backend/tests/services/test_completed_daily_candles.py`
- bulk and single-sync tests
- orchestration and portfolio-decision API tests
- Evaluate and Portfolio Actions frontend tests

Continuity documentation updated: `AGENTS.md`, `docs/PROJECT_STATE.md`,
`docs/DECISIONS.md`, `docs/SPRINT11D_PLAN.md`, and this report.

## 67. Part AB conclusion and Git handoff

Part AB is complete. AlphaPilot's daily decision pipeline now has one explicit,
tested completed-session invariant from provider ingestion through persistence,
research calculation, API metadata, and UI presentation. It does not alter EMA
HYBRID 2%, Micho BOTH, RS20, ATR14, sizing, constraints, T+1 execution,
backtesting accounting, or any other frozen research rule.

The implementation deliberately favors correctness over earliest possible
same-day availability: normal and early-close sessions become usable only after
the conservative 16:15 New York boundary. Stored SPY sessions handle actual
weekends/holidays, while a future production enhancement could adopt a dedicated
exchange calendar plus provider-finalization status.

All Sprint 11 through Sprint 11D work remains local on `feature/ui-mvp`. Sprint
12 was not started. No commit, push, PR, merge, force-push, tag, destructive
database action, or partial-row deletion was performed.

Final `git status --porcelain` reports 66 entries: 39 tracked modified paths and
27 untracked paths/directories. The tracked-only `git diff --stat` is 39 files
changed, 2,140 insertions, and 282 deletions; the untracked `frontend/` tree and
new backend/docs files are additional intended Sprint 11 work. `.env`,
`node_modules`, `dist`, and browser artifacts remain excluded. `git diff
--check` passed with only informational LF-to-CRLF notices.

Recommended commit message:

```text
feat: complete Sprint 11 research UI and data readiness workflow
```
