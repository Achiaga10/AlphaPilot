# AlphaPilot — Current Decisions

This file records decisions that must not be silently changed.

## 0. Current Phase

Sprint 6 is complete and merged.

Sprint 7 — Multi-Stock Portfolio Backtesting — is complete and merged.

Sprint 8 — Candidate Ranking & Portfolio Selection — is complete and merged.

Sprint 9 — Ranking Robustness, Transaction Costs & Return Attribution — is complete and merged.

Sprint 10 — Portfolio Risk, Position Sizing & Decision API — is complete and reviewed.

Sprint 10B — Risk Model Hardening & Decision Orchestration — is complete locally
and awaiting user review/Git operations. Sprint 11 is not started.

Sprint 8 compares the non-alpha alphabetical control with fixed RS20. Do not optimize the 20-bar lookback, strategy parameters, portfolio constraints, or use validation to retune the formula.

## 0.3 Sprint 8 Ranking Decisions

- `ticker-ascending` remains the deterministic, economically meaningless control.
- `relative-strength-20` uses stock 20-bar return minus SPY 20-bar return.
- Scores use information through the BUY signal day only and are frozen before next-OPEN execution.
- Higher score ranks first; equal scores use ticker ascending.
- Scored candidates rank before candidates lacking history; unscored candidates use ticker ascending and never receive fabricated scores.
- Ranking features, ordering, allocation, execution, and accounting remain separate concerns.
- Selection decisions must be auditable with signal/execution dates, score, rank, outcome, rejection reason, slots, cash, and equity context.
- The fixed experiment is complete locally. RS20 beat the alphabetical control for both strategies in both development and validation without parameter retuning.
- This validates the ranking infrastructure and supports further research; it does not make RS20 production-ready or change either strategy.

## 0.4 Sprint 9 Robustness Decisions

- RS20 is frozen as Ranking Baseline V1: 20 stock bars minus 20 SPY bars, using signal-day information only.
- Fixed per-side scenarios are COST_0 = 0 bps, COST_LOW = 5 bps, and COST_CONSERVATIVE = 15 bps; all use zero commission.
- Fixed folds are 2021-08-20–2022-12-31, 2023-01-01–2024-12-31, and 2025-01-01–2026-08-20.
- Attribution uses additive dollar P&L and distinguishes gross P&L, friction, net realized P&L, and final open unrealized P&L.
- Positive-contributor HHI is the sum of squared shares of total positive ticker P&L.
- Stored sector values may be reported; missing values are `Unknown` and are never inferred.
- Strategy rules, 2% HYBRID, Micho BOTH, 10 positions, equal-slot sizing, costs, folds, and RS20 may not be retuned after results.
- Sprint 9 completed locally without retuning. RS20 beat control at 5 and 15 bps for both strategies on the validation period.
- Temporal evidence was mixed: RS20 beat control on total return in 2/3 EMA folds and 1/3 Micho folds. RS20 therefore remains a useful research baseline, not a proven universal default.
- Validation performance was materially concentrated, especially for Micho and in final open positions; future research must retain contributor and realized/unrealized attribution.

## 0.5 Sprint 10 Risk and Decision Decisions

- ATR14 uses the latest 14 true ranges through signal day and requires the preceding close; no future candle may affect it.
- ATR-risk sizing uses 1% equity risk, 2× ATR stop proxy, 10% position cap, 8% portfolio risk cap, 10% entry cash reserve, 30% sector cap, 10 positions, and whole shares.
- Equal-slot remains available and unchanged for research compatibility.
- Position modeled risk is frozen at entry as shares × entry stop distance; portfolio risk is the sum across active positions.
- Missing sectors form one explicit `Unclassified` bucket subject to the same sector cap; sectors are never inferred.
- Strategy signals and portfolio decisions are separate typed concepts; entry constraints never block SELL.
- The decision API is advisory only: no broker execution or persistence.
- All V1 parameters are frozen for the Sprint 10 experiments and may not be retuned after results.
- Sprint 10 completed locally without retuning. ATR-risk reduced EMA drawdown but materially reduced return; it did not reduce Micho drawdown and also reduced Micho return.
- All entry risk, cash-reserve, sector, max-position, whole-share, and cash constraints validated without breaches. Sector weights may drift above the entry cap through appreciation; no forced selling occurs.
- The typed decision API is suitable for UI consumption as an advisory contract. Automated market-data/signal enrichment and broker synchronization remain separate adapters.

## 0.6 Sprint 10B Frozen Decisions

- Preserve `equal-slot` and Sprint 10 `atr-risk` without formula changes.
- Add only the predeclared `atr-volatility-normalized` policy: inverse ATR14
  percentage weights normalized across the same eligible candidate group.
- Use 10% reserve, 10% position cap, 8% modeled-risk cap, 30% sector cap, and 10
  positions. Do not search parameters after development or validation results.
- Volatility normalization requires a batch allocation boundary; it must not be
  approximated through unrelated one-candidate normalizations.
- Existing holdings consume investable capital and are not force-rebalanced.
- The high-level portfolio-plan API must calculate strategy signals, RS20, ATR14,
  and sector facts in the backend from stored data as of an explicit date.
- Domain orchestration must use existing service/repository boundaries and must
  not call external providers directly.
- Sprint 10B is not Sprint 11. No UI/frontend implementation is authorized.
- Sprint 10B completed without parameter retuning. Candidate-group weights
  normalized exactly and every audited entry respected risk, reserve, position,
  sector, whole-share, and cash constraints.
- Volatility-normalized sizing improved on ATR-risk V1 consistently for Micho,
  but not for EMA: EMA results were mixed across development and validation.
- Policy classifications are strategy-specific: equal-slot is a promising
  research baseline for EMA and Micho; ATR-risk remains research-only for both;
  volatility-normalized is research-only for EMA and a promising research
  baseline for Micho. None is production-ready.
- The high-level `/api/v1/portfolio/plan` contract passes the UI-readiness gate:
  stored-data strategy evaluation, RS20, ATR14, sectors, risk constraints, and
  reason codes are backend-owned. Broker state and authenticated persistence
  remain future backend adapters.

## 0.1 Sprint 7 Portfolio Baseline Decisions

- One shared cash balance funds all tickers.
- Long-only, whole shares, no leverage, and cash may not become negative.
- Maximum concurrent positions and transaction assumptions are configurable.
- Signal T executes at that ticker's next available trading-day OPEN.
- Executable exits run before entries so released cash is available that day.
- Open positions are marked to market at the end; they are not force-liquidated.
- Existing Scanner output has no ranking score. Sprint 7 therefore uses a pluggable stable ticker-order baseline selector, explicitly not alpha.
- Baseline sizing uses fixed equal slots based on current equity divided by configured maximum positions, capped by available cash. Existing positions are not rebalanced.
- Baseline results are engine validation only and must disclose current-constituent survivorship bias, benchmark alignment limitations, and transaction-cost assumptions.

## 0.2 Sprint 7 Validation Outcome

Sprint 7's shared-cash engine, tests, reports, and two baseline runs completed successfully.

Both baselines used stable ticker-ascending selection, 10 fixed equal slots, zero commission, and zero slippage. They prove shared capital, deterministic execution, accounting, valuation, metrics, and reporting work end to end. They do not establish a production ranking or strategy winner.

Do not use the fact that Micho BOTH returned more than EMA HYBRID 2% in these particular runs to declare Micho superior. Alphabetical slot priority materially affects which signals receive capital.

Open positions remain open and are marked to market at the final close. They are not included as completed trades or force-liquidated.

## 1. Package / Environment

Use uv.

Primary validation command:

.\run_checks.ps1

Do not introduce unrelated pip-based workflows.

## 2. Git Ownership

The user controls Git publishing.

Codex must NOT:
- git push
- force push
- push tags
- merge to main
- open/merge remote PRs

Codex should not automatically commit.

At the end of work Codex should provide:
- git status
- changed files
- recommended commit message

The user decides when to commit and push.

## 3. Backtesting Execution

Signal produced on trading day T executes at the next trading day's OPEN.

No lookahead is allowed.

Long-only baseline.

BUY while already long:
ignored.

SELL while flat:
ignored.

Final-day signal:
cannot execute.

## 4. Survivorship Bias

Historical S&P 500 experiments currently use the current active constituent list.

Therefore results have survivorship bias.

This must always be disclosed.

## 5. EMA20 vs EMA50

Do not declare either universally superior.

Observed behavior:

EMA20:
- more defensive
- lower drawdown/giveback in many cases

EMA50:
- preserves strong trends
- benefits some large winners

## 6. HYBRID Exit

HYBRID exists to combine EMA20 protection with EMA50 trend persistence.

Development threshold experiment:
1%, 2%, 3%, 4%, 5%.

Selected:
2%

Selection was made on:
2021-08-20 -> 2024-12-31

The threshold is frozen.

Do not retune it on validation data.

## 7. HYBRID Production Status

HYBRID 2% passed later validation as a balanced candidate.

It is NOT yet automatically the Scanner default.

Final strategy/default choice should wait for portfolio-level evidence.

## 8. Micho V1

Micho 150 is currently a mechanical deterministic baseline.

Current core rules:
- SMA150
- trend filter
- breakout
- bounce
- close-below-SMA150 exit

Do not describe it as an exact implementation of discretionary/proprietary rules.

Do not add during current Sprint 6 experiment:
- news
- AI
- volume
- alternative stops
- alternative SMA periods
- new chart patterns

## 9. Do Not Optimize Micho From Validation Data

Micho performed materially better on the full five-year period than on the later validation period.

This suggests possible regime sensitivity.

Do not immediately tune parameters to make validation look better.

First isolate strategy components.

## 10. Executed Entry Reason Analytics

Raw BUY signals are not the same as executed entries.

Completed trade diagnostics must be used when evaluating:
- BREAKOUT
- BOUNCE

This is because BUY signals can occur while already holding a position.

## 11. BOTH-Mode Breakout vs Bounce Was Not Sufficient

Initial completed-trade diagnostics showed Breakout generally stronger than Bounce.

However:
Breakout often opens the position before later Bounce signals can act.

Therefore Bounce had fewer independent opportunities.

Decision:

Do NOT remove Bounce based solely on BOTH-mode diagnostics.

## 12. MichoEntryMode

Implemented:
- both
- breakout-only
- bounce-only

Default:
both

Reason:

Allow controlled isolation of entry logic without changing original V1 behavior.

## 13. Category Isolation

In bounce-only:

a day already classified as Breakout must not fall through and be reclassified as Bounce.

Reason:

The experiment must isolate existing categories rather than invent a different strategy.

## 14. Separate Report Files

Each Micho entry mode must produce a unique report name.

Examples:
- strategy_universe_micho_150_both_...
- strategy_universe_micho_150_breakout_only_...
- strategy_universe_micho_150_bounce_only_...

Experiments must never silently overwrite each other.

## 15. Smoke Test Result

10-stock validation smoke passed for:
- both
- breakout-only
- bounce-only

Preliminary result:

BREAKOUT_ONLY looked strongest.

BOUNCE_ONLY looked weakest.

But:

No strategy decision may be made from the 10-stock smoke.

A full-universe experiment is required.

## 16. Current Final Sprint 6 Experiment

Run:
- BOTH
- BREAKOUT_ONLY
- BOUNCE_ONLY

on the full current S&P 500 universe.

Validation period:
2025-01-01 -> 2026-08-20

Only entry mode may change.

Keep all other assumptions consistent.

## 17. Micho V2 Is Not Yet Approved

Do not change permanent Micho rules until the A/B/C full-universe results have been analyzed.

Potential future V2 work may be justified by the data, but must be a separate experiment.

## 18. Sprint 6 Must Produce a Completion Report

At the end of Sprint 6 create:

docs/SPRINT6_COMPLETION_REPORT.md

The report must contain:
- work completed
- files changed
- tests/checks
- full A/B/C results
- comparison
- final conclusion
- limitations
- Git state
- recommended commit message
- recommendation for Sprint 7

The report must be understandable without access to the Codex conversation.

## 19. Codex Stops After Sprint 6

Codex must NOT begin Sprint 7 automatically.

After producing:

docs/SPRINT6_COMPLETION_REPORT.md

stop.

The user will review the report with ChatGPT.

Sprint 7 begins only after that review.

## 20. Likely Sprint 7 Direction

Current likely next major architectural step:

Multi-Stock Portfolio Backtesting

Possible flow:

Scanner
→ Ranking
→ Candidate Selection
→ Position Sizing
→ Simultaneous Positions
→ Portfolio Constraints
→ Portfolio Equity
→ Portfolio Drawdown
→ Benchmark

This is only a recommendation.

Do not implement it during Sprint 6.

## 21. News Intelligence Is Future Work

Planned future layer:

Technical Strategy
+
News Collection
+
AI News Analysis
+
Risk Layer
→ Decision

Keep it separate from current technical validation.

## 22. Portfolio Manager Is Future Work

Long-term AlphaPilot should eventually create an actionable portfolio report including:
- capital allocation
- cash allocation
- stocks to buy
- stocks to sell
- quantities
- risk/stop rules
- position management
- rationale

This comes after strategy and portfolio validation.
