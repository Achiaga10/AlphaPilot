# Sprint 25 — Micho Forward Portfolio Operations & Trade Lifecycle

Completion report for user review, 2026-09-13. Status: implemented and verified locally; no Git publication or development-database deployment. This is automatic **virtual** execution with manual/external broker execution, not autonomous trading.

## Purpose, scope, and authority

AlphaPilot now owns a dedicated persistent Forward Portfolio that manages the frozen operational `micho-150-v1` profile, version 1, BOTH entry mode. A completed-session Micho signal enters the existing backend Portfolio Decision pipeline; only `final_action=BUY` **and** `is_final_actionable=true` can create a Forward pending entry. Existing RS20 ranking, ATR-volatility-normalized allocation, ten-position limit, user exclusions, and Micho loss-control readiness remain authoritative. Technical signals, candidate allocations, News, and browser fields cannot independently authorize a virtual order. No Micho strategy parameter, profile version, historical conclusion, or research result changed.

Forward is separate from ResearchPortfolio recommendation/accounting state, immutable observational Paper evidence and Forward Paper Analytics, and Alpaca. It neither submits nor reads broker orders/positions as Forward authority. EMA20 Pullback retains its existing Portfolio Plan `APPROVED BUY` and `USER_MANUAL` / `MANUAL STOP REQUIRED` policy but has typed `forward_execution_eligible=false`, reason `SPRINT25_MICHO_ONLY`. News remains advisory-only; the Forward decision provider neither requires nor refreshes News. The pre-existing Copilot authority note and News UI notice were corrected to describe the EMA20 manual-stop exception without changing financial authority.

## Architecture and lifecycle

Migration `e9b2bc954dea` (down revision `d3f8a1b6c204`) creates seven isolated tables: `forward_portfolios`, `forward_cycles`, `forward_orders`, `forward_positions`, `forward_trades`, `forward_events`, and `forward_equity_points`. Portfolio identity records strategy ID/version, `VIRTUAL` execution, `MANUAL_EXTERNAL` broker mode, creation/start session, and explicit initial cash; current status, cash, equity, realized P&L, revision, last processed session, last success, and error are durable. Order, position, trade, event, and equity rows retain session, reason and numeric provenance. No existing economic table is repurposed.

Initialization requires an explicit positive cash amount (positive at four-decimal currency precision) and start session. The start may not precede the latest already stored completed session; older candles can warm indicators but never produce pre-start Forward trades. There is no silent production cash default, retroactive backfill, destructive reset, or archive API. `ACTIVE` admits new entries; `PAUSED` cancels pending entries and blocks new ones while continuing marks and Micho exits on open positions; `ARCHIVED` is terminal and not processed.

The existing `CompletedDailySessionPolicy` is authoritative: America/New_York completed-day cutoff is conservatively 16:15, and stored SPY dates identify available sessions. Each cycle reads only data through its own completed session and processes missing sessions oldest first. A final-actionable BUY on completed session T creates `PENDING_ENTRY`, not a position. It fills at the next available stored session U **open** using the stored raw open and 5 bps adverse BUY friction; raw open, modeled fill, and friction are separately persisted. Opening scheduled exits execute before opening entries. Whole shares are capped by planned shares, approved allocation, actual modeled opening cost and available Forward cash; an unaffordable entry is reduced or cancelled as `INSUFFICIENT_CASH_AT_FILL`. Cash never goes negative and no leverage or pyramiding is allowed. A repeated BUY for an open or pending ticker is skipped with a typed reason.

Micho's approved loss control is `SMA150_COMPLETED_CLOSE_EXIT` with `COMPLETED_DAILY_CLOSE_BELOW`, not an intraday protective-stop order. The current completed SMA150 boundary, source and planned risk/share are retained. An entry-day low, ordinary low touch, or opening gap below SMA150 does **not** independently trigger an exit. A completed close below the current SMA150 on session V schedules an exit for the next available stored session open, with 5 bps adverse SELL friction and separately recorded raw/modeled exit prices. Thus the request's conditional intraday stop-touch, entry-day activation and gap-through-stop scenarios are inapplicable to frozen Micho V1; implementing them would change the strategy. A synthetic gap-below-SMA case verifies that entry fills at U, U's completed close signals exit, and the position sells at V's open—not at U's low/open as a fabricated stop. `STOP_TRIGGERED` is a reserved typed event and is not emitted by this V1 policy. Exits are filled once, before same-open entries, and can fund those entries. Open positions mark to their stored completed close; equity is exactly cash plus marked market value.

The FastAPI lifespan starts a dedicated worker immediately and repeats hourly by default. It calls the same idempotent service as the manual recovery endpoint. PostgreSQL transaction advisory locking and row locking serialize portfolio work across workers; durable uniqueness protects `(portfolio_id, trading_session)` cycles, source-signal orders, one pending entry and one open position per ticker, one trade per position, event idempotency keys, and one equity point per session. Replaying a completed session creates at most one idempotent `CYCLE_SKIPPED` audit event and no economic duplication. A missing/stale required market datum rolls back that session's economic transaction, then records a typed `FAILED` cycle and `DATA_UNAVAILABLE` or `DATA_STALE` event separately; the same session remains retryable. Scheduler status and error are visible. The worker is not a second decision authority.

The API under `/api/v1/forward-portfolio` provides `GET /current`, `POST /initialize`, revision-checked `POST /{id}/pause` and `/resume`, `POST /{id}/cycles/run`, and `GET /{id}/positions`, `/orders`, `/trades`, `/events`, `/analytics`, and `/health`. Pause/resume require confirmation. The Dashboard Forward panel shows explicit virtual/manual boundaries, identity/status, cash/equity and P&L, open positions and pending entries, closed trades, activity, analytics, and compact engine health. It does not claim an Alpaca fill or provide a broker action.

Backend-owned analytics include starting/current equity, cash, market value, realized/unrealized/total P&L, net return, maximum drawdown, completed/open trades, win rate, profit factor, dollar expectancy, average winner/loser/worst trade, average holding sessions, turnover, friction, current/average exposure, maximum concurrency, and stop/strategy exit counts. Insufficient-sample trade statistics are null; no Sharpe or Calmar is fabricated. Health exposes scheduler running/status, portfolio status, last successful cycle, last processed session, latest completed market session, pending session count, data readiness, last error, and latest cycle status.

## Verification and controlled evidence

- Focused backend: Ruff passed, mypy passed across 205 source files, and 19 Forward/API/scheduler tests passed after the final replay-event change. Full backend `backend/run_checks.ps1`: Ruff and format passed, mypy passed across 205 source files, **675 tests passed**.
- Focused frontend: **24 tests passed**. Full frontend: lint passed, **102 tests passed**, and production build passed. No frontend code changed after this gate.
- Migration: generated revision `e9b2bc954dea` was verified against the isolated `TEST_DATABASE_URL` only, including head, upgrade, schema/constraint tests, downgrade where safe, and upgrade again. No destructive migration or test was run against the development database; that database has not yet been upgraded for Sprint 25.
- Controlled browser acceptance used the real FastAPI and Vite apps with isolated test-safe Forward data in Edge. Initialization, ACTIVE rendering, pending entry, modeled fill and open values, confirmed pause, cancellation of pending entry, continued exit management while paused, closed trades/activity/analytics, health, EMA20 recommendation-only copy, News advisory copy, startup catch-up, and idempotent rerun were observed. Temporary acceptance helpers and servers were removed/stopped. The local ignored screenshot `backend/backtest_reports/sprint25/forward-portfolio-browser.png` is diagnostic only, not commit-ready. No existing ResearchPortfolio, Paper, News, or broker state was mutated.
- Deterministic single-trade example: start $100,000; T approved BUY; U open $100 plus 5 bps = $100.05, 99 shares, cash $90,095.05; X raw exit $110 less 5 bps = $109.945, proceeds $10,884.555, gross P&L $990, net P&L $979.605, total friction $10.395, final cash/equity **$100,979.605**. Reprocessing produced no duplicate cash, order, position, trade, or transition events. Synthetic restart/catch-up matches uninterrupted processing, and concurrent same-session calls have one economic result.
- A richer isolated browser lifecycle closed AAA and BBB while CCC remained managed during PAUSED status and DDD's pending entry was cancelled; it reconciled cash $91,856.3590 plus open market value $10,395.0000 to equity $102,251.3590. These are synthetic acceptance figures, not live performance.
- Existing Micho, EMA20, Portfolio, News, entry-safety, Paper, research, API, and backtesting regression tests remained in the full passing suite. No strategy research was rerun or tuned.

## Audit event vocabulary

`PORTFOLIO_INITIALIZED`, `CYCLE_STARTED`, `CYCLE_COMPLETED`, `CYCLE_SKIPPED`, `CYCLE_FAILED`, `SIGNAL_APPROVED`, `SIGNAL_SKIPPED`, `ENTRY_PLANNED`, `ENTRY_CANCELLED`, `ENTRY_FILLED`, `POSITION_OPENED`, `STOP_TRIGGERED` (reserved/not emitted for Micho V1), `STRATEGY_EXIT_SIGNALLED`, `EXIT_PLANNED`, `EXIT_FILLED`, `POSITION_CLOSED`, `PORTFOLIO_PAUSED`, `PORTFOLIO_RESUMED`, `DATA_STALE`, and `DATA_UNAVAILABLE`. Stable event keys make replay audit idempotent; reason codes and numeric facts carry decision provenance.

## Required completion answers

1. **Sprint:** Sprint 25, Micho Forward Portfolio Operations & Trade Lifecycle; operational strategy version 1.
2. **Real Alpaca automation:** No.
3. **Automatic virtual management:** Yes, after explicit initialization and while the app/worker runs, with sequential downtime catch-up.
4. **Strategy:** Micho only.
5. **Identity/version:** `micho-150-v1`, version `1`, BOTH entry mode.
6. **Micho technical rules changed:** No.
7. **EMA20 Forward entries:** No.
8. **EMA20 Portfolio APPROVED BUY preserved:** Yes, including `USER_MANUAL` / `MANUAL STOP REQUIRED` and null automatic stop.
9. **News advisory-only:** Yes; it cannot create, block, size, cancel, or exit Forward trades.
10. **Persistence:** The seven separate Forward tables named above, with durable portfolio, cycle, order, position, trade, event, and equity provenance.
11. **Initial cash:** Explicit positive user input once; no Alpaca/ResearchPortfolio inference or prefilled production value.
12. **Forward start:** Explicit start session, no earlier than the latest already stored completed session; no pre-start trades.
13. **Completed session:** Existing New York 16:15 conservative cutoff and stored completed SPY session dates; each cycle is causally bounded to its own session.
14. **Entry timing:** Completed T approval produces a pending entry; next available stored U open fills it.
15. **Entry fill:** Stored raw U open plus 5 bps adverse BUY friction, both prices and friction persisted.
16. **Shares/allocation:** Whole shares, never above approved/planned allocation, fill-time Forward cash or capacity; opening gaps reduce or cancel quantity, never increase above plan.
17. **Micho loss control:** Approved current SMA150 completed-close-below policy with numeric boundary/source and planned risk evidence; no fallback stop.
18. **Stop activation:** No intraday stop exists to activate, including on entry day; completed-close rule applies while held.
19. **Gap-through:** An opening gap below SMA150 is not an immediate stop; a qualifying completed close schedules next-open strategy exit.
20. **Strategy exit:** Completed V close below current SMA150 schedules exit for next available stored open, with adverse SELL friction.
21. **Exit precedence:** Already scheduled opening exits fill before opening entries; no separate intraday-stop precedence is invented.
22. **Cash:** Opening entry debits modeled fill × shares; exit credits modeled proceeds; nonnegative Decimal cash, no leverage, one debit/credit per fill.
23. **Marking:** Open shares × stored completed close; equity = cash + market value, with realized/unrealized P&L reconciled.
24. **Capacity:** Maximum ten open positions, enforced in planning and filling; a causally completed opening exit frees a slot.
25. **Duplicate signal:** Open or pending ticker cannot pyramid; skipped with a typed reason.
26. **Pause:** Cancels/blocks new entries, but continues marks and exits; resume restores ordinary eligibility.
27. **Restart:** Oldest missing completed session through newest processed in order, without future-session information or duplicate economics.
28. **Scheduler:** Immediate FastAPI-startup run, then hourly by default; manual cycle endpoint calls the same service.
29. **Cross-process safety:** PostgreSQL transaction advisory lock, portfolio row lock, and database uniqueness constraints.
30. **Cycle key:** Unique `(portfolio_id, trading_session)`.
31. **Entry key:** Unique `(portfolio_id, company_id, side, source_signal_session)` order provenance plus one-pending-entry partial unique index.
32. **One-open invariant:** Partial unique `(portfolio_id, company_id)` OPEN-position index and no-pyramiding service check.
33. **Events:** Exact typed vocabulary listed in the Audit event vocabulary section.
34. **Analytics:** Backend-owned P&L, return/drawdown, trade outcomes, turnover/friction, exposure and concurrency, with unavailable metrics null.
35. **Versus backtest:** Forward persists incremental post-start evidence from newly completed operational sessions; it is not a frozen historical research rerun or hypothetical pre-start backfill.
36. **Versus Alpaca:** Forward fills are modeled from stored candles, not broker acknowledgements or actual executions; manual real trades may differ.
37. **Broker API mutations:** No.
38. **ResearchPortfolio mutation:** No economic or history mutation; existing read-only exclusion preferences are consulted.
39. **Paper evidence mutation:** No.
40. **Existing News evidence deleted:** No.
41. **Strategy research rerun:** No.
42. **Migration required:** Yes, before use against the development database.
43. **Revision:** `e9b2bc954dea`.
44. **Focused backend:** Ruff/mypy pass; 19 tests pass.
45. **Full backend:** Ruff/format pass, mypy 205 source files, 675 tests pass.
46. **Focused frontend:** 24 tests pass.
47. **Full frontend tests:** 102 pass; lint passes.
48. **Production build:** Pass.
49. **Browser:** Controlled real-app Edge acceptance passes in isolated test state; no broker/current Portfolio/Paper mutation.
50. **Synthetic lifecycle:** Pending → next-open fill → mark → completed-close signal → next-open exit → one closed trade and reconciled P&L passes.
51. **Catch-up:** Chronological restart replay and startup catch-up pass; state matches uninterrupted processing.
52. **Concurrency/idempotency:** Concurrent/repeated processing yields one economic result; durable keys prevent duplicate cash, orders, positions, trades and transition events.
53. **Cash/equity example:** $100,000 start → $90,095.05 after 99-share entry → $100,979.605 after exit, with zero open market value and net P&L $979.605.
54. **Health:** Scheduler running/status, portfolio status, last successful cycle, last processed/latest completed sessions, pending sessions, data readiness, last error, latest cycle status.
55. **Created files:** Exact inventory below.
56. **Modified files:** Exact inventory below.
57. **Git:** `research/ema20-loss-control`, HEAD `9c03a6bf3daf094193eb3d5204427d01d46407b4` (required base commit).
58. **Status:** 23 modified tracked files, 15 untracked Sprint 25 files including this report, nothing staged; local ignored diagnostic screenshot is not part of Git status.
59. **Commit:** No.
60. **Push:** No.
61. **Limitations:** See below; notably simulated daily-candle fills, no broker knowledge/reconciliation, downtime reconstruction, and historical current-constituent survivorship bias.
62. **Next step:** User reviews the report and diff, applies the migration to the intended development database after verifying its target, then tests with an explicit virtual start/cash; user alone decides whether to stage, commit and push. Do not begin Sprint 26 under this task.

## Exact Git inventory

Created/untracked (15, including this report):

```text
backend/migrations/versions/e9b2bc954dea_add_micho_forward_virtual_portfolio.py
backend/src/alphapilot/api/routes/forward_portfolio.py
backend/src/alphapilot/database/models/forward_portfolio.py
backend/src/alphapilot/repositories/forward_portfolio.py
backend/src/alphapilot/schemas/forward_portfolio.py
backend/src/alphapilot/services/forward_portfolio.py
backend/src/alphapilot/services/forward_portfolio_scheduler.py
backend/tests/api/test_forward_portfolio_api.py
backend/tests/portfolio/test_forward_portfolio.py
backend/tests/services/test_forward_portfolio_scheduler.py
frontend/src/api/forwardPortfolio.ts
frontend/src/features/dashboard/ForwardPortfolioPanel.test.tsx
frontend/src/features/dashboard/ForwardPortfolioPanel.tsx
frontend/src/types/forwardPortfolio.ts
docs/sprints/SPRINT_25_FORWARD_PORTFOLIO.md
```

Modified tracked (23):

```text
AGENTS.md
backend/migrations/env.py
backend/src/alphapilot/api/router.py
backend/src/alphapilot/api/routes/copilot.py
backend/src/alphapilot/core/config.py
backend/src/alphapilot/core/lifespan.py
backend/src/alphapilot/database/models/__init__.py
backend/src/alphapilot/portfolio/decisions.py
backend/src/alphapilot/portfolio/execution_readiness.py
backend/src/alphapilot/repositories/__init__.py
backend/src/alphapilot/schemas/portfolio.py
backend/tests/conftest.py
backend/tests/portfolio/test_ema_manual_stop_policy.py
docs/DECISIONS.md
docs/PROJECT_STATE.md
frontend/src/api/portfolio.ts
frontend/src/features/dashboard/NewsIntelligencePanel.tsx
frontend/src/hooks/usePortfolioApi.ts
frontend/src/pages/DashboardPage.tsx
frontend/src/styles.css
frontend/src/test/fixtures.ts
frontend/src/test/server.ts
frontend/src/types/portfolio.ts
```

All 38 Sprint 25 files are locally ready for user review/commit; none was staged, committed, or pushed by Codex. Recommended commit message: `feat(portfolio): add Micho forward virtual trade lifecycle`.

## Limitations and future boundary

Daily-candle next-open fills are modeled, not actual intraday or Alpaca fills. The reused 5 bps friction convention is an assumption and actual spread, price impact, partial fills, latency, halts and broker rejection can differ. AlphaPilot does not know actual manual Alpaca orders or positions, does not reconcile them, and cannot enforce a real broker stop; the user remains responsible for all external broker activity. Chronological downtime catch-up reconstructs virtual events from stored sessions, not historical real-time broker execution. Required stored-data gaps fail closed and delay a session until repaired. Historical S&P 500 research uses the **current constituent list and therefore has survivorship bias**; post-start Forward evidence is a distinct operational process, but universe membership during catch-up is not a frozen historical membership snapshot. `ARCHIVED` is represented as a terminal state but has no user-facing archive endpoint yet. No autonomous real-money execution, broker reconciliation, EMA20 Forward execution, or Sprint 26 work exists.
