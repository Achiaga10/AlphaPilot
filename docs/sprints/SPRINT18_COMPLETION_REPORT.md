# AlphaPilot Sprint 18 Completion Report

Date: 2026-08-28  
Branch: `feature/position-intelligence-paper-validation`  
Status: COMPLETE LOCALLY — Sprint 19 NOT STARTED

## Goal and result

Sprint 18 created a deterministic backend Position Intelligence contract, a
manual Alpaca Paper forward-validation journal, and structured Manage Portfolio
reason codes. It added no AI/LLM, broker connection, order submission,
automatic trade, strategy/profile change, or active stop/trailing/profit policy.

## Position Intelligence architecture and API

`PositionIntelligenceService.get_position_intelligence()` is a side-effect-free
read boundary over persistent portfolio/position identity, the resolved stored
Strategy Profile, backend completed-session valuation, stored monitoring
history, sticky exit state, trade events, and reconciliation events. FastAPI
only validates/serializes it at:

`GET /api/v1/portfolio/{portfolio_id}/positions/{position_id}/intelligence`

The typed response includes portfolio ID/revision; position/company/ticker,
OPEN/CLOSED state and provenance; quantity, entry day/price, average cost and
cost basis; stored strategy/profile ID/version/snapshot, selection and entry
decision/reason; completed day/close, market value, realized/unrealized P&L;
monitoring readiness/status/reason/session/indicators; previous state/latest
transition; sticky trigger facts; and audit-event counts.

Known EMA and Micho profile identities resolve through the unchanged Strategy
Profile registry. Unknown/unsupported `LEGACY_IMPORTED` and `MANUAL_EXTERNAL`
provenance returns `strategy_guidance_available=false`, an explicit unavailable
reason, and no fabricated strategy, HOLD/ATTENTION/SELL, exit explanation, or
indicator facts. Missing historical entry indicators are not reconstructed.

The active exit policy is the stored profile rule (EMA HYBRID 2% or Micho close
below SMA150). Protective stop, trailing stop, and profit target remain `NONE`
for valid normal profiles. The Sprint 12 static 3× ATR14 EMA and 1.5× ATR14
Micho candidates are separate `research_only_stop_candidate` facts with
`NOT_ACTIVE`; no hypothetical live protection is implied or calculated.

Deterministic templates explain supported stored reasons (for example EMA20
held, HYBRID strong-trend exception, EMA50 breakdown, SMA150 recovery, and
SMA150 breakdown). Structured fields remain authoritative. “What changed”
includes entry-reference versus current close, current/previous monitoring,
latest transition, sticky trigger, and actual stored event counts.

## Paper Validation architecture and contract

Migration `a18c4d9e2f70` adds `paper_validation_records`. V1 stores one immutable
aggregated entry and permits one one-time full aggregated exit; there is no
generic update/delete or partial-fill/tax-lot/order-state engine. The source is
always exactly `ALPACA_PAPER_MANUAL`. Numeric financial values use
`Numeric(20,4)` and backend `Decimal` arithmetic.

APIs:

- `POST /portfolio/{portfolio_id}/positions/{position_id}/paper-validations`
- `GET /portfolio/{portfolio_id}/paper-validations`
- `GET /portfolio/{portfolio_id}/positions/{position_id}/paper-validations`
- `POST /portfolio/{portfolio_id}/paper-validations/{validation_id}/exit`

The entry request contains only actual whole-share quantity, average fill,
execution timestamp, and optional note. The backend captures ticker,
provenance, stored strategy/profile/version, decision/reason, recommendation
day, planned quantity, and reference price where AlphaPilot provenance supports
them. External unknown-profile positions remain valid but planned/reference
comparison fields are null rather than invented.

Derived entry facts are actual minus reference price, basis points as
`difference/reference × 10,000`, and actual minus planned quantity. A closed
record derives paper entry/exit values, gross dollar P&L and gross return from
the actual fills. If the stored position has a sticky AlphaPilot SELL, exit
recording captures trigger day/reason and that monitoring snapshot close. An
early user exit stores no fake AlphaPilot trigger.

Controlled acceptance recorded 10 AAPL shares at $100.25 against AlphaPilot’s
10 at $100 reference: +$0.25/share and +25 bps. A full manual exit at $110
produced backend gross paper P&L of exactly $97.50 and gross return based on the
$100.25 actual entry. Recording entry/exit left Research Portfolio cash,
quantity, revision, monitoring, and strategy facts unchanged. Paper validation
is observational forward evidence, not portfolio authority, broker execution,
or a performance conclusion.

## Structured reconciliation reasons

The existing additive audit table now has nullable `reason_code` and `note`.
Legacy `reason` remains unchanged/readable; direct legacy service calls remain
compatible and produce a null code. New API requests require a supported enum.

- Cash: `EXTERNAL_DEPOSIT`, `EXTERNAL_WITHDRAWAL`,
  `PAPER_ACCOUNT_RECONCILIATION`, `CORRECTION`, `OTHER`.
- External position: `ALPACA_PAPER_TRADE`, `EXTERNAL_BROKER_TRADE`,
  `INITIAL_PORTFOLIO_IMPORT`, `CORRECTION`, `OTHER`.
- Position reconciliation: `PAPER_ACCOUNT_RECONCILIATION`,
  `QUANTITY_CORRECTION`, `COST_BASIS_CORRECTION`,
  `ENTRY_DATE_CORRECTION`, `OTHER`.

Deposit/withdrawal direction is validated. Optional human notes are stored
separately (500-character maximum). Arbitrary machine reason codes return 422.

## Frontend

Each backend-valued holding now offers **Why this position?** and opens a compact
Position Intelligence panel with Entry, Current state, Exit & risk, What
changed, and Forward paper validation sections. React formats but does not
calculate valuation, P&L, monitoring, indicator, policy, fill comparison, or
paper P&L facts. Unknown provenance visibly says guidance is unavailable and
does not fake HOLD/SELL. Research-only stops visibly say `NOT ACTIVE`.

The paper UI displays read-only AlphaPilot reference facts, accepts only manual
entry/exit facts, identifies the record as forward paper validation and
“manually recorded, not broker-connected,” and never uses connected-account
wording. Manage Portfolio now uses three reason dropdowns plus optional Note.

Frontend parsing validates the new response boundaries at runtime. A malformed
Position Intelligence or paper payload is rejected by the existing typed JSON
client rather than rendered as trusted data.

## Database and files

Migration revision: `a18c4d9e2f70`, down revision `f41c8e2067ab`. It is
additive, asyncpg/PostgreSQL compatible, has FKs/checks/indexes, changes no
DailyCandle/dataset/Profile table, and reached head on the dedicated test and
development databases.

Created backend files:

- `backend/migrations/versions/a18c4d9e2f70_add_position_intelligence_paper_validation.py`
- `backend/src/alphapilot/services/position_intelligence.py`
- `backend/src/alphapilot/services/paper_validation.py`
- `backend/tests/portfolio/test_position_intelligence.py`

Modified backend files: portfolio route/schema, research portfolio model/model
exports/repository/service. Created frontend file:
`frontend/src/features/portfolio/PositionIntelligencePanel.tsx`. Modified
frontend portfolio API/types/hooks, portfolio panel, Manage Portfolio, test
server, and Portfolio page test. Documentation created/updated:
`SPRINT18_PLAN.md`, this report, `AGENTS.md`, `PROJECT_STATE.md`, and
`DECISIONS.md`. The regression acceptance also created
`frontend/scripts/sprint18-multi-action-smoke.mjs`.

## Test and acceptance evidence

Focused backend command covered intelligence, paper, reconciliation,
monitoring, scheduler, portfolio API, and Scanner: **38 passed**. A smaller
intelligence/reconciliation group passed **21 tests**. Coverage includes EMA
profile facts, unknown-profile safety, completed valuation, monitoring and
indicators, inactive policies, side-effect-free reads, exact Decimal entry/exit
calculations, duplicate close rejection, portfolio separation, structured
reasons/notes/direction, and typed API validation.

Final backend command:

```powershell
cd backend
$env:DEBUG='false'
.\run_checks.ps1
```

Result: Ruff PASS; Ruff format PASS (230 files unchanged); mypy PASS across 157
source files; pytest **309 passed in 39.73s**; overall **All checks passed**.

Final frontend commands:

```powershell
cd frontend
npm run lint
npm test -- --run --reporter=dot
npm run build
```

Result: ESLint PASS; Vitest **16 files / 66 tests passed** with no unmatched
request warnings on the final run; TypeScript/Vite build PASS, 105 modules,
official AlphaPilot logo bundled.

Controlled headless Edge acceptance at 1440×1000 used the real built UI and
existing local persistent portfolio with controlled responses only for the two
new read contracts. It opened **Why this position?**, rendered Position
Intelligence, explicit unknown-profile safety and Forward paper labeling, and
observed no Alpaca/broker/order request. PASS. The known EMA and exact paper
entry/exit cases are covered end to end by the green backend/API and frontend
tests; no external provider was called.

## Multi-Action Portfolio Plan Regression Fix

Root cause: Sprint 16 revision safety correctly bound every mutation to an exact
current portfolio revision, but the frontend treated any difference between the
original plan revision and the refreshed portfolio revision as making every
remaining plan candidate unusable. It also sent the original plan revision for
later previews/applies. Therefore the first successful action changed revision
N to N+1 and the browser blocked all remaining same-plan recommendations before
fresh backend validation could occur.

Final semantics distinguish the historical plan snapshot from an action. The
plan’s analysis metrics remain the original snapshot and applied candidates are
marked Applied. A remaining candidate is only an input to a new action request.
The browser refetches the persistent portfolio and sends its exact current
revision. The backend reloads authoritative cash/positions for that revision,
resolves the exact Strategy Profile, and revalidates already-held state, maximum
positions, cash, position weight, reserve, sector and modeled-risk constraints.
Browser cash/positions remain absent from persistent requests. A genuinely
stale expected **current** revision still returns HTTP 409; profile mismatches
still return 422.

Untouched plan quantities are now recalculated against current capacity. The
backend caps the current recommendation by original shares, current cash,
position weight, sector capacity, and—when applicable—cash reserve and modeled
risk capacity. `CURRENT_REVALIDATED_RECOMMENDATION` explicitly identifies a
changed default (focused acceptance reduced 100 original shares to 50). An
explicit user quantity remains `USER_QUANTITY_OVERRIDE` and must pass all
current constraints; the old 100-share quantity in that reduced-capacity case
was rejected with `SECTOR_LIMIT`, never silently applied. Zero capacity retains
the specific rejection reason rather than inventing shares.

Backend regressions prove two persistent candidates apply from one plan at
revisions 0→1→2, the second preview reads updated cash, old revision 0 remains
rejected, already-held/max-position/insufficient-cash and user override rules
remain enforced, and Strategy Profile protection remains green. Focused action/
API result: **17 passed**.

Frontend regressions prove the plan remains visible, candidate one becomes
Applied, authoritative portfolio revision refetches, candidate two remains
Preview/Apply capable, preview requests use revisions `[0, 1]`, no Regenerate
warning appears solely because the first action succeeded, and true plan-input
changes still use the unchanged stale-plan mechanism. Current backend rejection
facts continue to render in the preview dialog and disable Apply. Position
Intelligence/paper-validation tests remained green. Focused frontend result:
**2 files / 16 tests passed**.

Controlled headless Edge acceptance generated one plan with AAPL and MSFT,
applied AAPL, freshly previewed MSFT against revision 1, then applied MSFT to
revision 2 without regenerating. Captured result:
`previewRevisions=[0,1]`, two distinct applied action IDs,
`fullRegenerationRequired=false`, PASS. The controlled run made no broker or
provider call.

Migration commands used the verified dedicated test URL (required `test` in
the target name) before upgrading and also applied the additive revision to the
development database. CI was inspected and unchanged: it creates clean dev/test
PostgreSQL databases, upgrades both to head, runs backend Ruff/format/mypy/
pytest and frontend lint/test/build, leaves the scheduler disabled by default,
provides no broker credentials, and makes no Alpaca Trading API call.

## Regression guarantees

EMA HYBRID 2%, Micho BOTH/SMA150, HOLD/ATTENTION/SELL classifications, sticky
SELL, completed-session valuation, the 16:30 New York scheduler, Strategy
Profiles, Strategy Lab, Sprint 13 reproducibility, Scanner/Evaluate identity,
portfolio accounting/revisions, sizing/risk, and T+1 research semantics did not
change. All corresponding suites passed within the 309-test gate. No stop,
trailing stop, or profit target became active. Paper facts do not feed strategy,
monitoring, ranking, sizing, plans, or portfolio mutations.

No Alpaca Trading API was authenticated or called; no keys, account/orders/
positions, broker synchronization, order submission/cancel, or automatic
reconciliation was added. No OpenAI SDK, prompt, chat endpoint, LLM, LangChain,
LangGraph, agent, or Sprint 19 code exists.

## What Sprint 18 proved and did not prove

It proved that one typed backend endpoint can structurally explain a persistent
position using stored provenance, valuation, monitoring, exit, policy and audit
facts; that missing provenance stays explicit; and that manual Alpaca Paper
entry/exit evidence can be compared deterministically without compromising
portfolio authority.

It did not prove strategy profitability, execution quality, live-broker
accuracy, market impact/latency/fees/taxes/dividends, partial-fill accounting,
multi-user security, authenticated account ownership, broker synchronization,
or AI-grounding quality in production.

Biggest remaining limitation: paper fills and portfolio state are manually
entered/separately reconciled, with one aggregate entry/full exit and no
authenticated live broker state. Scheduler status remains process-local and
market intelligence remains completed-daily-session rather than live/intraday.

Recommended Sprint 19 direction only: an AlphaPilot AI Copilot foundation whose
tools call deterministic services such as `get_position_intelligence`, profile,
portfolio context, monitoring, and paper-validation reads. Require grounded
citations to structured backend facts, explicit unavailable states, and no
trade execution. Sprint 19 was not started.

## Exact material commands

```powershell
git status --short
git branch --show-current
git log --oneline -10
git checkout main
git pull
git checkout -b feature/position-intelligence-paper-validation

cd backend
$env:DEBUG='false'
# TEST_DATABASE_URL was verified distinct and visibly a test database
uv run alembic upgrade head
uv run alembic current
uv run pytest tests/portfolio/test_position_intelligence.py `
  tests/portfolio/test_research_portfolio.py `
  tests/portfolio/test_position_monitoring.py `
  tests/services/test_daily_market_scheduler.py `
  tests/api/test_portfolio_decisions.py tests/api/test_scanner.py -q
.\run_checks.ps1

cd ..\frontend
npm run lint
npm test -- --run --reporter=dot
npm run build
node scripts/sprint18-multi-action-smoke.mjs
# controlled local headless-Edge acceptances; no provider/broker call

git diff --check
git diff --stat
git status --short
```

## Git handoff

The working tree intentionally contains only local Sprint 18 changes on
`feature/position-intelligence-paper-validation`. No commit, push, PR, merge,
force-push, or tag operation was performed. The final `git status` and diff stat
are: 24 modified tracked files and eight untracked Sprint 18 files. Tracked diff
stat is **24 files changed, 962 insertions, 65 deletions**; untracked files are
not included by `git diff --stat`. `git diff --check` passed with only expected
Windows LF-to-CRLF working-copy notices.

Untracked files:

- `backend/migrations/versions/a18c4d9e2f70_add_position_intelligence_paper_validation.py`
- `backend/src/alphapilot/services/paper_validation.py`
- `backend/src/alphapilot/services/position_intelligence.py`
- `backend/tests/portfolio/test_position_intelligence.py`
- `docs/sprints/SPRINT18_COMPLETION_REPORT.md`
- `docs/sprints/SPRINT18_PLAN.md`
- `frontend/scripts/sprint18-multi-action-smoke.mjs`
- `frontend/src/features/portfolio/PositionIntelligencePanel.tsx`

All modified and untracked files listed by final Git status are ready for user
review and commit.

Recommended commit message:

`feat(portfolio): add position intelligence and paper validation`
