# AlphaPilot Sprint 16 Plan — Persistent Research Portfolio

## Goal

Replace browser-authoritative financial state with one backend-owned persistent
research portfolio. Preserve entry facts and an append-only trade lifecycle,
derive current value from stored completed daily candles, and bind normal plans
and actions to a monotonic portfolio revision.

## Scope and boundaries

Sprint 16 adds additive PostgreSQL persistence, repositories/services, typed
portfolio APIs, normal-plan/action contract migration, one-time legacy browser
import, backend-valued Dashboard/Portfolio displays, and sync-triggered query
refresh. It adds no broker execution, scheduler, exit monitoring, AI, strategy,
backtest, Strategy Lab, Strategy Profile, stop, ranking, or risk change.

## Persistent aggregate

`ResearchPortfolio` stores stable identity/name, cash, cumulative realized P&L,
revision, and timestamps. `ResearchPosition` stores one open/closed aggregate
position per company lifecycle with quantity, average cost, cost basis, entry
date/price, optional modeled risk, strategy/profile/selection/decision facts,
an immutable profile snapshot where known, explicit provenance status, and
timestamps. `ResearchTradeEvent` is append-only application history for OPEN,
PARTIAL_EXIT, and FULL_EXIT.

Money uses `Numeric`/`Decimal`; quantities and revisions are integers. The
migration is additive, asyncpg-compatible, and does not touch candle/history or
Sprint 13 tables.

## Transaction and concurrency model

Mutations run in one SQLAlchemy transaction. The portfolio row is loaded with
`SELECT ... FOR UPDATE`; the request revision must equal the stored revision.
Only after the pure existing action validator succeeds does the service mutate
cash/position, append an event, increment revision, and commit. A failed/stale
request rolls back and creates no successful event. Two requests carrying one
revision therefore cannot both succeed.

## BUY and SELL accounting

BUY remains positive whole shares, no leverage, no BUY while held. Cash falls
by quantity × research execution price; average cost and cost basis are stored;
profile provenance and an OPEN event are recorded.

SELL cannot exceed quantity. Gross proceeds are quantity × execution price.
Realized P&L is quantity × (execution price − stored average cost). Partial sell
reduces quantity and cost basis by sold quantity × average cost; full sell marks
the row closed without deleting it. Both append an event and increment revision.
Manual sale continues to use the latest stored completed close or an explicit
user research price. No tax lots, commissions, leverage, or broker orders.

## Entry provenance

Normal plan BUYs persist strategy, exact Strategy Profile ID/version, selection
policy, entry decision/reason, and canonical resolved profile JSON. This audit
snapshot does not depend on a future registry retaining V1. Legacy import uses
`LEGACY_IMPORTED`/unknown fields and never claims EMA or Micho provenance.

## Mark-to-market valuation

Portfolio reads load each open position plus
`DailyCandleRepository.get_latest()`. That repository already enforces
`CompletedDailySessionPolicy`. Returned position facts include quantity,
average cost, cost basis, latest completed date/close, market value, unrealized
P&L and percentage, plus provenance. Market sync updates candles only; refetching
the portfolio changes valuation without rewriting entry facts.

If any position lacks a completed price, it remains listed with explicit
`PRICE_UNAVAILABLE`. Cash, cost basis, realized P&L, and valued positions remain
inspectable; total equity/aggregate market value and unrealized totals are null
and portfolio valuation status is `PARTIAL` or `UNAVAILABLE`, never fabricated
zero.

## Normal API contract

Expose minimal endpoints to get/initialize/import the current research
portfolio and read events. High-level plan requests carry portfolio ID rather
than cash/positions; backend loads the aggregate. Plan response carries
portfolio ID/revision, included in the plan fingerprint. Preview/apply and
manual sell carry portfolio ID/revision; the backend reloads and revalidates the
current aggregate. Lower-level `/portfolio/decisions` remains explicitly
configurable.

## Frontend and migration

React queries typed backend portfolio state and formats backend financial facts;
it performs no market-value/P&L/equity arithmetic. Existing localStorage is
parsed once only for import. If no backend portfolio exists, the UI offers/
performs a deterministic initialization/import; missing provenance remains
legacy. If one exists, local financial state never overwrites it. Strategy,
selection, date, and ticker-scope preferences may remain local.

Successful BUY/SELL/import invalidates portfolio/plan queries. Successful admin
candle sync invalidates portfolio valuation queries so stored completed-close
changes appear without F5.

## Testing and completion

Focused backend tests cover persistence, entry/profile/legacy provenance,
events, accounting, completed-candle valuation, missing price, the exact 10 at
$100 then completed $110 scenario, atomic rollback, revision races, normal plan
binding, stale actions, and Sprint 13–15/Scanner regressions. Frontend tests
cover backend authority, one-time migration, plan/action revisions, refetch,
valuation display, safe missing/malformed responses, and Evaluate identity.

Near completion run one backend `run_checks.ps1`, one frontend lint/test/build,
then one controlled browser acceptance with no provider or broker call. Create
`docs/sprints/SPRINT16_COMPLETION_REPORT.md`, record Git state, and stop before
Sprint 17.
