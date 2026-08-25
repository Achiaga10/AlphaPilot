# AlphaPilot Sprint 10 Plan

## 1. Goal

Add a deterministic portfolio-risk, ATR sizing, decision-plan, and typed API layer suitable for a future UI while preserving Sprint 7–9 research behavior.

## 2. Scope

- Add signal-day ATR14 risk features.
- Preserve `equal-slot` and add selectable `atr-risk` sizing.
- Enforce position weight, portfolio risk, entry cash reserve, sector weight, cash, whole-share, and max-position constraints.
- Produce structured BUY/SELL/HOLD/SKIP decisions and stable reason codes.
- Add in-memory portfolio-state and future-UI Pydantic contracts.
- Add `GET /api/v1/portfolio/risk-config` and `POST /api/v1/portfolio/decisions`.
- Run frozen equal-slot versus ATR-risk comparisons for EMA HYBRID 2% and Micho BOTH at RS20/COST_LOW.

## 3. Non-goals

- No UI, broker orders, persistence, stop-order execution, parameter tuning, new ranking formula, strategy changes, or Sprint 11 implementation.
- The API computes decisions from typed candidate/portfolio facts; broker synchronization and automated live signal orchestration remain future integrations.

## 4. Risk Model

For candles available through signal day T:

```text
TR = max(high-low, abs(high-previous_close), abs(low-previous_close))
ATR14 = mean(latest 14 true ranges)
stop_distance = 2 × ATR14
position_modeled_risk = shares × stop_distance
portfolio_modeled_risk = sum(active position modeled risk)
```

The first true range requires a previous close; ATR14 therefore requires 15 closes/bars. Future candles are filtered out. Entry ATR/stop distance and modeled risk are frozen on the position; market movement does not silently rewrite the risk budget.

## 5. Position Sizing

`equal-slot` remains byte-for-behavior compatible. `atr-risk` calculates:

```text
risk_budget = equity × 1%
risk_shares = floor(risk_budget / stop_distance)
weight_shares = floor((equity × 10%) / slipped execution price)
cash_shares = floor(entry-available cash / slipped execution price)
portfolio_risk_shares = floor(remaining portfolio risk dollars / stop_distance)
sector_shares = floor(remaining sector dollars / slipped execution price)
final shares = min(all share caps)
```

No leverage or fractional shares.

## 6. Portfolio Constraints

Defaults: 10 positions, 1% risk per position, 8% maximum portfolio modeled risk, 10% maximum position weight, 10% minimum cash reserve, and 30% maximum sector weight. Existing positions are never force-closed to restore a breached limit. SELL decisions are never blocked by entry-risk constraints.

## 7. Cash Reserve

At each new entry, required reserve is `equity × 10%`. Entry cost plus commission must not intentionally reduce cash below that amount. Whole-share flooring leaves cash at or above the reserve. Market movement may later change the reserve/equity relationship without forced action.

## 8. Sector Rule

Current sector market value is valued at the decision/execution reference price. A BUY may not cause its sector value to exceed `equity × 30%`. Missing/blank sectors are normalized to the explicit `Unclassified` bucket; they are not inferred and share one conservative sector cap.

## 9. Decision Model and Reasons

Strategy signal and portfolio decision remain distinct. Decisions are `BUY`, `HOLD`, `SELL`, `SKIP`. Stable reasons include `BUY_APPROVED`, `SELL_APPROVED`, `ALREADY_HELD`, `NO_POSITION_TO_SELL`, `MAX_POSITIONS`, `INSUFFICIENT_CASH`, `CASH_RESERVE`, `MAX_POSITION_WEIGHT`, `PORTFOLIO_RISK_LIMIT`, `SECTOR_LIMIT`, `INSUFFICIENT_HISTORY`, `INVALID_RISK_DISTANCE`, and `RANKING_NOT_SELECTED`.

Each decision exposes ranking, price, ATR, stop proxy, risk budget, shares, allocation/weight/risk, sector weights, and relevant current position facts. The plan exposes cash/equity/reserve, active positions, modeled/available risk, ranked candidates, and aggregate reason diagnostics.

## 10. API Contract

- `GET /api/v1/portfolio/risk-config`: frozen research defaults.
- `POST /api/v1/portfolio/decisions`: accepts strategy/ranking metadata, portfolio state, risk config, and enriched candidate facts (not raw candles); returns a typed decision plan.

The endpoint does not trade or persist. Historical-candle enrichment and broker state adapters can call the same domain service later without changing the UI response model.

## 11. Testing Requirements

Focused tests cover TR/ATR/no-lookahead/history/invalid values; exact risk/stop/share formulas; every cap and reason; sector/Unclassified handling; order preservation; BUY-to-SKIP; unrestricted SELL; held/flat cases; plan totals; risk aggregation; whole shares/nonnegative cash; unchanged equal-slot; deterministic output; API defaults, successful realistic plan, validation errors, and Decimal serialization. Sprint 7–9 and single-stock tests remain green.

## 12. Baseline Validation

Period 2025-01-01–2026-08-20, current active S&P 500, $100,000, 10 positions, RS20, COST_LOW (5 bps/side), final positions marked. Compare equal-slot with frozen ATR-risk defaults for EMA HYBRID 2% and Micho BOTH. Report return, drawdown, Sharpe, cash/exposure, concentration, rejection reasons, modeled risk, sector utilization, SPY, and open-position caveats. Do not tune after results.

## 13. Completion Criteria

Domain architecture, API, reports, and diagnostics are deterministic and tested; focused tests and `run_checks.ps1` pass; four experiments complete and reconcile; completion report and continuity docs are final; no Sprint 11, commit, push, PR, merge, or tag occurs.
