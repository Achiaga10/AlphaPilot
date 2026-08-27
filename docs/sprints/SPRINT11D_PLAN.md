# AlphaPilot Sprint 11D Plan

## 1. Goal

Complete the uncommitted Sprint 11 product handoff by making stored-data
readiness explicit, adding responsive portfolio-value visualization and
observable synchronization progress, and hardening research-portfolio
bookkeeping. Sprint 11D continues `feature/ui-mvp`; Sprint 12 is not started.

## 2. Scope

- Diagnose and explain the observed 502 `STALE_DATA` portfolio-plan result.
- Preserve strict benchmark-session freshness and add typed plan readiness and
  reconciled coverage/count facts.
- Distinguish a genuine zero-opportunity result from unusable or partial data.
- Add a backend-valued, accessible allocation donut bound to the current
  reactive Research Portfolio Draft.
- Add determinate/indeterminate progress and completion detail for all Admin
  sync workflows.
- Replace Sprint 11C one-action invalidation with safe, backend-validated
  same-plan multi-action application.
- Add backend-owned partial/full manual sale bookkeeping using latest stored
  candles or an explicit user price.
- Keep one persisted client workspace shared by Dashboard and Portfolio Plan.

## 3. Non-goals and frozen research boundaries

Do not change EMA HYBRID 2%, Micho BOTH, RS20, ATR14, sizing formulas, risk
constraints, ranking, T+1 execution, backtest accounting, or research policy
classifications. Do not forward-fill missing sessions, evaluate stale stocks,
fabricate data, automatically start an expensive sync, add live quotes, place
broker orders, add authentication/account persistence, or begin Sprint 12.

## 4. Freshness semantics

For requested calendar date `R`, the expected analysis session is the newest
stored SPY trading session `S <= R`. This naturally maps weekends and market
closures to the preceding stored benchmark session. A ticker is fresh when its
newest candle through `S` is exactly `S`, stale when it is earlier, and no-data
when none exists. Stale/no-data tickers never enter strategy evaluation.

The observed 502-stale result arose after SPY advanced beyond the last
constituent session while Sprint 11C had deliberately avoided a full
market-candle universe refresh. The rule is not weakened to make signals appear.

## 5. Plan readiness and coverage

Add backend-owned readiness states `READY`, `PARTIAL_DATA`, `DATA_NOT_READY`,
and `NO_ACTION`, plus counts for requested, normally evaluated, fresh, stale,
no-data, insufficient-history, company-not-found, BUY signals, approved BUYs,
approved SELLs, actionable decisions, and BUY rejection reasons. Counts must
reconcile to requested status rows. React renders these facts; it does not
derive domain readiness.

## 6. Zero-BUY and recovery UX

An all-stale/no-data plan shows **Data refresh required**, coverage, latest
session/date facts, and a Data Management link. A partial plan identifies the
excluded count. A fully evaluated plan with no approved BUY states that the
strategy/portfolio rules produced no current approval and may show constraint
reason counts. After sync, freshness queries refetch and the UI offers a clear
return/regenerate path.

## 7. Portfolio allocation visualization

Add a small reusable SVG donut with one deterministic-color slice per current
position and a neutral Cash slice. Amounts and portfolio weights come from a
typed backend draft-summary response; React only maps those returned weights to
SVG geometry. The chart includes an accessible legend, keyboard-focusable slice
descriptions, responsive layout, and an all-cash state.

## 8. Research Portfolio Draft architecture

`PortfolioWorkspace` remains the single canonical client state and localStorage
owner. Dashboard and Portfolio consume the same reactive draft and backend
summary. The last Portfolio Plan remains a separate analysis snapshot.
Same-plan applied actions update draft cash/positions immediately while keeping
the recommendation set usable; a notice explains that snapshot risk metrics
describe the earlier analysis. Manual/configuration changes make the plan stale.

## 9. Same-plan selectable-action semantics

Each approved BUY/SELL receives a deterministic action identifier and advisory
application order. Candidate rank is recommendation priority, not mandatory
execution order, so BUY actions do not depend synthetically on higher-ranked
BUYs. Applied IDs are tracked per plan; cards remain visible and become
**Applied**. Backend preview/application revalidates the current draft, duplicate
state, holdings, whole shares, cash, position count/weight, sector, and the
sizing-policy-applicable reserve and modeled-risk constraints. React performs no
transaction arithmetic. A user share quantity is explicitly classified as
`SAME_PLAN_ACTION` or `USER_QUANTITY_OVERRIDE`; an override marks the draft as
deviated while leaving remaining recommendations visible for revalidation.

## 9A. Post-review exit guidance and metric semantics

The backend exposes typed strategy exit context derived from the frozen EMA20
HYBRID 2% or Micho SMA150 evaluation through the stored-data analysis day. The
UI distinguishes strategy exit rules from the 2×ATR14 research risk reference,
states that no fixed take-profit policy exists, and never implies live
monitoring. Metrics unused by Equal-slot render as not used rather than zero.
Equal-slot keeps its unchanged share formula while reporting actual proposed
sector before/after weights.

## 10. Manual Sell Position

Add typed latest-stored-price, manual-sale preview, and manual-sale application
contracts. The dialog defaults to all shares and the latest stored DailyCandle
close/date; the user may choose a whole-share partial quantity and override the
execution price. The backend returns gross proceeds, cash before/after, shares
remaining, position removal, price source/date, and updated state. Missing
stored price requires explicit input. Any manual sale invalidates the plan. No
endpoint sends an order.

## 11. Sync progress architecture

Extend existing process-local Admin job progress with a safe stage and current
ticker. Universe sync reports metadata progress; candle sync reports benchmark
then stock batches; Full Sync exposes universe/candle phases. A reusable
accessible `SyncProgress` renders determinate percentages only when a meaningful
total exists and otherwise renders indeterminate state. Completion remains
visible. Fast single/custom operations use explicit stages driven by their typed
response rather than fabricated timing.

## 12. Testing and real validation

Backend tests cover readiness variants/count reconciliation, weekend/session
behavior, stale exclusion/no-lookahead, action order/cash/duplicate validation,
partial/full manual sale, stored/overridden/missing price, draft summary, and
progress fields. Frontend tests cover readiness copy/recovery, donut data and
accessibility, sync progress, same-plan multi-apply, immediate Dashboard state,
manual sale, persistence, and no broker requests.

Final gates:

```powershell
cd frontend
npm run lint
npm run test -- --run
npm run build
npm run smoke:real

cd ../backend
$env:DEBUG='false'
.\run_checks.ps1
```

Real validation uses configured Alpaca IEX without printing credentials. The
current stored summary and a full current-universe plan will be recorded. A
provider sync is run only if needed and reasonable; controlled evidence is used
honestly otherwise.

## 13. Completion criteria

Sprint 11D completes when readiness semantics prevent a stale universe from
appearing as “no opportunities”; weekend behavior is tested; the allocation
donut and Dashboard reflect the reactive draft; all sync surfaces expose
accessible progress; multiple ordered approved actions apply safely through the
backend; manual partial/full sales work with stored-price clarity; all gates and
browser acceptance pass; the completion report records real coverage; all work
remains local; and Sprint 12 is not started.

## 14. Critical single-stock identity invariant

For every Evaluate Stock result:

```text
normalized(requested_ticker) == normalized(returned_target_ticker)
normalized(requested_ticker) == normalized(rendered_result.ticker)
```

The high-level plan may include held positions for portfolio context. The UI
selects the requested target by normalized ticker, never response position. If
the invariant cannot be satisfied, it renders a safe error. Editable input and
the last successful evaluation are separate snapshots, and only the latest
active request may update the result.

## 15. Completed daily candle integrity

Daily analysis, ranking, ATR, decision, exit guidance, latest stored price, and
Admin freshness use completed U.S. sessions only. A backend-owned
`America/New_York` policy treats the current calendar day's daily bar as
incomplete until 16:15 New York time. Incoming incomplete provider bars are not
persisted; legacy partial rows remain safely quarantined by repository and
orchestration cutoffs, and the ordinary unique-key upsert replaces them after
the session completes. Stored SPY session dates resolve weekends and holidays.
The UI displays requested date separately from completed analysis session and
does not perform market-clock calculations.
