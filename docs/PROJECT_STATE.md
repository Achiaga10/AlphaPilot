# AlphaPilot — Current Project State

## Current Phase

Sprint 19 — AlphaPilot AI Copilot Foundation
COMPLETE LOCALLY

Current development branch:
feature/ai-copilot-foundation

Sprint 6 is complete, merged, and documented in `docs/SPRINT6_COMPLETION_REPORT.md`.

Sprints 7 through 10B are complete, reviewed, and merged. Sprint 11, including
11B/11C/11D and completed-session hardening, is complete, reviewed, and merged.
Sprint 12 completed its frozen protocol, was reviewed, and is merged. Sprint 13
is complete, reviewed, and merged: immutable market-data versions, explicit
ingestion provenance, exact universe/candle snapshots, deterministic hashes,
and snapshot-bound research replay are implemented without changing strategy or
normal UI behavior. Sprint 14 is complete, reviewed, and merged with
backend-owned versioned strategy profiles. Sprint 15 is complete, reviewed, and
merged with a frozen-snapshot, stage-governed Strategy Lab. Sprint 16 is complete,
reviewed, and merged. Sprint 17 and Sprint 18 are complete, reviewed, and
merged. Sprint 19 is complete locally. Sprint 20 is not started.

## Project Goal

AlphaPilot is intended to become a stock trading decision-support system.

Current focus:
- S&P 500 market data
- deterministic strategies
- historical testing
- empirical strategy validation
- scanner/ranking infrastructure

Future planned layers:
- multi-stock portfolio engine
- position sizing
- portfolio risk
- News Intelligence
- AI-supported decision layer
- actionable Portfolio Manager report

Those future layers are not part of the current task.

## Backend

Backend:
backend/

Source:
backend/src/alphapilot/

Tests:
backend/tests/

Primary stack:
- Python 3.12
- uv
- FastAPI
- PostgreSQL
- async SQLAlchemy
- pytest
- Ruff
- mypy

Quality command:

.\run_checks.ps1

## Completed Project Phases

Sprint 1 — Infrastructure
DONE

Sprint 2 — Core Architecture
DONE

Sprint 3 — Market Data Pipeline & API
DONE

Sprint 4 — Strategy Engine V1
DONE / merged

Sprint 5 — S&P 500 Universe & Scanner
DONE / merged

Sprint 6 — Backtesting & Strategy Validation
DONE / merged

Sprint 7 — Multi-Stock Portfolio Backtesting
DONE / merged

Sprint 8 — Candidate Ranking & Portfolio Selection
DONE / merged

Sprint 9 — Ranking Robustness, Transaction Costs & Return Attribution
DONE / merged

Sprint 10 — Portfolio Risk, Position Sizing & Decision API
COMPLETE / merged

Sprint 10B — Risk Model Hardening & Decision Orchestration
COMPLETE / merged

Sprint 11 — UI MVP
COMPLETE / merged

Sprint 11B — UI Product Hardening & Admin Data Operations
COMPLETE / merged

Sprint 11C — Portfolio Actions, Ticker Management & UI Explainability
COMPLETE / merged

Sprint 11D — Data Readiness, Sync UX & Portfolio Visualization
COMPLETE / merged

Post-completion manual-review hardening is also complete locally: BUY candidate
rank is advisory rather than forced order; user-selected whole-share quantities
receive backend preview and current-draft constraint validation; frozen EMA20
HYBRID/Micho exit guidance is backend-owned; Equal-slot risk metrics use explicit
not-applicable semantics; and proposed sector weights no longer display false
zero values. This work was complete before Sprint 12 began.

The critical Part AA single-stock identity blocker is fixed locally. Evaluate
Stock no longer assumes the first portfolio-plan status is the requested ticker.
The response carries an explicit normalized evaluation target and authoritative
Company ID; React matches the submitted ticker explicitly, keeps the evaluated
snapshot separate from editable input, and rejects mismatched responses instead
of rendering another holding. Latest-request-wins protection prevents an older
response from replacing a newer evaluation. Real stored-data acceptance passed
with LDOS held: SBET rendered Sharplink Inc, then AAPL replaced SBET only after
an explicit second evaluation.

Sprint 12 — Deep Strategy Research: Protective Stops, Exit Optimization &
Profit Management
COMPLETE / merged

Sprint 13 — Research Data Versioning, Provenance & Reproducibility
COMPLETE / merged

Sprint 14 — Strategy-Specific Configuration Profiles
COMPLETE LOCALLY

Sprint 15
NOT STARTED

## Sprint 7 Portfolio Infrastructure

Implemented:

- one shared cash balance across all tickers
- multiple simultaneous long positions
- configurable capital, maximum positions, commission, and slippage
- whole-share fixed equal-slot allocation
- ticker-specific next-available-bar OPEN execution
- deterministic exits-before-entries processing
- pluggable candidate selection with a non-alpha ticker-ascending baseline
- one daily cash/invested/equity curve
- final open-position mark-to-market without forced liquidation
- portfolio return, CAGR, drawdown, Sharpe, exposure, trade, turnover, and concurrency metrics
- SPY buy-and-hold comparison
- reproducible multi-portfolio CLI and summary/equity/trade reports

Focused tests: 22 passed.

Final quality gate: Ruff passed, mypy passed across 101 source files, and 101 tests passed.

## Sprint 7 Engine-Validation Baselines

Shared configuration:

- current active S&P 500 universe (502/502 successful)
- 2025-01-01 through 2026-08-20 requested; 2025-01-02 through 2026-08-20 actual portfolio curve
- $100,000 initial capital
- 10 maximum positions
- fixed equal-slot sizing
- $0 commission and 0 bps slippage
- stable ticker-ascending selection (non-alpha)
- final positions marked to market

EMA20 Pullback HYBRID 2%:

- final equity: $106,008.04
- total return: +6.01%
- CAGR: +3.65%
- max drawdown: 18.70%
- Sharpe: 0.30
- exposure: 90.74%
- completed trades: 229
- SPY return: +29.27%

Micho V1 BOTH:

- final equity: $118,335.24
- total return: +18.34%
- CAGR: +10.89%
- max drawdown: 20.26%
- Sharpe: 0.66
- exposure: 99.04%
- completed trades: 126
- SPY return: +29.27%

These runs validate the engine only. Alphabetical priority is not alpha, results contain current-constituent survivorship bias, and the raw returns must not be used to choose a strategy.

## Sprint 6 Infrastructure

Implemented under:

src/alphapilot/backtesting/

Includes:
- historical replay engine
- trade simulator
- portfolio simulator
- portfolio equity curve
- metrics
- portfolio metrics
- benchmark simulator
- diagnostics
- MFE
- MAE
- peak giveback
- entry/exit reason diagnostics
- universe comparison
- HYBRID threshold experiment
- generic strategy-universe runner
- Micho entry analysis

## Backtest Execution Rules

Historical evaluation is day-by-day.

Signal on day T executes at T+1 OPEN.

Current portfolio behavior:
- long only
- whole shares
- configurable capital
- configurable position percentage
- configurable commission
- configurable slippage

Repeated BUY while already long is ignored.

SELL while flat is ignored.

Signal on final available day cannot execute.

## Current Universe Limitation

Historical universe experiments currently use the CURRENT active S&P 500 constituent list.

Therefore:

Results contain survivorship bias.

This must remain clearly documented.

## EMA20 Pullback Research

Strategy includes:
- EMA20
- EMA50
- market regime
- pullback/reclaim logic

Exit modes tested:
- EMA20
- EMA50
- HYBRID

Five-year experiments showed a trade-off:

EMA20:
- faster defensive exit
- lower drawdown in many stocks
- lower giveback

EMA50:
- preserves large trends better
- stronger in many large trend winners

## HYBRID Exit Research

HYBRID attempts to combine EMA20 protection with EMA50 trend preservation.

Thresholds tested on development data:
- 1%
- 2%
- 3%
- 4%
- 5%

Development period:

2021-08-20 -> 2024-12-31

Selection rule was predefined.

Selected threshold:

2%

This threshold is frozen.

## HYBRID Validation

Validation period:

2025-01-01 -> 2026-08-20

HYBRID 2% approximately:
- Median return: -0.44%
- Median CAGR: -0.27%
- Median Max DD: 18.62%
- Median Sharpe: 0.07
- Profit Factor: 0.76
- Peak Giveback: 5.50%
- Profitable: 243/502
- Beats SPY: 55/502
- Beats own B&H: 143/502

EMA20 on same validation:
- Median return: -1.25%
- Sharpe: 0.01
- Max DD: 17.31%
- Giveback: 4.39%
- Beats SPY: 41
- Beats own B&H: 139

EMA50:
- Median return: -0.37%
- Sharpe: 0.09
- Max DD: 19.22%
- Giveback: 6.91%
- Beats SPY: 53
- Beats own B&H: 147

Current interpretation:

HYBRID 2% is a balanced candidate.

Do not yet make it the universal production default.

Portfolio-level testing is still required.

## Micho 150 V1

Micho 150 V1 currently uses:
- SMA150
- 5-period slope lookback
- approximately 98%-102% SMA touch area
- flat/rising trend filter
- breakout BUY
- bounce BUY
- close below SMA150 SELL

Backtest warm-up:
260 calendar days

Micho V1 intentionally does NOT currently include:
- News AI
- volume filters
- discretionary chart patterns
- alternative stops
- alternative moving-average lengths

## Micho Five-Year Baseline

Period:
2021-08-20 -> 2026-08-20

Original mode:
BOTH

502/502 successful.

Approximate median metrics:
- Total Return: +1.98%
- CAGR: +0.39%
- Max Drawdown: 28.88%
- Sharpe: 0.12
- Profit Factor: 0.93
- Win Rate: 24.07%
- Exposure: 34.78%
- Holding: 35.12 days
- MFE: 7.08%
- MAE: -2.88%
- Giveback: 6.40%

Profitable:
265/502

Beats SPY:
55/502

Beats own B&H:
135/502

Micho displayed strong right-tail behavior:
a relatively low win rate but some extremely large trend winners.

## Micho Validation

Validation period:
2025-01-01 -> 2026-08-20

Original mode:
BOTH

502/502 successful.

Results:
- Profitable: 216/502
- Beats SPY: 75/502
- Beats own B&H: 148/502
- No completed trades: 32/502

Median:
- Total Return: -1.03%
- CAGR: -0.63%
- Max Drawdown: 16.95%
- Sharpe: -0.02
- Profit Factor: 0.19
- Win Rate: 16.67%
- Exposure: 29.22%
- Holding: 23.00 days
- MFE: 5.24%
- MAE: -3.00%
- Giveback: 6.22%

Conclusion:

The five-year Micho advantage did not persist at the same strength during the later validation period.

The strategy appears regime-sensitive.

Do not tune parameters based on this result.

## Micho Executed Entry Analysis

Completed-trade entry reasons were added.

Validation period:
2025-01-01 -> 2026-08-20

Original BOTH mode:

Total completed trades:
2646

Classified:
2646

Unclassified:
0

BREAKOUT:
2124 completed trades

Per-stock median:
- Win Rate: 20.00%
- Average Trade: -1.29%
- Average Win: +2.91%
- Average Loss: -2.39%
- Profit Factor: 0.08
- Compounded Return: -4.93%
- Holding: 16.25 days
- MFE: 4.09%
- MAE: -2.74%
- Giveback: 5.77%

BOUNCE:
522 completed trades

Per-stock median:
- Win Rate: 0.00%
- Average Trade: -1.91%
- Average Win: +5.91%
- Average Loss: -2.88%
- Profit Factor: 0.00
- Compounded Return: -2.59%
- Holding: 18.00 days
- MFE: 4.01%
- MAE: -3.45%
- Giveback: 6.66%

Head-to-head where both existed:
- stocks compared: 318
- Breakout higher average trade: 180
- Bounce higher average trade: 138
- ties: 0

This suggested Breakout may be stronger.

However, BOTH mode gives Breakout and Bounce unequal entry opportunities.

Therefore this result was not enough to remove Bounce.

## Micho Entry Modes

Implemented:
- both
- breakout-only
- bounce-only

Default:
both

Purpose:

Run an independent A/B/C experiment.

Report filenames include entry mode so results do not overwrite each other.

## Entry-Mode Smoke Test

Period:
2025-01-01 -> 2026-08-20

10 stocks.

All modes:
10/10 successful.

BOTH median:
- Return: +3.52%
- CAGR: +2.13%
- Max DD: 14.81%
- Sharpe: 0.32
- Profit Factor: 0.45
- Win Rate: 17.14%
- Exposure: 38.63%
- Holding: 28.00 days

Completed trades:
46

BREAKOUT ONLY median:
- Return: +4.35%
- CAGR: +2.64%
- Max DD: 14.82%
- Sharpe: 0.44
- Profit Factor: 0.23
- Win Rate: 8.33%
- Exposure: 28.24%
- Holding: 16.20 days

Completed trades:
33

Isolation verified:
- Breakout signals present
- Bounce signals = 0

BOUNCE ONLY median:
- Return: -0.43%
- CAGR: -0.27%
- Max DD: 14.44%
- Sharpe: -0.05
- Profit Factor: 0.11
- Win Rate: 13.39%
- Exposure: 33.37%
- Holding: 26.50 days

Completed trades:
37

Isolation verified:
- Bounce signals present
- Breakout signals = 0

## Important Interpretation

The 10-stock smoke result is NOT sufficient to choose a winning mode.

Its main purpose was to verify:
- implementation works
- modes are isolated
- reports are reproducible
- original BOTH behavior remains available

## Sprint 11C Completion

Sprint 11 and Sprint 11B remain preserved locally. Sprint 11C completed:

- preserve backend ownership of strategy, signal, RS20, ATR14, ranking, sizing,
  risk constraints, and portfolio decisions;
- use the exact user-provided AlphaPilot PNG through Vite without modification;
- make decision priority, all-evaluated A-Z ordering, counts, filters, data
  status, and single-stock evaluation explicit;
- mark displayed plan results stale whenever plan-affecting form state changes;
- expose research-admin freshness and sync operations only behind the safe
  disabled-by-default `ADMIN_TOOLS_ENABLED` gate;
- reuse existing data/provider/service boundaries and never fabricate arbitrary
  company metadata; and
- fix tooltip clipping with a viewport-aware accessible popover;
- distinguish approved SELL decisions from SELL signals;
- apply one backend-approved BUY/SELL at a time to research draft state, then
  require regeneration;
- keep S&P membership separate from custom tracked companies and never delete
  historical candles during deactivation;
- split universe and candle synchronization while retaining safe typed jobs;
- remove hardcoded Alpaca SIP, expose the configured IEX/SIP feed, never fall
  back silently, and report benchmark/feed failures safely; and
- keep Sprint 12 not started.

The detailed frozen protocol is in `docs/SPRINT11C_PLAN.md`; final evidence is
in `docs/SPRINT11C_COMPLETION_REPORT.md`. All work remains local on
`feature/ui-mvp`. Sprint 12 is not started.

## Sprint 11D Complete Locally

Sprint 11D preserves every prior Sprint 11 deliverable and added backend-owned
plan readiness/coverage, explicit SPY-session freshness, contextual zero-BUY
recovery, a reactive backend-valued portfolio allocation donut, accessible
Admin progress, backend-validated ordered same-plan action application, and
typed partial/full manual sale bookkeeping. It does not weaken freshness,
change research rules, execute broker orders, or begin Sprint 12. Full frontend
and backend gates pass, controlled browser acceptance passes, and real stored
data produced 501 normally evaluated current-universe tickers plus one
insufficient-history ticker, 61 BUY signals, and 10 approved BUYs.
The final review addendum removed synthetic rank dependencies, added backend
quantity preview/override semantics and hard-constraint revalidation, exposed
stored-date strategy exit context for BUY/HOLD/SELL decisions, and corrected
Equal-slot sector/not-applicable display semantics without changing any strategy
or sizing formula.
