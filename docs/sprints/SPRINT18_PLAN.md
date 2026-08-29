# AlphaPilot Sprint 18 Plan

## Goal

Create one deterministic backend-owned Position Intelligence contract and a
manual Alpaca Paper forward-validation journal. Improve reconciliation inputs
with typed reason codes and optional notes. Sprint 18 adds no broker connection,
automatic trade, AI/LLM, strategy change, or Sprint 19 work.

## Scope and architecture

`PositionIntelligenceService` composes persistent position, valuation, Strategy
Profile, monitoring/history, sticky exit, trade, and reconciliation facts.
FastAPI validates and serializes; React presents backend facts. Unknown-profile
positions retain valuation/history but receive explicitly unavailable strategy
guidance.

An additive paper-validation journal stores one immutable manual
`ALPACA_PAPER_MANUAL` entry and at most one aggregated full exit. A service owns
Decimal planned-versus-actual comparisons, lifecycle, trigger association, and
paper P&L. Paper records never mutate portfolio cash, holdings, revision,
monitoring, profiles, or decisions.

Typed cash, external-position, and position-reconciliation reason enums are
validated server-side and persisted with optional notes. Existing legacy reason
text remains readable.

## Non-goals

No Alpaca Trading API, broker synchronization/order state machine, automatic
BUY/SELL, partial paper exits, tax lots, destructive record editing, strategy or
risk tuning, scheduler changes, market-data work, AI/LLM, or Sprint 19.

## API and UI

- typed position-intelligence read endpoint per persistent position;
- focused paper entry/list/exit endpoints under the portfolio API;
- existing reconciliation endpoints upgraded to structured reason and note;
- compact Position Intelligence and Forward Paper Validation presentation in
  the existing Portfolio experience, with no React financial calculations.

## Persistence

One additive asyncpg-compatible Alembic revision adds the paper journal and
nullable structured reconciliation fields. Financial values use
Numeric/Decimal. Existing history is not rewritten.

## Testing and completion

Focused backend tests cover known/unknown profiles, valuation, monitoring
history, sticky exits, inactive policy facts, side-effect-free reads, exact
paper comparisons/P&L, portfolio separation, trigger association, reason-code
validation, and legacy compatibility. Frontend tests cover runtime parsing,
intelligence/paper states, dropdowns/notes, and monitoring regressions. Near
completion run the backend full gate once, frontend lint/test/build once, then
one controlled local browser acceptance without provider/broker calls.

Sprint 18 completes only when all contracts work end to end, all gates pass,
the completion report records the evidence, and Sprint 17/frozen research
semantics remain unchanged. Stop before Sprint 19.
