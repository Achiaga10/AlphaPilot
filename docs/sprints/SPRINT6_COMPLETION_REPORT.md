# AlphaPilot Sprint 6 Completion Report

## Status and Work Completed

Sprint 6 — Backtesting & Strategy Validation is complete. The final Micho 150 A/B/C validation ran successfully across all 502 current active S&P 500 constituents for 2025-01-01 through 2026-08-20. No Sprint 7 work was started, and Micho V1 was not changed.

This pass read `AGENTS.md`, `docs/PROJECT_STATE.md`, and `docs/DECISIONS.md`; inspected Git, `MichoEntryMode`, Micho classification, strategy construction, universe runner/CLI/reporting, diagnostics, entry analysis, and relevant tests; ran focused and full checks; ran all experiments; and cross-checked every CSV and summary.

The implementation was correct, so no source or test code changed. Verified: `both` remains the default; `breakout-only` permits only breakouts; `bounce-only` permits only bounces and does not reclassify a blocked breakout as a bounce; common exit/trend/warm-up/data/portfolio rules are unchanged; and mode-specific filenames prevent overwrites. This report is the only file created during this completion pass. Six experiment artifacts were generated in Git-ignored `backend/backtest_reports/micho_entry_modes_validation/`.

## Validation Performed

The initial focused-test attempt stopped before collection because host `DEBUG=release` is invalid for the application's boolean setting. Subsequent commands scoped `DEBUG=false` without changing or exposing `.env`.

From `backend/`:

```powershell
$env:DEBUG='false'; uv run pytest tests/strategy/test_micho150.py tests/strategy/test_factory.py tests/backtesting/test_strategy_universe.py tests/backtesting/test_entry_analysis.py tests/backtesting/test_engine.py tests/backtesting/test_simulator.py tests/backtesting/test_diagnostics.py
```

PASS: 25 tests in 2.28 seconds, covering mode isolation, construction, entry analytics, no lookahead, T+1 OPEN execution, final-day/repeated-BUY rules, and diagnostic attribution.

```powershell
$env:DEBUG='false'; .\run_checks.ps1
```

PASS: Ruff passed; formatting left 132 files unchanged; mypy found no issues in 95 source files; all 89 tests passed in 7.64 seconds.

Exact experiment commands:

```powershell
$env:DEBUG='false'; uv run alphapilot-backtest-strategy-universe --strategy micho-150 --micho-entry-mode both --start 2025-01-01 --end 2026-08-20 --output-dir backtest_reports/micho_entry_modes_validation
$env:DEBUG='false'; uv run alphapilot-backtest-strategy-universe --strategy micho-150 --micho-entry-mode breakout-only --start 2025-01-01 --end 2026-08-20 --output-dir backtest_reports/micho_entry_modes_validation
$env:DEBUG='false'; uv run alphapilot-backtest-strategy-universe --strategy micho-150 --micho-entry-mode bounce-only --start 2025-01-01 --end 2026-08-20 --output-dir backtest_reports/micho_entry_modes_validation
```

All passed: 502 successful, 0 failed each. Shared assumptions were $100,000 capital, 100% sizing, $0 commission, and 0 bps slippage. Ticker sets/modes matched exactly. Isolation: BOTH had 2,297 breakout/5,814 bounce signals; BREAKOUT_ONLY 2,297/0; BOUNCE_ONLY 0/5,814. All trades were classified: 2,646/2,646, 2,124/2,124, and 1,750/1,750.

## Micho A/B/C Results

These are independent single-stock 100%-capital simulations.

| Metric | BOTH | BREAKOUT_ONLY | BOUNCE_ONLY |
|---|---:|---:|---:|
| Successful / failed | 502 / 0 | 502 / 0 | 502 / 0 |
| Median total return | -1.03% | **-0.90%** | -1.36% |
| Median CAGR | -0.63% | **-0.56%** | -0.84% |
| Median max drawdown | 16.95% | **13.54%** | 15.22% |
| Median Sharpe | **-0.02** | -0.14 | -0.08 |
| Median profit factor | **0.19** | 0.08 | 0.06 |
| Median win rate | **16.67%** | 14.29% | 14.29% |
| Median exposure | 29.22% | **15.77%** | 23.11% |
| Median average holding | 23.00 days | **16.25 days** | 28.43 days |
| Median MFE | 5.24% | 4.09% | **5.87%** |
| Median MAE | -3.00% | **-2.74%** | -3.44% |
| Median peak giveback | 6.22% | **5.77%** | 7.15% |
| Profitable stocks | **216/502** | 189/502 | 203/502 |
| Beats SPY | **75/502** | 57/502 | 55/502 |
| Beats own B&H | 148/502 | 151/502 | **153/502** |
| No completed trades | **32/502** | 63/502 | 47/502 |
| Total completed trades | 2,646 | 2,124 | 1,750 |
| Mean total return | **9.65%** | 7.63% | 7.29% |

### Mode details and distribution

**BOTH:** 216 profitable, 75 SPY wins, 148 own-B&H wins, 32 no-trade stocks. Its 2,646 trades were 2,124 breakout and 522 bounce. Top five: LITE +684.96%, CIEN +305.67%, FIX +277.02%, INTC +275.81%, ECHO +272.39%; worst HON -54.53%. It led breadth, Sharpe, profit factor, win rate, mean, and SPY wins, but had the highest exposure/drawdown.

**BREAKOUT_ONLY:** 189 profitable, 57 SPY wins, 151 own-B&H wins, 63 no-trade stocks; 2,124 breakout trades. Top five: LITE +684.96%, CIEN +305.67%, FIX +277.02%, INTC +275.81%, GLW +180.81%; worst HON -52.83%. It led median return/CAGR, drawdown, exposure, holding, MAE, and giveback, but had weaker Sharpe/breadth than BOTH.

**BOUNCE_ONLY:** 203 profitable, 55 SPY wins, 153 own-B&H wins, 47 no-trade stocks; 1,750 bounce trades. Top five: LITE +642.43%, CIEN +325.41%, ECHO +322.34%, INTC +318.93%, GLW +179.70%; worst HON -52.76%. It led MFE and own-B&H wins, but had the worst return/CAGR, profit factor, MAE, giveback, and holding.

All modes had negative medians but positive means driven by extreme winners. Pairwise total returns: BREAKOUT_ONLY beat BOTH 258–107 with 137 ties; BOUNCE_ONLY beat BOTH 240–212 with 50 ties; BREAKOUT_ONLY beat BOUNCE_ONLY 258–226 with 18 ties. BOTH's superior mean/breadth despite many pairwise losses shows its right-tail trade-off: bounce often hurt or did nothing, but sometimes improved large-winner capture.

## Head-to-Head Conclusion

BREAKOUT_ONLY is the best isolated mode for the typical stock and capital efficiency: best median return (-0.90%), CAGR (-0.56%), drawdown (13.54%), exposure (15.77%), MAE (-2.74%), and giveback (5.77%), and it beat BOUNCE_ONLY on 258 versus 226 tickers.

It is not universally superior. BOTH had more profitable stocks (216), SPY wins (75), better Sharpe (-0.02), profit factor (0.19), win rate (16.67%), and mean return (+9.65%), showing better breadth/right-tail capture at greater exposure/drawdown. BOUNCE_ONLY was weakest overall but exceeded BREAKOUT_ONLY in profitable and own-B&H counts and captured large trends.

This supports a separately predefined future Micho V2 entry experiment, not a V1 change. All modes retained negative medians, low profit factors, and weak SPY breadth. Micho V1 remains `both`.

## Overall Sprint 6 Conclusion

Sprint 6 delivered deterministic no-lookahead replay, T+1 OPEN execution, accounting, benchmarks, diagnostics, MFE/MAE/giveback, universe comparison, exit experiments, and executed-entry isolation.

EMA20 proved more defensive with lower drawdown/giveback; EMA50 preserved trends and large winners. HYBRID 2%, selected on 2021-08-20–2024-12-31 and frozen, remained balanced in validation: approximately -0.44% return, -0.27% CAGR, 18.62% drawdown, 0.07 Sharpe, 0.76 profit factor, and 5.50% giveback. It is not yet the Scanner default; portfolio evidence is required.

Micho proved regime-sensitive/right-tail-dependent: five-year BOTH median was about +1.98%, versus -1.03% later. Breakouts are the cleaner typical-stock candidate, while combined entries improve breadth/large-winner capture. No mode warrants production promotion. Infrastructure is ready for portfolio research, but these remain independent simulations, not one investable portfolio.

## Known Limitations and Technical Debt

- **Survivorship bias:** current S&P 500 constituents exclude former/delisted members.
- **Incomplete history/benchmark alignment:** shorter stock histories can create differing actual periods and imperfect comparisons.
- **No multi-stock portfolio:** cash competition, simultaneous positions, ranking, constraints, turnover, and portfolio drawdown are absent.
- **Zero costs:** commission and slippage were zero.
- **Right-tail concentration and regime sensitivity:** a few winners dominate means; validation must not be retuned and called untouched.
- **Environment collision:** host `DEBUG=release` conflicts with the boolean setting; commands needed scoped `DEBUG=false`.
- **Ignored evidence:** raw reports are Git-ignored unless policy deliberately changes.

## Git State

Branch: `feature/backtesting-engine`.

Before this report, `git status --short` showed modified `.gitignore`, `backend/pyproject.toml`, `universe_market_sync_runner.py`, `ema20_pullback.py`, and `evaluation.py`; and untracked `AGENTS.md`, `backend/src/alphapilot/backtesting/`, four backtest CLI files, `exit_mode.py`, `factory.py`, `micho150.py`, `micho_entry_mode.py`, `name.py`, `backend/tests/backtesting/`, three strategy test files, `docs/DECISIONS.md`, and `docs/PROJECT_STATE.md`. This report adds `docs/SPRINT6_COMPLETION_REPORT.md`.

`git diff --stat` before the report (untracked excluded): 5 files changed, 100 insertions, 5 deletions. The six ignored artifacts are the BOTH, BREAKOUT_ONLY, and BOUNCE_ONLY CSV/summary pairs in the requested output directory. All Sprint 6 source, tests, CLI, and documentation files are ready for user review/commit. Nothing was committed or pushed.

Recommended commit message: `feat: complete Sprint 6 strategy validation`

## Sprint 7 Recommendation

Only after review, Sprint 7 should focus on multi-stock portfolio backtesting: ranking/selection, sizing, simultaneous positions, cash/exposure constraints, costs, portfolio equity/drawdown, turnover, and benchmark comparison. Any Micho V2 study should be separate and predefined. No Sprint 7 work was implemented.
