# AlphaPilot Sprint 9 Completion Report

## 1. Goal and Outcome

Sprint 9 tested whether frozen Relative Strength 20 (RS20) remained credible after predeclared transaction costs, three temporal folds, and return/concentration attribution. It completed successfully.

RS20 survived 5 bps and 15 bps per-side slippage for both strategies on the 2025–2026 validation period. Temporal evidence was materially weaker: RS20 beat alphabetical control in 2/3 EMA folds and only 1/3 Micho folds. Performance was concentrated in large contributors, particularly for Micho, and final open positions were a major part of reported gains. RS20 remains a useful AlphaPilot research baseline, but the evidence does not support calling it universally robust or deployment-ready.

No lookback, formula, strategy, cost, fold, max-position, or sizing parameter was retuned.

## 2. Architecture and Files

The Sprint preserved:

`Strategy -> Signal -> Candidate -> Frozen RS20 -> Selection -> Allocation -> Execution -> Accounting -> Metrics`

It added a parallel attribution layer after accounting:

`Executed trades + final open positions + raw OPEN references + final marks -> ticker/sector P&L -> friction reconciliation -> concentration diagnostics`

Created:

- `backend/src/alphapilot/backtesting/cost_scenarios.py`
- `backend/src/alphapilot/backtesting/portfolio_attribution.py`
- `backend/tests/backtesting/test_cost_scenarios.py`
- `backend/tests/backtesting/test_portfolio_attribution.py`
- `docs/SPRINT9_PLAN.md`
- `docs/SPRINT9_COMPLETION_REPORT.md`

Modified:

- `AGENTS.md`
- `backend/src/alphapilot/backtesting/multi_portfolio.py`
- `backend/src/alphapilot/backtesting/multi_portfolio_models.py`
- `backend/src/alphapilot/backtesting/multi_portfolio_service.py`
- `backend/src/alphapilot/cli/backtest_multi_portfolio.py`
- `backend/tests/backtesting/test_multi_portfolio_metrics.py`
- `backend/tests/backtesting/test_multi_portfolio_reporting.py`
- `docs/DECISIONS.md`
- `docs/PROJECT_STATE.md`

No strategy or ranking-feature source file changed.

## 3. Frozen Assumptions

- RS20 = stock 20-trading-bar return minus SPY 20-trading-bar return.
- Score uses information through signal day T only and is frozen before next-available-OPEN execution.
- Higher score first; ticker ascending tie-break; scored candidates precede unscored.
- EMA20 Pullback uses HYBRID with frozen 2% threshold.
- Micho V1 uses BOTH entries.
- Current active S&P 500 constituents, $100,000, 10 equal slots, whole shares, no leverage.
- Open positions are marked to final close and not force-liquidated.
- Alphabetical ordering is an economically meaningless control, not alpha.

## 4. Fixed Cost and Fold Protocol

| Cost | Commission/order | Slippage/side |
|---|---:|---:|
| COST_0 (`cost-0`) | $0 | 0 bps |
| COST_LOW (`cost-low`) | $0 | 5 bps |
| COST_CONSERVATIVE (`cost-conservative`) | $0 | 15 bps |

| Fold | Requested period | Actual period |
|---|---|---|
| Fold 1 | 2021-08-20–2022-12-31 | 2021-08-20–2022-12-30 |
| Fold 2 | 2023-01-01–2024-12-31 | 2023-01-03–2024-12-31 |
| Fold 3 | 2025-01-01–2026-08-20 | 2025-01-02–2026-08-20 |

Fold 1 processed 492 tickers and failed 10: `FDXF`, `GEV`, `HONA`, `KVUE`, `PSKY`, `Q`, `RDDT`, `SNDK`, `SOLV`, `VLTO`. Fold 2 processed 497 and failed `FDXF`, `HONA`, `PSKY`, `Q`, `SNDK`. Fold 3 and every cost run processed 502/502.

## 5. Attribution and Reconciliation Method

Dollar P&L is additive under the current accounting model and is used instead of geometrically additive return attribution.

For completed trades:

```text
gross realized P&L = shares × (raw exit OPEN - raw entry OPEN)
realized friction  = entry slippage + exit slippage + entry/exit commissions
net realized P&L   = gross realized P&L - realized friction
```

For final open positions:

```text
gross unrealized P&L = shares × (final marked close - raw entry OPEN)
open friction         = incurred entry slippage + entry commission
net unrealized P&L    = gross unrealized P&L - open friction
```

Every run reconciled exactly:

```text
initial equity + gross realized + gross unrealized - friction = final equity
initial equity + net realized + net unrealized = final equity
```

All 24 reported reconciliation residuals were exactly `$0.00000000`.

Contribution CSVs report ticker, stored sector, completed/open counts, realized/unrealized/combined P&L, friction, and net-gain contribution. Sector values came directly from Company records. All held tickers in these runs had sector data; no inferred or `Unknown` sector was required.

Positive-P&L HHI is `sum((positive ticker P&L / total positive P&L)^2)`. Negative contributors are excluded from this explicitly positive-contributor concentration measure.

## 6. Tests and Checks

Focused command from `backend/`:

```powershell
$env:DEBUG='false'
uv run pytest tests/backtesting/test_cost_scenarios.py tests/backtesting/test_portfolio_attribution.py tests/backtesting/test_multi_portfolio.py tests/backtesting/test_multi_portfolio_metrics.py tests/backtesting/test_multi_portfolio_reporting.py tests/backtesting/test_candidate_selection.py tests/backtesting/test_ranking_features.py tests/backtesting/test_engine.py tests/backtesting/test_portfolio.py tests/backtesting/test_simulator.py
```

Result: **39 passed in 3.17s**. Earlier targeted iteration: 29 passed after correcting a fixture whose default 10-slot budget could not buy a $100 share after slippage.

Full command:

```powershell
$env:DEBUG='false'
.\run_checks.ps1
```

Result: **passed**. Ruff passed and formatted one file (147 unchanged); mypy found no issues in 104 source files; pytest reported **118 passed in 10.44s**. `DEBUG=false` was scoped to child processes because the Codex host injects invalid `DEBUG=release`; application configuration was not changed.

## 7. Exact Experiment Commands

The initial `uv run alphapilot backtest-multi-portfolio ...` attempt failed before execution because this repository exposes no `main` through that entry point. No result was produced. All experiments used the registered `alphapilot-backtest-multi-portfolio` executable below.

Each of the following cost commands was executed for both strategy fragments and both policies:

```powershell
# Strategy fragments
--strategy ema20-pullback --exit-mode hybrid --hybrid-trend-threshold-pct 2
--strategy micho-150 --micho-entry-mode both

# Policies
--selection-policy ticker-ascending
--selection-policy relative-strength-20

# Cost runs (12 expanded combinations total)
uv run alphapilot-backtest-multi-portfolio <STRATEGY> <POLICY> --cost-scenario cost-0 --fold-label validation --start 2025-01-01 --end 2026-08-20 --capital 100000 --max-positions 10 --output-dir backtest_reports/sprint9/costs
uv run alphapilot-backtest-multi-portfolio <STRATEGY> <POLICY> --cost-scenario cost-low --fold-label validation --start 2025-01-01 --end 2026-08-20 --capital 100000 --max-positions 10 --output-dir backtest_reports/sprint9/costs
uv run alphapilot-backtest-multi-portfolio <STRATEGY> <POLICY> --cost-scenario cost-conservative --fold-label validation --start 2025-01-01 --end 2026-08-20 --capital 100000 --max-positions 10 --output-dir backtest_reports/sprint9/costs
```

Each fold command was executed for both strategy fragments and both policies at COST_0 (12 expanded combinations total):

```powershell
uv run alphapilot-backtest-multi-portfolio <STRATEGY> <POLICY> --cost-scenario cost-0 --fold-label fold-1 --start 2021-08-20 --end 2022-12-31 --capital 100000 --max-positions 10 --output-dir backtest_reports/sprint9/folds
uv run alphapilot-backtest-multi-portfolio <STRATEGY> <POLICY> --cost-scenario cost-0 --fold-label fold-2 --start 2023-01-01 --end 2024-12-31 --capital 100000 --max-positions 10 --output-dir backtest_reports/sprint9/folds
uv run alphapilot-backtest-multi-portfolio <STRATEGY> <POLICY> --cost-scenario cost-0 --fold-label fold-3 --start 2025-01-01 --end 2026-08-20 --capital 100000 --max-positions 10 --output-dir backtest_reports/sprint9/folds
```

Fold 3 was rerun rather than reusing Sprint 8 so the new attribution fields and fold metadata were generated. Reports contain six artifacts per run: summary, equity, trades, selection audit, ticker attribution, and sector attribution. There are 72 files in `costs/` and 72 in `folds/`; all remain Git-ignored.

## 8. Cost Sensitivity — EMA HYBRID 2%

| Policy | Cost | Final equity | Return | CAGR | DD | Sharpe | Turnover | Trades |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Control | 0 bps | $106,008.04 | 6.01% | 3.65% | 18.70% | 0.30 | 4367.21% | 229 |
| RS20 | 0 bps | $158,407.40 | 58.41% | 32.63% | 20.48% | 0.98 | 3248.09% | 151 |
| Control | 5 bps | $104,058.27 | 4.06% | 2.47% | 19.01% | 0.23 | 4316.90% | 229 |
| RS20 | 5 bps | $155,571.92 | 55.57% | 31.17% | 20.79% | 0.95 | 3212.65% | 151 |
| Control | 15 bps | $99,432.41 | -0.57% | -0.35% | 19.79% | 0.06 | 4219.27% | 229 |
| RS20 | 15 bps | $150,401.82 | 50.40% | 28.47% | 21.44% | 0.89 | 3154.56% | 151 |

RS20 minus control return was +52.40 points at 0 bps, +51.51 at 5 bps, and +50.97 at 15 bps. Relative to its COST_0 run, EMA RS20 lost $2,835.48 / 2.84 return points at 5 bps and $8,005.58 / 8.01 points at 15 bps. Control lost $1,949.77 / 1.95 points and $6,575.63 / 6.58 points.

EMA RS20 survived both costs convincingly relative to control. Its lower turnover/trade count helped, but cost drag was still material in absolute dollars. Drawdown remained worse than control at every cost and rose with friction.

## 9. Cost Sensitivity — Micho BOTH

| Policy | Cost | Final equity | Return | CAGR | DD | Sharpe | Turnover | Trades |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Control | 0 bps | $118,335.24 | 18.34% | 10.89% | 20.26% | 0.66 | 2183.93% | 126 |
| RS20 | 0 bps | $127,184.06 | 27.18% | 15.91% | 17.97% | 1.06 | 1963.38% | 100 |
| Control | 5 bps | $118,386.41 | 18.39% | 10.92% | 20.53% | 0.66 | 2141.88% | 125 |
| RS20 | 5 bps | $126,101.55 | 26.10% | 15.30% | 18.23% | 1.02 | 1944.50% | 100 |
| Control | 15 bps | $114,803.03 | 14.80% | 8.84% | 20.96% | 0.55 | 2139.98% | 126 |
| RS20 | 15 bps | $123,210.29 | 23.21% | 13.67% | 18.69% | 0.93 | 1935.73% | 104 |

RS20 minus control return was +8.84 points at 0 bps, +7.71 at 5 bps, and +8.41 at 15 bps. Micho RS20 lost $1,082.51 / 1.08 return points at 5 bps and $3,973.77 / 3.97 points at 15 bps. The 15 bps control lost $3,532.21 / 3.54 points.

The 5 bps control finished $51.17 above COST_0 rather than below it. This is not negative friction: whole-share flooring changed whether a candidate fit its slot, causing 125 rather than 126 completed trades and a different path/held ticker set (80 versus 79 unique). The identical-execution arithmetic test proves higher slippage cannot improve a fixed cash-flow sequence. Cost sensitivity in a constrained whole-share simulation includes both direct drag and path-dependent selection changes.

Micho RS20 survived both fixed costs, with lower turnover than control. The edge is smaller than EMA's and should not be extrapolated beyond these scenarios.

## 10. Temporal Robustness — EMA

| Fold | Policy | Return | CAGR | DD | Sharpe | PF | Win | Turnover | Trades | Exposure | Avg positions | SPY |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Control | 2.37% | 1.74% | 14.39% | 0.20 | 1.11 | 32.32% | 2016.70% | 99 | 48.39% | 4.83 | -13.12% |
| 1 | RS20 | -9.59% | -7.14% | 20.68% | -0.36 | 0.72 | 28.92% | 1602.98% | 83 | 52.28% | 5.19 | -13.12% |
| 2 | Control | 13.83% | 6.72% | 9.50% | 0.52 | 1.30 | 31.44% | 5559.61% | 264 | 96.70% | 9.69 | 52.44% |
| 2 | RS20 | 107.19% | 44.12% | 24.36% | 1.50 | 1.93 | 33.54% | 4331.91% | 164 | 96.04% | 9.66 | 52.44% |
| 3 | Control | 6.01% | 3.65% | 18.70% | 0.30 | 0.89 | 29.69% | 4367.21% | 229 | 90.74% | 9.12 | 29.27% |
| 3 | RS20 | 58.41% | 32.63% | 20.48% | 0.98 | 1.46 | 33.77% | 3248.09% | 151 | 92.51% | 9.26 | 29.27% |

RS20 minus control return: fold 1 **-11.96 points**, fold 2 **+93.36**, fold 3 **+52.40**.

EMA counts: RS20 beat total return in **2/3** folds, improved Sharpe in **2/3**, and improved (lowered) drawdown in **0/3**. Fold 1 is a clear failure relative to control, while folds 2/3 are extremely strong but more drawdown-heavy. EMA RS20 is directionally persistent in two later folds, not across the full predeclared temporal set.

## 11. Temporal Robustness — Micho

| Fold | Policy | Return | CAGR | DD | Sharpe | PF | Win | Turnover | Trades | Exposure | Avg positions | SPY |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Control | 24.83% | 17.71% | 16.48% | 0.87 | 1.35 | 25.89% | 2192.09% | 112 | 97.85% | 9.88 | -13.12% |
| 1 | RS20 | 18.62% | 13.37% | 18.85% | 0.65 | 1.15 | 24.14% | 2212.69% | 116 | 97.35% | 9.84 | -13.12% |
| 2 | Control | 35.75% | 16.57% | 9.17% | 1.06 | 1.21 | 20.83% | 2833.22% | 144 | 99.43% | 9.96 | 52.44% |
| 2 | RS20 | 32.88% | 15.33% | 17.57% | 0.99 | 1.20 | 20.57% | 2745.02% | 141 | 99.14% | 9.95 | 52.44% |
| 3 | Control | 18.34% | 10.89% | 20.26% | 0.66 | 1.07 | 15.87% | 2183.93% | 126 | 99.04% | 9.96 | 29.27% |
| 3 | RS20 | 27.18% | 15.91% | 17.97% | 1.06 | 1.10 | 20.00% | 1963.38% | 100 | 98.47% | 9.96 | 29.27% |

RS20 minus control return: fold 1 **-6.21 points**, fold 2 **-2.87**, fold 3 **+8.84**.

Micho counts: RS20 beat total return in **1/3** folds, improved Sharpe in **1/3**, and improved drawdown in **1/3**. The validation improvement did not persist backward into folds 1/2. Micho RS20 is not temporally robust under this protocol.

## 12. Return Attribution and Concentration

Validation COST_0:

| Strategy/policy | Realized P&L | Final-open unrealized P&L | Total P&L | Unique | Positive / negative | Top 1 / top 5 positive share | HHI |
|---|---:|---:|---:|---:|---:|---:|---:|
| EMA control | -$4,676.70 | $10,684.73 | $6,008.04 | 83 | 33 / 50 | 22.03% / 57.50% | 0.10 |
| EMA RS20 | $32,987.68 | $25,419.72 | $58,407.40 | 136 | 50 / 86 | 13.56% / 46.03% | 0.06 |
| Micho control | $1,841.06 | $16,494.18 | $18,335.24 | 79 | 21 / 57 | 38.00% / 82.48% | 0.21 |
| Micho RS20 | $2,946.02 | $24,238.04 | $27,184.06 | 99 | 27 / 72 | 25.97% / 66.28% | 0.12 |

Because negative contributors offset winners, top-5 shares of **net portfolio gain** were 353.78% (EMA control), 96.42% (EMA RS20), 190.57% (Micho control), and 135.48% (Micho RS20). Values over 100% are valid: the leading winners generated more than the final net gain and were offset by losses.

Top contributors:

- EMA control: `AMAT` +$8,143.78 (135.55% of net gain).
- EMA RS20: `LITE` +$16,582.25 (28.39%); next were `WDC`, `COHR`, open `CRL`, and `CIEN`.
- Micho control: `GLW` +$16,100.70 (87.81%).
- Micho RS20: `WBD` +$14,430.40 (53.08%); final-open `CASY`, `TGT`, and `STT` were the next three.

RS20 broadened the held universe and reduced HHI/top-positive shares versus control for both strategies. It did **not** eliminate concentration. EMA RS20 is materially but less excessively concentrated; Micho remains heavily dependent on a few winners.

Open positions matter greatly. EMA control's completed trades lost money and its entire net gain came from final marks. EMA RS20 had both positive realized and unrealized P&L, with 43.52% of net gain unrealized. Micho control and RS20 had approximately 89.96% and 89.16% of net gain unrealized. Micho conclusions are therefore highly sensitive to the final mark and are not equivalent to locked-in trade profits.

## 13. Sector Attribution

Stored sector coverage was complete for held tickers. Leading validation COST_0 sectors were:

- EMA RS20: Information Technology +$45,719.68 (78.28% of net gain), Health Care +$21,214.57 (36.32%). Losses in other sectors offset the total above 100%.
- EMA control: Information Technology +$7,807.12 (129.94%), Communication Services +$4,506.66 (75.01%).
- Micho RS20: Consumer Staples +$17,992.42 (66.19%), Communication Services +$15,298.53 (56.28%).
- Micho control: Information Technology +$11,125.19 (60.68%), Consumer Staples +$6,309.70 (34.41%).

Sector concentration reinforces the large-winner warning. These are current stored classifications, not point-in-time sector membership.

## 14. SPY and Cost/Turnover Interpretation

Fold SPY returns were -13.12%, +52.44%, and +29.27%. EMA RS20 beat SPY in folds 1 (despite losing money), 2, and 3 on total return; Micho RS20 beat SPY in fold 1, trailed in fold 2, and trailed slightly in fold 3. This does not make SPY an exposure-matched benchmark.

Cost-scenario SPY returns change slightly (29.27%, 29.22%, 29.12%) because the existing buy-and-hold simulator applies the same scenario friction. Strategy-versus-control remains the primary comparison.

Turnover is high for all variants. RS20 usually lowered turnover relative to control, which reduced friction, but 15 bps still removed 8.01 return points from EMA RS20 and 3.97 from Micho RS20. Costs did not erase the validation ranking edge, but realistic liquidity, spreads, market impact, and taxes are absent; surviving 15 bps is not deployment validation.

## 15. Bottom-Line Answers

1. **Does RS20 survive costs?** Yes, at 5 and 15 bps for both strategies relative to their controls.
2. **Does RS20 beat control across folds?** Partially: EMA 2/3; Micho 1/3.
3. **Broad or concentrated?** RS20 is broader than control but still materially concentrated; Micho is heavily concentrated.
4. **Extreme-winner dependence?** Micho depends more heavily on top contributors and final-open gains. EMA control also depends on a few winners; EMA RS20 is comparatively broader.
5. **Does turnover threaten realism?** Yes. Fixed costs did not erase the edge, but turnover makes unmodeled friction important.
6. **Realized versus unrealized?** Materially different. Micho's validation gain is about 89% unrealized; EMA RS20 is more balanced.
7. **Should RS20 remain the default research ranker?** Yes, as a frozen research baseline/reference. No, if “default” implies universal or production-ready superiority.

## 16. What Sprint 9 Proved and Did Not Prove

Sprint 9 proved AlphaPilot can run named costs/folds reproducibly; preserve no-lookahead ranking; attribute realized and final-open P&L by ticker/sector; measure concentration; and exactly reconcile final equity. It showed the validation-period RS20 edge survives 5/15 bps per-side slippage.

It did not prove temporal universality: fold 1 rejected EMA RS20 superiority, and folds 1/2 rejected Micho RS20 superiority. It did not model bid/ask spreads separately, liquidity, market impact, taxes, point-in-time membership, delisted stocks, or live fills. It did not prove statistical significance, causality, optimality, or future profitability. No parameter was retuned to repair inconvenient folds.

## 17. Known Limitations and Technical Debt

- **Survivorship bias/current constituents:** historical folds use today's active S&P 500 list, excluding former/delisted constituents.
- **Incomplete histories:** 10 fold-1 and 5 fold-2 current constituents lacked candles.
- **Benchmark limitations:** SPY is not exposure-, constraint-, turnover-, or cash-timing-matched.
- **Open-position handling:** final positions are marked, not force-closed; completed-trade metrics exclude them.
- **Large-winner/final-mark dependence:** especially material for Micho.
- **Cost model:** fixed price slippage is not an empirical liquidity/impact model. Whole-share path changes can make observed scenario drag non-monotonic.
- **Sector data:** current stored sectors are complete for these holdings but are not point-in-time classifications.
- **Fold count:** three regimes are informative but insufficient for statistical claims.
- **Attribution:** dollar P&L is exact and additive, but percentage contribution to a small/negative net gain can be unintuitive or exceed 100%.
- **Performance:** universe histories are loaded/evaluated sequentially; independent experiment processes can run concurrently, but one run remains slow.

## 18. Sprint 10 Recommendation

After user/ChatGPT review, Sprint 10 should address Portfolio Risk, Position Sizing & Decision API: explicit per-position risk, volatility-aware sizing, concentration/sector limits, cash reserve, portfolio-decision output, and an API contract for a future UI. The risk layer should consume Sprint 9 attribution and avoid treating RS20 as infallible. Point-in-time universe work and empirical execution-cost modeling remain important research infrastructure.

No Sprint 10 functionality was implemented.

## 19. Git State

Branch: `feature/ranking-robustness-analysis`. All Sprint 9 source, tests, and documents remain local and uncommitted. The 144 experiment artifacts are Git-ignored. No commit, push, PR, merge, force-push, or tag was performed by Codex.

Final `git status --short -uall`:

```text
 M AGENTS.md
 M backend/src/alphapilot/backtesting/multi_portfolio.py
 M backend/src/alphapilot/backtesting/multi_portfolio_models.py
 M backend/src/alphapilot/backtesting/multi_portfolio_service.py
 M backend/src/alphapilot/cli/backtest_multi_portfolio.py
 M backend/tests/backtesting/test_multi_portfolio_metrics.py
 M backend/tests/backtesting/test_multi_portfolio_reporting.py
 M docs/DECISIONS.md
 M docs/PROJECT_STATE.md
?? backend/src/alphapilot/backtesting/cost_scenarios.py
?? backend/src/alphapilot/backtesting/portfolio_attribution.py
?? backend/tests/backtesting/test_cost_scenarios.py
?? backend/tests/backtesting/test_portfolio_attribution.py
?? docs/SPRINT9_COMPLETION_REPORT.md
?? docs/SPRINT9_PLAN.md
```

Final tracked-file `git diff --stat` (untracked files are not included by Git):

```text
 AGENTS.md                                          |  36 +++----
 .../src/alphapilot/backtesting/multi_portfolio.py  |  10 ++
 .../backtesting/multi_portfolio_models.py          |   9 ++
 .../backtesting/multi_portfolio_service.py         |  15 ++-
 .../src/alphapilot/cli/backtest_multi_portfolio.py | 119 ++++++++++++++++++++-
 .../backtesting/test_multi_portfolio_metrics.py    |   3 +
 .../backtesting/test_multi_portfolio_reporting.py  |   7 ++
 docs/DECISIONS.md                                  |  17 ++-
 docs/PROJECT_STATE.md                              |  13 ++-
 9 files changed, 200 insertions(+), 29 deletions(-)
```

Recommended commit message:

```text
feat(backtesting): add ranking robustness and return attribution
```
