# AlphaPilot Sprint 10B Completion Report

## 1. Why Sprint 10B Was Needed

Sprint 10 proved the ATR risk architecture, constraints, typed decisions, and
advisory API, but ATR-risk V1 sacrificed too much validation return and left
substantial cash idle. Its lower-level API also required clients to supply
precomputed signal, RS20, ATR, and sector facts. Sprint 10B therefore added a
fixed group-aware inverse-volatility sizing policy and moved current decision
fact construction into the backend before any UI work.

Sprint 10B completed successfully. No UI or Sprint 11 functionality was built,
and no research parameter was changed after development or validation results.

## 2. Architecture Changes

Sizing now has three explicit policies:

```text
equal-slot                       (unchanged compatibility/control)
atr-risk                         (unchanged Sprint 10 V1)
atr-volatility-normalized        (new candidate-batch policy)
```

The new high-level flow is:

```text
typed portfolio state + strategy/policy/scope/as-of request
  -> PortfolioDecisionOrchestrator
  -> stored Company / DailyCandle / active-universe services
  -> StrategyFactory evaluation with stored SPY context
  -> signal-time RS20 and ATR14
  -> stored sector enrichment and deterministic data status
  -> ranked PortfolioCandidate batch
  -> selected sizing/risk policy
  -> PortfolioDecisionEngine
  -> typed PortfolioDecisionPlan API response
```

Strategy, ranking, risk features, group sizing, constraints, accounting, and API
serialization remain separate. External providers are not called by domain
logic, and no broker execution or persistence was added.

## 3. Files Created

Sprint 10B created:

- `backend/src/alphapilot/portfolio/orchestration.py`
- `backend/tests/portfolio/test_orchestration.py`
- `docs/SPRINT10B_PLAN.md`
- `docs/SPRINT10B_COMPLETION_REPORT.md`

## 4. Files Modified

Sprint 10B modified the still-local Sprint 10 foundation:

- `backend/src/alphapilot/portfolio/sizing.py`
- `backend/src/alphapilot/portfolio/decisions.py`
- `backend/src/alphapilot/schemas/portfolio.py`
- `backend/src/alphapilot/api/routes/portfolio.py`
- `backend/src/alphapilot/backtesting/multi_portfolio.py`
- `backend/src/alphapilot/backtesting/multi_portfolio_models.py`
- `backend/src/alphapilot/backtesting/multi_portfolio_service.py`
- `backend/src/alphapilot/cli/backtest_multi_portfolio.py`
- `backend/tests/portfolio/test_sizing.py`
- `backend/tests/portfolio/test_decisions.py`
- `backend/tests/api/test_portfolio_decisions.py`
- `backend/tests/backtesting/test_multi_portfolio.py`
- `AGENTS.md`
- `docs/PROJECT_STATE.md`
- `docs/DECISIONS.md`

Sprint 10 had been reviewed but was still uncommitted on
`feature/portfolio-risk-decision-api`; the clean/merged branch-switch condition
was not met. Sprint 10B therefore continued in that working tree without a
checkout, pull, or new branch, preserving all user-owned local work.

## 5. Tests Added or Changed

Tests cover:

- exact ATR percentage and inverse-volatility weights
- lower-volatility/higher-volatility ordering
- weights summing exactly to one per candidate group
- ranked group determinism and missing/invalid ATR rejection
- 10% position cap, 10% reserve, shared cash, 8% modeled risk, and 30% sector cap
- whole shares and nonnegative cash
- simulator batch integration and normalized-weight audit persistence
- unchanged equal-slot and ATR-risk behavior
- backend company/candle/universe loading
- backend strategy evaluation, RS20, ATR14, and stored-sector enrichment
- explicit stored-data as-of semantics and future-candle filtering
- deterministic stale-data status
- typed high-level API without ATR/RS20 inputs
- lower-level `/portfolio/decisions` compatibility

## 6. Exact Volatility-Normalized Formula

For each valid ranked candidate in the slot-eligible same-day group:

```text
ATR14_i = mean(latest 14 true ranges available through signal day T)
atr_pct_i = ATR14_i / reference_price_i
raw_weight_i = 1 / atr_pct_i
normalized_weight_i = raw_weight_i / sum(raw_weight for the selected group)

target_investable_equity = equity * (1 - 10%)
existing_invested_value = current marked value of existing holdings
remaining_investable_capital = max(
    target_investable_equity - existing_invested_value,
    0
)
remaining_investable_capital is also capped by cash minus reserve/commission

candidate_target_dollars_i = remaining_investable_capital * normalized_weight_i
```

The candidate target is capped without redistributing cap leftovers:

```text
target_shares = floor(
    min(candidate_target_dollars, equity * 10%) / slipped execution price
)
cash_shares = floor((cash - equity * 10% reserve - commission) / price)
stop_distance = 2 * ATR14
risk_shares = floor((equity * 8% - current modeled risk) / stop_distance)
sector_shares = floor((equity * 30% - current sector value) / price)
final shares = min(target_shares, cash_shares, risk_shares, sector_shares)
```

Whole shares only; no leverage; transaction slippage and commission are included.
The experiments used zero commission and COST_LOW 5 bps per side.

## 7. Candidate-Group Normalization Semantics

Exits execute before entries. BUY candidates already held are removed, then the
existing RS20 policy orders higher score first with ticker-ascending ties. From
the ranked candidates with positive ATR and price, the first `available_slots`
candidates form the normalization group. Missing/invalid ATR candidates are not
assigned a fabricated weight; they receive `INSUFFICIENT_HISTORY` or
`INVALID_RISK_DISTANCE`. Valid candidates outside the group receive
`RANKING_NOT_SELECTED`.

All group weights are calculated once from the same post-exit/pre-entry portfolio
state. Constraints then apply sequentially in rank order, sharing cash, modeled
risk, and sector room. Existing holdings consume investable capital but are not
rebalanced. Price appreciation may later move cash/risk/sector ratios beyond an
entry cap without a forced sale.

The selection audit now preserves `normalized_sizing_weight`. Across the six
volatility-normalized runs, 546 execution-day groups were audited and every group
summed to 1 within `1e-12`.

## 8. Exact Constraints and Decision Reasons

Frozen settings:

- ATR period: 14 trading bars
- modeled stop distance: 2 × ATR14
- maximum position weight: 10% at entry
- minimum cash reserve: 10% at entry
- maximum modeled portfolio risk: 8% at entry
- maximum sector weight: 30% at entry
- maximum positions: 10
- missing sector: shared `Unclassified` bucket
- final positions: marked to market; not force-closed

Existing stable reasons remain, with deterministic
`INSUFFICIENT_ALLOCATION` and `STALE_DATA` added. SELL remains independent of
BUY constraints.

Artifact audit across all 12 runs found:

- negative cash observations: 0
- max-position breaches: 0
- signal day on/after execution day: 0
- selected-entry modeled-risk breaches: 0
- selected-entry sector breaches: 0
- selected-entry position-weight breaches: 0
- selected-entry reserve breaches: 0
- attribution reconciliation residuals: all exactly `$0.00000000`

Daily EMA validation volatility-normalized risk/equity later reached 8.36%
because equity moved after entry. No entry exceeded 8%; the cap is deliberately
entry-only, as are reserve and sector constraints.

## 9. Decision Orchestration and Data Semantics

`PortfolioDecisionOrchestrator` accepts the Sprint 10 in-memory portfolio state
and high-level configuration. It loads SPY and stock candles through existing
services/repositories. The actual analysis date is the newest stored SPY candle
on or before the requested date. Every stock history is filtered to that date.

A stock must have a candle on the analysis date. Missing company, no data,
stale data, insufficient history, ready action, and no-action states are reported
with typed deterministic statuses. The backend evaluates the real StrategyFactory
strategy, calculates fixed RS20 for BUYs, calculates ATR14 for BUYs, loads the
stored Company sector, builds candidates, and applies the requested policy.

No T+1/future candle can affect current orchestration facts. Backtesting T+1 OPEN
execution remains unchanged.

## 10. API Contract

Preserved:

- `GET /api/v1/portfolio/risk-config`
- `POST /api/v1/portfolio/decisions`

Added:

- `POST /api/v1/portfolio/plan`

High-level request fields:

```text
strategy
exit_mode / frozen EMA threshold or Micho entry mode
selection_policy
sizing_policy
as_of_date
optional ticker scope
typed current portfolio state
typed risk configuration
```

It does **not** accept ATR, RS20, stop distance, sector facts, or enriched
candidates. The response reuses the typed portfolio summary/config/decision
schemas and adds requested/actual analysis dates, sizing policy, and per-ticker
orchestration statuses. Decimal and enum serialization are covered by API tests.

The contract is advisory only: no trades, external live fetches, account
persistence, authentication, or broker synchronization occur.

## 11. Validation Commands and Test Results

Focused command from `backend/`:

```powershell
$env:DEBUG='false'
uv run ruff format src tests
uv run ruff check src tests
uv run mypy src
uv run pytest tests/portfolio tests/api/test_portfolio_decisions.py tests/backtesting/test_multi_portfolio.py tests/backtesting/test_multi_portfolio_reporting.py
```

Result: **37 passed**; Ruff and mypy passed.

Full quality command (the first attempt from repository root correctly failed
because the script lives under `backend/`; it was immediately rerun from the
documented backend directory):

```powershell
$env:DEBUG='false'
.\run_checks.ps1
```

Result: **passed**. Ruff passed (one file formatted, 159 unchanged), mypy found
no issues in 111 source files, and pytest reported **140 passed in 23.32s**.
`DEBUG=false` was scoped only to child processes; application configuration was
not changed.

## 12. Exact Experiment Commands

All successful commands ran from `backend/`. An initial three-command launch
without the child override stopped before loading data because the Codex host
provided invalid `DEBUG=release`; those produced no artifacts. Every successful
command below scoped `DEBUG=false` only to its child.

```powershell
# Development — EMA
$env:DEBUG='false'; uv run alphapilot-backtest-multi-portfolio --strategy ema20-pullback --exit-mode hybrid --hybrid-trend-threshold-pct 2 --sizing-policy equal-slot --selection-policy relative-strength-20 --cost-scenario cost-low --start 2021-08-20 --end 2024-12-31 --capital 100000 --max-positions 10 --risk-per-position-pct 1 --atr-period 14 --atr-stop-multiple 2 --max-position-weight-pct 10 --max-portfolio-risk-pct 8 --minimum-cash-reserve-pct 10 --max-sector-weight-pct 30 --fold-label sprint10b-development --output-dir backtest_reports/sprint10b/development
$env:DEBUG='false'; uv run alphapilot-backtest-multi-portfolio --strategy ema20-pullback --exit-mode hybrid --hybrid-trend-threshold-pct 2 --sizing-policy atr-risk --selection-policy relative-strength-20 --cost-scenario cost-low --start 2021-08-20 --end 2024-12-31 --capital 100000 --max-positions 10 --risk-per-position-pct 1 --atr-period 14 --atr-stop-multiple 2 --max-position-weight-pct 10 --max-portfolio-risk-pct 8 --minimum-cash-reserve-pct 10 --max-sector-weight-pct 30 --fold-label sprint10b-development --output-dir backtest_reports/sprint10b/development
$env:DEBUG='false'; uv run alphapilot-backtest-multi-portfolio --strategy ema20-pullback --exit-mode hybrid --hybrid-trend-threshold-pct 2 --sizing-policy atr-volatility-normalized --selection-policy relative-strength-20 --cost-scenario cost-low --start 2021-08-20 --end 2024-12-31 --capital 100000 --max-positions 10 --risk-per-position-pct 1 --atr-period 14 --atr-stop-multiple 2 --max-position-weight-pct 10 --max-portfolio-risk-pct 8 --minimum-cash-reserve-pct 10 --max-sector-weight-pct 30 --fold-label sprint10b-development --output-dir backtest_reports/sprint10b/development

# Development — Micho
$env:DEBUG='false'; uv run alphapilot-backtest-multi-portfolio --strategy micho-150 --micho-entry-mode both --sizing-policy equal-slot --selection-policy relative-strength-20 --cost-scenario cost-low --start 2021-08-20 --end 2024-12-31 --capital 100000 --max-positions 10 --risk-per-position-pct 1 --atr-period 14 --atr-stop-multiple 2 --max-position-weight-pct 10 --max-portfolio-risk-pct 8 --minimum-cash-reserve-pct 10 --max-sector-weight-pct 30 --fold-label sprint10b-development --output-dir backtest_reports/sprint10b/development
$env:DEBUG='false'; uv run alphapilot-backtest-multi-portfolio --strategy micho-150 --micho-entry-mode both --sizing-policy atr-risk --selection-policy relative-strength-20 --cost-scenario cost-low --start 2021-08-20 --end 2024-12-31 --capital 100000 --max-positions 10 --risk-per-position-pct 1 --atr-period 14 --atr-stop-multiple 2 --max-position-weight-pct 10 --max-portfolio-risk-pct 8 --minimum-cash-reserve-pct 10 --max-sector-weight-pct 30 --fold-label sprint10b-development --output-dir backtest_reports/sprint10b/development
$env:DEBUG='false'; uv run alphapilot-backtest-multi-portfolio --strategy micho-150 --micho-entry-mode both --sizing-policy atr-volatility-normalized --selection-policy relative-strength-20 --cost-scenario cost-low --start 2021-08-20 --end 2024-12-31 --capital 100000 --max-positions 10 --risk-per-position-pct 1 --atr-period 14 --atr-stop-multiple 2 --max-position-weight-pct 10 --max-portfolio-risk-pct 8 --minimum-cash-reserve-pct 10 --max-sector-weight-pct 30 --fold-label sprint10b-development --output-dir backtest_reports/sprint10b/development

# Validation — EMA
$env:DEBUG='false'; uv run alphapilot-backtest-multi-portfolio --strategy ema20-pullback --exit-mode hybrid --hybrid-trend-threshold-pct 2 --sizing-policy equal-slot --selection-policy relative-strength-20 --cost-scenario cost-low --start 2025-01-01 --end 2026-08-20 --capital 100000 --max-positions 10 --risk-per-position-pct 1 --atr-period 14 --atr-stop-multiple 2 --max-position-weight-pct 10 --max-portfolio-risk-pct 8 --minimum-cash-reserve-pct 10 --max-sector-weight-pct 30 --fold-label sprint10b-validation --output-dir backtest_reports/sprint10b/validation
$env:DEBUG='false'; uv run alphapilot-backtest-multi-portfolio --strategy ema20-pullback --exit-mode hybrid --hybrid-trend-threshold-pct 2 --sizing-policy atr-risk --selection-policy relative-strength-20 --cost-scenario cost-low --start 2025-01-01 --end 2026-08-20 --capital 100000 --max-positions 10 --risk-per-position-pct 1 --atr-period 14 --atr-stop-multiple 2 --max-position-weight-pct 10 --max-portfolio-risk-pct 8 --minimum-cash-reserve-pct 10 --max-sector-weight-pct 30 --fold-label sprint10b-validation --output-dir backtest_reports/sprint10b/validation
$env:DEBUG='false'; uv run alphapilot-backtest-multi-portfolio --strategy ema20-pullback --exit-mode hybrid --hybrid-trend-threshold-pct 2 --sizing-policy atr-volatility-normalized --selection-policy relative-strength-20 --cost-scenario cost-low --start 2025-01-01 --end 2026-08-20 --capital 100000 --max-positions 10 --risk-per-position-pct 1 --atr-period 14 --atr-stop-multiple 2 --max-position-weight-pct 10 --max-portfolio-risk-pct 8 --minimum-cash-reserve-pct 10 --max-sector-weight-pct 30 --fold-label sprint10b-validation --output-dir backtest_reports/sprint10b/validation

# Validation — Micho
$env:DEBUG='false'; uv run alphapilot-backtest-multi-portfolio --strategy micho-150 --micho-entry-mode both --sizing-policy equal-slot --selection-policy relative-strength-20 --cost-scenario cost-low --start 2025-01-01 --end 2026-08-20 --capital 100000 --max-positions 10 --risk-per-position-pct 1 --atr-period 14 --atr-stop-multiple 2 --max-position-weight-pct 10 --max-portfolio-risk-pct 8 --minimum-cash-reserve-pct 10 --max-sector-weight-pct 30 --fold-label sprint10b-validation --output-dir backtest_reports/sprint10b/validation
$env:DEBUG='false'; uv run alphapilot-backtest-multi-portfolio --strategy micho-150 --micho-entry-mode both --sizing-policy atr-risk --selection-policy relative-strength-20 --cost-scenario cost-low --start 2025-01-01 --end 2026-08-20 --capital 100000 --max-positions 10 --risk-per-position-pct 1 --atr-period 14 --atr-stop-multiple 2 --max-position-weight-pct 10 --max-portfolio-risk-pct 8 --minimum-cash-reserve-pct 10 --max-sector-weight-pct 30 --fold-label sprint10b-validation --output-dir backtest_reports/sprint10b/validation
$env:DEBUG='false'; uv run alphapilot-backtest-multi-portfolio --strategy micho-150 --micho-entry-mode both --sizing-policy atr-volatility-normalized --selection-policy relative-strength-20 --cost-scenario cost-low --start 2025-01-01 --end 2026-08-20 --capital 100000 --max-positions 10 --risk-per-position-pct 1 --atr-period 14 --atr-stop-multiple 2 --max-position-weight-pct 10 --max-portfolio-risk-pct 8 --minimum-cash-reserve-pct 10 --max-sector-weight-pct 30 --fold-label sprint10b-validation --output-dir backtest_reports/sprint10b/validation
```

Reports are Git-ignored under `backend/backtest_reports/sprint10b/`: 36
development files and 36 validation files (summary, equity, trades, selection
audit, ticker attribution, and sector attribution for each run).

## 13. Development Results

Requested/actual period: 2021-08-20 through 2024-12-31. Every run processed
497/502 tickers. `FDXF`, `HONA`, `PSKY`, `Q`, and `SNDK` had no historical
candles. COST_LOW SPY returned 33.06%.

### EMA HYBRID 2% + RS20

| Metric | Equal-slot | ATR-risk | Vol-normalized |
|---|---:|---:|---:|
| Final equity | $180,145.51 | $172,789.17 | $139,084.52 |
| Return | 80.15% | 72.79% | 39.08% |
| CAGR | 19.12% | 17.65% | 10.30% |
| Max drawdown | 26.43% | 23.04% | 22.63% |
| Sharpe | 0.87 | 1.00 | 0.66 |
| Profit factor | 1.47 | 1.48 | 1.13 |
| Win rate | 32.02% | 33.33% | 32.00% |
| Exposure | 78.79% | 68.92% | 66.74% |
| Turnover | 5,511.94% | 4,594.39% | 4,119.22% |
| Completed trades | 253 | 246 | 250 |
| Average positions | 7.89 | 7.80 | 7.85 |
| Average cash / % | $20,991.85 / 21.21% | $32,950.57 / 31.08% | $33,608.21 / 33.26% |
| Final cash | $86.85 | $20,370.02 | $14,496.75 |
| Realized / unrealized P&L | $45,251.47 / $34,894.04 | $37,118.07 / $35,671.11 | $9,971.61 / $29,112.91 |
| Top-1 / top-5 positive share | 27.47% / 61.48% | 32.56% / 66.51% | 32.39% / 61.64% |
| Positive-P&L HHI | 0.11 | 0.14 | 0.14 |
| Avg / max modeled risk % | 0 / 0 | 3.82% / 7.72% | 3.71% / 7.09% |
| Max observed sector % | 88.48% | 34.39% | 31.89% |

Vol-normalized reduced equal-slot drawdown by 3.80 points but sacrificed 41.07
return points. It slightly lowered drawdown versus ATR-risk by 0.41 points but
sacrificed 33.71 return points and reduced Sharpe.

### Micho BOTH + RS20

| Metric | Equal-slot | ATR-risk | Vol-normalized |
|---|---:|---:|---:|
| Final equity | $159,916.35 | $139,781.71 | $148,434.79 |
| Return | 59.92% | 39.78% | 48.43% |
| CAGR | 14.97% | 10.47% | 12.46% |
| Max drawdown | 19.27% | 18.04% | 15.74% |
| Sharpe | 0.81 | 0.65 | 0.77 |
| Profit factor | 1.50 | 1.30 | 1.31 |
| Win rate | 24.02% | 23.08% | 21.88% |
| Exposure | 98.68% | 89.07% | 87.92% |
| Turnover | 5,228.17% | 4,650.30% | 4,396.86% |
| Completed trades | 254 | 260 | 256 |
| Average positions | 9.93 | 9.92 | 9.93 |
| Average cash / % | $1,516.45 / 1.32% | $12,546.56 / 10.93% | $13,870.90 / 12.08% |
| Final cash | $261.96 | $14,057.18 | $15,111.93 |
| Realized / unrealized P&L | $28,354.44 / $31,561.91 | $16,166.15 / $23,615.56 | $15,132.99 / $33,301.80 |
| Top-1 / top-5 positive share | 11.57% / 43.79% | 12.48% / 42.24% | 13.29% / 46.84% |
| Positive-P&L HHI | 0.06 | 0.06 | 0.06 |
| Avg / max modeled risk % | 0 / 0 | 4.17% / 5.74% | 4.12% / 5.90% |
| Max observed sector % | 66.80% | 37.30% | 36.85% |

Vol-normalized sacrificed 11.49 return points versus equal-slot while reducing
drawdown by 3.53 points. It beat ATR-risk by 8.65 return points, reduced drawdown
2.30 points, and improved Sharpe by 0.12.

## 14. Validation Results

Requested period: 2025-01-01 through 2026-08-20. Actual period: 2025-01-02
through 2026-08-20. All runs processed 502/502 tickers. COST_LOW SPY returned
29.22%.

### EMA HYBRID 2% + RS20

| Metric | Equal-slot | ATR-risk | Vol-normalized |
|---|---:|---:|---:|
| Final equity | $155,571.92 | $115,835.23 | $119,958.11 |
| Return | 55.57% | 15.84% | 19.96% |
| CAGR | 31.17% | 9.44% | 11.82% |
| Max drawdown | 20.79% | 16.06% | 21.41% |
| Sharpe | 0.95 | 0.52 | 0.58 |
| Profit factor | 1.43 | 0.98 | 1.04 |
| Win rate | 33.77% | 34.90% | 31.10% |
| Exposure | 92.49% | 80.43% | 80.67% |
| Turnover | 3,212.65% | 2,473.91% | 2,650.38% |
| Completed trades | 151 | 149 | 164 |
| Average positions | 9.26 | 9.24 | 9.18 |
| Average cash / % | $7,218.33 / 7.51% | $19,384.66 / 19.57% | $18,755.32 / 19.33% |
| Final cash | $74.83 | $11,455.35 | $11,980.19 |
| Realized / unrealized P&L | $30,743.00 / $24,828.92 | -$905.31 / $16,740.54 | $2,635.55 / $17,322.56 |
| Top-1 / top-5 positive share | 13.27% / 45.96% | 14.05% / 44.56% | 20.49% / 49.90% |
| Positive-P&L HHI | 0.06 | 0.06 | 0.08 |
| Avg / max modeled risk % | 0 / 0 | 5.15% / 7.49% | 5.30% / 8.36%* |
| Max observed sector % | 84.21% | 37.18% | 42.38% |

`*` Later mark-to-market drift; entry audit breaches were zero.

Vol-normalized kept 4.12 more return points than ATR-risk and raised Sharpe by
0.06, but drawdown was 5.35 points worse and concentration increased. Versus
equal-slot it sacrificed 35.61 return points and worsened drawdown by 0.62.

### Micho BOTH + RS20

| Metric | Equal-slot | ATR-risk | Vol-normalized |
|---|---:|---:|---:|
| Final equity | $126,101.55 | $115,417.38 | $135,363.99 |
| Return | 26.10% | 15.42% | 35.36% |
| CAGR | 15.30% | 9.20% | 20.43% |
| Max drawdown | 18.23% | 19.00% | 11.44% |
| Sharpe | 1.02 | 0.71 | 1.46 |
| Profit factor | 1.08 | 1.00 | 1.20 |
| Win rate | 20.00% | 18.69% | 19.19% |
| Exposure | 98.49% | 86.57% | 88.47% |
| Turnover | 1,944.50% | 1,755.20% | 1,696.43% |
| Completed trades | 100 | 107 | 99 |
| Average positions | 9.96 | 9.90 | 9.96 |
| Average cash / % | $1,736.30 / 1.51% | $14,366.32 / 13.43% | $13,160.79 / 11.53% |
| Final cash | $1,334.11 | $31,415.17 | $16,300.42 |
| Realized / unrealized P&L | $2,183.38 / $23,918.17 | -$62.66 / $15,480.04 | $4,924.83 / $30,439.16 |
| Top-1 / top-5 positive share | 26.11% / 66.47% | 29.13% / 70.30% | 23.06% / 65.87% |
| Positive-P&L HHI | 0.12 | 0.15 | 0.12 |
| Avg / max modeled risk % | 0 / 0 | 3.97% / 5.78% | 3.93% / 5.35% |
| Max observed sector % | 55.32% | 33.91% | 33.52% |

Vol-normalized beat ATR-risk by 19.94 return points, lowered drawdown 7.56
points, raised Sharpe 0.75, used cash more effectively, reduced turnover, and
reduced concentration. It also beat equal-slot by 9.26 return points while
lowering drawdown 6.79 points and raising Sharpe 0.44.

## 15. Risk-Efficiency Ratios

These are simple research ratios, not standardized financial metrics.

| Period | Strategy | Policy | Return / DD | CAGR / DD |
|---|---|---|---:|---:|
| Development | EMA | Equal-slot | 3.03 | 0.72 |
| Development | EMA | ATR-risk | 3.16 | 0.77 |
| Development | EMA | Vol-normalized | 1.73 | 0.46 |
| Validation | EMA | Equal-slot | 2.67 | 1.50 |
| Validation | EMA | ATR-risk | 0.99 | 0.59 |
| Validation | EMA | Vol-normalized | 0.93 | 0.55 |
| Development | Micho | Equal-slot | 3.11 | 0.78 |
| Development | Micho | ATR-risk | 2.21 | 0.58 |
| Development | Micho | Vol-normalized | 3.08 | 0.79 |
| Validation | Micho | Equal-slot | 1.43 | 0.84 |
| Validation | Micho | ATR-risk | 0.81 | 0.48 |
| Validation | Micho | Vol-normalized | 3.09 | 1.79 |

EMA volatility normalization did not deliver a stable return/drawdown trade-off.
Micho volatility normalization did: it was near equal-slot efficiency in
development and substantially stronger in validation.

## 16. Cash, Concentration, Open P&L, and Constraint Diagnostics

Volatility-normalized did not solve EMA idle cash: average cash was 33.26% in
development and 19.33% in validation. It also increased validation top-1/top-5
positive-P&L concentration and HHI. ATR-risk had similarly high EMA idle cash.

For Micho, vol-normalized average cash stayed closer to the intended reserve
(12.08% development, 11.53% validation) than ATR-risk, while validation
concentration improved relative to ATR-risk and slightly relative to equal-slot.

Final-open positions remain critical. Unrealized P&L shares of total gain were
approximately:

- EMA development: equal 43.54%, ATR-risk 49.01%, vol-normalized 74.48%
- EMA validation: equal 44.68%, ATR-risk 105.72% (realized loss), vol-normalized 86.79%
- Micho development: equal 52.68%, ATR-risk 59.36%, vol-normalized 68.76%
- Micho validation: equal 91.63%, ATR-risk 100.41% (realized loss), vol-normalized 86.07%

Micho vol-normalized remains highly dependent on final-open unrealized gains,
despite its strong validation metrics.

Constraint rejection counts excluding rank/slot scarcity:

| Period/strategy | ATR-risk | Vol-normalized |
|---|---|---|
| Dev EMA | cash reserve 2,200; sector 33 | sector 21 |
| Val EMA | cash reserve 2; sector 23 | portfolio risk 2; sector 18 |
| Dev Micho | cash reserve 393; sector 21 | sector 10 |
| Val Micho | cash reserve 410; sector 8 | sector 2 |

The group policy eliminated cash-reserve rejection as a common failure because
its batch target starts from investable capital, while retaining exact entry
caps. Sector limits affected relatively few entries. Modeled portfolio risk was
generally well below 8%, particularly for Micho.

## 17. EMA Conclusion and Classification

- `equal-slot`: **PROMISING_RESEARCH_BASELINE**. Strong, persistent return and
  validation Sharpe, but no risk/sector/reserve protection and substantial
  sector/contributor concentration.
- `atr-risk`: **RESEARCH_ONLY**. Strong development efficiency and lower EMA
  validation drawdown, but severe validation return/Sharpe sacrifice and idle cash.
- `atr-volatility-normalized`: **RESEARCH_ONLY**. It improved validation return
  slightly over ATR-risk but failed to preserve equal-slot return, did not
  control validation drawdown, and increased concentration. Evidence was not
  directionally strong enough for promising-baseline status.

For EMA, volatility-normalized sizing did **not** robustly improve on ATR-risk V1.
The trade-off reversed between development and validation.

## 18. Micho Conclusion and Classification

- `equal-slot`: **PROMISING_RESEARCH_BASELINE**. Positive and competitive in
  both periods, but nearly fully invested without risk/sector controls and highly
  final-open dependent.
- `atr-risk`: **RESEARCH_ONLY**. It underperformed the other policies and did not
  improve validation drawdown; idle cash remained material.
- `atr-volatility-normalized`: **PROMISING_RESEARCH_BASELINE** for Micho research.
  It improved on ATR-risk in both periods, reduced development drawdown while
  retaining more return, and dominated both alternatives in validation. It is
  not production-ready because its validation gain remained 86% unrealized and
  the universe/cost assumptions remain limited.

For Micho, volatility-normalized sizing **did** improve on ATR-risk V1
directionally in both development and validation.

## 19. What Sprint 10B Proved

- Candidate-group inverse-ATR% normalization can be implemented deterministically
  and audited without one-candidate normalization errors.
- Equal-slot and ATR-risk remain compatible and reproducible.
- All entry constraints remain exact under batch sizing.
- Backend orchestration can own stored-data strategy evaluation, RS20, ATR14,
  sector loading, data status, ranking, sizing, and reason generation.
- The high-level plan API does not require frontend domain calculations.
- A sizing policy can behave differently by strategy; one validation winner is
  not a universal default.
- Fixed vol-normalized sizing improved Micho risk/return evidence but did not
  produce a stable EMA improvement.

## 20. What Sprint 10B Did Not Prove

- No sizing policy is production-ready or universally optimal.
- The Micho validation improvement is not independent of final-open marks or a
  few contributors.
- ATR is not a realized stop loss and does not model gaps/correlation/liquidity.
- No statistical significance, point-in-time universe, live execution, or
  broker-account behavior was established.
- No parameter was optimized; alternative ATR periods, exponents, caps, reserves,
  risk limits, or sector limits were deliberately not tested.

## 21. Known Limitations and Technical Debt

- **Survivorship bias/current constituents:** historical runs use today's active
  S&P 500 constituents, not point-in-time membership or delisted securities.
- **Costs:** fixed 5 bps per side and zero commission; no empirical spread,
  liquidity, market-impact, taxes, or borrow model.
- **SPY:** not exposure-, risk-, cash-, sector-, turnover-, or timing-matched.
- **Final positions:** marked to final close, never force-liquidated; completed
  trade statistics exclude them.
- **Micho dependence:** final-open unrealized P&L remains the majority of gain.
- **RS20:** remains a frozen research baseline, not proven universal alpha.
- **Risk:** entry ATR/stop proxy ignores gaps, correlation, volatility changes,
  and actual stop execution; ratios may drift after entry.
- **Group allocation:** capped target leftovers are not redistributed and a
  constrained group member is not replaced/reoptimized; this is explicit V1
  semantics, not an optimized portfolio solver.
- **Current-data orchestration:** requires stored same-date candle data and does
  not fetch live quotes. Calendar/staleness thresholds beyond same-date status
  remain future policy work.
- **No live state:** no broker synchronization, authenticated account ownership,
  portfolio persistence, saved plans, or order execution.
- **Runtime:** each CLI policy repeats identical sequential universe strategy
  evaluation; a future read-only prepared-backtest cache/matrix runner could
  reduce research runtime without changing results.

## 22. UI Readiness Gate

**PASS — backend is ready to begin a UI MVP after user approval.**

1. High-level `/api/v1/portfolio/plan` works end to end: pass.
2. Backend calculates strategy signal, RS20, ATR14, sector, and risk facts: pass.
3. Frontend supplies no domain calculations or enriched candidates: pass.
4. Structured decision/data reason codes are stable: pass.
5. Portfolio state and request/response contracts are typed: pass.
6. Existing research/backtesting tests remain green: pass (140 total).
7. Explicit research policy status is documented: pass. Equal-slot remains the
   broad compatibility/research baseline; vol-normalized is promising for Micho
   and research-only for EMA; no policy is described as production-ready.

The UI should present the selected policy and its classification, not silently
claim one universal sizing winner. Frontend code must consume this API and must
not duplicate strategy/ranking/risk calculations.

## 23. Recommendation

Proceed to Sprint 11 UI MVP only after the user/ChatGPT review approves this
handoff. Build dashboard, portfolio summary, stored-data as-of/status, cash/risk,
positions, opportunities, BUY/HOLD/SELL/SKIP decisions, stable reasons, and
backtest summaries against the high-level plan API.

Do not add more sizing/ranking experiments as part of UI work. Broker state,
authenticated persistence, and current-market adapters remain future backend
hardening topics, not frontend calculations.

No Sprint 11 code was implemented.

## 24. Git State

Sprint 10 and Sprint 10B changes remain local on
`feature/portfolio-risk-decision-api`. Reports are Git-ignored. Codex performed
no commit, push, PR, merge, force-push, or tag operation.

Final `git status --short --branch --untracked-files=all`:

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
?? backend/src/alphapilot/portfolio/__init__.py
?? backend/src/alphapilot/portfolio/decisions.py
?? backend/src/alphapilot/portfolio/orchestration.py
?? backend/src/alphapilot/portfolio/risk.py
?? backend/src/alphapilot/portfolio/sizing.py
?? backend/src/alphapilot/schemas/portfolio.py
?? backend/tests/api/test_portfolio_decisions.py
?? backend/tests/portfolio/test_decisions.py
?? backend/tests/portfolio/test_orchestration.py
?? backend/tests/portfolio/test_risk.py
?? backend/tests/portfolio/test_sizing.py
?? docs/SPRINT10B_COMPLETION_REPORT.md
?? docs/SPRINT10B_PLAN.md
?? docs/SPRINT10_COMPLETION_REPORT.md
?? docs/SPRINT10_PLAN.md
```

Tracked `git diff --stat` (untracked files are listed above and are not included
in Git's statistic):

```text
9 files changed, 563 insertions(+), 48 deletions(-)
```

`git diff --check` passed. Git emitted only the existing Windows LF-to-CRLF
working-copy warnings for the three continuity documents.

Recommended commit message:

```text
feat(portfolio): harden risk sizing and add decision orchestration
```
