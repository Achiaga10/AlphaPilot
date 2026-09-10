# EMA20 Manual-Stop Approved BUY — Completion Report

Status: implemented locally; all deterministic, full-stack and controlled browser
gates pass. Feature development is paused.

## Outcome

EMA20 Pullback can now produce a final `APPROVED BUY` without a system-generated
numeric stop when, and only when, every other deterministic hard gate passes. The
decision is explicitly returned as:

- `final_action=BUY`
- `is_final_actionable=true`
- `execution_readiness=ACTIONABLE`
- `execution_readiness_reason=MANUAL_STOP_REQUIRED`
- `loss_control_source=USER_MANUAL`
- `manual_stop_required=true`
- `approved_protective_stop_price=null`
- `loss_control_boundary_price=null`

The UI displays `APPROVED BUY`, `MANUAL STOP REQUIRED`, and “No system stop — set
manually.” AlphaPilot does not infer or fabricate a stop. The user is responsible
for choosing and placing it.

The exception is strategy-scoped to EMA20 Pullback. Missing or non-eligible backend
entry-revalidation evidence, entry extension, stale/missing data, user exclusion,
already-held state, sizing, cash, sector and portfolio-capacity gates still block.
The low-level decisions endpoint fails closed when it lacks EMA20 entry-safety
evidence. News remains advisory-only. Micho behavior is unchanged.

A genuine approved EMA20 system policy is preserved when supplied: its source is
`APPROVED_SYSTEM_POLICY`, manual-stop is false, and its numeric boundary/automatic
stop is displayed. This support is covered with controlled evidence only; the
current production EMA20 profile has no approved system policy. No ATR, EMA50,
fixed-percentage, signal-day-low, trailing, or other fallback stop was added.

## Controlled A–D integration

| Candidate | Condition | Final result |
|---|---|---|
| A | All gates pass; no system stop | APPROVED BUY / USER_MANUAL / MANUAL STOP REQUIRED |
| B | All gates pass; approved system evidence | APPROVED BUY / APPROVED_SYSTEM_POLICY / numeric stop |
| C | EMA20 entry too extended | NOT ACTIONABLE / ENTRY_TOO_EXTENDED_ABOVE_EMA20 |
| D | Portfolio capacity fails | NOT ACTIONABLE / MAX_POSITIONS |

The authoritative approved BUY count is exactly 2. A separate exclusion test remains
non-actionable, and adverse, severe, unavailable and timed-out News outcomes preserve
the otherwise-approved manual-stop decision without refreshing News.

## Current real read-only acceptance

Request: current S&P 500 universe, relative-strength-20 selection, requested and
completed session 2026-09-09. The current ResearchPortfolio had no open positions.
It remained at revision 25 with $97,418.2800 cash. Plan generation was read-only.

### EMA20 Pullback

- Technical BUYs: 45.
- Entry-safety passes: 33.
- Allocation passes: 10.
- Approved automatic/system stops: 0.
- Manual-stop-required approved BUYs: 10.
- Final approved BUYs: 10.
- News-blocked: 0.
- Remaining first blockers: 12 entry-safety, 23 portfolio-capacity.
- Entry-safety blocked: BKR, C, CVNA, EXPD, HUM, MRK, OKE, TRGP, UHS, VEEV, WFC,
  WMB.
- Portfolio-capacity blocked: AES, ANET, APH, BAC, BNY, BRK.B, CAH, EOG, EQT, FANG,
  GEN, GPC, LYB, MCK, MDT, MS, MSFT, NUE, PFG, RSG, STT, TECH, ULTA.

All approved candidates use completed-session close evidence and the fixed completed
signal-session EMA20 anchor dated 2026-09-09:

| Ticker | Allocation | Shares | Entry/reference | EMA20 | Distance / pct | Entry result | Loss control |
|---|---:|---:|---:|---:|---:|---|---|
| EL | $9,678.97 | 98 | $98.7650 | $98.1167 | $0.6483 / 0.6607% | TOUCHING_OR_NEAR / ELIGIBLE | USER_MANUAL |
| CTVA | $9,661.50 | 114 | $84.7500 | $83.9860 | $0.7640 / 0.9096% | TOUCHING_OR_NEAR / ELIGIBLE | USER_MANUAL |
| KDP | $9,723.27 | 303 | $32.0900 | $31.8595 | $0.2305 / 0.7233% | TOUCHING_OR_NEAR / ELIGIBLE | USER_MANUAL |
| GILD | $9,612.57 | 66 | $145.6450 | $145.0666 | $0.5784 / 0.3987% | TOUCHING_OR_NEAR / ELIGIBLE | USER_MANUAL |
| SOLV | $9,724.86 | 108 | $90.0450 | $89.5213 | $0.5237 / 0.5849% | TOUCHING_OR_NEAR / ELIGIBLE | USER_MANUAL |
| IQV | $9,509.00 | 37 | $257.0000 | $254.8623 | $2.1377 / 0.8388% | TOUCHING_OR_NEAR / ELIGIBLE | USER_MANUAL |
| VZ | $9,703.20 | 195 | $49.7600 | $49.3558 | $0.4042 / 0.8189% | TOUCHING_OR_NEAR / ELIGIBLE | USER_MANUAL |
| PFE | $9,726.50 | 350 | $27.7900 | $27.7760 | $0.0140 / 0.0503% | TOUCHING_OR_NEAR / ELIGIBLE | USER_MANUAL |
| INCY | $9,700.46 | 77 | $125.9800 | $125.1643 | $0.8157 / 0.6517% | TOUCHING_OR_NEAR / ELIGIBLE | USER_MANUAL |
| AMT | $9,653.05 | 55 | $175.5100 | $174.9038 | $0.6062 / 0.3466% | TOUCHING_OR_NEAR / ELIGIBLE | USER_MANUAL |

Every row has `final_action=BUY`, a null automatic stop, and the explicit manual-stop
warning. No current EMA20 candidate has an approved system stop.

### Micho 150

- Technical BUYs: 11.
- Final approved BUYs: 10.
- Approved system loss-control count: 10.
- Manual-stop-required count: 0.
- First blocker: portfolio capacity — TXN.
- News-blocked: 0.

Approved tickers: HAL, RSG, DVA, EQIX, MDLZ, PM, WRB, CINF, ZBH and CB. Micho's
completed-close-below-SMA150 loss-control semantics were not changed.

## Verification and safety

- Focused backend: 95 passed; the dedicated manual-stop file contributes 11 tests.
- Full backend: Ruff and format passed; mypy passed across 199 source files; 656
  tests passed.
- Focused frontend: 24 passed.
- Full frontend: lint passed; 16 files / 100 tests passed; production build passed.
- Controlled Microsoft Edge/Playwright: PASS against real FastAPI/Vite and persisted
  data. Backend counts matched rendered approved tabs/cards; the EMA card displayed
  `APPROVED BUY` and `MANUAL STOP REQUIRED`.
- Browser request guard observed only the authorized read-only plan-generation POSTs.
  News API call counts were zero. Durable Portfolio and Paper signatures were equal
  before and after. No broker action occurred.
- Migration: none.
- Historical research rerun or rewrite: none.
- Portfolio, holdings, ResearchPortfolio, Paper, trade-event, News, DailyCandle or
  broker mutation: none.
- Git stage/commit/push: none.

## Files changed for this hotfix

Backend source:

- `backend/src/alphapilot/api/routes/portfolio.py`
- `backend/src/alphapilot/portfolio/daily_brief.py`
- `backend/src/alphapilot/portfolio/decisions.py`
- `backend/src/alphapilot/portfolio/execution_readiness.py`
- `backend/src/alphapilot/portfolio/orchestration.py`
- `backend/src/alphapilot/schemas/daily_brief.py`
- `backend/src/alphapilot/schemas/portfolio.py`
- `backend/src/alphapilot/services/daily_portfolio_brief.py`

Backend tests:

- `backend/tests/api/test_portfolio_decisions.py`
- `backend/tests/portfolio/test_daily_portfolio_brief.py`
- `backend/tests/portfolio/test_ema_manual_stop_policy.py`
- `backend/tests/portfolio/test_ema_news_advisory.py`
- `backend/tests/portfolio/test_orchestration.py`

Frontend and browser acceptance:

- `frontend/src/api/portfolio.ts`
- `frontend/src/features/dashboard/DailyPortfolioManager.tsx`
- `frontend/src/features/portfolio/BuyActionPreviewDialog.tsx`
- `frontend/src/features/portfolio/DecisionTable.tsx`
- `frontend/src/features/portfolio/DecisionTable.test.tsx`
- `frontend/src/pages/DashboardPage.test.tsx`
- `frontend/src/test/fixtures.ts`
- `frontend/src/test/server.ts`
- `frontend/src/types/portfolio.ts`
- `frontend/scripts/ema20-manual-stop-smoke.mjs`

Continuity:

- `AGENTS.md`
- `docs/PROJECT_STATE.md`
- `docs/DECISIONS.md`
- `docs/hotfixes/EMA20_MANUAL_STOP_APPROVED_BUY.md`

## Git status

Branch: `research/ema20-loss-control`. The shared worktree contains this hotfix plus
preserved earlier user-owned work: 40 tracked files are modified and 32 files are
untracked. Nothing is staged. The files listed above are the current hotfix review
set; unrelated dirty files were not reverted. Recommended commit message after user
review: `fix(portfolio): allow manual-stop EMA20 approved buys`.

## Required answers

1. Can EMA20 become APPROVED BUY without an automatic stop? **YES.**
2. What is shown instead? **USER_MANUAL / MANUAL STOP REQUIRED.**
3. Is a fake stop generated? **NO.**
4. Does `LOSS_CONTROL_UNAVAILABLE` still block an otherwise-valid EMA20 BUY? **NO.**
5. Does missing system stop reduce `approved_buy_count`? **NO.**
6. Is EMA20 entry safety still mandatory? **YES.**
7. Do portfolio constraints still apply? **YES.**
8. Does user exclusion still apply? **YES.**
9. Can News block EMA20? **NO.**
10. Were EMA20 technical rules changed? **NO.**
11. Were EMA20 exit rules changed? **NO.**
12. Was an ATR/EMA50/fixed-percentage fallback introduced? **NO.**
13. Current EMA20 technical/approved counts: **45 / 10**.
14. Current EMA20 manual/system approved counts: **10 / 0**.
15. Current Micho technical/approved counts: **11 / 10**.
16. Did this task modify Micho semantics? **NO.**

No further feature work is authorized. Sprint 25 remains unstarted.
