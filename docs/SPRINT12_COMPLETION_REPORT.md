# AlphaPilot Sprint 12 Completion Report

Date: 2026-08-27  
Branch: `feature/strategy-exit-research`  
Status: **COMPLETE LOCALLY — Sprint 13 NOT STARTED**

## 1. Sprint goal and bottom line

Sprint 12 tested whether deterministic protective stops, ATR trailing exits, or
fixed/partial profit taking improve the frozen EMA20 Pullback and Micho 150
research portfolios without changing entries, RS20, sizing, strategy exits, or
the UI.

The engineering work succeeded: AlphaPilot now has a replaceable, no-lookahead,
daily-OHLC trade-management overlay with auditable fills, exit reasons,
partial-exit accounting, recovery diagnostics, a governed research runner, and
full report artifacts.

The research conclusion is deliberately more cautious:

- **EMA:** the development-selected 3x ATR14 static stop improved aggregate
  development and current-data validation return/Sharpe/Calmar, but only 1/3
  folds improved return, Sharpe, or Calmar. Classification:
  **RESEARCH_ONLY**, not a promising baseline.
- **Micho:** the development-selected 1.5x ATR14 static stop improved aggregate
  development and validation return/Sharpe/Calmar, but validation drawdown
  worsened, one fold opposed it, 79.07% of measurable validation stop-outs
  recovered the entry price within 20 sessions, and validation concentration
  increased. Classification: **RESEARCH_ONLY**.
- No trailing or fixed/partial profit policy was selected. They generally
  truncated returns, especially Micho's right tail.
- The existing frozen strategy exits remain the recommended default research
  profiles. Sprint 12 stops remain optional research overlays only.

No strategy rule or normal UI/Decision API default was changed.

## 2. Protocol frozen before experiments

`docs/SPRINT12_PLAN.md` and the Sprint 12 section of `docs/DECISIONS.md` were
written before implementation/results. The frozen protocol specified:

- development: 2021-08-20 through 2024-12-31;
- validation: 2025-01-01 through 2026-08-20;
- folds: 2021-08-20–2022-12-31, 2023-01-01–2024-12-31, and the validation
  period;
- COST_LOW: commission $0, slippage 5 bps per side;
- current active S&P 500 constituents, $100,000, 10 positions;
- EMA: HYBRID 2%, RS20, equal-slot;
- Micho: BOTH, RS20, ATR-volatility-normalized;
- static ATR14 candidates: 1.5x, 2x, and 3x;
- trailing candidates: none, 2x ATR14, and 3x ATR14;
- profit candidates: none, one 50%-whole-share partial at +2R, and full +3R;
- highest development Calmar selection, then Sharpe, lower drawdown, CAGR;
- at least 80% retention of positive control CAGR for an optional overlay;
- no validation retuning, new multiple, or removed fold.

The final development selections were recorded in `docs/DECISIONS.md` and
encoded in `FROZEN_EXIT_SELECTIONS` before validation:

- EMA final: `atr-stop-3-0`, no additional overlay;
- Micho final: `atr-stop-1-5`, no additional overlay.

Validation/fold runner stages reject a configuration set that differs from the
frozen development selection.

## 3. Architecture implemented

The authoritative flow is now:

```text
frozen strategy signals
    -> ranked BUY candidate
    -> existing strategy-specific sizing
    -> shared-cash position
    -> replaceable TradeManagementPolicy
         |-- original strategy exit
         |-- initial ATR stop
         |-- optional monotonic ATR trail
         `-- optional fixed/partial profit action
    -> existing execution costs and portfolio accounting
    -> metrics, attribution, exit/recovery diagnostics
```

Key implementation points:

- `EMA20PullbackStrategy` and `Micho150Strategy` were not modified.
- `BacktestBarResult` now carries daily high/low so the existing shared-cash
  simulator can model pre-known stop/target touches.
- `TradeManagementPolicy` is a replaceable protocol; the configured V1 policy
  contains the frozen candidate family.
- Existing equal-slot, ATR-risk, and ATR-volatility-normalized sizing behavior
  remains separate and unchanged.
- `MultiPortfolioBacktestService.prepare()` loads/evaluates candles, signals,
  RS20, sectors, and the no-lookahead ATR14 series once. `run_prepared()` applies
  multiple exit policies to the exact same immutable facts.
- The Sprint 12 CLI accepts a declarative configuration matrix and never edits
  source between runs.
- Per-run JSON/CSV artifacts include metadata, equity, completed trade legs,
  final open positions, selection audit, ticker/sector attribution, stop
  recovery, and independent single-ticker universe comparisons.
- Hindsight recovery facts are generated only after execution completes and
  cannot influence the backtest.

## 4. Exact stop, trail, target, and ambiguity semantics

For a long entry filled at the existing slipped next-open execution price:

```text
initial_stop = entry_price - protective_multiple * ATR14_signal_day
R = entry_price - initial_stop
```

ATR14 is the mean of the latest 14 true ranges available through the BUY signal
day. A required missing/nonpositive ATR rejects the managed entry; no volatility
or stop is fabricated. An entry-created stop/target becomes active on the next
available session, ensuring it was known before the bar being tested.

For a pre-known long stop on day T:

```text
if open[T] <= stop: raw fill = open[T], gap_through = true
else if low[T] <= stop: raw fill = stop
else: no stop fill
```

Sell slippage then reduces the raw fill by 5 bps. A stop breached during T is
not canceled by a SELL signal generated from T's completed close; that signal
would normally execute T+1 open. A strategy SELL already pending from T-1 still
executes at T open unless T opens through the pre-known stop, in which case the
conservative stop reason is recorded.

For a trailing stop effective on T:

```text
highest_close = max(completed closes from entry through T-1)
candidate_trail = highest_close - trailing_multiple * ATR14_through_T_minus_1
effective_stop[T] = max(initial_stop, previous_effective_stop, candidate_trail)
```

The trail never decreases. T's high, close, or ATR cannot move the stop used on
T.

Profit target execution is:

```text
if open[T] >= target: raw fill = open[T]
else if high[T] >= target: raw fill = target
```

`PARTIAL_2R` sells `floor(current_shares * 0.50)` once; zero shares means no
partial. `FULL_3R` closes the full current position. If both a stop and target
are reachable within the same daily OHLC bar and opening prices do not resolve
the order, **STOP FIRST** is used. This is conservative and deterministic.

## 5. Exit reasons and accounting

Audited research exit reasons are:

- `STRATEGY_EXIT`
- `INITIAL_ATR_STOP`
- `ATR_TRAILING_STOP`
- `PARTIAL_PROFIT_2R`
- `FULL_PROFIT_3R`
- `FINAL_OPEN_POSITION` in the final-open artifact

Partial legs allocate entry commission proportionally by shares; every sell leg
incurs the configured sell friction. Remaining shares retain the residual cost
basis and entry commission. Across all 32 generated summary artifacts:

```text
cash + final marked position value = final equity
net realized P&L + net final unrealized P&L = final equity - initial capital
```

All 32 attribution reconciliation residuals were within `1E-8`; none failed.
Open positions are marked to final close and are not force-liquidated.

MFE/MAE for daily-OHLC exits use observable completed holding bars and the
executed reference; no unknowable intraday path before/after an exit is
invented. Holding period is reported in calendar days, while stop-to-reentry is
reported in portfolio trading sessions.

## 6. Files created

- `backend/src/alphapilot/backtesting/trade_management.py`
- `backend/src/alphapilot/backtesting/sprint12_protocol.py`
- `backend/src/alphapilot/backtesting/sprint12_reporting.py`
- `backend/src/alphapilot/backtesting/sprint12_diagnostics.py`
- `backend/src/alphapilot/cli/backtest_strategy_exits.py`
- `backend/tests/backtesting/test_trade_management.py`
- `backend/tests/backtesting/test_sprint12_protocol.py`
- `docs/SPRINT12_PLAN.md`
- `docs/SPRINT12_COMPLETION_REPORT.md`

## 7. Files modified

- `AGENTS.md`
- `backend/pyproject.toml`
- `backend/src/alphapilot/backtesting/engine.py`
- `backend/src/alphapilot/backtesting/models.py`
- `backend/src/alphapilot/backtesting/multi_portfolio.py`
- `backend/src/alphapilot/backtesting/multi_portfolio_metrics.py`
- `backend/src/alphapilot/backtesting/multi_portfolio_models.py`
- `backend/src/alphapilot/backtesting/multi_portfolio_service.py`
- `backend/src/alphapilot/portfolio/risk.py`
- `backend/tests/portfolio/test_risk.py`
- `docs/DECISIONS.md`
- `docs/PROJECT_STATE.md`

No frontend file, strategy class, database schema, migration, or normal
Decision API contract changed.

## 8. Tests added and coverage

`test_trade_management.py` covers the 1.5x/2x/3x formulas, declared config
validation, low touch/no touch, gap-open fill, sell slippage, next-session
activation, strategy-exit coexistence, missing ATR, prior-close/prior-ATR
trailing, monotonic floor, current-bar no-lookahead, intraday/gap trail, +2R
partial floor, one-share behavior, remaining position, +3R intraday/gap target,
same-bar stop-first, partial/full accounting, transaction friction, re-entry,
and deterministic repeated execution.

`test_sprint12_protocol.py` covers declared candidate parsing, rejection of
undeclared 2.5x-style tuning, exactly frozen validation/fold sets,
strategy-specific sizing, COST_LOW, metadata, and unchanged control config.

`test_risk.py` adds ATR-series immutability: adding a future/incomplete-session
candidate candle cannot change the ATR already calculated for a completed
signal day. Existing completed-session, ranking, portfolio, attribution,
strategy, and Scanner regressions all remain green.

Final focused command/result:

```text
$env:DEBUG='false'; uv run pytest tests/backtesting/test_trade_management.py tests/backtesting/test_sprint12_protocol.py tests/portfolio/test_risk.py -vv
31 passed
```

Final full gate:

```text
$env:DEBUG='false'; .\run_checks.ps1
Ruff: PASS
mypy: PASS (126 source files)
pytest: PASS (215 tests)
```

## 9. Phase 0 baseline reproduction and the validation data revision

Development controls reproduced the Sprint 10B COST_LOW values:

| Strategy | Final equity | Return | Max DD | Sharpe |
|---|---:|---:|---:|---:|
| EMA HYBRID 2% / RS20 / equal-slot | $180,145.51 | 80.15% | 26.43% | 0.87 |
| Micho BOTH / RS20 / vol-normalized | $148,434.79 | 48.43% | 15.74% | 0.77 |

The current validation controls did **not** reproduce older Sprint 10B
headlines. This was investigated before interpreting validation or running
folds:

- current versus archived Sprint 10B selection audits are identical through
  2025-07-22 signals and first diverge on 2025-07-23 execution;
- the UI's default full-candle sync range was 400 days, placing its boundary at
  the same point;
- a read-only timestamp query found 702,853 daily-candle rows across 503
  companies upserted on 2026-08-21, spanning 2019-07-17 through 2026-08-20;
- Sprint 11D records configured provider/feed `Alpaca / iex` and explicitly
  records that `DailyCandle` has no per-row feed provenance;
- the development controls ending 2024 remained unchanged.

The evidence supports a stored-data revision rather than an inactive-overlay
execution regression. Because row-level source provenance is absent, the exact
provider history of every revised row cannot be reconstructed; that is a known
technical limitation, not something inferred away.

Current Sprint 12 validation controls are therefore the comparable controls for
the current-data candidates. They are not directly comparable to the older
Sprint 10B validation headline:

| Strategy | Sprint 10B archived return | Current Sprint 12 return |
|---|---:|---:|
| EMA equal-slot | 55.57% | 18.06% |
| Micho vol-normalized | 35.36% | 28.51% |

Selections were already frozen before the current validation command ran, so
this data change did not cause parameter retuning. It does reduce confidence in
cross-sprint reproducibility and strengthens the case for research data
snapshots/provenance.

## 10. Data coverage, periods, costs, and benchmark

| Period | Actual portfolio period | Successful | Failed | SPY return |
|---|---|---:|---:|---:|
| Development | 2021-08-20–2024-12-31 | 497 | 5 | 33.06% |
| Fold 1 | 2021-08-20–2022-12-30 | 492 | 10 | -13.17% |
| Fold 2 | 2023-01-03–2024-12-31 | 497 | 5 | 52.39% |
| Validation / Fold 3 | 2025-01-02–2026-08-20 | 502 | 0 | 29.23% |

Development/Fold 2 missing histories: `FDXF`, `HONA`, `PSKY`, `Q`, `SNDK`.
Fold 1 additionally lacks `GEV`, `KVUE`, `RDDT`, `SOLV`, and `VLTO` for that
older window. Failures were identical within every control/candidate pair.

Every run uses commission $0 and fixed 5 bps slippage per side. This is more
realistic than zero cost but still omits spreads, market impact, borrow,
liquidity limits, taxes, and variable fees. SPY is an external reference, not a
like-for-like risk/exposure-controlled benchmark.

## 11. Phase 1 — EMA protective-stop development

### Portfolio and trade metrics

| Metric | Control | ATR 1.5x | ATR 2x | ATR 3x selected |
|---|---:|---:|---:|---:|
| Final equity | $180,145.51 | $163,157.10 | $170,387.79 | $184,652.98 |
| Return | 80.15% | 63.16% | 70.39% | 84.65% |
| CAGR | 19.12% | 15.66% | 17.16% | 19.99% |
| Max drawdown | 26.43% | 31.21% | 25.77% | 26.47% |
| Sharpe | 0.869 | 0.769 | 0.813 | 0.908 |
| Calmar | 0.723 | 0.502 | 0.666 | **0.755** |
| Profit factor | 1.467 | 1.280 | 1.335 | 1.507 |
| Win rate | 32.02% | 24.76% | 28.93% | 31.89% |
| Average trade | 2.05% | 1.16% | 1.46% | 2.24% |
| Median trade | -3.07% | -3.24% | -3.10% | -3.02% |
| Completed exit legs | 253 | 307 | 280 | 254 |
| Average holding days | 36.94 | 29.29 | 32.69 | 36.63 |
| Exposure | 78.79% | 75.96% | 77.52% | 78.39% |
| Turnover | 5,511.94% | 6,641.66% | 6,044.22% | 5,620.06% |
| Worst trade | -17.53% | -23.95% | -14.04% | -17.53% |
| 5th-percentile trade | -10.27% | -7.85% | -9.44% | -9.53% |
| Median MAE | -5.15% | -3.70% | -4.27% | -4.67% |
| Median MFE | 5.38% | 4.09% | 4.57% | 5.36% |
| Median giveback | 8.98% | 7.38% | 7.93% | 8.58% |
| Stop hits / gap stops | 0 / 0 | 158 / 31 | 87 / 29 | 26 / 4 |
| Strategy exits / final open | 253 / 10 | 149 / 10 | 193 / 10 | 228 / 10 |
| Net realized P&L | $45,251.47 | $29,696.16 | $33,438.17 | $48,354.21 |
| Net unrealized P&L | $34,894.04 | $33,460.94 | $36,949.62 | $36,298.77 |
| Top-5 positive-P&L share | 61.48% | 61.37% | 58.89% | 60.82% |

The declared rule selected 3x because it had the highest development Calmar.
The gain was modest and did not reduce development drawdown, but it improved
return, Sharpe, profit factor, realized P&L, and tail percentile without the
whipsaw of tighter stops. Its 26 stops included four gaps, 11 re-entries, two
repeated stop-outs, and 288.18 average sessions to re-entry.

Independent single-ticker breadth for 3x was 130 better, 138 worse, and 229
unchanged versus control. The shared-portfolio improvement was therefore not a
broad majority effect; ranking, freed slots, and portfolio path mattered.

## 12. Phase 1 — Micho protective-stop development

| Metric | Control | ATR 1.5x selected | ATR 2x | ATR 3x |
|---|---:|---:|---:|---:|
| Final equity | $148,434.79 | $159,501.79 | $150,508.47 | $153,309.31 |
| Return | 48.43% | 59.50% | 50.51% | 53.31% |
| CAGR | 12.46% | 14.88% | 12.92% | 13.54% |
| Max drawdown | 15.74% | 16.18% | 18.78% | 15.91% |
| Sharpe | 0.770 | 0.936 | 0.824 | 0.826 |
| Calmar | 0.791 | **0.920** | 0.688 | 0.851 |
| Profit factor | 1.309 | 1.524 | 1.420 | 1.426 |
| Win rate | 21.88% | 21.12% | 22.59% | 22.17% |
| Average trade | 0.59% | 0.95% | 1.00% | 0.88% |
| Median trade | -2.08% | -2.37% | -2.08% | -2.07% |
| Completed exit legs | 256 | 251 | 239 | 230 |
| Average holding days | 43.38 | 41.81 | 44.44 | 47.57 |
| Exposure | 87.92% | 87.75% | 88.16% | 88.55% |
| Turnover | 4,396.86% | 4,351.44% | 4,170.25% | 3,910.77% |
| Worst trade | -12.01% | -9.48% | -11.90% | -17.83% |
| 5th-percentile trade | -6.54% | -4.99% | -5.85% | -7.53% |
| Median MAE | -3.01% | -2.82% | -3.02% | -3.05% |
| Median MFE | 3.00% | 3.03% | 3.20% | 3.26% |
| Median giveback | 6.04% | 5.92% | 6.07% | 6.30% |
| Stop hits / gap stops | 0 / 0 | 94 / 18 | 45 / 7 | 17 / 5 |
| Strategy exits / final open | 256 / 10 | 157 / 10 | 194 / 10 | 213 / 10 |
| Net realized P&L | $15,132.99 | $23,373.33 | $18,931.60 | $19,556.04 |
| Net unrealized P&L | $33,301.80 | $36,128.45 | $31,576.87 | $33,753.26 |
| Top-5 positive-P&L share | 46.84% | 42.73% | 41.60% | 45.69% |

The rule selected 1.5x. It raised development drawdown by 0.44 points but
improved Calmar, Sharpe, return, worst trade, fifth percentile, realized P&L,
and concentration. It caused 94 stops, 18 gaps, 19 re-entries, nine repeated
stop-outs, and 97.84 average sessions to re-entry.

Single-ticker breadth was 223 better, 217 worse, and 57 unchanged—more balanced
than EMA but still not overwhelming.

## 13. Phase 2 — trailing development results

| Strategy | Configuration | Return | CAGR | Max DD | Sharpe | Calmar | Stops | Re-entries |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EMA | 3x static only | 84.65% | 19.99% | 26.47% | 0.908 | 0.755 | 26 | 11 |
| EMA | + trailing 2x | 10.64% | 3.05% | 22.84% | 0.260 | 0.134 | 470 | 238 |
| EMA | + trailing 3x | 74.04% | 17.90% | 27.17% | 0.854 | 0.659 | 245 | 103 |
| Micho | 1.5x static only | 59.50% | 14.88% | 16.18% | 0.936 | 0.920 | 94 | 19 |
| Micho | + trailing 2x | 1.03% | 0.30% | 16.33% | 0.092 | 0.019 | 653 | 384 |
| Micho | + trailing 3x | 18.01% | 5.04% | 17.92% | 0.412 | 0.282 | 421 | 198 |

EMA trailing 3x retained 89.53% of stop-only CAGR but worsened drawdown and
Calmar; it was not selected. EMA trailing 2x and both Micho trails created
extreme whipsaw/re-entry and destroyed return. Classification:

- EMA trailing 2x: **REJECTED**.
- EMA trailing 3x: **RESEARCH_ONLY**, but not selected.
- Micho trailing 2x/3x: **REJECTED**.

## 14. Phase 3 — fixed/partial profit development results

| Strategy | Configuration | Return | CAGR | Max DD | Sharpe | Calmar | Profit actions | Top-5 positive share |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EMA | 3x static only | 84.65% | 19.99% | 26.47% | 0.908 | 0.755 | 0 | 60.82% |
| EMA | partial +2R | 46.25% | 11.96% | 23.34% | 0.694 | 0.512 | 44 | 47.56% |
| EMA | full +3R | 45.42% | 11.77% | 27.09% | 0.687 | 0.435 | 40 | 37.64% |
| Micho | 1.5x static only | 59.50% | 14.88% | 16.18% | 0.936 | 0.920 | 0 | 42.73% |
| Micho | partial +2R | 34.97% | 9.32% | 13.31% | 0.795 | 0.700 | 83 | 35.24% |
| Micho | full +3R | 18.20% | 5.10% | 19.59% | 0.416 | 0.260 | 154 | 12.98% |

Both partial policies reduced concentration and drawdown, but retained only
59.83% (EMA) and 62.62% (Micho) of positive stop-only CAGR—below the frozen 80%
gate. Full +3R was worse. A higher win rate was not treated as success when
right-tail/CAGR was destroyed. All fixed/partial candidates are **REJECTED**.

## 15. Frozen final validation — EMA

| Metric | Existing strategy exit control | 3x ATR static stop | Difference |
|---|---:|---:|---:|
| Final equity | $118,058.42 | $137,544.44 | +$19,486.02 |
| Return | 18.06% | 37.54% | +19.49 pts |
| CAGR | 10.73% | 21.61% | +10.89 pts |
| Max drawdown | 23.74% | 22.48% | -1.25 pts |
| Sharpe | 0.478 | 0.769 | +0.291 |
| Calmar | 0.452 | 0.961 | +0.509 |
| Profit factor | 1.048 | 1.269 | +0.222 |
| Win rate | 31.01% | 30.52% | -0.49 pts |
| Average / median trade | 1.32% / -3.11% | 2.26% / -2.88% | improved |
| Completed exit legs | 158 | 154 | -4 |
| Average holding days | 33.62 | 33.82 | +0.20 |
| Exposure | 92.21% | 92.20% | flat |
| Turnover | 3,110.64% | 3,208.39% | +97.75 pts |
| Worst / 5th percentile | -38.51% / -15.56% | -35.47% / -12.63% | improved |
| Median MAE / MFE | -4.90% / 6.49% | -4.99% / 6.29% | slightly worse |
| Median giveback | 10.60% | 10.32% | improved |
| Stops / gaps / strategy exits | 0 / 0 / 158 | 24 / 7 / 130 | — |
| Re-entry / repeated stop-outs | 0 / 0 | 8 / 1 | — |
| Net realized / unrealized P&L | $3,631.28 / $14,427.14 | $19,920.84 / $17,623.59 | realized improved |
| Friction | $1,555.29 | $1,604.17 | +$48.88 |
| Top-1 / top-5 positive share | 11.95% / 44.34% | 10.42% / 41.07% | less concentrated |
| Positive-P&L HHI | 0.0569 | 0.0530 | less concentrated |

The stop retained more than 80% of positive control CAGR, reduced validation
drawdown, and improved Sharpe/Calmar. It also changed the current-data portfolio
from slightly below SPY (18.06% versus 29.23%) to above SPY (37.54%). However,
fold evidence below shows the benefit is concentrated in Fold 3, and the
validation data revision reduces reproducibility confidence. Classification:
**RESEARCH_ONLY**, not `PROMISING_RESEARCH_BASELINE`.

Validation single-ticker breadth: 83 better, 80 worse, 339 unchanged. The
portfolio improvement is not evidence that most stocks benefited.

## 16. Frozen final validation — Micho

| Metric | Existing strategy exit control | 1.5x ATR static stop | Difference |
|---|---:|---:|---:|
| Final equity | $128,508.10 | $163,686.12 | +$35,178.02 |
| Return | 28.51% | 63.69% | +35.18 pts |
| CAGR | 16.65% | 35.32% | +18.68 pts |
| Max drawdown | 11.44% | 13.44% | **+2.00 pts worse** |
| Sharpe | 1.228 | 1.577 | +0.349 |
| Calmar | 1.456 | 2.629 | +1.174 |
| Profit factor | 1.194 | 2.449 | +1.255 |
| Win rate | 21.36% | 25.25% | +3.89 pts |
| Average / median trade | 0.33% / -2.59% | 8.73% / -2.49% | highly right-skewed |
| Completed exit legs | 103 | 99 | -4 |
| Average holding days | 44.17 | 49.56 | +5.39 |
| Exposure | 88.65% | 87.12% | -1.53 pts |
| Turnover | 1,769.06% | 1,845.14% | +76.07 pts |
| Worst / 5th percentile | -15.01% / -8.95% | -11.89% / -7.01% | improved |
| Median MAE / MFE | -3.76% / 2.91% | -3.16% / 3.25% | improved |
| Median giveback | 6.41% | 6.92% | worse |
| Stops / gaps / strategy exits | 0 / 0 / 103 | 44 / 12 / 55 | — |
| Re-entry / repeated stop-outs | 0 / 0 | 7 / 1 | — |
| Net realized / unrealized P&L | $4,767.91 / $23,740.19 | $32,961.25 / $30,724.87 | realized improved |
| Friction | $884.51 | $922.55 | +$38.04 |
| Top-1 / top-5 positive share | 25.92% / 65.25% | 30.13% / 73.44% | **more concentrated** |
| Positive-P&L HHI | 0.1206 | 0.1505 | **more concentrated** |

Return, Sharpe, Calmar, loss tail, and realized P&L improved strongly, and the
candidate beat SPY's 29.23% return. But validation drawdown materially worsened
and concentration increased. It therefore fails the predeclared promising
heuristic. Classification: **RESEARCH_ONLY**.

Validation breadth was 163 better, 171 worse, and 168 unchanged. One matched
top-ten control winner, NFLX, was cut early: approximately +$1,556 in control
versus -$471 under the stop. The portfolio still improved through different
capital paths and larger contributors, not through uniformly better exits.

## 17. Temporal folds

Fold 3 is the configuration-identical validation artifact, reused after
successful metadata/config verification; it was not redundantly rerun.

### EMA

| Fold | Control return | Stop return | Control DD | Stop DD | Control Sharpe | Stop Sharpe | Control Calmar | Stop Calmar |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 (2021-08-20–2022-12-31) | -10.35% | -10.71% | 21.18% | 21.51% | -0.394 | -0.425 | -0.364 | -0.371 |
| 2 (2023-01-01–2024-12-31) | 97.60% | 80.51% | 25.95% | 23.51% | 1.401 | 1.288 | 1.570 | 1.467 |
| 3 (validation) | 18.06% | 37.54% | 23.74% | 22.48% | 0.478 | 0.769 | 0.452 | 0.961 |

EMA candidate improvement counts:

- total return: **1/3**;
- max drawdown: **2/3**;
- Sharpe: **1/3**;
- Calmar: **1/3**.

Aggregate development and validation both favored the 3x stop on
return/Sharpe/Calmar, but the non-overlapping folds show one-period dependence.

### Micho

| Fold | Control return | Stop return | Control DD | Stop DD | Control Sharpe | Stop Sharpe | Control Calmar | Stop Calmar |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 4.74% | 8.60% | 15.74% | 14.96% | 0.269 | 0.413 | 0.220 | 0.418 |
| 2 | 34.05% | 24.03% | 17.09% | 13.21% | 1.070 | 0.868 | 0.927 | 0.864 |
| 3 (validation) | 28.51% | 63.69% | 11.44% | 13.44% | 1.228 | 1.577 | 1.456 | 2.629 |

Micho candidate improvement counts:

- total return: **2/3**;
- max drawdown: **2/3**;
- Sharpe: **2/3**;
- Calmar: **2/3**.

Micho is more directionally supported than EMA, but Fold 2 sacrifices return
and risk-adjusted performance, while Fold 3 worsens drawdown and becomes more
concentrated.

## 18. False-stop, recovery, and whipsaw diagnostics

Recovery is explicitly ex-post hindsight: a stop is counted as recovered if a
subsequent close reaches the original entry price within 20 trading sessions.
It never changes execution.

| Strategy/period | Stops | Measurable | Recovered | Recovery rate | Avg +5 | Avg +10 | Avg +20 |
|---|---:|---:|---:|---:|---:|---:|---:|
| EMA development 3x | 26 | 26 | 6 | 23.08% | -0.07% | 1.02% | -0.19% |
| EMA validation 3x | 24 | 24 | 10 | 41.67% | 1.68% | 3.48% | 1.68% |
| Micho development 1.5x | 94 | 94 | 59 | 62.77% | 0.45% | 0.65% | 1.97% |
| Micho validation 1.5x | 44 | 43 | 34 | **79.07%** | 3.72% | 5.22% | 7.34% |

All 26 EMA development stop-outs and all 94 Micho development stop-outs had a
later strategy SELL signal in available history. Validation counts were 24/24
for EMA and 38/44 for Micho. This does not prove the strategy exit would have
been more profitable because portfolio re-entry/capital paths differ, but it
shows why stop adoption must be cautious.

The tight/trailing policies show severe whipsaw. For example, Micho trailing 2x
generated 653 stops and 384 re-entries, versus 94 stops/19 re-entries for the
selected static policy, while reducing return from 59.50% to 1.03%.

## 19. Large winners, MFE/giveback, and concentration

- EMA 3x did not exit any of the ten matched top development control trades
  early; their strategy exit days remained unchanged. Its top-5 positive share
  was nearly unchanged in development and lower in validation.
- Micho 1.5x did not exit any of nine matched top development winners early,
  but did cut one of eight matched top validation winners (NFLX) early.
- Micho validation top-1/top-5 concentration rose from 25.92%/65.25% to
  30.13%/73.44%; HHI rose from 0.121 to 0.150. Its headline gain is materially
  dependent on a few contributors.
- Fixed profits reduced measured concentration but destroyed CAGR. This is the
  expected failure mode for trend/right-tail systems and is why lower
  concentration alone was not treated as success.
- Final open positions remain material: EMA final candidate unrealized P&L was
  $17,623.59; Micho was $30,724.87. Micho still has substantial final-open and
  right-tail dependence.

## 20. Strategy-specific classifications and recommended research profiles

### EMA20 Pullback

```text
Entry: frozen EMA20 Pullback
Ranking: RS20 research baseline
Sizing: equal-slot
Strategy exit: HYBRID 2%
Protective stop: existing exit remains default; 3x ATR14 is RESEARCH_ONLY
Trailing: none; 2x rejected, 3x research-only/not selected
Profit management: none; partial +2R and full +3R rejected
Overall status: existing profile remains PROMISING_RESEARCH_BASELINE;
                Sprint 12 stop overlay is RESEARCH_ONLY
```

Biggest weakness discovered: EMA 3x looks strong in aggregate validation but
only Fold 3 improves return/Sharpe/Calmar. The evidence is path/period dependent
and recent-data revision further weakens portability.

### Micho 150

```text
Entry: Micho V1 BOTH
Ranking: RS20 research baseline
Sizing: ATR-volatility-normalized
Strategy exit: close below SMA150/trend breakdown
Protective stop: existing exit remains default; 1.5x ATR14 is RESEARCH_ONLY
Trailing: none; both declared trails rejected
Profit management: none; partial +2R and full +3R rejected
Overall status: existing profile remains PROMISING_RESEARCH_BASELINE;
                Sprint 12 stop overlay is RESEARCH_ONLY
```

Biggest weakness discovered: Micho's stop improves headline performance while
validation drawdown/concentration worsen and 79.07% of measurable stopped
positions recover their entry within 20 sessions. It remains highly exposed to
rare winners and final-open P&L.

## 21. What Sprint 12 proved

- Experimental trade management can be added without changing strategy entry
  or original exit classes.
- Static, trailing, partial, and fixed exits can be simulated deterministically
  from daily OHLC with conservative gap/same-bar rules and existing friction.
- No-lookahead trail and ATR semantics are testable and enforced.
- Partial exits and final-open positions reconcile exactly.
- A tighter stop is not automatically better: 1.5x harmed EMA, while 3x was its
  best development candidate; strategy-specific conclusions matter.
- Trailing/fixed profits can improve superficial drawdown/win-rate metrics while
  destroying right-tail return.
- Current evidence does not justify making any tested stop the automatic
  strategy default.

## 22. What Sprint 12 did not prove

- No stop is production-ready or broker-executable.
- Daily OHLC does not reveal intraday event order, liquidity, spread, or exact
  stop slippage.
- Results do not establish causality or future performance.
- The current S&P universe is not point-in-time.
- The validation set was not immune to later source-data revisions.
- The experiment did not optimize ATR period, multiples, targets, entries,
  ranking, sizing, max positions, costs, or sector/risk constraints.
- The research does not validate short positions, leverage, fractional shares,
  live orders, tax handling, or authenticated broker state.

## 23. Known limitations and technical debt

1. **Survivorship bias/current constituents:** historical experiments use the
   current active S&P 500 list, not historical membership.
2. **Data provenance/versioning:** candle rows do not store provider/feed or
   immutable research snapshot IDs. The 2026-08 sync materially changed the
   validation baseline and prevents exact old-data reproduction.
3. **Daily-bar path ambiguity:** stop-first is conservative but not necessarily
   the real intraday sequence.
4. **Gap and liquidity model:** gap fills use the open plus fixed slippage; no
   volume/impact/spread model exists.
5. **Cost model:** fixed 5 bps and zero commission are simplified.
6. **Open positions:** final holdings are marked, not liquidated; Micho remains
   particularly dependent on unrealized winners.
7. **Partial-leg metrics:** a partial sale is an executed trade leg and counts
   in completed-leg/win-rate metrics; position-lifecycle metrics remain a
   possible refinement.
8. **Recovery diagnostic:** the later SELL signal may occur after a legitimate
   re-entry and is hindsight context, not a counterfactual portfolio replay.
9. **No live stop state:** stop/trail values are research simulator state only;
   no persisted or broker order lifecycle exists.

## 24. Recommendation for Sprint 13

Do not automatically wire the Sprint 12 stops into normal UI defaults.

Recommended Sprint 13 direction:

**Research Dataset Versioning & Strategy-Specific Configuration Profiles**

First add reproducible research data manifests/snapshot hashes and candle
provider/feed provenance so a result can be rerun against the same data. Then
package the already-frozen existing EMA and Micho controls as backend-owned
strategy profiles. Advanced research mode may expose the Sprint 12 static stops
with explicit `RESEARCH_ONLY` labels, but normal mode should retain existing
strategy exits. The frontend must consume backend profiles and must not
duplicate stop/strategy logic.

## 25. Exact experiment commands executed

All commands ran from `backend/` with `$env:DEBUG='false'`.

### Baseline reproduction

```powershell
uv run alphapilot-backtest-strategy-exits --strategy ema20-pullback --start 2021-08-20 --end 2024-12-31 --stage baseline --fold-label development --configuration control --output-dir backtest_reports/sprint12
uv run alphapilot-backtest-strategy-exits --strategy micho-150 --start 2021-08-20 --end 2024-12-31 --stage baseline --fold-label development --configuration control --output-dir backtest_reports/sprint12
```

### Protective-stop development

```powershell
uv run alphapilot-backtest-strategy-exits --strategy ema20-pullback --start 2021-08-20 --end 2024-12-31 --stage development --fold-label protective-development --configuration control --configuration atr-stop-1-5 --configuration atr-stop-2-0 --configuration atr-stop-3-0 --output-dir backtest_reports/sprint12/protective_stops
uv run alphapilot-backtest-strategy-exits --strategy micho-150 --start 2021-08-20 --end 2024-12-31 --stage development --fold-label protective-development --configuration control --configuration atr-stop-1-5 --configuration atr-stop-2-0 --configuration atr-stop-3-0 --output-dir backtest_reports/sprint12/protective_stops
```

### Trailing and profit development

```powershell
uv run alphapilot-backtest-strategy-exits --strategy ema20-pullback --start 2021-08-20 --end 2024-12-31 --stage development --fold-label management-development --configuration atr-stop-3-0 --configuration atr-stop-3-0+atr-trailing-2-0 --configuration atr-stop-3-0+atr-trailing-3-0 --configuration atr-stop-3-0+partial-2r --configuration atr-stop-3-0+full-3r --output-dir backtest_reports/sprint12/exit_management
uv run alphapilot-backtest-strategy-exits --strategy micho-150 --start 2021-08-20 --end 2024-12-31 --stage development --fold-label management-development --configuration atr-stop-1-5 --configuration atr-stop-1-5+atr-trailing-2-0 --configuration atr-stop-1-5+atr-trailing-3-0 --configuration atr-stop-1-5+partial-2r --configuration atr-stop-1-5+full-3r --output-dir backtest_reports/sprint12/exit_management
```

### Frozen validation

```powershell
uv run alphapilot-backtest-strategy-exits --strategy ema20-pullback --start 2025-01-01 --end 2026-08-20 --stage validation --fold-label validation --configuration control --configuration atr-stop-3-0 --output-dir backtest_reports/sprint12/validation
uv run alphapilot-backtest-strategy-exits --strategy micho-150 --start 2025-01-01 --end 2026-08-20 --stage validation --fold-label validation --configuration control --configuration atr-stop-1-5 --output-dir backtest_reports/sprint12/validation
```

### Temporal folds

```powershell
uv run alphapilot-backtest-strategy-exits --strategy ema20-pullback --start 2021-08-20 --end 2022-12-31 --stage fold --fold-label fold-1 --configuration control --configuration atr-stop-3-0 --output-dir backtest_reports/sprint12/folds
uv run alphapilot-backtest-strategy-exits --strategy micho-150 --start 2021-08-20 --end 2022-12-31 --stage fold --fold-label fold-1 --configuration control --configuration atr-stop-1-5 --output-dir backtest_reports/sprint12/folds
uv run alphapilot-backtest-strategy-exits --strategy ema20-pullback --start 2023-01-01 --end 2024-12-31 --stage fold --fold-label fold-2 --configuration control --configuration atr-stop-3-0 --output-dir backtest_reports/sprint12/folds
uv run alphapilot-backtest-strategy-exits --strategy micho-150 --start 2023-01-01 --end 2024-12-31 --stage fold --fold-label fold-2 --configuration control --configuration atr-stop-1-5 --output-dir backtest_reports/sprint12/folds
```

Fold 3 reused the exact validation artifacts because period, universe, strategy,
ranking, sizing, costs, and exit configurations were identical.

## 26. Git status and recommended commit

Current branch: `feature/strategy-exit-research`.

All Sprint 12 source, tests, and documentation are local and uncommitted. Raw
artifacts under `backend/backtest_reports/sprint12/` are Git-ignored. No commit,
push, PR, merge, tag, or force operation was performed.

`git status --short`:

```text
 M AGENTS.md
 M backend/pyproject.toml
 M backend/src/alphapilot/backtesting/engine.py
 M backend/src/alphapilot/backtesting/models.py
 M backend/src/alphapilot/backtesting/multi_portfolio.py
 M backend/src/alphapilot/backtesting/multi_portfolio_metrics.py
 M backend/src/alphapilot/backtesting/multi_portfolio_models.py
 M backend/src/alphapilot/backtesting/multi_portfolio_service.py
 M backend/src/alphapilot/portfolio/risk.py
 M backend/tests/portfolio/test_risk.py
 M docs/DECISIONS.md
 M docs/PROJECT_STATE.md
?? backend/src/alphapilot/backtesting/sprint12_diagnostics.py
?? backend/src/alphapilot/backtesting/sprint12_protocol.py
?? backend/src/alphapilot/backtesting/sprint12_reporting.py
?? backend/src/alphapilot/backtesting/trade_management.py
?? backend/src/alphapilot/cli/backtest_strategy_exits.py
?? backend/tests/backtesting/test_sprint12_protocol.py
?? backend/tests/backtesting/test_trade_management.py
?? docs/SPRINT12_COMPLETION_REPORT.md
?? docs/SPRINT12_PLAN.md
```

Tracked-file `git diff --stat` (Git does not include the nine untracked files in
this statistic):

```text
 AGENTS.md                                          |  43 +--
 backend/pyproject.toml                             |   1 +
 backend/src/alphapilot/backtesting/engine.py       |   2 +
 backend/src/alphapilot/backtesting/models.py       |  10 +
 .../src/alphapilot/backtesting/multi_portfolio.py  | 372 +++++++++++++++++++--
 .../backtesting/multi_portfolio_metrics.py         |  47 ++-
 .../backtesting/multi_portfolio_models.py          |  43 ++-
 .../backtesting/multi_portfolio_service.py         | 166 +++++++--
 backend/src/alphapilot/portfolio/risk.py           |  18 +
 backend/tests/portfolio/test_risk.py               |  12 +
 docs/DECISIONS.md                                  |  83 ++++-
 docs/PROJECT_STATE.md                              |  37 +-
 12 files changed, 733 insertions(+), 101 deletions(-)
```

Recommended commit message:

```text
feat: complete Sprint 12 strategy exit research
```

Sprint 13 has not been started.
