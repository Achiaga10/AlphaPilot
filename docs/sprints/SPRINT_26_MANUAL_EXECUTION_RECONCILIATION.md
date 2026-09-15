# Sprint 26 — Forward Operations Console & Manual Broker Reconciliation

Status: completed on 2026-09-14 and published on 2026-09-15 after the user's
explicit follow-up authorization. No PR, merge, development-database migration or
broker action was performed. Sprint 27 has not started.

## Architecture and boundary

The Sprint 25 Micho Forward Virtual Portfolio remains the canonical controlled
strategy experiment. Each Micho Forward ENTRY or EXIT order now creates one
observational external-execution case in the same transaction. The case is exposed
before next-open modeled execution as an informational manual broker action. It does
not submit an order. The user independently trades in Alpaca and may enter one or
more actual fills, skip the external action, or void a mistyped fill with a reason
and add a correction. All facts are explicitly `MANUAL_USER_RECORDED`; they are not
verified by an Alpaca API. Existing Forward orders are backfilled into cases by the
migration without changing their virtual history.

Only the external case/fill/event tables are written by journal API mutations. No
external record modifies a Micho signal, Portfolio Plan, Forward order/position/
trade/cash/equity, loss control, News, EMA20, ResearchPortfolio or Paper. Missing
external records cannot block Forward processing. No account-wide cash, equity,
positions or P&L is inferred.

The dashboard separates the virtual portfolio from a manual broker operations
section. It shows backend-owned BUY and SELL actions, due state, modeled and
user-recorded facts, partial fills, skip/correction controls, events, divergence,
closed-trade comparison and aggregate execution analytics. Unknown values render
as unavailable, not zero. A cancelled virtual order is not presented as a normal
action needed, while any separately entered execution remains auditable.

## Required completion answers

1. **Sprint name:** Forward Operations Console & Manual Broker Reconciliation.
2. **Alpaca API integration added?** No.
3. **Can AlphaPilot submit broker orders?** No.
4. **Can it automatically read Alpaca fills?** No.
5. **Source of external facts:** User-entered, `MANUAL_USER_RECORDED` observations.
6. **Can external fills modify Forward?** No; journal writes are separate.
7. **Can missing external records block Forward?** No.
8. **Partial fills supported?** Yes, multiple independently persisted fills.
9. **Corrections audited?** Yes: original fill retained and void metadata/event appended.
10. **SKIPPED supported?** Yes, with typed reason and explicit confirmation.
11. **Does skipped external trade remain a normal Forward virtual trade?** Yes.
12. **BUY and SELL visible before planned execution?** Yes, when the corresponding
    Forward pending order exists; exact future market price is never claimed.
13. **Action statuses:** `AWAITING_ACTION`, `AWAITING_RECORD`,
    `PARTIALLY_RECORDED`, `RECORDED`, `SKIPPED`, `VIRTUAL_CANCELLED`. Separate due
    statuses are `UPCOMING`, `AWAITING_RECORD`, `OVERDUE_RECORDING`, `DONE`,
    `CANCELLED`.
14. **Reconciliation statuses:** `INCOMPLETE`, `VIRTUAL_CANCELLED`,
    `MISSING_RECORD`, `PARTIAL`, `SKIPPED`, `EXECUTED_AFTER_VIRTUAL_CANCEL`,
    `ALIGNED`, `PRICE_DIVERGENCE`, `QUANTITY_DIVERGENCE`,
    `PRICE_AND_QUANTITY_DIVERGENCE`. `ALIGNED` requires exact comparable quantity
    and price equality; no hidden quality threshold.
15. **Persistence:** `external_execution_cases` has a unique Forward-order FK;
    `external_execution_fills` stores each Decimal fill and unique per-case request
    key with positive quantity/price and nonnegative optional fee checks;
    `external_execution_events` stores append-only typed audit events and unique
    per-case event keys. Cases also retain skip and recording-complete state.
16. **Migration:** generated revision `f650e3a238a0`, descending from Sprint 25
    `e9b2bc954dea`; backfills existing Forward orders. Upgrade, constraint tests,
    downgrade to `e9b2bc954dea`, and upgrade again to head passed against
    `TEST_DATABASE_URL` only. Downgrade removes journal tables and their data, so it
    is a test verification, not a routine deployed rollback procedure.
17. **Fill idempotency:** caller-supplied request key is unique per case. Same key
    and identical payload replays one result; changed payload returns conflict.
    The UI preserves its key and form on a failed response for safe retry.
18. **Concurrency:** PostgreSQL portfolio advisory lock, case row lock, transaction
    commit and durable unique constraints serialize concurrent journal writes.
    Concurrent same-key submissions produce one fill.
19. **Weighted fill:** `sum(active quantity × exact price) / sum(active quantity)`,
    rounded half-up to 8 decimal places. Voided fills are excluded; source rows are
    retained. Financial calculations use `Decimal`, not binary floating point.
20. **Entry price difference:** recorded weighted BUY price minus virtual modeled
    BUY price; bps = difference / virtual modeled price × 10,000.
21. **Exit price difference:** the same signed formula for the SELL order. Signed
    difference is a factual execution comparison, not strategy grading.
22. **P&L:** for a closed Forward trade with complete recorded BUY and SELL, equal
    recorded entry/exit share counts and known fees, recorded-execution gross P&L is
    recorded exit notional minus recorded entry notional; net subtracts recorded
    fees. Difference is recorded net minus unchanged virtual net. Recorded shares
    may differ from virtual shares and that variance remains visible. Completeness
    states are `COMPLETE`, `MISSING_ENTRY`, `MISSING_EXIT`, `PARTIAL`,
    `QUANTITY_MISMATCH`, `FEES_UNKNOWN`, `SKIPPED`.
23. **Unknown external metrics null?** Yes. Missing side, unmatched quantities or
    unknown fee prevents fabricated net recorded-execution P&L.
24. **Alpaca account equity claimed?** No. This is only linked recorded execution.
25. **Micho strategy semantics changed?** No.
26. **Micho Forward semantics changed?** No economic or decision semantics; only
    additive atomic observational case/event creation per order.
27. **EMA20 semantics changed?** No. Its approved BUY/manual-stop behavior remains.
28. **Can EMA20 create Sprint 26 actions?** No; no EMA20 Forward order exists.
29. **News advisory-only?** Yes; journal and reconciliation make no News request.
30. **Research rerun or tuning?** No.
31. **ResearchPortfolio mutated?** No.
32. **Paper mutated?** No.
33. **Broker mutations?** No.
34. **Development DB migration performed?** No. All migration/browser writes used
    the explicitly guarded distinct test database.
35. **Focused backend:** 19 Forward/journal tests passed, covering pending action,
    partial and corrected fills, exact Decimal comparison, skipped trade, virtual
    cancel, concurrent replay, API validation/conflicts, missing exit and DB checks.
36. **Full backend:** Ruff passed; format passed; mypy passed on 208 source files;
    681 tests passed. The final added paused-exit journal assertion passed in a
    subsequent focused run.
37. **Focused frontend:** 2 new operations-panel interaction tests and 2 existing
    Forward-panel tests passed.
38. **Full frontend:** lint passed; 104 tests across 18 files passed.
39. **Build:** TypeScript and Vite production build passed.
40. **Browser acceptance:** real FastAPI, real Vite and headless Edge against
    isolated test PostgreSQL state passed pending BUY, partial/final fills,
    explicit skip, correction audit, pre-execution SELL and closed P&L display.
    No Alpaca request was observed. A final-code real-server fill smoke also
    passed after UI retry hardening. Browser seed used controlled synthetic Micho
    decisions; strategy behavior is covered separately by backend regressions.
41. **Entry example:** virtual 99 shares at `$100.0500`; user-recorded 95 shares
    weighted at `$100.17894737`. Recorded minus virtual is `$0.1289` per share
    after 4-decimal display rounding, with a `-4` share variance. Neither changes
    the virtual 99-share position.
42. **Closed example:** virtual net P&L `$979.6050`; the linked 95-share recorded
    entry/exit with `$2.0000` total entered fees yielded recorded-execution net
    `$921.5000`, difference `-$58.1050`. This is not Alpaca account P&L.
43. **Skipped example:** a second synthetic BUY was marked `MISSED_ENTRY`; its
    Forward virtual trade continued and no external realized P&L was fabricated.
44. **Files created:** `backend/migrations/versions/f650e3a238a0_add_manual_external_execution_journal.py`,
    `backend/src/alphapilot/database/models/external_execution.py`,
    `backend/src/alphapilot/schemas/external_execution.py`,
    `backend/src/alphapilot/services/external_execution.py`,
    `frontend/src/features/dashboard/ExternalExecutionPanel.tsx`,
    `frontend/src/features/dashboard/ExternalExecutionPanel.test.tsx`, and this
    report. Temporary browser seed/runner scripts were removed after acceptance.
45. **Files modified:** `AGENTS.md`, `docs/PROJECT_STATE.md`,
    `docs/DECISIONS.md`, `backend/migrations/env.py`,
    `backend/src/alphapilot/database/models/__init__.py`,
    `backend/src/alphapilot/services/forward_portfolio.py`,
    `backend/src/alphapilot/api/routes/forward_portfolio.py`,
    `backend/tests/conftest.py`, `backend/tests/portfolio/test_forward_portfolio.py`,
    `frontend/src/types/forwardPortfolio.ts`,
    `frontend/src/api/forwardPortfolio.ts`,
    `frontend/src/hooks/usePortfolioApi.ts`, and
    `frontend/src/features/dashboard/ForwardPortfolioPanel.tsx`.
46. **Git publication:** committed on `research/ema20-loss-control`, whose prior
    HEAD was the pushed Sprint 25 commit
    `476b6b219c1e825b62870c09441ea6502d7ba988`. The exact Sprint 26 commit is the
    commit containing this report and is printed by `git rev-parse HEAD`.
47. **Git status:** clean after publication; no unrelated dirty baseline was found.
48. **Sprint 26 commit?** Yes, only after the user's explicit 2026-09-15 follow-up
    instruction to push it.
49. **Sprint 26 push?** Yes, to `origin/research/ema20-loss-control`. No force push,
    tag, PR, main merge or remote-history rewrite was performed.
50. **Known limits:** entered fills may be wrong and are not Alpaca-verified;
    fees/timestamps/partials depend on user entry; omitted fees remain unknown;
    external account cash/equity, outside trades and positions are not reconstructed;
    no broker orders are submitted or synchronized. Forward execution is still
    modeled from stored daily candles. Comparison is not proof of broker history.
51. **Safe post-review deployment:** see the commands below. They are for the user
    after reviewing/publishing Sprint 26, not commands executed in this task.
52. **Recommended next step:** review the local diff and report, then the user
    decides whether to commit/push/merge. Verify the intended development database
    and back it up before applying the migration. Do not begin Sprint 27 implicitly.

## Post-review runbook — user-executed only

First publish and merge Sprint 26 through the user's normal Git workflow. Once the
worktree is clean and the user intends to update local `main`:

```powershell
git status --short
git fetch origin main
git switch main
git pull --ff-only origin main
```

Before touching a development database, inspect the configured host/database name
without printing any password or full URL. Confirm the target against the intended
environment and take a backup through the user's normal PostgreSQL process:

```powershell
cd backend
$env:DEBUG = 'false'
uv run python -c "from alphapilot.core.config import settings; from sqlalchemy.engine import make_url; u=make_url(settings.DATABASE_URL); print('host:',u.host,'database:',u.database)"
uv run alembic current
```

Only after that manual confirmation and backup, the user may run:

```powershell
uv run alembic upgrade head
uv run alphapilot
```

In a separate terminal:

```powershell
cd frontend
npm run dev
```

Inspect the Micho Forward panel and engine health. Initialize it only if the user
actually intends to start a new virtual portfolio; Sprint 26 does not initialize
one automatically. These read-only API checks may be used after the backend starts:

```powershell
$base = 'http://127.0.0.1:8000/api/v1/forward-portfolio'
$current = Invoke-RestMethod "$base/current"
$current
if ($null -ne $current) {
  Invoke-RestMethod "$base/$($current.id)/health"
  Invoke-RestMethod "$base/$($current.id)/external-actions"
}
```

The action queue is informational. Any Alpaca order or trade remains a separate
manual user action outside AlphaPilot.
