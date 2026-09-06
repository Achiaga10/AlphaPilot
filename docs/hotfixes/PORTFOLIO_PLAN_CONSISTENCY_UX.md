# Portfolio Plan Consistency, User Exclusions, and UX Hotfix

## Status and scope

Complete locally on `fix/portfolio-plan-consistency-ux`. This is a focused
post-Sprint-24 hotfix, not Sprint 25. No strategy, ranking, News-policy, portfolio-
constraint, Paper-history, or broker behavior was changed. No commit or push was
performed.

## Root cause and authoritative invariant

The real plan `cbc206e8555fd34186a12702`, portfolio revision 17, requested for
2026-09-03 and analyzed through completed session 2026-09-02 reproduced the defect.
The orchestration readiness summary was calculated before the News overlay and counted
two readiness-approved BUY decisions. The route then changed both final decisions to
SKIP but returned the stale readiness object. The Approved Buys tab correctly filtered
the final rows and showed zero. The stale header count was wrong; no plan, revision,
analysis-date, or completed-session snapshot mismatch was involved.

The authoritative definitions are now:

```text
final_approved_buys
= count(decision == BUY and is_final_actionable)

final_approved_sells
= count(decision == SELL and is_final_actionable)
```

The route completes the News overlay, freezes the final decision tuple, synchronizes
candidate statuses, and recomputes readiness from that exact tuple. Legacy
`approved_buys` and `approved_sells` mirror the explicit final counts. `plan_id`,
`portfolio_revision`, `requested_as_of_date`, `analysis_as_of_date`, and the new
`generated_at` preserve plan provenance. The frontend consumes the backend totals and
filters rows using the same `is_final_actionable` fact.

Real read-only post-fix acceptance returned 502 evaluated tickers, 65 technical BUY
signals, zero final approved BUYs and zero actionable BUY rows, zero final approved
SELLs and zero actionable SELL rows, 348 returned decision records, and 502 universe-
evaluation records. Returned Decision Records are tickers that produced a portfolio
decision; Universe Evaluated also includes no-action and data-status outcomes.
Technical SELL Signals are raw strategy evidence; Final Approved Sells are portfolio
actions after all final gates.

## Persistent user exclusions

Migration `d3f8a1b6c204` creates `portfolio_ticker_preferences`, uniquely keyed by
portfolio and company. It preserves ticker, `ELIGIBLE` or `USER_EXCLUDED` status,
optional reason, exclusion timestamp, and normal created/updated provenance.

Typed endpoints are:

- `GET /api/v1/portfolio/{portfolio_id}/excluded-tickers`
- `PUT /api/v1/portfolio/{portfolio_id}/excluded-tickers/{ticker}`
- `POST /api/v1/portfolio/{portfolio_id}/excluded-tickers/{ticker}/restore`

Writes require the expected portfolio revision. A UBER exclusion persists across plan
generation and creates `USER_EXCLUDED_FROM_RECOMMENDATIONS`. Its technical signal and
RS20 score may remain auditable, but it receives no shares/allocation, consumes no
actionable slot, cannot be an approved BUY, and does not trigger targeted BUY News or
Gemini assessment. Positive News and RS20 cannot override it. Restoring UBER only
returns it to normal strategy, safety, News, risk, and allocation gates; it does not
force a BUY. Selling never creates an exclusion automatically.

Exclusion never deletes Company, DailyCandle, News, technical-signal, research,
trade-event, or Paper evidence. The UI provides “Exclude from future plans,” “Excluded
by you,” “Return to recommendation pool,” and a dedicated Excluded tickers manager.

## Dashboard and plan UX

The Dashboard now places Required Exits, Approved Buys, and Needs Attention first,
followed by compact Current Positions, Deferred Opportunities, and News Intelligence.
Position cards, including evidence-rich AXON, are status-first and keep provenance under
View details.

Deferred opportunities use backend-owned typed groups: entry too extended, News review
required, News/data unavailable, portfolio/cash constraint, user excluded, and other.
Each group has a count, keeps backend rank/order, shows five items initially, and
supports Show all, Collapse, and ticker search. React does not derive financial
priority.

News uses one collapsed summary per ticker. The backend orders adverse/review items
before routine context. Expansion visibly separates Adanos aggregate evidence, Finnhub
attributable articles, and Gemini targeted classifications; articles are not expanded
by default.

Final portfolio actions have primary labels. Technical BUY/SELL counts are secondary
evidence. The empty Approved Buys view explains technical BUY volume, user exclusions,
and typed rejection outcomes instead of reporting only an empty list.

Forward Paper Analytics remains on the Portfolio page because a separate route would be
disproportionate for this hotfix. It is a collapsed secondary summary by default. The
detailed sections are named “Current Open Paper Validation Trades” and “Historical
Closed Paper Trades,” and each row includes immutable Paper record/cycle and entry/exit
dates. Copy explicitly states that OPEN means no manual Paper exit is recorded and does
not assert current ResearchPortfolio ownership.

## APO and UBER read-only audits

APO has two genuine Paper cycles tied to ResearchPosition
`e3667010-9feb-4301-bf2c-f77e674ecf0b`:

- `7d5a8700-1752-4b84-9cc1-2dd1480bbd61`: CLOSED, EMA profile v1, entered
  2026-08-28 05:10 UTC at 74.0000 and exited 05:11 UTC at 136.0000.
- `38d2bd63-1177-4fab-8edf-764916089f2a`: OPEN, EMA profile v1, entered
  2026-08-28 05:12 UTC at 136.3900, with no recorded Paper exit.
- The ResearchPosition remains OPEN with quantity 74 and one OPEN trade event.

APO appearing in both Paper sections is correct historical truth, not a lifecycle bug.

UBER Paper record `7222ee1a-8e71-473c-be8a-00149ae476f6`, tied to ResearchPosition
`7f697909-3b1f-4790-960c-e0c8d6096c21`, is OPEN from 2026-08-28 05:16 UTC at
78.6900 because no manual Paper exit was recorded. The ResearchPosition itself is
CLOSED with quantity zero, and ResearchPortfolio trade events include OPEN and
FULL_EXIT (2026-09-03 16:51 UTC). The portfolio sale was recorded correctly. This is an
expected separate lifecycle with a missing manual Paper exit, not an automatic-sync or
portfolio-reconciliation bug. No immutable Paper evidence was changed.

## Tests, migration, and acceptance

Focused backend suite: 28 passed. Coverage includes final BUY/SELL count invariants,
entry-safety and News blocks, the hard pre-allocation exclusion gate, high-RS20
non-override, persistence/revision safety, restore-to-pool behavior, and suppression of
targeted News assessment for excluded BUYs.

Backend full gate:

- Ruff: PASS.
- mypy: PASS, 188 source files.
- pytest: PASS, 445 tests.

Frontend full gate:

- ESLint: PASS.
- Vitest: PASS, 16 files / 84 tests.
- TypeScript/Vite production build: PASS.

Fresh isolated PostgreSQL migration acceptance passed: upgrade to head, current at
`d3f8a1b6c204`, downgrade to `b4e2c8a1d903`, re-upgrade, and current again at
`d3f8a1b6c204`. The exactly named temporary database was removed afterward. The
development database was not reset; it received only the required upgrade from the
prior revision for real read-only acceptance.

Microsoft Edge/Playwright acceptance passed against local Vite and real FastAPI. It
verified same-plan BUY/SELL invariants, final-versus-technical labels, exclusion
controls and management, Dashboard hierarchy, deferred search, collapsed News, and
distinct Paper sections. Before/after ResearchPortfolio and Paper signatures were
identical. There was no portfolio mutation, Paper mutation, market sync, broker order,
or automatic trade.

## Files changed

Backend source/migration:

- `backend/migrations/versions/d3f8a1b6c204_add_portfolio_ticker_preferences.py`
- `backend/src/alphapilot/api/routes/news.py`
- `backend/src/alphapilot/api/routes/portfolio.py`
- `backend/src/alphapilot/database/models/__init__.py`
- `backend/src/alphapilot/database/models/research_portfolio.py`
- `backend/src/alphapilot/portfolio/daily_brief.py`
- `backend/src/alphapilot/portfolio/decisions.py`
- `backend/src/alphapilot/portfolio/orchestration.py`
- `backend/src/alphapilot/portfolio/sizing.py`
- `backend/src/alphapilot/repositories/research_portfolio.py`
- `backend/src/alphapilot/schemas/daily_brief.py`
- `backend/src/alphapilot/schemas/portfolio.py`
- `backend/src/alphapilot/services/daily_portfolio_brief.py`
- `backend/src/alphapilot/services/research_portfolio.py`

Backend tests:

- `backend/tests/api/test_portfolio_ticker_preferences.py`
- `backend/tests/portfolio/test_daily_portfolio_brief.py`
- `backend/tests/portfolio/test_orchestration.py`
- `backend/tests/portfolio/test_plan_consistency_and_exclusions.py`

Frontend source/tests:

- `frontend/src/api/portfolio.ts`
- `frontend/src/features/dashboard/DailyPortfolioManager.tsx`
- `frontend/src/features/dashboard/NewsIntelligencePanel.tsx`
- `frontend/src/features/dashboard/PlanOverview.tsx`
- `frontend/src/features/portfolio/DecisionTable.tsx`
- `frontend/src/features/portfolio/ExcludedTickersPanel.tsx`
- `frontend/src/features/portfolio/ForwardPaperAnalyticsPanel.tsx`
- `frontend/src/features/portfolio/OpportunityExplorer.test.tsx`
- `frontend/src/features/portfolio/OpportunityExplorer.tsx`
- `frontend/src/features/portfolio/PlanReadinessBanner.test.tsx`
- `frontend/src/features/portfolio/PlanReadinessBanner.tsx`
- `frontend/src/features/portfolio/PortfolioWorkspace.tsx`
- `frontend/src/features/portfolio/ResearchPortfolioPanel.tsx`
- `frontend/src/hooks/usePortfolioApi.ts`
- `frontend/src/pages/DashboardPage.test.tsx`
- `frontend/src/pages/PortfolioPage.test.tsx`
- `frontend/src/pages/PortfolioPage.tsx`
- `frontend/src/test/fixtures.ts`
- `frontend/src/test/server.ts`
- `frontend/src/types/portfolio.ts`

Continuity documentation:

- `AGENTS.md`
- `docs/PROJECT_STATE.md`
- `docs/DECISIONS.md`
- `docs/hotfixes/PORTFOLIO_PLAN_CONSISTENCY_UX.md`

## Final report answers

1. Header 2 came from pre-News readiness; the tab used final post-News rows.
2. The stale header/readiness count was wrong; the table’s zero was correct.
3. Approved BUY is final BUY plus `is_final_actionable=true` after every hard gate.
4. The final tuple recomputation and invariant tests prevent recurrence.
5. Plan/snapshot mismatch was not involved.
6. The persistent model and typed user-exclusion APIs are implemented.
7. UBER can be excluded persistently.
8. Exclusion is reloaded and survives Generate Portfolio.
9. UBER can be restored; ordinary gates still decide its outcome.
10. Sell does not automatically exclude.
11. Positive News cannot override exclusion.
12. RS20 cannot override exclusion.
13. Deferred Opportunities are grouped, counted, searchable, and collapsible.
14. News is compact, expandable, backend-prioritized, and provider-separated.
15. AXON/position cards are compact and status-first.
16. APO OPEN plus CLOSED means two separate immutable Paper cycles.
17. APO lifecycle is correct.
18. UBER remained Paper OPEN because no manual Paper exit was recorded.
19. UBER Paper state is an expected separate lifecycle, not a portfolio bug.
20. Paper labels, cycle IDs/dates, explanations, and disclosure were improved.
21. Detailed analytics is collapsed away from the primary Plan flow.
22. Returned Decision Records is a subset; Universe Evaluated is all ticker statuses.
23. SELL Signals are technical evidence; Approved Sells are final actions.
24. Migration revision is `d3f8a1b6c204`.
25. Fresh DB upgrade/current/downgrade/re-upgrade/current passed.
26. Backend full gate passed: 445 tests.
27. Frontend full gate passed: 16 files / 84 tests plus build.
28. Microsoft Edge/Playwright acceptance passed.
29. Portfolio mutation during acceptance: NO.
30. Paper historical mutation: NO.
31. Broker action: NO.
32. Git status is a local modified/untracked hotfix; no commit or push.
33. Recommended commit: `fix: align portfolio actions exclusions and dashboard UX`.
