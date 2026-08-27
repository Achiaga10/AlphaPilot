# AlphaPilot Sprint 11B Plan

## 1. Goal

Harden the completed Sprint 11 research UI into a clearer product workflow and
add safely gated research-admin data operations before Git review. Sprint 11B
remains part of the UI MVP hardening cycle; Sprint 12 is not started.

The outcomes are to make large portfolio-plan results explainable, searchable,
and visibly tied to their inputs, and to expose stored-data freshness and
existing sync capabilities without moving financial calculations into React.

## 2. Scope

- Use the user-provided `frontend/src/assets/images/alphapilot-logo.png` as the
  primary sidebar brand through Vite asset imports, without modifying the PNG.
- Add accessible contextual help for strategy, ranking, sizing, scope, dates,
  risk, ordering, and constraints.
- Redesign opportunity presentation into counted decision categories while
  preserving backend priority order for approved BUY candidates.
- Expand universe-evaluation output with company/sector/fact metadata, counts,
  filters, pagination, and a direct single-ticker evaluation action.
- Add a dedicated single-stock `/evaluate` workflow backed by the existing
  high-level portfolio-plan endpoint.
- Add input-snapshot/dirty-plan detection so results cannot appear current after
  plan-affecting inputs change.
- Add a feature-gated Research Admin page with typed freshness summaries,
  known-ticker sync, and non-blocking full-universe sync job status.
- Preserve all Sprint 7-11 research, portfolio, and API semantics.

## 3. Non-goals

- Sprint 12, broker execution, order submission, authentication, account
  persistence, or live portfolio synchronization.
- Frontend EMA/Micho/RS20/ATR/ranking/risk/sizing/constraint calculations.
- Strategy, ranking, sizing, or portfolio-policy changes.
- A new market-data provider, custom metadata inference, or fabricated company
  records.
- Running an expensive full-universe/provider sync during completion validation.
- A universal ranking or sizing claim. Policies retain their reviewed research
  classifications.

## 4. Existing Architecture and Preserved Boundaries

The UI calls typed API modules and `POST /api/v1/portfolio/plan`.
`PortfolioDecisionOrchestrator` loads stored Company/DailyCandle data, evaluates
the frozen strategy, computes signal-day RS20 and ATR14, ranks candidates, and
applies the decision engine. Sprint 11B extends presentation metadata around
this flow; it does not reproduce domain calculations in React.

The sync stack already separates providers, `MarketSyncService`, bulk sync,
universe/company sync, and `UniverseMarketSyncRunner`. Admin endpoints will
delegate to those services. Background job state is a process-local research
facility, not durable production infrastructure.

## 5. Accessible Information Model

A reusable `InfoTooltip` will expose identical concise text through hover,
keyboard focus, and click/tap. The trigger will have an accessible name and an
`aria-describedby` relationship to non-hover-only content.

Content will state:

- EMA20 Pullback uses its frozen EMA20/EMA50 HYBRID 2% configuration.
- Micho uses mechanical SMA150 V1 with BOTH entries.
- RS20 is stock 20-trading-bar return minus SPY 20-trading-bar return; higher
  values get constrained-capacity priority, while negative values can still be
  selected.
- ticker ascending is a deterministic, economically meaningless control.
- sizing policies and strategy-specific classifications are research evidence,
  never production-ready labels.

## 6. Opportunity and Ordering Semantics

The result view will expose live counts and categories: Approved Buys, Sell /
Exit, Skipped, All Decisions, and All Evaluated. Approved Buys is the default
when non-empty. Approved BUY rows preserve backend decision order exactly.
Decision order is identified separately from RS20 rank. Full universe evaluation
defaults to ticker ascending and visibly displays `Sorted A-Z`; that order is
not recommendation priority. Filters operate only on returned backend rows.

## 7. Universe Evaluation Contract

Candidate orchestration statuses will add optional display metadata already
available during backend orchestration: company name, stored sector, RS20, ATR,
portfolio decision/reason, and candidate rank where applicable. The actual
status enum remains unchanged: `READY`, `NO_ACTION`, `COMPANY_NOT_FOUND`,
`NO_DATA`, `STALE_DATA`, and `INSUFFICIENT_HISTORY`.

The UI will show status counts, a paginated/filterable A-Z table, and an
`Evaluate` action. Missing company metadata remains visibly missing and is never
inferred.

## 8. Single-stock Evaluation

`/evaluate` will submit the same high-level plan contract with a one-ticker
scope and the current workspace portfolio/configuration. It will show stored
company/sector/date facts, strategy signal and portfolio decision separately,
RS20/ATR when applicable, reason, rank, and allocation. Unknown tickers return
the backend's explicit `COMPANY_NOT_FOUND` status.

## 9. Plan Snapshot and Dirty-state Rule

On successful generation the workspace stores a canonical snapshot of all
plan-affecting inputs. Any later change to cash, positions, strategy, selection,
sizing, requested date, ticker scope, or risk configuration marks the displayed
plan stale. A prominent warning and Regenerate action will remain until a new
successful response updates the snapshot. Failed requests do not replace the
last successful plan or its snapshot.

## 10. Research Admin Configuration Gate

Backend setting `ADMIN_TOOLS_ENABLED=false` is the safe default. Admin routes
return a deterministic disabled response unless enabled. This is a development
feature gate, not authentication/authorization. The UI hides admin navigation
when the typed capability/summary request reports disabled. Responses never
include credentials, database URLs, provider secrets, or raw tracebacks.

## 11. Freshness and Sync Operations

The admin summary will report active Company count, active current S&P 500
count, latest SPY date, earliest/latest per-company latest-candle dates for
active constituents, and latest process-local sync job state.

Known-ticker sync delegates to the existing bulk market-sync service and
returns explicit synced/skipped/failed/company-not-found outcomes. Current
provider contracts do not reliably discover arbitrary custom-ticker metadata,
so Sprint 11B will not expose `Add & Sync` for unknown companies.

Full sync will be a non-blocking job that reuses universe membership sync,
company metadata sync, the bulk provider, checkpoint-aware universe runner, and
progress callbacks. One active full-sync job is allowed per process; duplicates
receive the existing job status. Job state exposes progress and safe failures.

## 12. Reference-price Decision

The high-level request requires a positive reference price before orchestration
builds current portfolio state. Resolving it safely would require broader
current-position enrichment and would still not recover frozen entry risk.
Sprint 11B retains the required reference-price field and clarifies it rather
than introducing a partial automatic value.

## 13. Testing Plan

Frontend tests will cover the real logo, accessible tooltips, opportunity
categories/order/counts, filters/pagination, universe metadata/actions,
single-stock outcomes, dirty-state/regeneration, admin disabled/enabled/status,
Dashboard counts, Settings classifications, and typed serialization with no
technical facts supplied by the client.

Backend tests will cover the admin gate, freshness aggregation, existing-service
delegation, duplicate prevention, progress/completion/safe failures, explicit
unknown ticker behavior, enriched orchestration metadata, deterministic ranks,
compatibility, and unchanged no-lookahead behavior.

## 14. Validation

From `frontend/`:

```powershell
npm run lint
npm run test
npm run build
```

From `backend/`:

```powershell
$env:DEBUG='false'
.\run_checks.ps1
```

Manual browser validation covers desktop/narrow navigation, plan generation,
dirty-state regeneration, categorized opportunities, universe evaluation,
single-stock evaluation, and disabled/safe admin behavior. It will not launch
an expensive real full-universe provider sync.

## 15. Completion Criteria

Sprint 11B is complete when the exact logo is bundled unchanged; UI ordering,
help, filters, and large-list behavior are accessible and deterministic;
single-stock and universe facts remain backend-owned; stale-plan ambiguity is
eliminated; admin operations are safe, typed, disabled by default, delegated,
and non-blocking; existing tests remain green; frontend/backend quality gates
and manual smoke pass; the completion report is created; and no Sprint 12 or
Git publishing operation occurs.
