# AlphaPilot Sprint 8 Completion Report

## Sprint Goal and Outcome

Sprint 8 built a deterministic, explainable, pluggable ranking layer for the Sprint 7 shared-cash portfolio engine. It decides which executable BUY candidates receive scarce slots and cash. The Sprint completed successfully: fixed RS20 beat the economically meaningless alphabetical control for both tested strategies in development and validation. No ranking parameter or strategy rule was changed after observing results.

## Architecture Implemented

`Strategy -> Signal -> Candidate -> Ranking Feature -> Ranking Policy -> Selection -> Allocation -> Execution -> Accounting -> Metrics`

- `RelativeStrength20Calculator` calculates signal-time features outside portfolio accounting.
- `MultiPortfolioBacktestService` uses warm-up-inclusive stock and SPY histories and keys scores by ticker and signal day.
- Scores are frozen onto executable candidates before next-OPEN execution.
- Replaceable policies order candidates; the simulator has no strategy-specific ranking formula.
- Exit-before-entry processing, shared cash, equal-slot sizing, and position constraints are preserved.
- Per-candidate audit records and aggregate diagnostics explain constrained decisions.

## Files Created

- `backend/src/alphapilot/backtesting/ranking_features.py`
- `backend/tests/backtesting/test_candidate_selection.py`
- `backend/tests/backtesting/test_ranking_features.py`
- `docs/SPRINT8_PLAN.md`
- `docs/SPRINT8_COMPLETION_REPORT.md`

## Files Modified

- `AGENTS.md`
- `backend/src/alphapilot/backtesting/candidate_selection.py`
- `backend/src/alphapilot/backtesting/multi_portfolio.py`
- `backend/src/alphapilot/backtesting/multi_portfolio_models.py`
- `backend/src/alphapilot/backtesting/multi_portfolio_service.py`
- `backend/src/alphapilot/cli/backtest_multi_portfolio.py`
- `backend/tests/backtesting/test_multi_portfolio.py`
- `docs/DECISIONS.md`
- `docs/PROJECT_STATE.md`

## Formula, Ordering, and No-Lookahead Semantics

The lookback was fixed and not optimized:

```text
stock_20d_return = stock_close[T] / stock_close[T-20 trading bars] - 1
spy_20d_return   = latest SPY close on/before T / SPY close 20 SPY bars earlier - 1
RS20             = stock_20d_return - spy_20d_return
```

For a BUY signal on T, stock and benchmark histories are filtered to dates on or before T. The score is frozen at signal time; T+1 or later stock/SPY data, future outcomes, and later portfolio state cannot affect it. Execution remains at the ticker's next available OPEN.

RS20 requires 21 closes for both stock and SPY. Insufficient history or a zero lookback close yields `None`; no score is fabricated. Scored candidates rank before unscored candidates. Higher scores rank first. Exact ties and unscored candidates use ticker ascending.

## Audit and Attribution

Each eligible executable BUY candidate records execution day, signal day, ticker, policy, frozen score, rank, selected/rejected state, rejection reason, available slots, cash, and equity. Rejections distinguish slots full from allocation unable to buy one share. Summaries report candidates considered/selected/rejected, selection rate, constrained days, both rejection counts, mean selected/rejected RS20, and missing-history count.

Each run emits summary, equity, trades, and selection-audit files. Artifact checks found 16 files per period (32 total), no signal day on/after its execution day, nonnegative cash, and at most 10 positions.

## Tests and Checks

Tests created/modified cover the exact formula, positive and negative scores, score and missing-value ordering, deterministic ties, T+1 stock and future-SPY isolation, no fabricated scores, unchanged control behavior, max positions, shared cash, exits before entries, SELL independence, audit attribution, score preservation, and repeatability. Existing Sprint 7 and single-stock tests remained green.

Focused command:

```powershell
$env:DEBUG='false'
uv run pytest tests/backtesting/test_ranking_features.py tests/backtesting/test_candidate_selection.py tests/backtesting/test_multi_portfolio.py tests/backtesting/test_multi_portfolio_reporting.py tests/backtesting/test_engine.py
```

Result: **27 passed in 2.16s**.

Full command:

```powershell
$env:DEBUG='false'
.\run_checks.ps1
```

Result: **passed**. Ruff checks passed; Ruff format reported 144 files unchanged; mypy found no issues in 102 source files; pytest reported **114 passed in 12.66s**. `DEBUG=false` was scoped only to child processes because the Codex host injected invalid `DEBUG=release`; project configuration was not changed.

## Exact Experiment Commands

All commands ran from `backend/`.

```powershell
# Development
uv run alphapilot backtest-multi-portfolio --strategy ema20-pullback --exit-mode hybrid --hybrid-trend-threshold-pct 2 --selection-policy ticker-ascending --start 2021-08-20 --end 2024-12-31 --capital 100000 --max-positions 10 --commission 0 --slippage-bps 0 --output-dir backtest_reports/sprint8/development
uv run alphapilot backtest-multi-portfolio --strategy ema20-pullback --exit-mode hybrid --hybrid-trend-threshold-pct 2 --selection-policy relative-strength-20 --start 2021-08-20 --end 2024-12-31 --capital 100000 --max-positions 10 --commission 0 --slippage-bps 0 --output-dir backtest_reports/sprint8/development
uv run alphapilot backtest-multi-portfolio --strategy micho-150 --micho-entry-mode both --selection-policy ticker-ascending --start 2021-08-20 --end 2024-12-31 --capital 100000 --max-positions 10 --commission 0 --slippage-bps 0 --output-dir backtest_reports/sprint8/development
uv run alphapilot backtest-multi-portfolio --strategy micho-150 --micho-entry-mode both --selection-policy relative-strength-20 --start 2021-08-20 --end 2024-12-31 --capital 100000 --max-positions 10 --commission 0 --slippage-bps 0 --output-dir backtest_reports/sprint8/development

# Validation
uv run alphapilot backtest-multi-portfolio --strategy ema20-pullback --exit-mode hybrid --hybrid-trend-threshold-pct 2 --selection-policy ticker-ascending --start 2025-01-01 --end 2026-08-20 --capital 100000 --max-positions 10 --commission 0 --slippage-bps 0 --output-dir backtest_reports/sprint8/validation
uv run alphapilot backtest-multi-portfolio --strategy ema20-pullback --exit-mode hybrid --hybrid-trend-threshold-pct 2 --selection-policy relative-strength-20 --start 2025-01-01 --end 2026-08-20 --capital 100000 --max-positions 10 --commission 0 --slippage-bps 0 --output-dir backtest_reports/sprint8/validation
uv run alphapilot backtest-multi-portfolio --strategy micho-150 --micho-entry-mode both --selection-policy ticker-ascending --start 2025-01-01 --end 2026-08-20 --capital 100000 --max-positions 10 --commission 0 --slippage-bps 0 --output-dir backtest_reports/sprint8/validation
uv run alphapilot backtest-multi-portfolio --strategy micho-150 --micho-entry-mode both --selection-policy relative-strength-20 --start 2025-01-01 --end 2026-08-20 --capital 100000 --max-positions 10 --commission 0 --slippage-bps 0 --output-dir backtest_reports/sprint8/validation
```

## Configuration and Caveats

Both periods used current active S&P 500 constituents, $100,000 capital, 10 positions, existing equal-slot sizing, $0 commission, 0 bps slippage, EMA20 Pullback HYBRID with frozen 2%, and Micho V1 BOTH. Open final positions were marked to the last close and not force-liquidated. SPY Buy & Hold uses the actual aligned portfolio period.

## Development Results

Period: 2021-08-20 through 2024-12-31. Each run had 497 successful and 5 failed stocks: `FDXF`, `HONA`, `PSKY`, `Q`, `SNDK` lacked historical candles. SPY: final $133,107.95; return 33.11%; CAGR 8.87%; drawdown 25.34%; Sharpe 0.57.

| Metric | EMA control | EMA RS20 | Micho control | Micho RS20 |
|---|---:|---:|---:|---:|
| Final equity | $116,493.30 | $175,929.08 | $155,083.22 | $163,452.16 |
| Total return | 16.49% | 75.93% | 55.08% | 63.45% |
| CAGR | 4.64% | 18.28% | 13.93% | 15.72% |
| Max drawdown | 19.99% | 26.54% | 16.73% | 18.85% |
| Sharpe | 0.40 | 0.84 | 0.83 | 0.84 |
| Exposure | 77.15% | 77.93% | 98.72% | 98.65% |
| Completed trades | 363 | 254 | 250 | 252 |
| Win rate | 31.96% | 31.89% | 26.00% | 25.79% |
| Profit factor | 1.24 | 1.40 | 1.41 | 1.56 |
| Average trade | 0.75% | 2.16% | 0.94% | 1.12% |
| Turnover | 7697.13% | 5503.53% | 5328.71% | 5305.83% |
| Average open positions | 7.72 | 7.88 | 9.94 | 9.92 |
| Maximum/open-at-end | 10 / 10 | 10 / 10 | 10 / 10 | 10 / 10 |

| Ranking diagnostic | EMA control | EMA RS20 | Micho control | Micho RS20 |
|---|---:|---:|---:|---:|
| Considered / selected / rejected | 40,969 / 373 / 40,596 | 41,515 / 264 / 41,251 | 15,209 / 260 / 14,949 | 15,172 / 262 / 14,910 |
| Selection rate | 0.91% | 0.64% | 1.71% | 1.73% |
| Constrained days | 606 | 606 | 809 | 810 |
| Slots / allocation rejects | 40,596 / 0 | 40,602 / 649 | 14,931 / 18 | 14,525 / 385 |
| Mean selected / rejected RS20 | N/A | 12.70% / 1.17% | N/A | 7.24% / -0.99% |
| Missing history | 0 | 0 | 0 | 0 |

EMA RS20 added $59,435.78 and 59.44 return points versus control, at 6.55 points worse drawdown. Micho RS20 added $8,368.94 and 8.37 return points, at 2.12 points worse drawdown. Both RS20 variants beat SPY total return.

## Validation Results

Requested: 2025-01-01 through 2026-08-20. Actual aligned period: 2025-01-02 through 2026-08-20 because January 1 was not a trading day. All 502 stocks succeeded. SPY: final $129,272.49; return 29.27%; CAGR 17.07%; drawdown 18.93%; Sharpe 1.03.

| Metric | EMA control | EMA RS20 | Micho control | Micho RS20 |
|---|---:|---:|---:|---:|
| Final equity | $106,008.04 | $158,407.40 | $118,335.24 | $127,184.06 |
| Total return | 6.01% | 58.41% | 18.34% | 27.18% |
| CAGR | 3.65% | 32.63% | 10.89% | 15.91% |
| Max drawdown | 18.70% | 20.48% | 20.26% | 17.97% |
| Sharpe | 0.30 | 0.98 | 0.66 | 1.06 |
| Exposure | 90.74% | 92.51% | 99.04% | 98.47% |
| Completed trades | 229 | 151 | 126 | 100 |
| Win rate | 29.69% | 33.77% | 15.87% | 20.00% |
| Profit factor | 0.89 | 1.46 | 1.07 | 1.10 |
| Average trade | -0.13% | 3.66% | 0.14% | 0.36% |
| Turnover | 4367.21% | 3248.09% | 2183.93% | 1963.38% |
| Average open positions | 9.12 | 9.26 | 9.96 | 9.96 |
| Maximum/open-at-end | 10 / 10 | 10 / 10 | 10 / 10 | 10 / 10 |

| Ranking diagnostic | EMA control | EMA RS20 | Micho control | Micho RS20 |
|---|---:|---:|---:|---:|
| Considered / selected / rejected | 22,399 / 239 / 22,160 | 22,749 / 161 / 22,588 | 7,804 / 136 / 7,668 | 7,883 / 110 / 7,773 |
| Selection rate | 1.07% | 0.71% | 1.74% | 1.40% |
| Constrained days | 353 | 353 | 402 | 406 |
| Slots / allocation rejects | 22,160 / 0 | 22,588 / 0 | 7,668 / 0 | 7,772 / 1 |
| Mean selected / rejected RS20 | N/A | 13.42% / 1.87% | N/A | 6.89% / -0.83% |
| Missing history | 0 | 0 | 0 | 0 |

EMA RS20 added $52,399.36 and 52.40 return points, with drawdown 1.78 points worse. It beat SPY return but had slightly worse drawdown and Sharpe. Micho RS20 added $8,848.82 and 8.84 return points, improved drawdown by 2.29 points, and raised Sharpe from 0.66 to 1.06. It slightly trailed SPY return but had lower drawdown and slightly higher Sharpe.

## Interpretation

Development and validation were directionally consistent: RS20 beat the control strongly for EMA and modestly for Micho in both periods. Selected candidates had materially higher mean RS20 than rejected candidates, confirming the intended selection mechanism. EMA's gain came with worse drawdown in both periods and fewer trades. Micho's drawdown worsened in development but improved in validation, so that risk trade-off was not stable.

Sprint 8 proved that AlphaPilot can calculate no-lookahead signal-time features, plug ranking policies into constrained portfolio selection, preserve accounting guarantees, and explain decisions. The repeated empirical improvement supports further research.

It did **not** prove RS20 is optimal, production-ready, robust to costs, statistically significant, or superior to other predeclared economic policies. It did not select EMA versus Micho, optimize the portfolio, or validate live execution. No alternative lookbacks were tested, and validation did not retune RS20.

## Known Limitations and Technical Debt

- **Survivorship bias:** all historical runs use today's active S&P 500 constituents, not point-in-time membership.
- **Zero-cost assumption:** $0 commission and 0 bps slippage make high-turnover results optimistic.
- **Benchmark limitations:** SPY does not reproduce strategy exposure, constraints, turnover, or cash timing; requested and actual dates can differ.
- **Open positions:** final positions are marked to the final close, not force-liquidated, and are absent from completed-trade metrics.
- Five current constituents lacked development history; data-provider history/corporate actions were not independently validated.
- Ten equal slots and frequent constraint can amplify a few decisions and large winners.
- Only two strategies and two periods were tested; there was no resampling, statistical significance, factor attribution, or cost sensitivity.
- Allocation failures are audited, but a future deliberately specified fallback policy could replace incidental next-candidate behavior.

## Sprint 9 Recommendation

After user/ChatGPT review, predeclare a ranking-robustness and attribution protocol: transaction-cost sensitivity, point-in-time universe improvements where feasible, multiple temporal folds, concentration/large-winner attribution, and a small set of economically motivated policies fixed before results. Preserve RS20 exactly as the Sprint 8 reference. No Sprint 9 implementation was started.

## Git State

Branch: `feature/candidate-ranking-engine`. All Sprint 8 source, test, and documentation changes remain uncommitted locally. Reports are Git-ignored. Codex performed no commit, push, PR, merge, force-push, or tag operation.

Final `git status --short`:

```text
 M AGENTS.md
 M backend/src/alphapilot/backtesting/candidate_selection.py
 M backend/src/alphapilot/backtesting/multi_portfolio.py
 M backend/src/alphapilot/backtesting/multi_portfolio_models.py
 M backend/src/alphapilot/backtesting/multi_portfolio_service.py
 M backend/src/alphapilot/cli/backtest_multi_portfolio.py
 M backend/tests/backtesting/test_multi_portfolio.py
 M docs/DECISIONS.md
 M docs/PROJECT_STATE.md
?? backend/src/alphapilot/backtesting/ranking_features.py
?? backend/tests/backtesting/test_candidate_selection.py
?? backend/tests/backtesting/test_ranking_features.py
?? docs/SPRINT8_COMPLETION_REPORT.md
?? docs/SPRINT8_PLAN.md
```

Final tracked-file `git diff --stat` (Git does not include untracked files in this output):

```text
 AGENTS.md                                          |  33 +++--
 .../alphapilot/backtesting/candidate_selection.py  |  44 +++++++
 .../src/alphapilot/backtesting/multi_portfolio.py  | 136 ++++++++++++++++++++-
 .../backtesting/multi_portfolio_models.py          |  43 +++++++
 .../backtesting/multi_portfolio_service.py         |  22 +++-
 .../src/alphapilot/cli/backtest_multi_portfolio.py | 101 ++++++++++++++-
 backend/tests/backtesting/test_multi_portfolio.py  | 119 ++++++++++++++++++
 docs/DECISIONS.md                                  |  18 ++-
 docs/PROJECT_STATE.md                              |  11 +-
 9 files changed, 499 insertions(+), 28 deletions(-)
```

Recommended commit message:

```text
feat: add deterministic candidate ranking and RS20 validation
```
