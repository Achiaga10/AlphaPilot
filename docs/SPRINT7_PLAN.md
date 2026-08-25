# AlphaPilot Sprint 7 Plan

## 1. Goal

Build a deterministic multi-stock portfolio backtesting platform that evaluates existing strategies across the current active S&P 500 universe while using one shared cash balance and supporting multiple simultaneous long positions.

Sprint 7 moves research from independent $100,000-per-ticker simulations to one portfolio whose candidates compete for capital and position slots.

## 2. Scope

- Reuse `BacktestingEngine` to produce lookahead-safe daily strategy evaluations per ticker.
- Add multi-stock portfolio models, configuration, simulation, metrics, service orchestration, reporting, and a CLI.
- Use one shared portfolio with configurable initial capital, maximum positions, allocation, commission, and slippage.
- Preserve whole-share, long-only, no-leverage behavior.
- Add a replaceable candidate-selection abstraction.
- Implement a stable ticker-order baseline selector because the existing Scanner filters BUY signals but does not rank them.
- Compare the portfolio with SPY buy-and-hold over the actual common portfolio period.
- Run engine-validation baselines for EMA20 Pullback HYBRID 2% and Micho V1 BOTH.

## 3. Non-goals

- No strategy parameter optimization.
- No Micho V1 rule changes.
- No HYBRID 2% retuning or Scanner-default change.
- No production alpha ranking, discretionary selection, News AI, shorting, leverage, fractional shares, stop experiments, or Sprint 8 features.
- No strategy winner declaration from ticker-order baseline results.
- No forced liquidation solely to make completed-trade metrics look complete.

## 4. Architecture

The implementation will keep these concerns separate:

1. `BacktestingEngine`: evaluates one strategy against one ticker's historical candles with only information available through each signal day.
2. Multi-stock orchestration service: loads the active universe, stock histories, and SPY history; creates one per-ticker `BacktestResult`; aligns them onto a common execution calendar.
3. Candidate generation: converts prior-session BUY/SELL evaluations into executable next-available-bar orders.
4. Candidate selection policy: orders eligible BUY candidates independently of accounting. Sprint 7 baseline uses normalized ticker ascending order and is explicitly non-alpha.
5. Multi-stock portfolio simulator: processes exits, allocation, entries, cash, positions, trades, and one daily equity curve.
6. Portfolio metrics: calculates return, CAGR, drawdown, Sharpe, exposure, trade statistics, turnover, average positions, and maximum positions used without changing existing single-stock metric definitions.
7. Benchmark/reporting: aligns SPY buy-and-hold to the portfolio's actual period and emits reproducible summary/CSV artifacts.
8. CLI: reuses `create_strategy()` and strategy-specific enums rather than duplicating construction rules.

Existing single-stock public APIs and tests remain intact. New multi-stock models and calculators will be separate where their data shape differs.

## 5. Execution Rules

- A signal calculated from ticker information through day T executes at that ticker's next available trading-day OPEN.
- Each ticker independently carries its signal to its next available bar; no same-day bar is required across every constituent.
- On each portfolio calendar day, executable SELLs are processed first in stable ticker order. Released cash is available to BUYs executing that same day.
- Eligible BUYs are then passed to the configured selection policy and processed in its deterministic order.
- BUY while already held is ignored. SELL while flat is ignored.
- One open position is allowed per ticker.
- A final-bar signal has no next bar and cannot execute.
- Open positions are not force-closed. They are marked to market at the last available close on or before each portfolio valuation day, including the final day.
- Missing ticker candles do not invent prices or executions; valuation carries forward the latest known close. Benchmark alignment limitations will be reported.

## 6. Portfolio Constraints and Allocation

- Long-only, whole shares, no leverage, and cash may never be negative.
- `initial_capital`, `max_positions`, `commission_per_order`, and `slippage_bps` are validated configuration.
- Baseline sizing is fixed equal-slot allocation: target notional per new position is `current portfolio equity / max_positions`, capped by available cash after commission.
- Allocation is recalculated on each entry day from that day's post-exit portfolio equity, but existing positions are not rebalanced.
- Buy slippage raises execution price; sell slippage lowers it, consistent with the current simulator.
- If the budget cannot buy at least one share plus commission, the candidate is skipped.
- Slot and cash constraints are enforced after exits and before each entry.

This sizing policy validates infrastructure; it is not a production portfolio optimizer.

## 7. Testing Requirements

Focused tests will prove:

1. Multiple tickers can be held simultaneously with one cash balance.
2. Cash never becomes negative.
3. Maximum positions, fixed-slot sizing, and whole shares are enforced.
4. Commission and buy/sell slippage are applied.
5. BUY and SELL execute at next available OPEN without lookahead.
6. Exits release cash before same-day entries.
7. Repeated BUY and flat SELL are ignored.
8. Final-bar BUY and SELL cannot execute.
9. Daily equity includes all positions and final positions are marked to market.
10. Candidate selection is deterministic when slots/cash are insufficient.
11. Metrics and SPY alignment/report metadata are correct.
12. Existing single-stock tests remain green.

Focused tests will run throughout, followed by `./run_checks.ps1` from `backend/` with all Ruff, mypy, and pytest checks passing.

## 8. Baseline Experiment Plan

Run the current active S&P 500 universe for 2025-01-01 through 2026-08-20 with:

- Initial capital: $100,000
- Maximum positions: 10
- Sizing: fixed equal-slot allocation (`equity / max_positions`)
- Commission: $0
- Slippage: 0 bps
- Selection: stable ticker ascending, explicitly engine-validation-only and non-alpha
- Open positions: marked to market, not force-closed

Strategies:

1. EMA20 Pullback with HYBRID exit and frozen 2% threshold.
2. Micho 150 V1 with BOTH entry mode.

Reports will include configuration, selection policy, survivorship warning, portfolio metrics, trade metrics, concurrency, and SPY comparison. Results will validate plumbing, not select a superior strategy.

## 9. Completion Criteria

Sprint 7 is complete when:

- Architecture and semantics above are implemented and documented.
- Required focused tests and all existing tests pass.
- `backend/run_checks.ps1` passes fully.
- Both baseline portfolio experiments complete reproducibly and their outputs are inspected.
- `docs/PROJECT_STATE.md` and `docs/DECISIONS.md` reflect final Sprint 7 facts.
- `docs/SPRINT7_COMPLETION_REPORT.md` contains the complete engineering/research handoff, exact commands/results, limitations, Git state, and Sprint 8 recommendation.
- Nothing is committed, pushed, merged, or opened as a PR by Codex.
