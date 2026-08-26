# AlphaPilot Sprint 11 Plan

## 1. Goal

Build the first production-structured UI MVP for AlphaPilot: a typed research
decision dashboard that consumes the backend Portfolio Plan API and proves the
current domain contract is usable without moving strategy, ranking, sizing, or
risk logic into the browser.

## 2. Frontend Stack

- React with strict TypeScript
- Vite
- React Router for the three required routes
- TanStack Query for backend/server state
- project-owned responsive CSS; no large component framework
- Vitest, React Testing Library, and MSW for frontend tests
- npm with a committed lockfile; no secrets in the frontend

The frontend lives at repository-root `frontend/`. `VITE_API_BASE_URL` selects
the backend base URL and is documented in `frontend/.env.example`.

## 3. Frontend Architecture

```text
pages/routes
  -> feature components and editable portfolio workspace state
  -> TanStack Query hooks
  -> centralized typed API modules
  -> FastAPI /api/v1 contract
```

`src/api` owns base URL, JSON parsing, cancellation, typed errors, and endpoint
functions. `src/types` mirrors the actual Pydantic request/response contract.
Feature folders own dashboard, portfolio-plan, and settings presentation.
Reusable cards, badges, states, and formatting live outside pages. No domain
indicator, signal, ranking, sizing, constraint, or decision calculation is
implemented in the frontend.

## 4. Backend API Contract

Required real endpoints:

- `GET /api/v1/health/` for connectivity
- `GET /api/v1/portfolio/risk-config` for frozen research defaults
- `POST /api/v1/portfolio/plan` for normal UI orchestration

The plan request contains current cash/positions, strategy, frozen strategy
configuration, selection policy, sizing policy, risk configuration, optional
ticker scope, and requested as-of date. It never contains ATR, RS20, sector,
stop distance, or precomputed strategy signals.

The existing lower-level `POST /api/v1/portfolio/decisions` remains compatible
but is not the normal UI workflow. Minimal backend work may add configurable
local-development CORS and display-ready current-position/portfolio summary
fields so the frontend does not recreate financial-domain calculations.

## 5. Screens and Views

- `/`: Research Decision Dashboard with connectivity/as-of status, portfolio
  summary, current positions, decisions/opportunities, and risk configuration.
- `/portfolio`: editable current portfolio state, supported strategy/selection/
  sizing choices, optional ticker scope and requested date, Generate Portfolio
  Plan workflow, detailed decisions, and per-ticker data statuses.
- `/settings`: backend defaults and session/research configuration explanation.

Company detail and historical backtest visualization are deferred because the
required workflow is the stored-data Portfolio Plan and no dedicated combined
analysis/backtest-summary contract currently exists.

## 6. State Ownership

- TanStack Query owns health and risk-config server state and plan mutations.
- A React workspace provider owns editable portfolio/request state and the most
  recent plan for cross-route presentation.
- Browser storage may preserve high-level form inputs for refresh convenience;
  it is explicitly local research state, not authenticated persistence.
- FastAPI remains the source of all domain decisions and calculated facts.

## 7. Loading, Error, and Empty States

Every query/mutation has an explicit loading state. Health/network failures,
422 validation details, and generic backend failures are distinguished.
Per-ticker `READY`, `NO_ACTION`, `COMPANY_NOT_FOUND`, `NO_DATA`, `STALE_DATA`,
and `INSUFFICIENT_HISTORY` remain inline research/data statuses rather than
global failures. Empty positions, no decisions, and no approved BUY decisions
have separate copy.

## 8. API Error Handling

The centralized client throws one typed `ApiError` containing status, safe
message, and FastAPI validation details. It never renders backend HTML or Python
tracebacks. Requests pass `AbortSignal` where supported. Plan submission is
disabled while pending and retry is available for recoverable failures.

## 9. Testing Strategy

Component/integration tests use Vitest, React Testing Library, and MSW without a
real backend for every test. Coverage includes routes, connectivity failures,
risk config, form validation/add/remove, exact request serialization, all four
decision types, reason labels, number/date formatting, data statuses,
loading/error/empty states, frozen strategy configuration, policy selection,
navigation, and responsive-safe structure. Backend tests cover any schema/CORS
changes. One real stored-data frontend-to-backend smoke scenario validates the
full request path after both suites are green.

## 10. Accessibility Baseline

Use semantic landmarks/headings/tables, explicit form labels, keyboard-usable
controls, accessible validation/error announcements, visible focus states,
adequate contrast, and text/icon labels in addition to status color. Expandable
decision details use native semantic controls.

## 11. Responsive Behavior

Desktop is primary. Navigation, summary cards, forms, and decision layouts
collapse for tablet/mobile; dense tables use an accessible horizontal container
instead of clipping. Touch targets and form controls remain usable at narrow
widths.

## 12. Non-goals

No broker synchronization/orders, live quotes/streaming, authentication, user
accounts, cloud portfolio persistence, AI/news recommendations, alerts, native
mobile app, advanced charts, backtest explorer, admin/payment system, or Sprint
12 work. No UI copy may imply live trading or production validation.

## 13. Completion Criteria

Sprint 11 completes when the strict typed frontend and three routes exist;
`/portfolio/plan` works through the real UI; no financial-domain logic is
duplicated; decisions, risk/as-of/data status, loading/error/empty states are
clear; frontend lint/tests/build pass; backend `run_checks.ps1` passes; a real
stored-data demo is verified; documentation and the completion report are
finished; and no commit, push, PR, merge, tag, or Sprint 12 implementation is
performed.
