# AlphaPilot Sprint 21 Plan

## Goal

Turn Dashboard into a deterministic Daily Portfolio Manager that answers what requires
attention after the latest completed-session data sync. It remains read-only decision
support and routes the user to existing audited research-portfolio and manual Paper
Validation workflows; it never submits or simulates broker orders.

## Architecture reused

`DailyPortfolioBriefService` will be an orchestration/projection boundary over:

- `ResearchPortfolioService.value()` for backend-owned valuation and revision;
- `PositionIntelligenceService` and stored monitoring snapshots for sticky SELL,
  ATTENTION, HOLD, and unavailable profile/data facts;
- `StopExitGuidanceService` for strategy references and Micho SMA150 loss control;
- `PortfolioDecisionOrchestrator` for both frozen Strategy Profiles, signal evaluation,
  RS20, sizing, constraints, and candidate decisions;
- `ExecutionReadiness` already attached to decisions;
- stored SPY/latest completed-candle semantics and existing sync/scheduler facts.

The brief will not persist duplicated state and requires no migration. React will render
the typed projection without calculating indicators, status, readiness, loss-control
distance, risk, sizing, or portfolio constraints.

## API and model

Add read-only `GET /api/v1/portfolio/{portfolio_id}/daily-brief`, with an optional
requested `as_of_date`; absent input resolves through stored latest completed-session
data. The typed response contains portfolio ID/revision, generated timestamp,
expected/synchronized/brief sessions, `READY`/`DEGRADED`/`BLOCKED` readiness, explicit
freshness explanation, valuation summary, max positions, workflow status, and ordered
collections for required actions, attention, actionable opportunities, research-only
opportunities, deferred opportunities, hold, and unavailable positions.

Each position projection retains position/ticker/profile identity, status/reason and
backend explanation, quantity, completed-session close, P&L, sticky SELL facts, and
backend stop/exit references. Each opportunity retains source profile/plan identity,
portfolio revision, ranking/decision facts, entry and quantity, sizing, sector,
ExecutionReadiness/reason, loss-control evidence, strategy references, and provenance.

## Priority and workflow rules

Order is SELL, ATTENTION, actionable opportunities, research-only/deferred
opportunities, HOLD, then unavailable. Within position sections use ticker order;
opportunities preserve authoritative portfolio-plan ranking/order with ticker fallback.

Sticky SELL is authoritative and never downgraded. If any required exit exists, new
opportunities remain visible but their orchestration workflow is
`WAITING_FOR_REQUIRED_EXITS`; no hypothetical proceeds or post-SELL cash are used.
Existing plan/action revision and fingerprint revalidation remain the only mutation path.

## Freshness and completed-session behavior

The service uses stored completed daily sessions only, via the existing
`CompletedDailySessionPolicy` and SPY session authority. It exposes expected completed,
latest synchronized, position-guidance, and brief dates explicitly. Missing/stale or
failed current sync produces `DEGRADED`/`BLOCKED`; safe last-known position guidance may
remain visible with its actual as-of session, while new ACTIONABLE entries are blocked
or deferred. Missing values remain null/unavailable, never numeric zero.

## Opportunities and loss control

Both frozen profiles are evaluated through existing plan orchestration with their
recommended RS20 policy and profile-owned sizing. Micho may be ACTIONABLE only when the
existing readiness contract includes positive numeric SMA150 boundary, completed-close
trigger, and profile provenance; it is explicitly not a broker stop. EMA BUY signals
remain `RESEARCH_ONLY` with `NO_APPROVED_LOSS_CONTROL_POLICY`. No policy, formula,
parameter, profile, research result, or sizing behavior changes.

## Frontend

Evolve `/` Dashboard into Daily Portfolio Manager with completed-session/readiness
header, Refresh (brief refetch only), backend valuation cards, explicit stale warning,
and priority sections. SELL cards link to existing Position Intelligence/Ask AI/manual
management flows. HOLD is compact. Actionable and research-only candidates visibly show
their readiness, blocker/loss control, trigger, and broker-stop distinction. Empty states
remain normal. No new market-sync action is attached to Refresh.

## Copilot

Add only the minimal deterministic daily-brief intent/facts required for questions such
as “What requires action today?”. Counts/actions come from the same brief projection;
Ollama may explain supplied facts but cannot choose, create, mutate, or execute actions.

## Acceptance criteria

- Typed read-only daily-brief endpoint, no migration and no duplicated financial logic.
- READY and stale/degraded/blocked cases are explicit and completed-session safe.
- SELL/ATTENTION/HOLD/UNAVAILABLE are separate, sticky SELL is preserved, and severity
  order is deterministic.
- Existing plan authority supplies opportunities; actionable Micho has numeric SMA150
  evidence, EMA is never actionable, and missing loss control cannot be actionable.
- Required exits defer reliance on new-entry quantities without changing underlying
  financial readiness or cash.
- Portfolio revision/plan identity remain present and existing action APIs remain the
  only write path; Paper Validation remains separate.
- Dashboard and Copilot render/explain backend facts; Refresh causes no sync/mutation.
- Focused tests, full backend/frontend gates, and controlled browser acceptance pass.

## Expected files

Backend: new daily-brief domain/service/schema/tests; portfolio and Copilot route/context/
intent integration; narrowly scoped bulk helpers only if necessary. Frontend: daily-brief
API/types/hook, Dashboard components/styles/tests and controlled browser smoke.
Documentation: continuity files, this plan, and Sprint 21 completion report. No Alembic
migration is expected.
