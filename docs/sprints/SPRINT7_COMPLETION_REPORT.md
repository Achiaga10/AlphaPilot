# AlphaPilot Sprint 7 Completion Report

## 1. Goal and Outcome

Sprint 7 — Multi-Stock Portfolio Backtesting — completed successfully locally. AlphaPilot now supports one shared portfolio in which multiple ticker signals compete for the same cash and configurable position slots. No Sprint 8 work was started, no strategy parameters were optimized, Micho V1 was unchanged, and HYBRID remains frozen at 2%.

## 2. Architecture Implemented

The implementation preserves the existing single-stock APIs and separates concerns:

1. Existing `BacktestingEngine` evaluates each ticker day by day with no future candles.
2. `MultiPortfolioBacktestService` loads current constituents, stock warm-up histories, and SPY history, then creates per-ticker `BacktestResult` objects.
3. `MultiPortfolioSimulator` converts each ticker's signal into an order at its next available bar and merges executable events onto one calendar.
4. `CandidateSelectionPolicy` keeps candidate ordering outside accounting. `TickerAscendingSelectionPolicy` provides the deterministic non-alpha baseline.
5. The simulator handles exits, entries, allocation, shared cash, positions, trades, and one daily equity curve.
6. A separate calculator produces portfolio and completed-trade metrics without changing existing single-stock definitions.
7. The CLI reuses `create_strategy()` and emits summary, equity CSV, and completed-trade CSV artifacts plus SPY comparison.

## 3. Files Created

Source:

- `backend/src/alphapilot/backtesting/candidate_selection.py`
- `backend/src/alphapilot/backtesting/multi_portfolio.py`
- `backend/src/alphapilot/backtesting/multi_portfolio_metrics.py`
- `backend/src/alphapilot/backtesting/multi_portfolio_models.py`
- `backend/src/alphapilot/backtesting/multi_portfolio_service.py`
- `backend/src/alphapilot/cli/backtest_multi_portfolio.py`

Tests:

- `backend/tests/backtesting/test_multi_portfolio.py`
- `backend/tests/backtesting/test_multi_portfolio_metrics.py`
- `backend/tests/backtesting/test_multi_portfolio_reporting.py`

Documentation:

- `docs/SPRINT7_PLAN.md`
- `docs/SPRINT7_COMPLETION_REPORT.md`

## 4. Files Modified

- `AGENTS.md`: moved continuity rules to Sprint 7 and its completion handoff.
- `backend/pyproject.toml`: registered `alphapilot-backtest-multi-portfolio`.
- `docs/PROJECT_STATE.md`: marked Sprint 6 merged and Sprint 7 complete locally; recorded architecture and baselines.
- `docs/DECISIONS.md`: recorded frozen Sprint 7 execution/allocation/selection decisions and interpretation limits.

No existing strategy implementation or existing single-stock backtesting API was modified.

## 5. Exact Execution Semantics

- Long-only; no leverage; one position per ticker; whole shares.
- A signal on ticker day T executes at that ticker's next available bar OPEN. Different tickers may therefore have different next-available dates.
- The final bar has no successor, so its BUY or SELL cannot execute.
- On each execution date, SELLs are processed first in ticker order. Their proceeds are immediately available for same-day BUY allocation.
- BUY while held and SELL while flat are ignored.
- Eligible BUYs are ordered by the injected selection policy.
- Buy slippage increases OPEN; sell slippage decreases OPEN. Commission is charged per executed order.
- Cash is checked after every transaction and may never be negative.
- The union of evaluated ticker days forms the daily portfolio curve. Each held ticker is valued at that day's close when available, otherwise its latest known close is carried forward.
- Open positions are not force-liquidated. They remain open and are marked to market at the final available close.

## 6. Capital Allocation and Candidate Selection

Configuration includes initial capital, maximum concurrent positions, commission, and slippage. Baseline allocation targets `current execution-time portfolio equity / max_positions` per new position, capped by cash after commission. Shares are floored to whole units; candidates unable to buy one share are skipped. Existing positions are not rebalanced.

The existing Scanner filters BUY signals but exposes no ranking score. Sprint 7 therefore uses stable normalized ticker-ascending order. This is deliberately labeled `ticker-ascending-baseline`, is pluggable, and is not alpha. When cash or slots are scarce, alphabetical priority affects holdings and results.

## 7. Tests Added and Requirements Covered

The new tests prove:

- two simultaneous holdings and one shared cash balance
- nonnegative cash
- maximum-position enforcement
- equal-slot sizing and whole-share flooring
- commissions and buy/sell slippage
- next-available-OPEN entry and exit
- exits releasing cash before same-day entries
- repeated BUY and flat SELL ignored
- final-day BUY and SELL ignored
- deterministic ticker priority under scarcity
- daily equity includes every holding
- final open positions are marked to market
- return, CAGR-supporting curve, drawdown, Sharpe inputs, exposure, trade, turnover, and concurrency metrics
- reports disclose sizing, selection, final-position handling, survivorship bias, and benchmark caveat

Existing `test_engine.py` continues to prove no lookahead. Existing single-stock portfolio and simulator tests remained green.

## 8. Exact Validation Commands and Results

Host `DEBUG=release` conflicts with the application's boolean `DEBUG`, so commands scoped `DEBUG=false` to the child process without changing `.env`.

Focused command from `backend/`:

```powershell
$env:DEBUG='false'; uv run pytest tests/backtesting/test_multi_portfolio.py tests/backtesting/test_multi_portfolio_metrics.py tests/backtesting/test_multi_portfolio_reporting.py tests/backtesting/test_engine.py tests/backtesting/test_portfolio.py tests/backtesting/test_simulator.py
```

Result: PASS — 22 tests passed in 1.62 seconds.

Full quality gate:

```powershell
$env:DEBUG='false'; .\run_checks.ps1
```

Result: PASS.

- Ruff check/format/check passed; 7 new/changed files were formatted and 134 left unchanged.
- mypy passed with no issues in 101 source files.
- pytest passed: 101 tests in 9.46 seconds.

## 9. Baseline Portfolio Configuration

- Requested period: 2025-01-01 through 2026-08-20
- Actual equity-curve period: 2025-01-02 through 2026-08-20 (409 rows)
- Universe: 502 current active S&P 500 constituents
- Initial capital: $100,000
- Maximum positions: 10
- Sizing: fixed equal slot (`current equity / 10`), no rebalance
- Commission: $0
- Slippage: 0 bps
- Selection: stable ticker ascending, non-alpha engine-validation baseline
- End handling: 10 open positions marked to market, not force-closed, in each run

## 10. Exact Baseline Commands

EMA20 Pullback HYBRID 2%:

```powershell
$env:DEBUG='false'; uv run alphapilot-backtest-multi-portfolio --strategy ema20-pullback --exit-mode hybrid --hybrid-trend-threshold-pct 2 --start 2025-01-01 --end 2026-08-20 --capital 100000 --max-positions 10 --commission 0 --slippage-bps 0 --output-dir backtest_reports/multi_portfolio_validation
```

Micho V1 BOTH:

```powershell
$env:DEBUG='false'; uv run alphapilot-backtest-multi-portfolio --strategy micho-150 --micho-entry-mode both --start 2025-01-01 --end 2026-08-20 --capital 100000 --max-positions 10 --commission 0 --slippage-bps 0 --output-dir backtest_reports/multi_portfolio_validation
```

Both completed with 502 successful and 0 failed tickers.

## 11. Baseline Results and SPY Comparison

| Metric | EMA HYBRID 2% | Micho V1 BOTH | SPY Buy & Hold |
|---|---:|---:|---:|
| Final equity | $106,008.04 | $118,335.24 | $129,272.49 |
| Total return | +6.01% | +18.34% | +29.27% |
| CAGR | +3.65% | +10.89% | +17.07% |
| Max drawdown | 18.70% | 20.26% | 18.93% |
| Sharpe | 0.30 | 0.66 | 1.03 |
| Portfolio exposure | 90.74% | 99.04% | N/A |
| Completed trades | 229 | 126 | N/A |
| Win rate | 29.69% | 15.87% | N/A |
| Profit factor | 0.89 | 1.07 | N/A |
| Average completed trade | -0.13% | +0.14% | N/A |
| Turnover | 4,367.21% | 2,183.93% | N/A |
| Average open positions | 9.12 | 9.96 | N/A |
| Maximum concurrent positions | 10 | 10 | N/A |

Artifact verification:

- Both equity curves contain 409 rows from 2025-01-02 through 2026-08-20.
- Minimum cash was $2.195 for EMA and $0.135 for Micho; cash never became negative.
- Maximum observed positions was 10 in both runs.
- Trade CSVs contain 229 EMA trades across 81 tickers and 126 Micho trades across 75 tickers.
- Final CSV equity exactly matches summary equity before display rounding.

The portfolio underperformed SPY in both baseline runs. This is not a valid strategy-ranking conclusion because alphabetical allocation decides which simultaneous signals receive scarce capital. Zero costs also make reported results optimistic.

## 12. Report Artifacts

Six Git-ignored files were created in `backend/backtest_reports/multi_portfolio_validation/`: summary, equity CSV, and trade CSV for each strategy. Filenames encode strategy and strategy-specific mode/threshold.

## 13. Known Limitations and Technical Debt

- **Survivorship bias:** current, not historical, S&P 500 constituents were used.
- **Benchmark alignment:** SPY aligns to the actual portfolio curve, but incomplete/newer ticker histories remain and carried-forward closes may occur on missing ticker dates.
- **Ranking limitation:** alphabetical priority is deterministic but economically meaningless; it can materially change allocations and returns.
- **Zero transaction costs:** both baselines used zero commission/slippage.
- **Open trades:** final positions are marked to market but excluded from completed-trade win rate, profit factor, and average trade.
- **Turnover definition:** gross executed entry/exit notional plus still-open entry cost divided by initial capital; it is not annualized.
- **Sequential loading/evaluation:** 502 histories are loaded and evaluated sequentially, and the existing replay engine builds available-history slices day by day. Correctness is adequate, but performance can be improved without changing semantics.
- **No corporate-action/universe history model:** results rely on stored adjusted market data and current constituent membership.
- **Baseline sizing only:** fixed equal slots do not model volatility targeting, sector caps, liquidity, or risk budgets.
- **No portfolio diagnostics for open trades:** MFE/MAE and unrealized trade diagnostics were not added because they were not required for engine validation.

## 14. What Sprint 7 Proved

- Existing deterministic strategy signals can drive one shared-cash portfolio end to end.
- Multiple positions, scarce slots, shared capital, T+1 OPEN execution, exits-before-entries, costs, daily valuation, benchmark comparison, and reporting work together.
- The engine enforces whole shares, maximum positions, and nonnegative cash.
- Existing single-stock research infrastructure remains compatible and green.

## 15. What Sprint 7 Did Not Prove

- It did not prove EMA HYBRID or Micho is a superior production strategy.
- It did not validate alphabetical selection as alpha.
- It did not optimize position count, sizing, ranking, costs, or any strategy rule.
- It did not eliminate survivorship bias, incomplete histories, or benchmark-alignment limitations.
- It did not model live execution, liquidity, taxes, sector/risk limits, or News AI.

## 16. Sprint 8 Recommendation

After user/ChatGPT review, Sprint 8 should define and validate a deterministic, economically meaningful candidate-ranking layer using development/validation discipline. It should add ranking diagnostics and allocation attribution, test transaction-cost sensitivity, and consider sector/liquidity/risk constraints. Historical constituent data and performance optimization should be scoped separately. Do not change strategy rules merely to improve this baseline.

## 17. Git State

The branch is `feature/portfolio-backtesting-engine`. All Sprint 7 changes are local and uncommitted. No commit, push, PR, merge, tag, or remote-history operation was performed by Codex.

Final `git status --short -uall`:

```text
 M AGENTS.md
 M backend/pyproject.toml
 M docs/DECISIONS.md
 M docs/PROJECT_STATE.md
?? backend/src/alphapilot/backtesting/candidate_selection.py
?? backend/src/alphapilot/backtesting/multi_portfolio.py
?? backend/src/alphapilot/backtesting/multi_portfolio_metrics.py
?? backend/src/alphapilot/backtesting/multi_portfolio_models.py
?? backend/src/alphapilot/backtesting/multi_portfolio_service.py
?? backend/src/alphapilot/cli/backtest_multi_portfolio.py
?? backend/tests/backtesting/test_multi_portfolio.py
?? backend/tests/backtesting/test_multi_portfolio_metrics.py
?? backend/tests/backtesting/test_multi_portfolio_reporting.py
?? docs/SPRINT7_COMPLETION_REPORT.md
?? docs/SPRINT7_PLAN.md
```

Final `git diff --stat` (Git does not include untracked-file contents in this output):

```text
 AGENTS.md              | 154 +++++++------------------------------------------
 backend/pyproject.toml |   1 +
 docs/DECISIONS.md      |  32 +++++++++-
 docs/PROJECT_STATE.md  |  75 +++++++++++++++++++++---
 4 files changed, 120 insertions(+), 142 deletions(-)
```

Files ready for review/commit are the 6 new source files, 3 new test files, 2 new Sprint 7 documents, and modifications to `AGENTS.md`, `backend/pyproject.toml`, `docs/PROJECT_STATE.md`, and `docs/DECISIONS.md`. Raw report artifacts remain ignored.

Recommended commit message:

```text
feat(backtesting): add shared multi-stock portfolio engine
```
