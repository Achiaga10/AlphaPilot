# AlphaPilot Sprint 12 Plan

## 1. Goal and research questions

Sprint 12 researches trade management separately for EMA20 Pullback and Micho
150. It asks whether the existing strategy exit is sufficient; whether a fixed
ATR14 protective stop improves loss tails, drawdown, Sharpe, and Calmar without
unacceptable return destruction; whether a no-lookahead ATR trailing stop
protects established winners; whether fixed/partial R targets improve results or
truncate the right tail; and which strategy-specific configuration, if any,
deserves frozen research-baseline status. Sprint 13 is not started.

## 2. Scope, architecture, and non-goals

Research exits are replaceable backtest `TradeManagementPolicy` overlays between
an opened position and the existing simulator execution/accounting layer. The
frozen strategy classes continue to generate entries and their original exits.
The overlay may add a static protective stop, monotonic trailing stop, or fixed
profit action. It does not enter the production strategy, Decision API, or UI.

The existing shared-cash engine remains authoritative for ranking, sizing,
positions, cash, equity, costs, and mark-to-market. It will be extended rather
than duplicated. No entry logic, RS20 formula/lookback, sizing, max positions,
sector/reserve limits, strategy parameter, frontend behavior, AI/ML, news,
broker execution, or Sprint 13 feature is changed.

## 3. Frozen controls and portfolio configurations

- EMA control: EMA20 Pullback entry, HYBRID exit, frozen 2% trend threshold,
  RS20 selection, equal-slot sizing.
- Micho control: Micho V1 BOTH entry, existing close-below-SMA150 exit, RS20
  selection, ATR-volatility-normalized sizing.
- Both: current active S&P 500 universe only, $100,000 initial capital, 10
  positions, whole shares, no leverage, existing constraints/accounting,
  commission $0, COST_LOW 5 bps per side, final positions marked to market and
  not force-closed.

These controls agree with Sprint 10B classifications. They are research
baselines, not production defaults. Custom-tracked tickers are excluded.

## 4. Phase 0 baseline reproduction

Before exit experiments, rerun both controls on development and validation and
compare directionally with Sprint 10B COST_LOW results. Material unexplained
differences block later phases. Completed-session fixes may legitimately affect
only boundaries, not historical strategy/execution semantics.

## 5. Protective-stop candidates

Development compares exactly:

- `control`: original strategy exit only.
- `atr-stop-1-5`: entry price minus 1.5 times entry ATR14.
- `atr-stop-2-0`: entry price minus 2.0 times entry ATR14.
- `atr-stop-3-0`: entry price minus 3.0 times entry ATR14.

ATR14 uses the 14 true ranges available through BUY signal day T, before
next-open entry. The initial stop uses the slipped entry price and is fixed.
Missing/nonpositive ATR produces no entry under a stop policy and is explicitly
audited; no value is fabricated.

## 6. Stop activation and daily OHLC execution

An initial stop derived at the entry open becomes active on the next available
trading session, so every stop tested on day U was known before U began. For a
long position and a pre-known stop:

```text
if open[U] <= stop: raw exit = open[U], gap-through = true
else if low[U] <= stop: raw exit = stop
else: no stop
```

Existing sell slippage and per-order commission then apply. A stop breached on
U has priority over a strategy SELL generated from U's completed close, whose
normal execution would be U+1 open. A pending prior strategy exit at U open is
processed at the open; if the same open is also below a pre-known stop, the
protective stop is the recorded conservative exit reason. Normal re-entry is
allowed only after a later legitimate strategy BUY; no cooldown is added.

## 7. Protective-stop development selection and classification

For each strategy, select the declared ATR candidate with highest development
Calmar (CAGR divided by max drawdown). Ties use higher Sharpe, lower drawdown,
then higher CAGR. Record and freeze the choice before validation. Control is
always retained.

Validation classification is `REJECTED`, `RESEARCH_ONLY`, or
`PROMISING_RESEARCH_BASELINE`. Promising requires validation drawdown not to
materially worsen, validation Calmar or Sharpe to improve, at least 80% of a
positive control CAGR to be retained, and no obvious one-fold-only dependence.
If control CAGR is nonpositive, compare absolute CAGR/return direction and tail
risk rather than applying a nonsensical 80% ratio.

## 8. Trailing-stop candidates and semantics

With the selected protective stop frozen, development compares:

- `no-additional-profit-management`;
- `atr-trailing-2-0`;
- `atr-trailing-3-0`.

For day U, only completed information through U-1 is used:

```text
reference_close = max(completed closes from entry through U-1)
candidate_trail = reference_close - multiple * ATR14_through_U_minus_1
effective_stop[U] = max(initial_stop, prior_effective_stop, candidate_trail)
```

The current U high/low/close and ATR including U cannot move the same-day stop.
The effective stop never decreases. Execution and gap rules equal the protective
stop rules. Development selection uses highest Calmar with the same tie-breaks.

## 9. Fixed and partial profit-management candidates

Only a valid positive initial risk distance permits this phase. With the frozen
protective stop and no trailing overlay (to isolate one additional policy),
development compares:

- `control-profit`: no fixed target;
- `partial-2r`: once, sell floor(current shares times 50%) at +2R; if zero,
  skip the partial; remaining shares continue under strategy plus protective
  stop;
- `full-3r`: sell the full current position at +3R; no 2R partial.

`R = entry price - initial protective stop` is frozen at entry. Targets activate
on the next available session. For a pre-known target on U, open at/above target
fills at open; otherwise high at/above target fills at the target; sell friction
then applies.

If both a pre-known stop and target are reachable after the open on one OHLC bar
and ordering is unknowable, the stop executes first. An unambiguous opening gap
executes its opening trigger. No profitable intraday ordering is assumed.

Profit candidates are eligible for development selection only if they retain at
least 80% of positive no-profit-control CAGR and do not worsen max drawdown.
Eligible candidates rank by Calmar, then Sharpe, lower drawdown, and CAGR. If
none qualify, no fixed target is selected.

## 10. Final additional-policy selection

At most one additional profit-management overlay is frozen per strategy. The
stop-only candidate, best declared trailing candidate, and best eligible fixed/
partial candidate are compared on development. A trailing or profit candidate
must retain at least 80% of positive stop-only CAGR; among eligible candidates,
highest Calmar wins with the established tie-breaks. Thus the final candidate
is protective stop plus either no additional overlay, one trailing overlay, or
one fixed/partial policy—never an untested combination.

## 11. Periods, folds, and validation order

- Development: 2021-08-20 through 2024-12-31.
- Validation: 2025-01-01 through 2026-08-20.
- Fold 1: 2021-08-20 through 2022-12-31.
- Fold 2: 2023-01-01 through 2024-12-31.
- Fold 3: 2025-01-01 through 2026-08-20.

For each strategy: complete development, freeze one protective stop and at most
one additional overlay in `docs/DECISIONS.md`, then run validation. No parameter
is reopened after validation. After validation, run control and frozen final
candidate on all three folds without removing an inconvenient fold.

## 12. Metrics and diagnostics

Portfolio output includes final equity, return, CAGR, max drawdown, Sharpe,
Calmar, profit factor, win rate, average/median trade, completed trades,
holding period, exposure, turnover, worst and fifth-percentile trade, realized/
unrealized P&L, final-open count, and top-1/top-5 concentration.

Trade diagnostics include ticker, entry signal/day/price, initial ATR/R/stop,
exit day/price/reason, shares and partial legs, P&L dollars/percent, holding
days, MFE, MAE, giveback, stop/gap/strategy/profit flags, and final-open status.
Aggregates include median MFE/MAE/giveback, exit-reason counts, re-entry count,
repeated stop-outs, time to re-entry, and universe breadth.

Stopped-trade 5/10/20-session recovery and later original-strategy-exit facts
are explicitly ex-post hindsight diagnostics and never affect execution.

## 13. No-lookahead and completed-session rules

Historical input contains completed daily sessions. Strategy signals remain
T-to-T+1-open. Entry ATR uses data through T only. A stop or target tested on U
must have been frozen using data no later than U-1 (except its prior entry-open
creation, which activates on the following session). Trailing references and ATR
exclude U. Post-stop recovery is calculated only after the simulated outcome.
`CompletedDailySessionPolicy` and all existing future-data protections remain
unchanged.

## 14. Accounting and determinism

Partial exits allocate entry commission/cost basis deterministically by shares;
each exit leg incurs configured sell commission/slippage. Cash plus marked
position value equals equity. Net realized plus final unrealized P&L reconciles
to portfolio gain within Decimal tolerance. Same input, candidate ordering, and
configuration must produce identical results. Metadata records every frozen
strategy, ranker, sizer, exit overlay, ATR period/multiple, cost, period,
universe, execution rule, final-open handling, and survivorship warning.

## 15. Completion criteria

Sprint 12 completes when controls reproduce or differences are explained; all
declared development candidates run; selections are frozen before validation;
validation and three folds complete; trade/accounting/no-lookahead/governance
tests and full `run_checks.ps1` pass; Git-ignored reports provide auditable
tables/CSV diagnostics; `docs/SPRINT12_COMPLETION_REPORT.md` records the full
evidence and strategy-specific classifications; all work remains local; and
Sprint 13 is not started.
