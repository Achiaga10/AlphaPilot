# Sprint 19 Completion Report — AlphaPilot AI Copilot Foundation

Date: 2026-08-29  
Branch: `feature/ai-copilot-foundation`  
Status: COMPLETE LOCALLY — Sprint 20 NOT STARTED

## Goal and result

Sprint 19 added a read-only grounded conversational layer over AlphaPilot's
deterministic backend and a deterministic Stop/Exit Guidance contract. The
governing rule is **AlphaPilot calculates/decides; AI explains**. The work adds
no strategy, active stop, broker connection, portfolio mutation, autonomous
decision, news, SQL/shell tool, or Sprint 20 functionality.

## Architecture

The final flow is typed and explicit:

`Copilot API → CopilotOrchestrator → CopilotContextAssembler → approved AlphaPilot reads → canonical facts → LLMProvider → validated answer + fact references`.

Approved reads are Position Intelligence, existing portfolio valuation and
stored monitoring, Paper Validation, and Stop/Exit Guidance. The context
assembler emits compact JSON-compatible facts; it never passes ORM objects,
repositories, sessions, secrets, SQL, shell, browser/network tools, or write
functions to a model. Position and portfolio requests are stateless.

LangChain and LangGraph were deliberately not used: this fixed read workflow
does not justify an agent framework. Direct Python interfaces keep the domain
boundary smaller and auditable while remaining adaptable to future tooling.

## Provider abstraction and configuration

`LLMProvider` accepts only a user question, fixed server grounding policy, and
canonical facts. `OllamaProvider` calls configured local `/api/chat` with JSON
output and exposes safe availability via `/api/tags`. `FakeLLMProvider` is
deterministic and records its inputs for tests. Automated tests and CI require
no Ollama process and make no real model/network call.

Configuration, documented in `backend/.env.example`, is:

- `AI_COPILOT_ENABLED=false` (default)
- `AI_PROVIDER=ollama`
- `OLLAMA_BASE_URL=http://127.0.0.1:11434`
- `OLLAMA_MODEL=` (user-selected; no model is pulled or hardcoded)
- `OLLAMA_TIMEOUT_SECONDS=30`

Disabled requests return `AI_COPILOT_DISABLED` without calling a provider.
Unavailable providers return `AI_PROVIDER_UNAVAILABLE`; malformed JSON,
grounding status, or nonexistent fact references return `AI_RESPONSE_INVALID`.
The safe status endpoint returns enabled/provider/model/availability without
secrets and does not probe a provider while disabled.

## APIs and contracts

- `GET /api/v1/ai/copilot/status`
- `POST /api/v1/ai/copilot/portfolio/{portfolio_id}/positions/{position_id}/ask`
- `POST /api/v1/ai/copilot/portfolio/{portfolio_id}/ask`

The position endpoint assembles Position Intelligence, Stop/Exit Guidance, and
all paper comparisons for the explicit selected position. The compact portfolio
endpoint reuses existing valuation and stored position monitoring to explain
equity/cash and HOLD/ATTENTION/SELL context; it does not scan or recommend new
stocks. Responses contain answer, scope, portfolio/position/ticker identity,
completed-session date, grounding status, authoritative fact references,
limitations, and safe provider/model metadata.

## Stop / Exit Guidance

Typed categories are `ACTIVE_POLICY`, `STRATEGY_EXIT_REFERENCE`,
`RESEARCH_ONLY`, `NONE`, and `UNAVAILABLE`, with typed EMA50/EMA20/SMA150
reference kinds. The design can later represent a governed active policy, but
none was introduced.

For `ema20-pullback-v1`:

- protective stop, trailing stop, and profit target are `NONE`;
- EMA50 is `EMA50_HARD_BREAKDOWN`, condition
  `COMPLETED_DAILY_CLOSE_BELOW`;
- EMA20 is `EMA20_CONDITIONAL_BREAKDOWN`, condition
  `COMPLETED_DAILY_CLOSE_BELOW_CONDITIONAL`, qualified by frozen HYBRID 2%; and
- stored sticky SELL remains visible.

For `micho-150-v1`:

- protective stop, trailing stop, and profit target are `NONE`; and
- SMA150 is the completed-daily-close breakdown reference. An intraday touch
  alone is explicitly not a SELL trigger.

EMA static 3× ATR14 and Micho static 1.5× ATR14 remain `RESEARCH_ONLY` /
`NOT_ACTIVE`. No current hypothetical price is calculated. Unknown-profile
positions return `UNAVAILABLE` with no EMA, SMA, ATR, stop, or SELL threshold.

For “Where should I put my stop?”, the grounded contract states that no active
protective stop exists, then may explain available backend strategy-exit
references, their hard/conditional and completed-close semantics, and that they
are not broker stop orders. It cannot turn a reference or research candidate
into a recommendation.

## Grounding, validation, and prompt injection

The fixed server policy declares AlphaPilot facts authoritative; forbids new
values, indicators, thresholds, strategies, stops and intraday semantics; keeps
NONE distinct from ACTIVE and RESEARCH_ONLY distinct from active; requires
unavailable facts to remain unavailable; and labels the question/context as
untrusted data. Stored free-text paper notes are not supplied to the provider.
The provider has no tool registry at all.

Every returned fact ID must exist in that exact assembled context. The UI shows
the narrative separately from “Based on AlphaPilot data,” including completed
session, typed labels, values, and limitations. Structured evidence remains
authoritative even though Sprint 19 intentionally does not implement a complex
semantic prose verifier.

## Frontend UX

Position Intelligence now includes **Ask AlphaPilot AI about {ticker}**. The
selected holding is explicit; the user can ask a stateless question; loading and
controlled unavailable/invalid states render safely. The answer, completed
session, and evidence render separately. `NONE`, strategy references, and
research-only facts remain visibly distinct. React performs no EMA/SMA/ATR,
P&L, basis-point, stop, portfolio-value, or decision calculation and sends no
mutation or broker request from Copilot.

## Files

Created backend:

- `backend/src/alphapilot/copilot/__init__.py`
- `backend/src/alphapilot/copilot/context.py`
- `backend/src/alphapilot/copilot/orchestrator.py`
- `backend/src/alphapilot/copilot/provider.py`
- `backend/src/alphapilot/portfolio/stop_exit_guidance.py`
- `backend/src/alphapilot/schemas/copilot.py`
- `backend/src/alphapilot/api/routes/copilot.py`
- `backend/tests/portfolio/test_copilot.py`

Modified backend: config/env example, API router, and the existing Position
Intelligence fixture (only to include already-authoritative EMA50/strong-trend
facts). No migration was needed because Copilot is stateless/read-only.

Modified frontend: portfolio types/API/hooks, Position Intelligence panel,
Portfolio Page tests, and MSW server. Created controlled acceptance script
`frontend/scripts/sprint19-copilot-smoke.mjs`. Continuity docs and Sprint 19
plan/report were created/updated.

## Testing and acceptance

Focused backend after final audit:

```powershell
cd backend
$env:DEBUG='false'
uv run ruff check src/alphapilot/api/routes/copilot.py tests/portfolio/test_copilot.py
uv run mypy src
uv run pytest tests/portfolio/test_copilot.py -q
```

Result: Ruff PASS, mypy PASS, **10 passed**. Earlier combined Copilot/Position
Intelligence focused result: **15 passed**.

Full backend:

```powershell
$env:DEBUG='false'
.\run_checks.ps1
```

Result: Ruff PASS; format PASS (238 files unchanged); mypy PASS across 164
source files; pytest **320 passed in 39.15s**; All checks passed.

Frontend:

```powershell
npm run lint
npm test -- --run
npm run build
```

Result: ESLint PASS; **16 files / 68 tests passed**; TypeScript/Vite production
build PASS (105 modules, official logo bundled).

Controlled browser acceptance:

```powershell
npx vite preview --host 127.0.0.1
node scripts/sprint19-copilot-smoke.mjs
```

Headless Edge at 1440×1000 used controlled API facts and exactly one fake
Copilot response. AAPL displayed protective stop NONE, EMA50 `$19.16` hard
completed-close reference, EMA20 `$20.10` conditional reference, no “Stop Loss”
mislabel, one Copilot call, and zero provider/broker calls: **PASS**.

Pure backend controlled acceptance also passed for Micho `$19.16` SMA150 with
completed-close/intraday distinction; unknown profile with no fabricated level;
exact Paper reference/fill/difference/P&L context; invalid fact references;
disabled/unavailable provider; prompt injection separation; portfolio
non-mutation; and exact EMA hard/conditional semantics. Existing full suites
cover Paper Decimal/accounting, sticky SELL, Position Intelligence, multi-action
plans, scheduler, Strategy Profiles/Lab, and Sprint 13 reproducibility.

## Regression guarantees

EMA20 Pullback, HYBRID 2%, Micho BOTH/SMA150, RS20, sizing/risk, T+1 execution,
Sprint 12 conclusions, Strategy Profiles, Strategy Lab, Sprint 13 data replay,
Sprint 17 monitoring/sticky SELL, Sprint 18 Position Intelligence/Paper
Validation/timezone behavior, and same-plan multi-action behavior are unchanged.
No active protective/trailing/profit policy exists. No Alpaca Trading API,
broker order, portfolio mutation, SQL/shell access, web/news source, LangChain,
LangGraph, conversation persistence, or real LLM call in CI was added.

## What Sprint 19 proved and did not prove

It proved deterministic AlphaPilot facts can be assembled into a compact,
read-only, provider-independent grounded context; exact exit references and
paper evidence can be explained with authoritative citations; malformed facts
fail closed; and the UI can present this safely without domain calculations.

It did not prove any model's financial judgment, prose factuality beyond the
validated references, production prompt-injection immunity, Ollama deployment
availability/quality, multi-user privacy/authentication, conversation memory,
live/intraday accuracy, broker reconciliation, or trade profitability.

Biggest remaining limitation: a configured local model can still produce poor
narrative prose; Sprint 19 validates grounding references and preserves
authoritative facts but intentionally does not implement a semantic claim
verifier. Data remains completed-daily and paper/broker state remains manually
recorded, with no authenticated account ownership.

Recommended Sprint 20 direction only: review richer multi-turn Copilot and
grounded response evaluation/observability first; consider LangGraph only if a
future multi-tool workflow genuinely requires it. Separately govern any News
Intelligence or validated protective-stop research. Sprint 20 was not started.

## Git handoff

All Sprint 19 changes remain local and uncommitted on
`feature/ai-copilot-foundation`. No commit, push, PR, merge, force-push, or tag
operation was performed. Final status contains **13 modified tracked files** and
**11 untracked Sprint 19 files**. The tracked `git diff --stat` is **13 files
changed, 155 insertions, 16 deletions**; untracked files are not included in
that stat. `git diff --check` passed with only expected Windows LF/CRLF notices.

Untracked files are the Copilot route; four-file Copilot package; Stop/Exit
Guidance service; Copilot schemas; Copilot tests; Sprint 19 plan/report; and the
controlled browser smoke script. Every listed file is ready for user review.

Recommended commit message:

`feat(ai): add grounded read-only AlphaPilot Copilot`
