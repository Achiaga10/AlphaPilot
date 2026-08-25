# AlphaPilot Sprint 9 Plan

## 1. Goal

Test whether frozen RS20 remains credible after predeclared transaction costs, three temporal folds, and auditable return/concentration attribution.

## 2. Scope

- Preserve the Sprint 7 portfolio engine and Sprint 8 ranking semantics.
- Add named, deterministic cost scenarios using the existing per-side slippage mechanism.
- Add fold/cost metadata and collision-safe report names.
- Add ticker and sector dollar-P&L attribution for completed and final open positions.
- Reconcile initial equity, gross P&L, transaction friction, and final equity.
- Run the fixed cost and fold matrices for EMA HYBRID 2% and Micho BOTH.

## 3. Non-goals

- No new ranking feature, RS20 tuning, strategy changes, sizing/max-position optimization, forced liquidation, live execution, or Sprint 10 implementation.
- No global EMA-versus-Micho winner declaration.
- No post-result changes to costs, folds, or interpretation protocol.

## 4. Frozen RS20 Baseline

RS20 remains AlphaPilot Ranking Baseline V1:

```text
stock_return = stock_close[T] / stock_close[T-20 trading bars] - 1
spy_return   = spy_close[T] / spy_close[T-20 trading bars] - 1
RS20         = stock_return - spy_return
```

SPY and the 20-bar lookback are frozen. Signal-day filtering, scored-before-unscored ordering, descending score, and ticker tie-break remain unchanged.

## 5. Cost-Sensitivity Protocol

Named scenarios are fixed before results:

| Scenario | Commission/order | Slippage/side |
|---|---:|---:|
| COST_0 | $0 | 0 bps |
| COST_LOW | $0 | 5 bps |
| COST_CONSERVATIVE | $0 | 15 bps |

The current mechanism raises BUY price and lowers SELL price. Cost experiments use 2025-01-01 through 2026-08-20, both policies, both strategies, $100,000, 10 equal slots. Compare RS20 with its within-strategy control and calculate final-equity/return drag relative to COST_0 alongside turnover.

## 6. Temporal-Fold Protocol

At COST_0, run the same four strategy/policy combinations in these predeclared folds:

1. `fold-1`: 2021-08-20 through 2022-12-31
2. `fold-2`: 2023-01-01 through 2024-12-31
3. `fold-3`: 2025-01-01 through 2026-08-20

Actual equity dates may move inward only for non-trading days/data availability and will be reported. No fold is removed or altered after results.

## 7. Return-Attribution Protocol

Attribution uses additive dollar P&L, not geometrically additive return contribution:

- Completed trade gross P&L uses raw entry/exit OPENs.
- Completed friction is BUY slippage + SELL slippage + both commissions.
- Realized net P&L is gross realized P&L minus realized friction.
- Final open gross P&L uses raw entry OPEN to final marked close.
- Open-position friction includes incurred BUY slippage and entry commission.
- Unrealized net P&L is gross open P&L minus open friction.
- Combined ticker P&L is realized plus unrealized net P&L.

Reconciliation:

```text
initial equity + gross realized P&L + gross unrealized P&L - total friction = final equity
initial equity + net realized P&L + net unrealized P&L = final equity
```

Decimal equality is expected; any material residual is an error.

## 8. Concentration Diagnostics

Report ticker contributions; top 1/5/10 dollar contribution and share of total portfolio gain; unique tickers held; positive/negative contributors; top 1/5 share of total positive P&L; and positive-contributor HHI.

HHI is `sum((positive ticker P&L / total positive ticker P&L)^2)`. It ranges from near 0 for diffuse positive P&L to 1 for one positive contributor. Negative contributors are excluded from this explicitly labeled positive-P&L concentration measure.

Company sector is nullable but populated by the current universe pipeline. Sector attribution will use stored values only; missing/blank values are labeled `Unknown`, never inferred. It reports ticker count, completed trades, realized/unrealized/combined P&L, and combined-P&L share.

## 9. Testing Requirements

Focused tests will cover deterministic cost configuration; 5 bps BUY/SELL arithmetic; 15 bps configuration; monotonic friction arithmetic; unchanged zero-cost behavior; realized/open/combined attribution; exact reconciliation; top ordering and top 5/10 math; negative contributors; HHI; fold metadata/boundaries; frozen no-lookahead RS20; unchanged control; report metadata; and reproducibility. Existing Sprint 7, Sprint 8, and single-stock tests must remain green.

## 10. Experiment Matrix

- Costs: 2 strategies x 2 policies x 3 scenarios = 12 runs on the validation period.
- Folds: 3 folds x 2 strategies x 2 policies = 12 COST_0 runs.
- An identical fold-3 COST_0 artifact may be reused only after exact metadata/configuration and reproducibility are verified; otherwise it is rerun.
- Reports live under ignored `backtest_reports/sprint9/costs/` and `backtest_reports/sprint9/folds/`, with attribution CSVs beside each run.

## 11. Interpretation Rules

Answer separately whether RS20 survives both cost levels, wins across folds, depends on a few tickers, differs between realized and unrealized P&L, and has turnover that threatens its edge. Compare policies within the same strategy. Surviving 15 bps does not establish deployability or eliminate survivorship/data/benchmark limitations.

## 12. Completion Criteria

- Architecture and reporting are deterministic, auditable, and tested.
- Focused tests and `backend/run_checks.ps1` pass.
- All predeclared runs complete or exact reused artifacts are verified.
- Cost, fold, attribution, concentration, SPY, and reconciliation results are inspected and documented in `docs/SPRINT9_COMPLETION_REPORT.md`.
- Continuity docs are updated; no parameter is retuned; no Sprint 10 code, commit, push, PR, merge, or tag is performed.
