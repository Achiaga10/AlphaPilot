# Final BUY Actionability Semantics Hotfix

Status: **COMPLETE LOCALLY**  
Branch: `fix/portfolio-plan-consistency-ux`  
Sprint 25: **NOT STARTED**

## Purpose and root cause

The real 2026-09-03 EMA20 plan correctly reported zero approved BUYs, but its returned
records showed IBKR and EOG as `decision=BUY`, with candidate allocations and
`reason=BUY_APPROVED`. These were intermediate allocation results. Both candidates
lacked the approved numeric loss-control evidence required for final actionability.
The UI incorrectly gave the intermediate fields primary, terminal meaning.

This hotfix changes semantics and enforcement only. It changes no strategy, EMA20
entry-safety, loss-control, News, ranking, sizing, portfolio, or SELL threshold.

## Authoritative contract

Three facts are separate:

1. `signal`: frozen technical strategy output.
2. `decision` plus `allocation_reason`: intermediate portfolio/allocation outcome.
3. `final_action` plus `terminal_reason` and `is_final_actionable`: sole user-facing
   authority.

The invariant is:

```text
Approved BUY = final_action == BUY AND is_final_actionable == true
```

Backend `PortfolioDecision.is_approved_buy` and `is_approved_sell` own this invariant;
shared frontend helpers render and filter the typed contract. `final_action` is typed as
`BUY`, `SELL`, `HOLD`, `ATTENTION`, `EXIT_REQUIRED`, or `NOT_ACTIONABLE`. The legacy
`reason` now mirrors `terminal_reason`; an intermediate `BUY_APPROVED` survives only as
`allocation_reason`. The apply/preview service rejects any decision without a matching
approved final action and actionability flag. EMA20 action-time revalidation retains
precedence when it finds an entry-safety failure.

## UI behavior

Cards lead with Final status, then technical signal and candidate decision. A
non-actionable proposal is `Candidate allocation`; only a real final BUY is `Approved
allocation`. `LOSS_CONTROL_UNAVAILABLE` is visible without expanding details as:

```text
LOSS CONTROL
No approved numeric loss-control policy
Status: NOT ACTIONABLE
```

The primary filter is Final action, Candidate decision is explicitly secondary, and the
old Skipped tab is Not Actionable. Review Add / Apply controls render only for a typed
final actionable BUY/SELL.

## Real reproduction

Pre-fix reproduction and post-fix acceptance used requested/analysis session 2026-09-03,
portfolio revision 17, and plan ID `cbc206e8555fd34186a12702`.

### IBKR

- signal/base/candidate decision: `BUY` / `BUY` / `BUY`
- allocation evidence: `BUY_APPROVED`, $9,760.80, 105 shares
- EMA20 safety: `ELIGIBLE`, `TOUCHING_OR_NEAR`, 0.1995222105% above the fixed
  completed signal-session EMA20
- execution readiness: `RESEARCH_ONLY` /
  `NO_APPROVED_LOSS_CONTROL_POLICY`
- loss control: inactive, policy `NONE`, no numeric boundary
- News: `NEVER_REFRESHED`, `NO_EFFECT`; not evaluated because the earlier gate failed
- sector context: Financials 28.7652864407% before, candidate projection
  38.6779912068% after
- terminal/legacy reason after fix: `LOSS_CONTROL_UNAVAILABLE`
- final action/actionable: `NOT_ACTIONABLE` / no

### EOG

- signal/base/candidate decision: `BUY` / `BUY` / `BUY`
- allocation evidence: `BUY_APPROVED`, $9,777.98, 67 shares
- EMA20 safety: `ELIGIBLE`, `TOUCHING_OR_NEAR`, 0.1556499042% above the fixed
  completed signal-session EMA20
- execution readiness: `RESEARCH_ONLY` /
  `NO_APPROVED_LOSS_CONTROL_POLICY`
- loss control: inactive, policy `NONE`, no numeric boundary
- News: `NEVER_REFRESHED`, `NO_EFFECT`; not evaluated because the earlier gate failed
- sector context: Energy 21.0999306117% before, candidate projection 31.0300827455% after
- terminal/legacy reason after fix: `LOSS_CONTROL_UNAVAILABLE`
- final action/actionable: `NOT_ACTIONABLE` / no

The Approved Buys count of zero was correct. The old row Decision was ambiguous and the
old row Reason was stale/intermediate.

## Tests and gates

Focused backend commands covered decision construction, counts, terminal precedence,
News, action application, EMA20 revalidation, orchestration, and API serialization.
The final focused command passed **59 tests**; the broader portfolio/API run passed
**157 tests**.

```powershell
cd backend
$env:DEBUG='false'
.\run_checks.ps1
```

- Ruff: PASS (the script formatted 12 touched files, then passed)
- mypy: PASS, 189 source files
- pytest: PASS, 454 tests

```powershell
cd frontend
npm run lint
npm test -- --run
npm run build
```

- ESLint: PASS
- Vitest: PASS, 16 files / 87 tests
- TypeScript/Vite build: PASS, 110 modules transformed

Coverage proves: allocation BUY plus missing loss control counts as zero approved BUYs;
final/terminal state is typed; entry-safety, News, and user-exclusion blockers never
display allocation approval; a true actionable BUY is counted and rendered; and a
non-actionable candidate cannot expose or bypass the apply control.

## Real Edge acceptance

Local FastAPI, Vite, and Microsoft Edge/Playwright ran:

```powershell
cd frontend
$env:ALPHAPILOT_FRONTEND_URL='http://127.0.0.1:5173'
$env:ALPHAPILOT_BACKEND_URL='http://127.0.0.1:8000'
node scripts/final-buy-actionability-smoke.mjs
```

Final result: **PASS** — 502 evaluated tickers, 72 technical BUYs, zero final approved
BUYs. The successful script issued exactly one plan request. IBKR/EOG backend fields
matched the facts above; Edge showed `Final action NOT ACTIONABLE`, Candidate allocation,
and the prominent loss-control blocker; neither card showed Buy approved or Review Add;
neither appeared in Approved Buys 0. Durable portfolio and Paper state were unchanged,
and no broker action occurred.

Three earlier script invocations each made a read-only plan before the final pass. Two
hit overly exact Playwright text locators after the correct product UI had rendered. One
completed all product assertions but treated Paper Analytics' volatile `generated_at`
response timestamp as durable state. The final guard excludes only that request timestamp
and compares all durable portfolio/Paper fields. The retries caused no News-provider
calls because no candidate reached News, and no portfolio, Paper, market-data, or broker
mutation.

## Files changed for this semantics hotfix

Backend source: `api/routes/portfolio.py`, `portfolio/actions.py`,
`portfolio/decisions.py`, `portfolio/news_gate.py`, `portfolio/orchestration.py`,
`portfolio/sizing.py`, and `schemas/portfolio.py` under `backend/src/alphapilot/`.

Backend tests: `tests/api/test_portfolio_decisions.py` and portfolio tests for actions,
decisions, News gate, orchestration, and plan consistency/exclusions.

Frontend: `src/api/portfolio.ts`, `src/components/StatusBadge.tsx`, DecisionTable and
OpportunityExplorer source/tests, `src/pages/PortfolioPage.test.tsx`, fixtures, types,
`src/utils/decisionSemantics.ts`, `src/utils/format.ts`, and
`scripts/final-buy-actionability-smoke.mjs`.

Continuity docs: `AGENTS.md`, `docs/PROJECT_STATE.md`, `docs/DECISIONS.md`, this report,
and `docs/hotfixes/BUY_FUNNEL_NEWS_GATE_AUDIT.md`. Approved uncommitted work from the
preceding hotfixes remains preserved. No commit or push was made.

## Required final answers

1. IBKR showed Buy approved because the row exposed its intermediate allocation reason.
2. IBKR was absent from Approved Buys because approved numeric loss control was missing
   and `is_final_actionable=false`.
3. EOG showed Buy approved for the same intermediate-allocation labeling bug.
4. EOG was absent because approved numeric loss control was missing and it was not final
   actionable.
5. Neither was actually final actionable.
6. Both terminal blockers were `LOSS_CONTROL_UNAVAILABLE`.
7. Approved Buys = 0 was correct.
8. The old primary Decision label was ambiguous.
9. The old primary Reason was stale/intermediate; `reason` now mirrors terminal reason.
10. `final_action` is authoritative, paired with terminal reason and actionability.
11. Can a non-actionable record display Buy approved? **NO**.
12. Can it expose Add to Position as approved? **NO**.
13. Does a true actionable BUY appear in Approved Buys? **YES**.
14. Does the count match actionable rows? **YES**.
15. Financial thresholds changed? **NO**.
16. Backend gate: **PASS** — Ruff, mypy (189), pytest (454).
17. Frontend gate: **PASS** — lint, 16 files / 87 tests, build.
18. Browser acceptance: **PASS** — real FastAPI/Vite/Edge/Playwright.
19. Portfolio mutation? **NO**.
20. Paper mutation? **NO**.
21. Broker action? **NO**.
22. Git status: local dirty tree on `fix/portfolio-plan-consistency-ux`; 48 tracked
    files are modified, 12 files are untracked, and nothing is staged.
23. Recommended commit message: `fix: make final portfolio actionability authoritative`.

## Git status

Branch: `fix/portfolio-plan-consistency-ux`.

- 48 tracked files are modified.
- 12 files are untracked.
- Nothing is staged, committed, or pushed by Codex.
- `git diff --check`: PASS (line-ending conversion warnings only; no whitespace
  errors).

Untracked files:

- `backend/migrations/versions/d3f8a1b6c204_add_portfolio_ticker_preferences.py`
- `backend/src/alphapilot/portfolio/news_gate.py`
- `backend/tests/api/test_portfolio_ticker_preferences.py`
- `backend/tests/portfolio/test_news_gate.py`
- `backend/tests/portfolio/test_plan_consistency_and_exclusions.py`
- `docs/hotfixes/BUY_FUNNEL_NEWS_GATE_AUDIT.md`
- `docs/hotfixes/FINAL_BUY_ACTIONABILITY_SEMANTICS.md`
- `docs/hotfixes/PORTFOLIO_PLAN_CONSISTENCY_UX.md`
- `frontend/scripts/buy-funnel-news-gate-smoke.mjs`
- `frontend/scripts/final-buy-actionability-smoke.mjs`
- `frontend/src/features/portfolio/ExcludedTickersPanel.tsx`
- `frontend/src/utils/decisionSemantics.ts`

The tracked and untracked changes comprise the approved accumulated
portfolio-consistency, BUY-funnel/News-gate, and final-actionability hotfix work and are
ready for the user's review and staging.
