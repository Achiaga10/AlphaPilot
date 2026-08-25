# AlphaPilot Sprint 8 Plan

## 1. Goal

Build a deterministic, explainable, and pluggable candidate-ranking layer that decides which executable BUY candidates receive scarce shared-portfolio slots and cash. Preserve Sprint 7's ticker-ascending policy as the non-alpha control and add fixed Relative Strength 20 (RS20).

## 2. Scope

- Add a stable selection-policy enum/configuration and CLI option.
- Add a signal-time ranking-feature calculator separate from strategy and portfolio accounting.
- Add RS20 ordering, deterministic missing-history behavior, and ticker tie-breaking.
- Freeze calculated scores onto executable candidates before T+1 OPEN execution.
- Add compact per-candidate selection audit records and aggregate ranking diagnostics.
- Extend ignored reports with ranking metadata, diagnostics, and an audit CSV.
- Run fixed development and untouched validation comparisons for EMA HYBRID 2% and Micho V1 BOTH.

## 3. Non-goals

- No ranking lookback optimization; 20 trading bars is frozen for Sprint 8.
- No strategy, HYBRID threshold, Micho rule, max-position, sizing, commission, or slippage optimization.
- No News AI, discretionary ranking, production-default promotion, or Sprint 9 work.
- No primary EMA-versus-Micho conclusion; comparisons are within each strategy by selection policy.

## 4. Ranking Architecture

The existing architecture remains:

`Strategy -> Signal -> Candidate -> Ranking Feature -> Selection Policy -> Allocation -> Execution -> Accounting -> Metrics`

- `BacktestingEngine` continues to generate no-lookahead signals.
- A new feature calculator receives already-loaded stock and SPY candle histories and a candidate signal day.
- It filters both histories through the signal day, calculates RS20 when sufficient history exists, and returns `None` otherwise.
- `MultiPortfolioBacktestService` builds a `(ticker, signal_day) -> score` mapping from warm-up-inclusive histories. This is necessary because `BacktestResult` intentionally contains only requested-period bars.
- `MultiPortfolioSimulator` attaches the precomputed frozen score to an `ExecutableCandidate` but does not know the RS20 formula.
- Replaceable policies order candidates. Allocation/execution/accounting remain strategy- and formula-agnostic.

## 5. Exact RS20 Formula

The fixed lookback is 20 trading bars, requiring the current close plus 20 prior closes:

```text
stock_20d_return = stock_close[T] / stock_close[T-20 bars] - 1
spy_20d_return   = latest SPY close on/before T / SPY close 20 SPY bars earlier - 1
RS20             = stock_20d_return - spy_20d_return
```

Higher RS20 ranks first. The value is stored as a decimal return, not fabricated or filled when unavailable.

## 6. No-Lookahead Semantics

- The feature calculator sorts and filters stock/SPY candles to `trading_day <= signal_day` before indexing.
- A signal on T receives its frozen score from closes available through T only.
- T+1 or later stock closes cannot change its score.
- T+1 or later SPY closes cannot change its score.
- Execution remains at the candidate ticker's next available OPEN.
- Portfolio cash, later positions, and future outcomes do not enter the score.

## 7. Tie-Breaking Rules

- Scored candidates: RS20 descending, then normalized ticker ascending.
- Exactly equal scores therefore resolve deterministically by ticker.
- The control remains ticker ascending and ignores scores.

## 8. Missing-History Rules

- RS20 requires 21 stock closes and 21 SPY closes available through the signal day.
- If either side is insufficient or the lookback close is zero, score is `None`.
- Scored candidates rank before unscored candidates.
- Unscored candidates rank ticker ascending.
- Future data is never used to fill gaps.

## 9. Ranking Diagnostics and Audit

For each eligible executable BUY candidate, record:

- execution date and signal day
- ticker, policy, frozen score, and candidate rank
- selected/rejected outcome and rejection reason
- available slots, cash, and portfolio equity at its decision point

Rejection reasons include full slots and allocation unable to purchase one share. Aggregate diagnostics include candidates considered/selected/rejected, selection rate, constrained days, rejection counts, selected/rejected scored averages, and missing-score count. Reports will emit a compact audit CSV plus summary totals.

## 10. Development Experiment

Period: 2021-08-20 through 2024-12-31.

Run four fixed experiments:

1. EMA HYBRID 2% + ticker-ascending control
2. EMA HYBRID 2% + RS20
3. Micho V1 BOTH + ticker-ascending control
4. Micho V1 BOTH + RS20

Shared configuration: current active S&P 500 universe, $100,000, 10 positions, existing equal-slot sizing, $0 commission, and 0 bps slippage. Do not change RS20 after results.

## 11. Validation Experiment

Period: 2025-01-01 through 2026-08-20.

After implementation and tests are frozen, repeat the exact four policy/strategy combinations and assumptions. Do not tune using validation. Compare RS20 with the alphabetical control within each strategy and assess development-to-validation directional persistence.

## 12. Completion Criteria

- Control behavior remains compatible and deterministic.
- RS20 formula, no-lookahead, tie, missing-history, audit, and portfolio invariants have focused tests.
- `backend/run_checks.ps1` passes fully.
- All eight development/validation runs complete and artifacts are verified.
- Results and continuity decisions are documented in `docs/PROJECT_STATE.md`, `docs/DECISIONS.md`, and `docs/SPRINT8_COMPLETION_REPORT.md`.
- No commit/push/PR/merge/tag is performed by Codex and no Sprint 9 work begins.
