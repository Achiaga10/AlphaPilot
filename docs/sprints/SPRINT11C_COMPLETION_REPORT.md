# AlphaPilot Sprint 11C Completion Report

Date: 2026-08-26  
Branch: `feature/ui-mvp`  
Status: **COMPLETE LOCALLY — READY FOR USER REVIEW AND GIT OPERATIONS**  
Sprint 12: **NOT STARTED**

## 1. User review findings

The post-Sprint-11B browser review found several practical gaps despite the UI
being technically functional: contextual help could be clipped by decision
cards; strategy SELL signals and portfolio-approved SELL actions were not
clearly separated; approved decisions could not update the local research
portfolio; Admin disappeared when disabled; universe and candle maintenance
were too coupled; custom non-S&P tickers could not be tracked end to end; and
financial/risk fields needed more explanation. The review also uncovered that
Alpaca SIP requests could return HTTP 403 for credentials without a SIP
entitlement.

Sprint 11C fixed those product/backend gaps without changing strategy,
ranking, risk, execution, or accounting research rules.

## 2. Tooltip clipping root cause

The prior help content lived inside decision-card layout and overflow/stacking
contexts. Its local positioning meant a visually open tooltip could still be
clipped by an ancestor or rendered under adjacent content.

## 3. Tooltip implementation fix

`InfoTooltip` now renders the popover into `document.body` with a React portal.
It uses `position: fixed`, measures the trigger and popover, chooses an
above/below position, clamps both axes to the viewport, and uses a high
z-index. It supports hover, focus, click/tap, outside click, Escape, and resize/
scroll repositioning. The trigger is a keyboard-operable button-role element
with `tabIndex=0`, `aria-expanded`, and `aria-describedby`.

## 4. Real-browser tooltip verification

The Playwright smoke test opened the RS20 tooltip against the real application
at desktop and mobile widths and verified positive dimensions, viewport bounds,
portal ownership, Escape close, and no card clipping.

| View | x | y | width | height | Result |
|---|---:|---:|---:|---:|---|
| Desktop | 644.3125 | 542.578125 | 280 | 103.328125 | Inside viewport; not clipped |
| Mobile | 12 | 302 | 280 | 103.328125 | Inside viewport; not clipped |

## 5. Decision category semantic changes

The Opportunities view now exposes six explicit filters:

- **Approved Buys**: backend `decision=BUY`, retaining backend priority order.
- **Approved Sells**: backend `decision=SELL`; a strategy SELL with no held
  position is not included.
- **Sell Signals**: strategy `signal=SELL`, whether or not the portfolio can
  execute the sale.
- **Skipped**: backend `decision=SKIP`.
- **All Decisions**: every portfolio decision.
- **All Evaluated**: every evaluated ticker, alphabetically, including
  no-action outcomes.

The UI explicitly explains that categories can overlap and that Approved Buys
use backend priority while All Evaluated is an A-Z inspection view.

## 6. Approved BUY Apply workflow

An approved BUY with positive proposed shares and a clean plan displays **Add
to Portfolio**. After confirmation, React uses the backend-provided share count
and `cash_after_decision`, creates/replaces the draft position with the decision
reference price as its research cost basis/current price, saves the draft to
local storage, displays a success message, and marks the plan stale. It sends no
broker order.

## 7. Approved SELL Apply workflow

An approved SELL for a held position displays **Apply Sell**. After
confirmation, React removes the full draft position and uses the backend's
`estimated_proceeds`-derived `cash_after_decision`. It then persists the draft,
shows a success message, and marks the plan stale. Partial sales and broker
orders remain out of scope.

## 8. Exact portfolio/cash mutation semantics

The backend adds three optional, typed decision fields:

- `estimated_cash_outlay`: approved BUY target allocation dollars.
- `cash_after_decision`: submitted snapshot cash minus the one BUY outlay, or
  plus the one approved SELL's estimated proceeds.
- `modeled_stop_reference_price`: reference price minus modeled stop distance,
  only when the result is positive.

The frontend does not recalculate these cash values. Each value describes one
decision applied to the exact submitted snapshot; this is why sequential
application requires regeneration.

## 9. Stale-plan safety behavior

Only a clean plan may be applied. Applying one BUY or SELL mutates the local
draft, makes its serialized state differ from the plan snapshot, disables all
remaining decision actions, and tells the user to regenerate. A second action
cannot use stale cash/risk/position assumptions. There is deliberately no
“Apply All.”

The real-browser controlled workflow confirmed BUY cash `20100`, SELL cash
`50100`, the sequential stale gate, and absence of any broker-order request.

## 10. Manual position workflow

The pre-existing manual **Add Position** and **Remove** controls remain
available and visually discoverable. Manual edits also invalidate an existing
plan. This supports correction of the in-browser research draft without
pretending it is synchronized to a brokerage account.

## 11. Custom ticker architecture

`Company.is_custom_tracked` is the explicit persistent flag for independently
tracked non-S&P companies. It is separate from `Company.is_active` and from
`IndexConstituent.is_active`. Blank portfolio scope continues to mean the
current active S&P 500 universe; explicitly requested stored custom tickers are
accepted by the portfolio orchestrator. There is no ticker-specific code for
SBET.

## 12. Custom ticker add/sync workflow

The typed service normalizes and validates the symbol, checks existing Company
and active S&P membership, obtains metadata through the configured metadata
provider, creates/updates through the Company service/repository boundary,
marks valid non-S&P coverage as custom, and synchronizes a bounded 400-day
candle window. The Admin UI supports Add & Sync, progress/result messaging,
Evaluate navigation, and later candle resynchronization.

Provider/candle failures are typed. A metadata failure leaves no new database
row; a candle failure is reported as partial onboarding rather than false
success.

## 13. Custom ticker removal/deactivation semantics

Deactivate Tracking changes only `is_custom_tracked` to false. It preserves
the Company row and all DailyCandles. Adding the same ticker later reactivates
the existing row and synchronizes it; it does not create a duplicate.

## 14. S&P membership protection

A current active S&P constituent cannot be added as a duplicate custom ticker
or removed through custom deactivation. S&P membership is changed only by the
universe synchronization path. Custom tracking never creates an
`IndexConstituent` row.

## 15. Metadata provider used

Custom onboarding uses the existing configured Finnhub integration through a
small `CompanyMetadataProvider` protocol and typed `CompanyMetadata` DTO. The
company-profile response supplies ticker, name, exchange, and reliable optional
sector/industry values. Missing or invalid required metadata is rejected
deterministically; no sector is fabricated.

## 16. Admin discoverability changes

**Data Management** is always present in navigation. When admin tools are
disabled it carries a **Locked** badge and opens a read-only page with the data
summary plus non-secret `ADMIN_TOOLS_ENABLED=true` and restart guidance. Read
capability/summary endpoints remain available; all mutation endpoints remain
403. When enabled, the page exposes custom tracking and each sync operation.

## 17. Universe Sync behavior

**Sync S&P 500 Universe** is an independent typed `UNIVERSE_SYNC` job. It
refreshes Wikipedia constituents, Company metadata, and active memberships,
reporting requested/created/updated/unchanged and membership added/removed
counts. It does not synchronize market candles.

## 18. Market Candles Sync behavior

**Sync Market Candles** is an independent typed `MARKET_CANDLES_SYNC` job. It
first requires successful SPY synchronization and then targets the union of
active S&P constituents and active custom-tracked companies. It uses the exact
configured Alpaca feed and reports progress/failures without exposing secrets.

## 19. Full/single sync behavior

**Full Sync** composes universe sync followed by candle sync and remains
available as an explicit convenience, not the only operation. **Sync One
Stored Ticker** refreshes candles only for an existing Company. Custom **Add &
Sync** is the path for a genuinely new ticker. Sprint validation deliberately
did not launch an unnecessary full S&P 500 sync.

## 20. Job model

The process-local typed job model distinguishes `UNIVERSE_SYNC`,
`MARKET_CANDLES_SYNC`, `TICKER_SYNC`, and `FULL_SYNC`; records requested range,
provider/feed, stage, ticker, progress, universe counts, state, timestamps,
safe error code/reason; and prevents conflicting expensive jobs. Process-local
job history is an acknowledged limitation, not durable audit storage.

## 21. Data freshness

The read-only summary reports active Company, active S&P, and active custom
counts; newest SPY candle; oldest/newest latest candle across the union of
active S&P and custom coverage; count of tracked tickers lagging SPY (including
tracked tickers with no candles); last successful universe/candle jobs; current
provider/feed; and latest process-local job. Dashboard shows a compact stored-
data health panel. Dates are explicitly stored-data dates, not live quotes.

## 22. Decision Details glossary

A centralized glossary now explains every financial/risk datum rendered in
Decision Details: signal, decision, reason, RS20/rank, reference price, ATR14,
stop distance/reference, shares, allocation/outlay, target weight, modeled
position risk, risk budget, sector weights, normalized sizing weight, current
shares, and estimated proceeds. The reusable portal tooltip provides consistent
mouse, keyboard, and mobile interaction.

## 23. Stop-reference semantics and explicit limitations

The field is labeled **Research stop reference**, never “Stop Loss.” It is the
reference price minus the existing `2 × ATR14` sizing proxy when positive. It
is informational research context only: AlphaPilot does not place, monitor, or
execute a stop; strategies and backtests retain their existing exit rules.

## Logo preservation and validation

- Source asset: `frontend/src/assets/images/alphapilot-logo.png`.
- Display: primary sidebar brand area; the prior placeholder icon is replaced.
- Presentation: `object-fit: contain`, 148 × 148 desktop and restrained mobile
  sizing; source aspect ratio is preserved with no crop/distortion.
- Accessibility: `alt="AlphaPilot"`; adjacent visible product copy is arranged
  to keep the identity clear.
- Integrity: original PNG remained unchanged: 150,156 bytes, 1024 × 1024,
  SHA-256 `45294393C92AF82A3859B12932507016EFA9C8065AC5634736DE551E60C501B1`.
- Build: Vite emitted `dist/assets/alphapilot-logo-Dp3JkXYr.png`.

## 24. Backend files changed

Modified:

- `.gitignore`
- `backend/.env.example`
- `backend/src/alphapilot/api/router.py`
- `backend/src/alphapilot/api/routes/portfolio.py`
- `backend/src/alphapilot/core/config.py`
- `backend/src/alphapilot/database/models/company.py`
- `backend/src/alphapilot/main.py`
- `backend/src/alphapilot/market/dto/__init__.py`
- `backend/src/alphapilot/market/providers/alpaca.py`
- `backend/src/alphapilot/market/providers/base.py`
- `backend/src/alphapilot/market/providers/finnhub.py`
- `backend/src/alphapilot/portfolio/decisions.py`
- `backend/src/alphapilot/portfolio/orchestration.py`
- `backend/src/alphapilot/repositories/company.py`
- `backend/src/alphapilot/repositories/index_constituent.py`
- `backend/src/alphapilot/schemas/company.py`
- `backend/src/alphapilot/schemas/portfolio.py`
- `backend/src/alphapilot/services/alpaca_bulk_market_sync.py`
- `backend/src/alphapilot/services/company.py`
- `backend/src/alphapilot/services/market_batch_sync.py`
- `backend/src/alphapilot/services/universe_company_sync.py`
- `backend/src/alphapilot/services/universe_market_sync_runner.py`

Created:

- `backend/src/alphapilot/api/routes/admin_data.py`
- `backend/src/alphapilot/market/dto/company.py`
- `backend/src/alphapilot/market/providers/errors.py`
- `backend/src/alphapilot/repositories/research_data.py`
- `backend/src/alphapilot/schemas/admin_data.py`
- `backend/src/alphapilot/services/admin_data.py`
- `backend/src/alphapilot/services/custom_ticker.py`

## 25. Frontend files changed

The combined uncommitted Sprint 11/11B/11C frontend is currently a new
`frontend/` tree. Sprint 11C materially changed or added:

- `frontend/src/components/InfoTooltip.tsx`
- `frontend/src/components/InfoTooltip.test.tsx`
- `frontend/src/features/portfolio/CandidateStatuses.tsx`
- `frontend/src/features/portfolio/DecisionTable.tsx`
- `frontend/src/features/portfolio/OpportunityExplorer.tsx`
- `frontend/src/features/portfolio/OpportunityExplorer.test.tsx`
- `frontend/src/features/portfolio/PortfolioWorkspace.tsx`
- `frontend/src/features/portfolio/metricGlossary.ts`
- `frontend/src/layouts/AppLayout.tsx`
- `frontend/src/layouts/AppLayout.test.tsx`
- `frontend/src/pages/AdminDataPage.tsx`
- `frontend/src/pages/AdminDataPage.test.tsx`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/pages/DashboardPage.test.tsx`
- `frontend/src/pages/PortfolioPage.tsx`
- `frontend/src/pages/PortfolioPage.test.tsx`
- `frontend/src/pages/PlanDirtyState.test.tsx`
- `frontend/src/api/admin.ts`
- `frontend/src/api/client.ts`
- `frontend/src/hooks/usePortfolioApi.ts`
- `frontend/src/types/portfolio.ts`
- `frontend/src/test/server.ts`
- `frontend/src/styles.css`
- `frontend/scripts/real-smoke.mjs`

The official user-provided logo remains at its original source path and was not
rewritten or moved.

Continuity documentation changed/created across the combined branch:
`AGENTS.md`, `docs/PROJECT_STATE.md`, `docs/DECISIONS.md`, Sprint 11/11B plan and
completion files, this Sprint 11C plan, and this completion report.

## 26. Database migration

Created
`backend/migrations/versions/6e1464ffb227_add_custom_company_tracking.py`,
which adds non-null Boolean `company.is_custom_tracked` with a false default and
removes the server default after population. Development and test database
targets were verified as distinct before `uv run alembic upgrade head` was run
against each. No destructive database command was used.

## 27. Focused test results

Focused suites were run throughout implementation. Recorded final focused
groups included:

```powershell
cd backend
$env:DEBUG='false'
uv run pytest tests/services/test_research_admin_data.py tests/api/test_admin_data.py -q
```

Result: **9 passed**. Earlier focused Sprint 11C backend groups passed **35**
tests, followed by **12** targeted custom-scope/freshness tests after those
paths were hardened. Tests cover exact BUY/SELL workflow values, modeled stop
reference, custom lifecycle/membership isolation, split jobs, feed behavior,
safe errors, freshness, explicit custom portfolio scope, and compatibility.

## 28. Full frontend test/lint/build results

Exact final commands:

```powershell
cd frontend
npm run lint
npm run test -- --run
npm run build
```

Results:

- ESLint: **passed**, zero warnings.
- Vitest: **11 files, 45 tests passed**.
- TypeScript/Vite production build: **passed**, 98 modules transformed.
- Official PNG bundled successfully.

## 29. Full backend run_checks result

Exact final command:

```powershell
cd backend
$env:DEBUG='false'
.\run_checks.ps1
```

The `DEBUG=false` override was scoped only to the child validation process.
Application configuration was not changed for a host-only DEBUG value.

Results:

- Ruff check: **passed**.
- Ruff format check: **170 files unchanged; passed**.
- mypy: **118 source files; no issues**.
- pytest: **163 passed in 13.02s**.
- Overall: **All checks passed**.

## 30. Real-browser results

Exact final command:

```powershell
cd frontend
npm run smoke:real
```

The real-browser test used the actual backend and controlled API routes where a
specific approved BUY/SELL scenario was necessary. It verified:

- real 1024 × 1024 logo rendered at 148 × 148 with `object-fit: contain`;
- bounded portal tooltip on desktop and mobile;
- three real backend evaluated rows;
- enabled Admin shows independent universe/candle/custom controls, SBET, and
  configured feed;
- BUY then stale/regenerate then SELL produces exact controlled cash values;
- no broker-order request occurs;
- disabled Admin remains discoverable and has no write controls;
- mobile navigation remains visible/usable.

Screenshot artifact:
`backend/backtest_reports/sprint11c/ui-smoke.png` (Git-ignored).

## 31. Remaining known issues

- Research portfolio state is browser-local; there is no authenticated account
  persistence or live broker synchronization.
- Decision application is full-position and deliberately one action per plan;
  no partial fill/order lifecycle exists.
- Admin job state is process-local and is lost on restart.
- DailyCandle rows do not store provider/feed provenance per row. Current job
  metadata records the configured provider/feed boundary.
- The research universe has current-constituent/survivorship limitations; this
  UI work does not make historical results point-in-time constituent clean.
- Data is stored daily data, not live streaming quotes; freshness is relative
  to the stored SPY session and provider availability.
- Finnhub metadata and Alpaca data remain external-service dependencies.
- SIP requires the user's Alpaca entitlement; AlphaPilot intentionally does
  not hide that requirement with fallback.
- The research stop reference is not an executable stop and is not monitored.
- No new strategy, ranking, or risk-model validation was performed in Sprint
  11C.

## 32. Whether Sprint 11 is finally ready to commit/PR

**Yes.** The combined Sprint 11/11B/11C work is ready for the user to review,
commit, push, and open a PR. The backend/frontend quality gates and real-browser
acceptance checks all pass. No commit, push, PR, or merge was performed by
Codex.

## 33. Git status

Branch: `feature/ui-mvp`.

The working tree is intentionally dirty. It contains the combined local Sprint
11, Sprint 11B, and Sprint 11C changes: 33 tracked files modified plus new
backend migration/admin/custom-ticker modules and tests, the new `frontend/`
tree, Sprint continuity documents, and this report. Nothing is staged or
committed. Full short status is included under **Final repository evidence**.

## 34. Git diff --stat

The tracked-file diff is:

```text
33 files changed, 822 insertions(+), 253 deletions(-)
```

Important: ordinary `git diff --stat` excludes untracked files, including the
entire frontend, new backend modules/tests/migration, and Sprint documents.
The short-status inventory is therefore the authoritative complete local-change
view until the user stages files.

## 35. Recommended commit message

```text
feat(ui): harden portfolio actions, data admin, and explainability
```

## 36. Alpaca feed configuration and root cause of SIP 403

`ALPACA_DATA_FEED` is a validated `iex | sip` setting; the example/default local
research value is `iex`. `AlpacaProvider` passes exactly that configured feed to
historical-bars requests. The observed SIP HTTP 403 was an entitlement failure
for the supplied credentials, not a strategy, database, or symbol error. It is
translated to typed code `MARKET_DATA_FEED_NOT_AUTHORIZED` with safe provider/
feed context.

## 37. Exact configured feed used during final local validation

Final local application validation used:

```text
ALPACA_DATA_FEED=iex
```

A lightweight real SPY synchronization for 2026-08-20 through 2026-08-26
returned `SYNCED` using Alpaca IEX. No credential value was printed or copied.

## 38. Confirmation that there is no silent SIP -> IEX fallback

Confirmed. A separate process-scoped `ALPACA_DATA_FEED=sip` provider call sent
SIP and returned the typed `MARKET_DATA_FEED_NOT_AUTHORIZED` response naming
Alpaca/SIP. It did not retry IEX. Automated tests also prove exact IEX/SIP
propagation, allowed-value validation, 403 mapping, and absence of a fallback.

## 39. SPY benchmark failure behavior

SPY is mandatory for candle sync and RS20 benchmark integrity. A SPY provider
failure fails the job at stage `benchmark`, records ticker `SPY`, provider,
configured feed, and safe typed reason, and prevents the stock batch from being
reported successful. Secrets/raw provider bodies are not exposed.

## 40. SBET custom-ticker onboarding result

Real **Add & Sync** validation for `SBET` over 2025-07-22 through 2026-08-26
returned `TRACKED_AND_SYNCED`. Stored metadata was:

- name: Sharplink Inc
- exchange: NASDAQ
- sector: Hotels, Restaurants & Leisure

This was a normal generic workflow; SBET is not hardcoded.

## 41. Whether SBET was stored independently of S&P membership

Yes. SBET ended active with `is_custom_tracked=true` and no active S&P 500
membership. Explicitly scoped portfolio planning accepted it, while blank scope
continued to resolve only the active S&P universe.

## 42. SBET candle synchronization result

The real onboarding stored **276** DailyCandles, first date 2025-07-22 and
latest available date 2026-08-25. The requested end was 2026-08-26; reporting
correctly distinguishes request date from newest stored market session.

## 43. SBET EMA evaluation result

Requested as of 2026-08-26; actual candle date 2026-08-25. EMA20 Pullback
returned strategy status `NO_ACTION`, portfolio signal `HOLD`, reason
`NO_PULLBACK`, and `is_custom_tracked=true`. A valid no-action result confirms
the custom ticker traversed the real backend evaluation path.

## 44. SBET Micho evaluation result

Requested as of 2026-08-26; actual candle date 2026-08-25. Micho V1 returned
strategy status `NO_ACTION`, portfolio signal `HOLD`, reason
`MICHO_150_TREND_NOT_READY`, and `is_custom_tracked=true`. No Micho rule was
changed.

## 45. Custom ticker deactivate/reactivate behavior

Real deactivation returned `DEACTIVATED`, set custom tracking false, and
preserved all 276 candles. Re-adding returned `REACTIVATED_AND_SYNCED`, reused
the Company/history, restored custom tracking, and left S&P membership false.
Final local state intentionally leaves SBET active as a custom-tracked company.

## Exact provider/admin validation commands and boundaries

Validation used the typed REST endpoints through PowerShell
`Invoke-RestMethod` for capability/summary, SPY single-ticker sync, SBET Add &
Sync/list/deactivate/reactivate, stock evaluation, and portfolio planning. A
standalone `uv run python` process with only `ALPACA_DATA_FEED=sip` overridden
validated the entitlement error path. No full-universe sync was launched and no
secret-bearing configuration was displayed.

## Final repository evidence

At report creation, `git branch --show-current` returned `feature/ui-mvp` and
the latest merged commit remained `bba02ac` (Sprint 10 merge). `git status
--short` contains:

```text
 M .gitignore
 M AGENTS.md
 M backend/.env.example
 M backend/src/alphapilot/api/router.py
 M backend/src/alphapilot/api/routes/portfolio.py
 M backend/src/alphapilot/core/config.py
 M backend/src/alphapilot/database/models/company.py
 M backend/src/alphapilot/main.py
 M backend/src/alphapilot/market/dto/__init__.py
 M backend/src/alphapilot/market/providers/alpaca.py
 M backend/src/alphapilot/market/providers/base.py
 M backend/src/alphapilot/market/providers/finnhub.py
 M backend/src/alphapilot/portfolio/decisions.py
 M backend/src/alphapilot/portfolio/orchestration.py
 M backend/src/alphapilot/repositories/company.py
 M backend/src/alphapilot/repositories/index_constituent.py
 M backend/src/alphapilot/schemas/company.py
 M backend/src/alphapilot/schemas/portfolio.py
 M backend/src/alphapilot/services/alpaca_bulk_market_sync.py
 M backend/src/alphapilot/services/company.py
 M backend/src/alphapilot/services/market_batch_sync.py
 M backend/src/alphapilot/services/universe_company_sync.py
 M backend/src/alphapilot/services/universe_market_sync_runner.py
 M backend/tests/api/test_health.py
 M backend/tests/api/test_portfolio_decisions.py
 M backend/tests/integration/test_universe_company_sync.py
 M backend/tests/market/providers/test_alpaca.py
 M backend/tests/market/providers/test_finnhub.py
 M backend/tests/portfolio/test_decisions.py
 M backend/tests/portfolio/test_orchestration.py
 M backend/tests/services/test_universe_market_sync_runner.py
 M docs/DECISIONS.md
 M docs/PROJECT_STATE.md
?? backend/migrations/versions/6e1464ffb227_add_custom_company_tracking.py
?? backend/src/alphapilot/api/routes/admin_data.py
?? backend/src/alphapilot/market/dto/company.py
?? backend/src/alphapilot/market/providers/errors.py
?? backend/src/alphapilot/repositories/research_data.py
?? backend/src/alphapilot/schemas/admin_data.py
?? backend/src/alphapilot/services/admin_data.py
?? backend/src/alphapilot/services/custom_ticker.py
?? backend/tests/api/test_admin_data.py
?? backend/tests/services/test_custom_ticker.py
?? backend/tests/services/test_research_admin_data.py
?? docs/SPRINT11B_COMPLETION_REPORT.md
?? docs/SPRINT11B_PLAN.md
?? docs/SPRINT11C_COMPLETION_REPORT.md
?? docs/SPRINT11C_PLAN.md
?? docs/SPRINT11_COMPLETION_REPORT.md
?? docs/SPRINT11_PLAN.md
?? frontend/
```

No files are staged. All listed Sprint 11/11B/11C source, tests, migration,
frontend, and continuity documents are ready for the user's review and commit.
No commit, push, tag, PR, or merge was performed.
