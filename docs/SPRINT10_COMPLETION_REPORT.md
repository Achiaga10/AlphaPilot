# AlphaPilot Sprint 10 Completion Report

## 1. Goal and Outcome

Sprint 10 turned the research portfolio stack into a deterministic portfolio-decision backend with ATR risk features, replaceable sizing, portfolio constraints, structured decisions/reasons, risk diagnostics, and a typed FastAPI contract for the future UI.

Sprint 10 completed successfully. The architecture and constraints worked end to end. Empirically, frozen ATR-risk sizing reduced EMA drawdown but destroyed much of its return; for Micho it reduced return and slightly worsened drawdown. No risk or strategy parameter was retuned.

## 2. Architecture Implemented

```text
Market/strategy signal
  -> frozen RS20 rank
  -> signal-day ATR14
  -> sizing policy (equal-slot or atr-risk)
  -> risk/weight/cash/sector/max-position constraints
  -> structured portfolio decision
  -> existing execution/accounting (backtest) or typed advisory plan (API)
```

Risk feature calculation, sizing, decision policy, execution/accounting, and API schemas remain separate. Existing equal-slot behavior and T+1 OPEN execution are preserved.

## 3. Files Created

- `backend/src/alphapilot/api/routes/portfolio.py`
- `backend/src/alphapilot/portfolio/__init__.py`
- `backend/src/alphapilot/portfolio/decisions.py`
- `backend/src/alphapilot/portfolio/risk.py`
- `backend/src/alphapilot/portfolio/sizing.py`
- `backend/src/alphapilot/schemas/portfolio.py`
- `backend/tests/api/test_portfolio_decisions.py`
- `backend/tests/portfolio/test_decisions.py`
- `backend/tests/portfolio/test_risk.py`
- `backend/tests/portfolio/test_sizing.py`
- `docs/SPRINT10_PLAN.md`
- `docs/SPRINT10_COMPLETION_REPORT.md`

## 4. Files Modified

- `AGENTS.md`
- `backend/src/alphapilot/api/router.py`
- `backend/src/alphapilot/backtesting/multi_portfolio.py`
- `backend/src/alphapilot/backtesting/multi_portfolio_models.py`
- `backend/src/alphapilot/backtesting/multi_portfolio_service.py`
- `backend/src/alphapilot/cli/backtest_multi_portfolio.py`
- `backend/tests/backtesting/test_multi_portfolio.py`
- `docs/DECISIONS.md`
- `docs/PROJECT_STATE.md`

No ranking or strategy implementation changed.

## 5. Exact Risk and Sizing Formulas

Using candles available through signal day T only:

```text
TR = max(high-low, abs(high-previous_close), abs(low-previous_close))
ATR14 = mean(latest 14 true ranges)
stop_distance = 2 × ATR14
risk_budget = portfolio_equity × 1%
risk_shares = floor(risk_budget / stop_distance)
weight_shares = floor((equity × 10%) / slipped entry price)
cash_shares = floor((cash - commission - equity × 10% reserve) / entry price)
portfolio_risk_shares = floor((equity × 8% - current modeled risk) / stop_distance)
sector_shares = floor((equity × 30% - current sector value) / entry price)
final shares = min(all nonnegative caps)
position modeled risk = final shares × frozen entry stop_distance
portfolio modeled risk = sum(active position modeled risks)
```

ATR14 needs 15 bars: one previous close plus 14 true ranges. Future bars are filtered. Missing ATR yields `INSUFFICIENT_HISTORY`; nonpositive risk distance yields `INVALID_RISK_DISTANCE`.

Whole shares only, no leverage, and cash cannot become negative.

## 6. Exact Constraint Semantics

- **Cash reserve:** a new entry may not intentionally lower cash below 10% of current execution-time equity after commission. Existing positions are not closed if later market movement changes the ratio.
- **Position weight:** new entry notional is capped at 10% of current equity.
- **Portfolio risk:** a new entry must keep frozen modeled active-position risk at or below 8% of current equity.
- **Sector:** a new entry must keep its sector value at or below 30% of current equity at entry. Subsequent appreciation may move the sector above 30%; there is no forced rebalance.
- **Missing sector:** normalized to one explicit `Unclassified` risk bucket; never inferred.
- **Maximum positions:** 10, hard constraint.
- **SELL:** processed/approved independently of entry risk constraints.

## 7. Decision Model and Reasons

Portfolio decisions are distinct from strategy signals. Decision types:

- `BUY`
- `HOLD`
- `SELL`
- `SKIP`

Stable reason codes:

- `BUY_APPROVED`
- `SELL_APPROVED`
- `ALREADY_HELD`
- `NO_POSITION_TO_SELL`
- `MAX_POSITIONS`
- `INSUFFICIENT_CASH`
- `CASH_RESERVE`
- `MAX_POSITION_WEIGHT`
- `PORTFOLIO_RISK_LIMIT`
- `SECTOR_LIMIT`
- `INSUFFICIENT_HISTORY`
- `INVALID_RISK_DISTANCE`
- `RANKING_NOT_SELECTED`
- `NO_ACTION`

BUY decisions expose ticker/signal/rank, price, ATR, stop proxy, risk budget, allocation, weight, shares, modeled risk, sector, and before/after sector weight. SELL decisions expose current shares and estimated proceeds. Plans expose current equity/cash/reserve, current and available modeled risk, open positions, and decisions.

## 8. API Contract and UI Readiness

Added:

- `GET /api/v1/portfolio/risk-config`
- `POST /api/v1/portfolio/decisions`

Requests are typed Pydantic schemas containing strategy/ranking metadata, current in-memory portfolio state, risk configuration, and enriched candidate facts. Clients do not send raw candle histories. Responses contain a typed portfolio summary, echoed config/metadata, and UI-friendly decision records with stable enums and Decimal serialization.

The API is advisory: it neither persists state nor submits broker orders. It is ready for a UI MVP to consume the plan contract and display decisions. Automated current-market signal/ATR enrichment and broker account synchronization remain backend adapter work; the frontend must not duplicate this domain logic.

## 9. Tests and Validation

Tests created/modified cover TR, ATR14, no-lookahead, insufficient/zero ATR, exact 1%/2× sizing, whole-share flooring, weight/cash/reserve/risk/sector caps, missing sector, ranked ordering, BUY-to-SKIP, unrestricted SELL, held/flat behavior, reason codes, plan consistency, risk aggregation, deterministic output, unchanged equal-slot behavior, realistic API response, default config, validation errors, serialization, and all Sprint 7–9 guarantees.

Focused command:

```powershell
$env:DEBUG='false'
uv run pytest tests/portfolio tests/api/test_portfolio_decisions.py tests/backtesting/test_multi_portfolio.py tests/backtesting/test_multi_portfolio_metrics.py tests/backtesting/test_multi_portfolio_reporting.py tests/backtesting/test_portfolio_attribution.py tests/backtesting/test_ranking_features.py tests/backtesting/test_candidate_selection.py tests/backtesting/test_engine.py tests/backtesting/test_portfolio.py tests/backtesting/test_simulator.py
```

Result: **51 passed in 3.38s**. A later reporting-focused run passed 13/13 after adding daily risk columns.

Final quality command:

```powershell
$env:DEBUG='false'
.\run_checks.ps1
```

Result: **passed**. Ruff passed (158 files unchanged), mypy found no issues in 110 source files, and pytest reported **131 passed in 10.11s**. `DEBUG=false` was scoped only to child processes; application configuration was not changed.

## 10. Exact Experiment Commands

From `backend/`, each command used the frozen common suffix:

```powershell
--selection-policy relative-strength-20 --cost-scenario cost-low --fold-label sprint10 --start 2025-01-01 --end 2026-08-20 --capital 100000 --max-positions 10 --risk-per-position-pct 1 --atr-period 14 --atr-stop-multiple 2 --max-position-weight-pct 10 --max-portfolio-risk-pct 8 --minimum-cash-reserve-pct 10 --max-sector-weight-pct 30 --output-dir backtest_reports/sprint10
```

Exact four expanded invocations:

```powershell
uv run alphapilot-backtest-multi-portfolio --strategy ema20-pullback --exit-mode hybrid --hybrid-trend-threshold-pct 2 --selection-policy relative-strength-20 --sizing-policy equal-slot --cost-scenario cost-low --fold-label sprint10 --start 2025-01-01 --end 2026-08-20 --capital 100000 --max-positions 10 --risk-per-position-pct 1 --atr-period 14 --atr-stop-multiple 2 --max-position-weight-pct 10 --max-portfolio-risk-pct 8 --minimum-cash-reserve-pct 10 --max-sector-weight-pct 30 --output-dir backtest_reports/sprint10
uv run alphapilot-backtest-multi-portfolio --strategy ema20-pullback --exit-mode hybrid --hybrid-trend-threshold-pct 2 --selection-policy relative-strength-20 --sizing-policy atr-risk --cost-scenario cost-low --fold-label sprint10 --start 2025-01-01 --end 2026-08-20 --capital 100000 --max-positions 10 --risk-per-position-pct 1 --atr-period 14 --atr-stop-multiple 2 --max-position-weight-pct 10 --max-portfolio-risk-pct 8 --minimum-cash-reserve-pct 10 --max-sector-weight-pct 30 --output-dir backtest_reports/sprint10
uv run alphapilot-backtest-multi-portfolio --strategy micho-150 --micho-entry-mode both --selection-policy relative-strength-20 --sizing-policy equal-slot --cost-scenario cost-low --fold-label sprint10 --start 2025-01-01 --end 2026-08-20 --capital 100000 --max-positions 10 --risk-per-position-pct 1 --atr-period 14 --atr-stop-multiple 2 --max-position-weight-pct 10 --max-portfolio-risk-pct 8 --minimum-cash-reserve-pct 10 --max-sector-weight-pct 30 --output-dir backtest_reports/sprint10
uv run alphapilot-backtest-multi-portfolio --strategy micho-150 --micho-entry-mode both --selection-policy relative-strength-20 --sizing-policy atr-risk --cost-scenario cost-low --fold-label sprint10 --start 2025-01-01 --end 2026-08-20 --capital 100000 --max-positions 10 --risk-per-position-pct 1 --atr-period 14 --atr-stop-multiple 2 --max-position-weight-pct 10 --max-portfolio-risk-pct 8 --minimum-cash-reserve-pct 10 --max-sector-weight-pct 30 --output-dir backtest_reports/sprint10
```

The four runs were repeated once after adding missing daily risk columns to the equity CSV. Metrics reproduced; corrected artifacts are the final set. All 502 tickers succeeded in every run. Twenty-four Git-ignored files were created (summary, equity, trades, selection audit, ticker attribution, and sector attribution per run).

## 11. EMA HYBRID 2% Results

| Metric | Equal-slot | ATR-risk | Change |
|---|---:|---:|---:|
| Final equity | $155,571.92 | $115,835.23 | -$39,736.69 |
| Total return | 55.57% | 15.84% | -39.73 pp |
| CAGR | 31.17% | 9.44% | -21.73 pp |
| Max drawdown | 20.79% | 16.06% | **-4.73 pp** |
| Sharpe | 0.95 | 0.52 | -0.43 |
| Exposure | 92.49% | 80.43% | -12.06 pp |
| Completed trades | 151 | 149 | -2 |
| Win rate | 33.77% | 34.90% | +1.13 pp |
| Profit factor | 1.43 | 0.98 | -0.45 |
| Turnover | 3212.65% | 2473.91% | -738.74 pp |
| Average positions | 9.26 | 9.24 | -0.02 |
| SPY return | 29.22% | 29.22% | — |

ATR-risk reduced drawdown, exposure, and turnover, but destroyed most of the return and reduced Sharpe. Equal-slot beat SPY; ATR-risk trailed SPY.

ATR-risk cash averaged $19,384.66 (19.57% of equity) and ended at $11,455.35 versus equal-slot $7,218.33 average (7.51%) and $74.83 final.

ATR-risk approved 159 and skipped 22,481 candidates: 22,456 ranking/not-selected (mostly full slots), 23 sector-limit, and 2 cash-reserve. Approved average position weight was 8.07%; average position modeled risk $565.90. Average/max portfolio risk was $5,230.66/$8,088.62; maximum daily risk/equity was 7.49%, below 8%. Maximum observed sector weight was 37.18% after appreciation; no selected entry exceeded 30%.

Concentration improved slightly: positive-P&L top-five share 45.96% to 44.56%; HHI remained 0.06. The top contributor changed from `LITE` ($15,905.32) to `TER` ($8,825.65), showing reduced single-winner dollars. Net realized P&L fell from +$30,743.00 to -$905.31; the ATR-risk gain depended entirely on $16,740.54 of final-open unrealized P&L.

## 12. Micho BOTH Results

| Metric | Equal-slot | ATR-risk | Change |
|---|---:|---:|---:|
| Final equity | $126,101.55 | $115,417.38 | -$10,684.17 |
| Total return | 26.10% | 15.42% | -10.68 pp |
| CAGR | 15.30% | 9.20% | -6.10 pp |
| Max drawdown | 18.23% | 19.00% | **+0.77 pp** |
| Sharpe | 1.02 | 0.71 | -0.31 |
| Exposure | 98.49% | 86.57% | -11.92 pp |
| Completed trades | 100 | 107 | +7 |
| Win rate | 20.00% | 18.69% | -1.31 pp |
| Profit factor | 1.08 | 1.00 | -0.08 |
| Turnover | 1944.50% | 1755.20% | -189.30 pp |
| Average positions | 9.96 | 9.90 | -0.06 |
| SPY return | 29.22% | 29.22% | — |

ATR-risk did not reduce Micho drawdown; it materially reduced return and Sharpe. Both variants trailed SPY.

ATR-risk cash averaged $14,366.32 (13.43%) and ended at $31,415.17 versus equal-slot $1,736.30 average (1.51%) and $1,334.11 final.

ATR-risk approved 117 and skipped 7,762 candidates: 7,344 ranking/not-selected, 410 cash-reserve, and 8 sector-limit. Average approved weight was 7.55%; average position risk $425.22. Average/max portfolio risk was $4,166.82/$5,323.91; maximum daily risk/equity was 5.78%, well below 8%. Maximum sector weight later reached 33.91%; no entry breached 30%.

Concentration worsened: top-five positive-P&L share rose 66.47% to 70.30% and HHI rose 0.12 to 0.15. `WBD` remained top contributor ($12,611.56 ATR-risk versus $14,335.55 equal-slot). Net realized P&L fell from +$2,183.38 to -$62.66; $15,480.04 unrealized final-open P&L produced the entire ATR-risk net gain. This confirms Sprint 9's Micho final-mark dependence.

## 13. Constraint and Artifact Validation

Across both ATR-risk runs:

- selected-entry portfolio-risk breaches: 0
- selected-entry sector breaches: 0
- selected-entry reserve breaches: 0
- negative cash observations: 0
- maximum positions: 10
- attribution reconciliation residual: exactly $0.00000000
- actual period: 2025-01-02–2026-08-20, 409 equity rows

Daily cash can later be below the current 10% reserve after market changes; the reserve is intentionally entry-only. Likewise sector drift after appreciation is allowed. No forced sale/rebalance was added.

## 14. What Sprint 10 Proved

- ATR14, risk sizing, cash/weight/risk/sector constraints, and diagnostics operate deterministically without lookahead.
- Equal-slot research behavior remains available and reproduced Sprint 9 COST_LOW results exactly.
- Strategy signal and portfolio decision can differ with stable machine-readable explanations.
- Current portfolio state is a reusable in-memory domain model rather than simulator-only state.
- The typed advisory API can support the planned UI decision views.
- Risk control can reduce exposure/turnover and sometimes drawdown, but these fixed settings impose a large opportunity cost.

## 15. What Sprint 10 Did Not Prove

- ATR-risk V1 is not production-ready or superior; it hurt both returns and did not improve Micho drawdown.
- The 2× ATR proxy is not an executable stop order or validated loss guarantee.
- No risk parameter was optimized, and one period cannot establish robustness.
- The API does not load live portfolio/broker state, automatically enrich candidates from current candles, persist plans, or execute orders.
- RS20 remains a research baseline, not universally robust alpha.

## 16. Known Limitations and Technical Debt

- **Survivorship bias/current constituents:** no point-in-time S&P 500 membership or delisted securities.
- **Cost assumption:** fixed 5 bps per side, zero commission; no empirical spread/liquidity/market-impact/tax model.
- **Benchmark:** SPY is not exposure-, risk-, turnover-, or cash-matched.
- **Open positions:** marked to final close and not force-liquidated; Micho and ATR-risk results are especially unrealized-P&L dependent.
- **Risk proxy:** frozen ATR risk ignores gap risk, correlations, changing volatility, and stop execution.
- **Sector drift:** entry-only cap can be exceeded later through appreciation.
- **API enrichment:** clients/adapters currently supply enriched candidate facts; a future backend orchestration service should load current candles and strategy signals before UI rollout.
- **Persistence/authentication:** no saved portfolio/account ownership, authorization, plan history, or broker adapter.
- **Sequential research runtime:** full-universe evaluation remains slow.
- **Diagnostics naming:** `RANKING_NOT_SELECTED` includes candidates that reached a full portfolio after higher-ranked approvals; future UI wording can distinguish rank scarcity from hard max-position rejection without changing accounting.

## 17. UI Readiness and Sprint 11 Recommendation

The Decision API response contract is ready for UI MVP consumption: typed portfolio summary, risk config, BUY/HOLD/SELL/SKIP decisions, stable reasons, allocations, weights, ATR, modeled risk, and sector context. The UI must remain presentation-only and must not duplicate strategy/risk logic.

Recommended Sprint 11: build the UI MVP (dashboard, portfolio summary, cash/risk, positions, ranked opportunities, decisions/reasons, company analysis, backtest summary) against this API. Before a real-account deployment, add authenticated portfolio persistence plus broker/current-market enrichment as backend adapters.

No Sprint 11 code was implemented.

## 18. Git State

Branch: `feature/portfolio-risk-decision-api`. All Sprint 10 changes remain local and uncommitted. The 24 corrected experiment artifacts are Git-ignored. No commit, push, PR, merge, force-push, or tag was performed by Codex.

Final `git status --short --branch`:

```text
## feature/portfolio-risk-decision-api
 M AGENTS.md
 M backend/src/alphapilot/api/router.py
 M backend/src/alphapilot/backtesting/multi_portfolio.py
 M backend/src/alphapilot/backtesting/multi_portfolio_models.py
 M backend/src/alphapilot/backtesting/multi_portfolio_service.py
 M backend/src/alphapilot/cli/backtest_multi_portfolio.py
 M backend/tests/backtesting/test_multi_portfolio.py
 M docs/DECISIONS.md
 M docs/PROJECT_STATE.md
?? backend/src/alphapilot/api/routes/portfolio.py
?? backend/src/alphapilot/portfolio/
?? backend/src/alphapilot/schemas/portfolio.py
?? backend/tests/api/test_portfolio_decisions.py
?? backend/tests/portfolio/
?? docs/SPRINT10_COMPLETION_REPORT.md
?? docs/SPRINT10_PLAN.md
```

Tracked `git diff --stat` (untracked files are listed above and are not included
by Git in this statistic):

```text
9 files changed, 375 insertions(+), 43 deletions(-)
```

Recommended commit message:

```text
feat(portfolio): add ATR risk sizing and decision API
```
