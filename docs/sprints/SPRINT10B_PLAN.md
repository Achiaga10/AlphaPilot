# AlphaPilot Sprint 10B Plan

## 1. Goal

Harden the backend before UI work by adding fixed inverse-ATR-percentage batch
sizing and a high-level portfolio-plan orchestrator. Sprint 10B is not Sprint
11; no frontend code is in scope.

## 2. Scope

- Preserve `equal-slot` and Sprint 10 `atr-risk` exactly.
- Add `atr-volatility-normalized` as a third selectable sizing policy.
- Allocate a same-day ranked BUY candidate group with one deterministic batch
  view of portfolio state, investable capital, ATR features, and constraints.
- Add backend orchestration that loads stored companies/candles, evaluates the
  selected strategy, calculates RS20 and ATR14 as of one explicit date, enriches
  candidates with stored sectors, and builds a typed decision plan.
- Preserve the lower-level `/api/v1/portfolio/decisions` endpoint and add
  `/api/v1/portfolio/plan` for future UI use.
- Run the predeclared 12-run development/validation experiment at COST_LOW.

## 3. Non-goals and Research Freeze

No UI, broker synchronization, broker orders, persistence, authentication,
external live fetches from domain logic, AI/ML, continuous rebalancing,
parameter search, or strategy/ranking changes. EMA HYBRID 2%, Micho BOTH,
RS20/20 bars, ATR14, 10 positions, T+1 execution, portfolio accounting, and
Sprint 9 cost scenarios remain frozen.

## 4. Volatility-Normalized Sizing

For each eligible candidate `i`, using signal-day data only:

```text
atr_pct_i = ATR14_i / reference_price_i
raw_weight_i = 1 / atr_pct_i
normalized_weight_i = raw_weight_i / sum(raw_weight for eligible batch)
target_investable_equity = equity * (1 - 10%)
remaining_investable_capital = max(target_investable_equity - existing holdings value, 0)
candidate_target_dollars = remaining_investable_capital * normalized_weight_i
```

Final whole shares are floored after applying the candidate target, 10% position
cap, available cash/reserve, 8% modeled portfolio-risk cap using `2 * ATR14`, and
30% entry-time sector cap. Commission and slipped execution price are included.
No leverage or negative cash is allowed.

## 5. Candidate-Group Semantics

Exits execute first. Remaining BUY candidates are ordered by the existing
selection policy. Candidates already held are excluded. The allocator receives
the full ranked, slot-eligible group for that execution day, not one candidate
at a time. Invalid/missing ATR candidates receive no fabricated weight and are
deterministically rejected with existing structured reasons. Valid candidates'
weights normalize to 100% before caps and whole-share rounding. Constraints are
then applied in rank order; existing holdings are not rebalanced.

## 6. Constraints

- maximum positions: 10
- ATR period: 14 bars; stop-distance risk proxy: `2 * ATR14`
- maximum position weight at entry: 10% of current equity
- minimum cash reserve at entry: 10% of current equity
- maximum modeled portfolio risk at entry: 8% of current equity
- maximum sector weight at entry: 30% of current equity
- missing sector: explicit shared `Unclassified` bucket
- whole shares, no leverage, cash never negative
- no forced rebalance after price/sector drift

## 7. Orchestration Architecture

```text
typed portfolio state + high-level strategy/policy/scope/as-of request
  -> PortfolioDecisionOrchestrator
  -> CompanyService / DailyCandleService / universe repository
  -> StrategyFactory evaluation with stored SPY context
  -> signal-time RS20 + ATR14 calculators
  -> enriched PortfolioCandidate group
  -> existing ranking policy
  -> selected sizing/risk policy and PortfolioDecisionEngine
  -> typed PortfolioDecisionPlan response
```

The orchestrator uses newest stored daily candles on or before `as_of_date`.
It does not fetch providers directly. One deterministic analysis date is the
newest stored SPY date on or before the requested date; ticker histories are
bounded by that date. The response reports requested and actual as-of dates.
Stale or insufficient data returns a stable candidate status/reason rather than
invented features.

## 8. API Contract

Preserve:

- `GET /api/v1/portfolio/risk-config`
- `POST /api/v1/portfolio/decisions`

Add:

- `POST /api/v1/portfolio/plan`

The high-level request contains current portfolio state, strategy and frozen
strategy parameters, selection policy, sizing policy, risk config, as-of date,
and optional ticker scope. It contains no ATR, RS20, stop distance, or enriched
candidate facts. The response reuses the decision-plan schema and adds analysis
date/data-status metadata needed by the UI.

## 9. Testing

Focused tests cover ATR%, inverse-vol ordering, exact normalization, batch
determinism, all caps, whole shares/cash, missing ATR, no-lookahead, unchanged
equal-slot/atr-risk, repository/service loading, backend strategy/RS20/ATR/sector
enrichment, stale/insufficient status, typed serialization, lower-level endpoint
compatibility, and high-level endpoint end to end. All Sprint 7-10 and
single-stock tests must remain green, followed by `run_checks.ps1`.

## 10. Fixed Experiment

Run development (2021-08-20 through 2024-12-31) and validation (2025-01-01
through 2026-08-20), current active S&P 500 constituents, $100,000, 10 positions,
RS20, COST_LOW (5 bps per side), final positions marked to market. For each
period run EMA HYBRID 2% and Micho BOTH with `equal-slot`, `atr-risk`, and
`atr-volatility-normalized` (12 total). Parameters are fixed before results and
will not be changed afterward.

## 11. Interpretation and Completion

Compare policies only within each strategy using return, CAGR, drawdown, Sharpe,
turnover, exposure/cash, realized/unrealized P&L, contributor concentration,
modeled risk, sector utilization, constraint reasons, Return/Drawdown, and
CAGR/Drawdown. Classify each policy only as `REJECTED`, `RESEARCH_ONLY`, or
`PROMISING_RESEARCH_BASELINE`; never production-ready.

Sprint 10B completes when implementation and compatibility tests pass, all 12
runs reconcile, the UI-readiness gate is assessed, continuity documents and
`docs/SPRINT10B_COMPLETION_REPORT.md` are complete, and no Sprint 11, commit,
push, PR, merge, or tag operation has occurred.
