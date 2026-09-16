# AlphaPilot — Codex Instructions

## Project

AlphaPilot is an async Python/FastAPI stock-trading research backend.

Primary market universe:
- S&P 500
- Custom ticker analysis is also allowed

The project currently focuses on deterministic technical strategies,
historical backtesting, strategy validation, and eventually portfolio-level
decision making.

Before doing any work, always read:

1. AGENTS.md
2. docs/PROJECT_STATE.md
3. docs/DECISIONS.md

These three files are the source of continuity for the project.

## Current Phase

The project is currently in:

Sprint 28 — Production Operations, Health & Alerting
(IMPLEMENTED LOCALLY — DETERMINISTIC OBSERVATION / ZERO TRADING AUTHORITY)

Sprint 28 adds durable operational incidents and audit events, deterministic
INFO/WARNING/CRITICAL severity, OPEN/ACKNOWLEDGED/RESOLVED lifecycle, stable active
deduplication with recurrence history, a backend-owned HEALTHY/ATTENTION/DEGRADED
summary, trading-session-aware manual-action deadlines, fresh-snapshot-only relevant-
Micho position drift, startup self-checks, a separate contained five-minute monitor,
typed APIs and a Dashboard Operations Center. It is in-app only and cannot submit,
cancel, replace or close broker orders or change Micho decisions, Forward economics,
Portfolio Plan, EMA20, News, ResearchPortfolio or Paper. Migration `c28a0f1b2d3e`
descends from `fa4edd0b0ef8` and was verified only against `TEST_DATABASE_URL`. See
`docs/sprints/SPRINT_28_PRODUCTION_OPERATIONS.md`. Sprint 29 is not started.

Sprint 27 — Alpaca Read-Only Broker Synchronization
(IMPLEMENTED LOCALLY — BROKER OBSERVATION / ZERO TRADING AUTHORITY)

Sprint 27 adds an optional, disabled-by-default Alpaca observation domain. The
adapter exposes GET-only account, position, order, fill-activity and clock reads;
PAPER is the default and credentials remain backend-only. Durable sync runs,
snapshots, broker-native order/execution deduplication, conservative Micho Forward
matching, audited manual link/unlink/ignore, conflict preservation and separate
five-minute scheduling are implemented. Broker evidence may populate the external
execution journal but can never submit/cancel/replace/close an Alpaca order or
change Micho decisions, Forward virtual economics, Portfolio Plan, EMA20, News,
ResearchPortfolio or Paper. Migration `fa4edd0b0ef8` descends from
`f650e3a238a0` and was verified only against `TEST_DATABASE_URL`. See
`docs/sprints/SPRINT_27_ALPACA_READ_ONLY_SYNC.md`. Sprint 28 is not started.

Sprint 26 — Forward Operations Console & Manual Broker Reconciliation
(PRESERVED BASELINE — OBSERVATIONAL USER-RECORDED EXECUTION)

Sprint 26 adds one durable manual external-execution case per Micho Forward order,
partial user-recorded fills, skip and audited void/correct workflows, a pre-execution
BUY/SELL action queue, backend Decimal reconciliation and complete-only recorded-
execution P&L. The journal is observational: it cannot change Micho decisions,
Forward virtual cash, positions, fills, exits, allocation or P&L. There is no Alpaca
order submission or read/sync. EMA20 remains recommendation-only and News remains
advisory-only. The separate migration is `f650e3a238a0`, descended from
`e9b2bc954dea`; it was verified only against TEST_DATABASE_URL. See
`docs/sprints/SPRINT_26_MANUAL_EXECUTION_RECONCILIATION.md`. Sprint 27 is not started.

Sprint 25 — Micho Forward Portfolio Operations & Trade Lifecycle
(PRESERVED BASELINE — AUTOMATIC VIRTUAL EXECUTION / MANUAL EXTERNAL BROKER)

Sprint 25 adds a dedicated persistent Forward Portfolio for the frozen
`micho-150-v1` version 1 profile. It processes stored completed sessions
sequentially, models final-actionable Micho entries and exits at the next stored
session open with the existing 5 bps adverse friction convention, marks open
positions at completed closes, and persists exact cash/equity, orders, positions,
trades, events, cycles and analytics. The hourly worker runs immediately at app
startup and uses PostgreSQL transaction advisory locking plus durable unique
constraints. It never calls a broker API.

Forward execution is Micho-only. EMA20 Portfolio Plan approvals, including
`USER_MANUAL` / `MANUAL STOP REQUIRED`, remain unchanged but have separate typed
Forward eligibility `false` / `SPRINT25_MICHO_ONLY`. News remains advisory-only.
ResearchPortfolio, Paper, News evidence, Alpaca, frozen strategies and historical
research conclusions are not mutated. Migration `e9b2bc954dea` owns the separate
Forward domain. See `docs/sprints/SPRINT_25_FORWARD_PORTFOLIO.md`.

News Intelligence is advisory-only for both Micho and EMA20 Pullback. It has no
authority over signal, allocation, loss control, final actionability, counts,
profiles, plans, HOLD, SELL or EXIT_REQUIRED. Persisted News evidence and explicit
bounded refresh remain available, but plan generation never refreshes News to
establish approval. Provider/read/parse failures attach unavailable advisory
context and cannot fail either supported strategy's Profile or Portfolio Plan.

`APPROVED BUY` means exactly `final_action=BUY` and
`is_final_actionable=true`. EMA20 Pullback may produce an approved BUY without an
approved automatic loss-control policy only after every other deterministic hard
gate passes. Such a decision is explicitly `loss_control_source=USER_MANUAL` and
`manual_stop_required=true`; its system stop/boundary remains null and the user is
responsible for choosing and placing the protective stop. This exception is EMA20-
only. Micho retains approved system loss control, and a future genuine approved
EMA20 system policy remains authoritative. No fallback stop was introduced.

Final read-only acceptance for completed session 2026-09-09: Micho produced 11
technical BUYs and 10 approved BUYs; TXN stopped at portfolio capacity. EMA20
produced 45 technical BUYs, 33 entry-safety passes and 10 approved BUYs, all marked
USER_MANUAL / MANUAL STOP REQUIRED with null automatic stops. The remaining EMA20
BUYs had 12 entry-safety blockers and 23 portfolio-capacity blockers. News blocked
zero candidates for both. Focused backend: 95 passed; full backend: Ruff/format,
mypy 199 source files and 656 tests passed. Frontend: focused 24 passed; lint, 100
tests and production build passed. Controlled Edge acceptance passed for both
profiles and verified no Portfolio, Paper or broker mutation. See
`docs/hotfixes/EMA20_MANUAL_STOP_APPROVED_BUY.md`. That prior acceptance remains
preserved.

Sprint 11 and all 11B/11C/11D hardening are complete and merged. Sprint 12 and
Sprint 13 through Sprint 15 are complete, reviewed, and merged. Sprint 16 is
complete, reviewed, and merged. Sprint 17 is complete, reviewed, and merged.
Sprint 18 and Sprint 19 are complete and merged. Sprint 20 is complete and merged; it
found no approved protective-stop winner. Sprint 21 is complete locally on
`feature/daily-portfolio-manager`; it added product orchestration only, with no new
research, strategy, broker integration, or autonomous trading.

Sprint 21 through Sprint 23 are merged. Sprint 22 added read-only ephemeral live
monitoring and deterministic indicator facts without changing completed-session strategy
semantics. Sprint 23 added immutable forward Paper evidence and backend-owned
execution/outcome analytics. Sprint 24 is complete locally: Adanos is the persisted
primary aggregate News sentiment source, Finnhub remains attributable/hard-event evidence,
Gemini is targeted deep interpretation only, Ollama is disabled, and the deterministic
backend remains the sole financial decision authority. At that point Sprint 25 had not started.
The focused `fix/ema20-entry-safety` hotfix is complete locally and adds fresh backend-owned EMA20 entry
revalidation without changing the frozen historical strategy. A technical EMA BUY
signal is not sufficient for actionability: current entry price must be at/below or
within the existing 1% upper proximity boundary of the fixed completed signal-session
EMA20. Extended or unavailable/stale geometry fails closed. Ranking and News cannot
override this gate. At that point Sprint 25 had not started.

The focused `fix/portfolio-plan-consistency-ux` hotfix is complete locally. An
approved BUY is now one final actionable BUY after entry safety, execution
readiness, News, user preference, allocation, and every other hard gate. Persistent
per-portfolio ticker exclusions are reversible, run before allocation and targeted
BUY News work, and never delete historical evidence. Selling does not automatically
exclude a ticker. Dashboard action surfaces are compact and priority-oriented, while
Forward Paper evidence is explicitly separate from current ResearchPortfolio state.

The subsequent BUY-funnel/News-gate audit is complete locally on the same branch.
The backend now assigns every technical BUY exactly one authoritative first blocker,
automatically refreshes only the bounded final News shortlist, and implements the
approved Option A semantics: sufficient current non-adverse Adanos aggregate evidence
can continue without routine Gemini completion; adverse or weak aggregate evidence
requires bounded attributable review; missing/stale evidence remains explicit.
Candidates stopped by EMA20 entry safety, user preference, loss-control readiness, or
portfolio constraints consume no candidate News quota. No threshold, strategy,
loss-control, or SELL-safety rule changed. At that point Sprint 25 had not started.

The final BUY-semantics follow-up is complete locally. Technical signal, intermediate
candidate allocation, and final portfolio action are distinct typed facts. A BUY is
approved only when `final_action=BUY` and `is_final_actionable=true`; terminal blockers
replace stale approval wording while allocation evidence remains auditable. Summary
counts, UI filters/rendering, and the apply service all use that invariant. Sprint 25
had not started at that point.

The focused `research/ema20-loss-control` study is complete locally. Its candidate
space and gates were frozen before results. The one new fixed signal-day EMA50
protective boundary failed development because entry-risk P90 was 11.06% (10% cap)
and maximum was 20.64% (20% cap), so validation and folds were not opened. The exact
prior ATR14 2× candidate was reused rather than rerun and retains its Sprint 20
`NO_WINNER` result. The outcome is `NO_APPROVED_EMA20_LOSS_CONTROL_POLICY`; no
Strategy Profile, ExecutionReadiness, Portfolio Plan, UI, Paper, or broker behavior
changed. At that point Sprint 25 had not started.

Final Sprint 24 hardening makes AI-only SEVERE insufficient for exit, requires
PRIMARY-source deterministic hard-event confirmation, and requires current persisted
provider/classifier coverage before a new BUY can be actionable. Candidate refresh is
explicit and capped at 25 tickers; Ollama remains disabled by default.

The new `achia-strat-ema20-v1` hypothesis is separate from EMA20 Pullback and Micho.
Its protocol is frozen in `docs/research/ACHIA_STRAT_EMA20_PROTOCOL.md`: completed
EMA20 > EMA50, inclusive close zone 90%–101% of EMA20, next-open entry, static
actual-fill minus signal ATR14 minus 1% actual-fill stop active on entry day, and
strict completed-close-below-EMA20 next-open exit. No sweep or production registry
change is authorized. Development gates govern access to validation/folds.
Development returned 15.46% with 40.95% drawdown, Sharpe 0.3080, Calmar 0.1066,
negative pooled independent expectancy, and maximum planned stop distance 26.30%.
It is REJECTED; validation/folds were not opened. A reporting-only Decimal-order
correction restored true 100% boundary coverage without changing performance or
classification. See `docs/research/ACHIA_STRAT_EMA20_RESULTS.md`. No production
activation, parameter tuning, portfolio/Paper writes, or broker action occurred.

The latest Shauli request explicitly authorizes DAILY/LONG_ONLY research and
supplies the numeric V1 rules, superseding the earlier broad definition blockers.
`docs/research/SHAULI_STRAT_PROTOCOL.md` freezes those rules and the now-approved
`AMBIGUOUS_ENTRY_TARGET_ORDER` no-trade exclusion. The isolated research strategy,
pending-limit adapter and deterministic tests are complete. The verified snapshot
Development run prepared 497 tickers (five known absent-history constituents):
7,895 setups, 1,353 sweeps, 104 structural confirmations, zero displacement/POI
plans or trades. All swept setups invalidated before displacement. Final equity
remained $100,000; this is no exposure, not evidence of profitable risk control.
Classification is REJECTED; validation/folds were not opened. The continuous HH/HL
gate and strictly post-sweep three-bar FVG sequence prevent progression in this
frozen implementation. No rule was relaxed or rerun after results. Full backend
gate: 592 tests passed, Ruff/format passed, mypy 199 source files. Handoff:
`docs/research/SHAULI_STRAT_RESULTS.md`. No operational activation or application-
data mutation occurred. Achia remains separately rejected; at that point Sprint 25
had not started.

## Development Environment

The approved `AMBIGUOUS_ENTRY_TARGET_ORDER` no-trade exclusion is frozen and
tested. Development failed mandatory gates and is complete; do not reopen
validation/folds, tune V1, or start another experiment without a new user request.
No operational activation or Portfolio Plan/Paper/broker mutation is authorized.

Backend directory:
backend/

Primary source:
backend/src/alphapilot/

Tests:
backend/tests/

Backtest reports:
backend/backtest_reports/

Environment:
- Windows 11
- PowerShell
- Python 3.12
- uv
- FastAPI
- PostgreSQL
- SQLAlchemy async
- pytest
- Ruff
- mypy

Use uv.

Do not introduce a separate pip workflow.

Examples:

uv run pytest
uv run alphapilot

Final local validation command:

.\run_checks.ps1

## General Coding Rules

Prefer small, targeted changes.

Do not perform unrelated refactors.

Do not rename working public interfaces unless required.

Inspect the existing implementation before modifying it.

Do not recreate files based on assumptions if the real implementation is available.

Do not change strategy behavior while fixing infrastructure unless absolutely required.

Do not introduce unrelated backend or research work during Sprint 11D.

## Testing Rules

When modifying code:

1. Run focused tests for the changed behavior.
2. Run:

.\run_checks.ps1

Do not weaken tests just to make implementation pass.

Important backtesting guarantees:

- no lookahead
- signal on trading day T executes at next trading day's OPEN
- last-day signal cannot execute
- BUY while already holding does not open another position
- SELL while flat does nothing
- commissions/slippage remain consistent
- trade diagnostics must point to the signal that actually opened the position

## Git Rules — IMPORTANT

The USER controls Git publishing.

You MUST NOT:
- run git push
- push any branch
- push tags
- open a remote PR
- merge a PR
- merge into main
- force-push
- rewrite remote history

The user explicitly wants to perform Git Push personally.

Do not automatically commit either.

You may inspect Git using read-only commands such as:

git status
git diff
git branch
git log

At the end of your work, tell the user:
- which files changed
- which files are untracked
- which files are ready to commit
- a recommended commit message

Then STOP.

The user will perform commit/push actions unless they explicitly instruct otherwise.

## Database Safety

Development and test databases are separate.

Never perform destructive database operations without confirming the target.

Never allow tests to operate against the development database.

Do not run destructive SQL such as:
- DROP DATABASE
- DROP TABLE
- TRUNCATE
- schema reset

unless the task explicitly requires it and the database target has been verified.

Do not create unrelated Alembic migrations.

## Secrets

Never expose, print, commit, or copy values from .env.

Sensitive values include:
- database credentials
- Polygon key
- Finnhub key
- Alpaca API key
- Alpaca secret
- private User-Agent contact information

Use the existing configuration system.

## Strategy Research Discipline

Strategies must remain deterministic during validation.

Do not add:
- AI judgment
- news sentiment
- discretionary chart analysis
- future information

to Sprint 6 strategy backtests.

Development/tuning data and validation data must remain conceptually separate.

Never tune a parameter on validation data and then describe that same result as untouched validation.

## EMA20 Pullback

Current strategy family supports:
- EMA20 exit
- EMA50 exit
- HYBRID exit

HYBRID threshold selected during development:

2%

This threshold is frozen.

Do not retune it during Sprint 6.

Do not automatically change Scanner default behavior based solely on single-stock backtests.

## Micho 150

Micho 150 is currently a deterministic mechanical V1 strategy.

It includes:
- SMA150
- SMA150 trend filter
- breakout entry
- bounce entry
- close below SMA150 exit

Do not add during the current experiment:
- volume filters
- news
- AI
- discretionary chart patterns
- stop-loss experiments
- different SMA lengths
- different touch zones
- different slope settings

Current entry modes:
- both
- breakout-only
- bounce-only

both preserves original Micho V1 behavior.

The other two modes exist only to isolate entry behavior.

A Breakout day blocked in bounce-only must not be reclassified as a Bounce.

## Backtesting Research Caveat

Current historical S&P 500 experiments use the CURRENT constituent list.

Therefore historical results contain:

Survivorship Bias

Every final interpretation must mention this.

## Sprint 24 Task

Build durable News Intelligence and a versioned deterministic News Decision Overlay.
Preserve base strategy decisions separately. AI may classify financial/business impact
through strict typed evidence but may never issue BUY/SELL/HOLD or portfolio instructions.
Positive news cannot create a BUY or cancel a technical SELL. Only narrow, fresh, direct,
strong-source severe evidence may produce a backend-owned News risk exit.

## End-of-Task Rule

After creating `docs/sprints/SPRINT_27_ALPACA_READ_ONLY_SYNC.md`, stop.
Do not begin Sprint 28.
