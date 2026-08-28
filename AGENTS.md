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

Sprint 17 — Position Monitoring, Exit Guidance, Portfolio Reconciliation &
Daily Completed-Session Sync Automation (COMPLETE LOCALLY)

Sprint 11 and all 11B/11C/11D hardening are complete and merged. Sprint 12 and
Sprint 13 through Sprint 15 are complete, reviewed, and merged. Sprint 16 is
complete, reviewed, and merged. Sprint 17 is complete locally on
`feature/position-monitoring`. Do not add or tune strategies. Do not begin Sprint 18.

## Development Environment

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

## Sprint 17 Task

Add backend-owned completed-session position monitoring from stored Strategy
Profiles, sticky exit triggers, audited portfolio reconciliation, and safe daily
market-data automation. Do not auto-trade or activate research-only stops.

## End-of-Task Rule

After creating `docs/sprints/SPRINT17_COMPLETION_REPORT.md`, stop. Do not begin
Sprint 18.
