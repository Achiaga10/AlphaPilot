# Sprint 19 Plan — AlphaPilot AI Copilot Foundation

## Goal

Add a read-only grounded explanation layer over deterministic AlphaPilot facts.
AlphaPilot calculates and decides; AI explains. Sprint 18 Position Intelligence,
monitoring, portfolio valuation, and Paper Validation remain authoritative.

## Scope and architecture

Position and compact portfolio question endpoints will call a
`CopilotOrchestrator`. It uses a `CopilotContextAssembler`, whose only approved
read boundaries are Position Intelligence, portfolio valuation/monitoring,
Paper Validation, and a new deterministic Stop/Exit Guidance service. Canonical
JSON-compatible facts—not ORM/session objects—cross the `LLMProvider` boundary.
The provider returns a typed answer plus references to real fact IDs.

An explicit provider protocol supports local Ollama and deterministic test
fakes. Ollama configuration is environment-owned and disabled by default. No
real model is needed by tests or CI. Provider-disabled, unavailable, and invalid
responses are controlled typed failures.

## Stop and exit guidance

Typed states distinguish `ACTIVE_POLICY`, `STRATEGY_EXIT_REFERENCE`,
`RESEARCH_ONLY`, `NONE`, and `UNAVAILABLE`. Current EMA and Micho protective
stops, trailing stops, and profit targets remain `NONE`.

- EMA exposes EMA50 as a hard `COMPLETED_DAILY_CLOSE_BELOW` reference and EMA20
  as a conditional completed-close reference under frozen HYBRID 2% semantics.
- Micho exposes SMA150 as a `COMPLETED_DAILY_CLOSE_BELOW` reference.
- Sticky SELL is reported from stored monitoring facts.
- Sprint 12 ATR candidates remain `RESEARCH_ONLY` / `NOT_ACTIVE`; no price is
  invented and no policy is activated.

## Grounding and security

The server-owned policy makes structured AlphaPilot facts authoritative,
forbids indicator/threshold/stop invention, preserves completed-close semantics,
and treats questions and stored notes as untrusted data. The Copilot receives no
SQL, shell, network browsing, broker, or portfolio-write tool. Returned fact
references must exist in the assembled context. V1 is stateless per request.

## API and UI

Required APIs are status and position ask; a compact portfolio ask is included
only by reusing current valuation/monitoring. Responses include answer, scope,
identity/as-of date, grounding status, authoritative evidence, limitations, and
safe provider metadata. Position Intelligence gains a compact “Ask AlphaPilot
AI” panel that always identifies the selected holding and displays narrative
separately from authoritative evidence and stop/reference categories.

## Non-goals

No LangChain/LangGraph, AI trading decision, mutation, broker/Alpaca Trading
integration, SQL/shell access, news/web browsing, strategy/profile change,
research-stop activation, new strategy, tuning, long-term memory, or Sprint 20.

## Testing and completion

Focused tests cover provider isolation/errors, exact EMA/Micho/unknown guidance,
completed-close semantics, sticky SELL, paper/portfolio read-only context,
fact-reference validation, prompt/context separation, APIs, and frontend runtime
validation/presentation. Completion requires backend checks, frontend lint/test/
build, one controlled browser acceptance, continuity updates, and
`docs/sprints/SPRINT19_COMPLETION_REPORT.md`.
