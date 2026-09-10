# EMA20 Loss-Control Research Protocol

Status: **FROZEN BEFORE IMPLEMENTATION RESULTS — 2026-09-06**

Canonical Strategy Lab protocol fingerprint:
`47dc814a331567efb15f0605de7257d601292907cadb6ab1c62646239881156c`.

Candidate fingerprints:

- control: `d1b5a13c243a77705e4c4ac8cff26cae156062654a5eec6dfe05e3bad2b323f0`
- fixed signal-day EMA50:
  `d6a7b25fc4e4fd35b7d3b0f992a75ddf4a91c80eb48a30bd5dec7aba786f65d1`
- reused ATR14 2×:
  `3a4a51c09f5c2cae5ce3d6638746f4fcf6d626ca9707e1d7d9c3fa1c57a72fce`

This protocol governs the focused `ema20-pullback-v1` pre-entry numeric
loss-control study on branch `research/ema20-loss-control`. It is risk-management
research, not a strategy-entry change and not production activation.

## Research question

Can a deterministic numeric boundary, known before the next-open entry, contain
EMA20 Pullback loss tails without unacceptable drawdown, turnover, whipsaw,
concentration, or return deterioration?

The frozen EMA20 Pullback entry, 1% entry-safety ceiling, EMA20/EMA50 periods,
HYBRID 2% exit, RS20, equal-slot sizing, ten-position limit, News rules,
portfolio constraints, and T+1 execution remain unchanged.

## Prior evidence and closed candidate families

Sprint 12 tested static entry ATR14 stops at 1.5×, 2.0×, and 3.0×; ATR14 trails
at 2.0× and 3.0×; a 50% whole-share partial at +2R; and a full exit at +3R.
EMA 3.0× was development-selected but remained `RESEARCH_ONLY` because only
one of three folds improved return, Sharpe, or Calmar. The tighter/static,
trailing, and profit-taking alternatives were rejected or not selected because
of return destruction, whipsaw, drawdown, or frozen CAGR-retention failures.

Sprint 20 Round 1 retested the closed EMA static space `control`, ATR14 2.0×,
2.5×, and 3.0× on the immutable Sprint 13 snapshot. ATR14 2.0× was the sole
development-gate qualifier but failed reused validation because max drawdown
worsened by 1.62 percentage points against the frozen 1.50-point ceiling.
Round 2 tested the same ATR14 2.0× arm only as a reference and one new
signal-day-low invalidation arm. Signal-day-low improved loss tails but raised
turnover about 72.5%, far beyond the 25% gate. Round 2 ended `NO_WINNER`.

No percentage stop, moving/future EMA50, trailing stop, profit target, new ATR
period, or alternate ATR multiple is reopened here.

## Closed candidate set

### Control

`control`: the existing frozen HYBRID 2% strategy exit only. It provides no
approved pre-entry numeric loss-control boundary and is the comparison arm.

### Candidate A — fixed signal-day EMA50 protective boundary

Policy identity: `ema20-fixed-signal-ema50-stop-v1`.

For a BUY signal generated on completed session T and executed at the next
available session U open:

```text
entry_loss_control_price = EMA50 calculated from completed candles through T
loss_control_source = SIGNAL_DAY_EMA50
loss_control_as_of = T
risk_per_share = slipped_entry_price[U] - entry_loss_control_price
risk_pct = risk_per_share / slipped_entry_price[U] * 100
```

The EMA50 is frozen from T. It never moves after entry and no future EMA value
can alter the boundary. A missing/nonpositive EMA50, or a boundary at/above the
actual entry price, rejects that managed entry rather than fabricating risk.

Trigger semantics are predeclared as a **protective price breach**, not a
completed-close signal: the boundary becomes active on the session after entry,
matching the existing research overlay convention. For an active long boundary
on session V:

```text
if open[V] <= boundary: raw exit = open[V] and gap_through = true
else if low[V] <= boundary: raw exit = boundary
else: no loss-control exit
```

Existing sell friction then applies. A pre-known protective breach has
conservative priority over a same-bar strategy exit; otherwise the frozen
HYBRID 2% strategy exit continues normally. Entry-session low is not used to
trigger a newly created boundary. Daily OHLC cannot establish intraday ordering.

This is intentionally distinct from the moving completed-close EMA50 strategy
exit that Sprint 20 correctly identified as duplicative. It is also a new
research semantic, not an approved broker stop.

### Candidate B — reused static ATR14 2× evidence

Policy identity: `ema20-static-atr14-2x-v1`.

```text
ATR period = 14 completed trading bars through signal day T
K = 2.0
entry_loss_control_price = slipped_entry_price[U] - 2.0 * ATR14[T]
loss_control_source = SIGNAL_DAY_ATR14
loss_control_as_of = T
```

The same next-session activation, daily-low/gap execution, strategy-exit
precedence, 5 bps sell friction, and missing/invalid-input rules apply. This is
the exact Sprint 20 ATR14 2.0× arm. Its frozen development, validation, and fold
artifacts will be reused and audited; it will **not** be rerun as a supposedly
new experiment.

ATR14 is the existing AlphaPilot convention. Fidelity describes 14 periods as
typical and ATR stops as volatility-adaptive; Schwab describes ATR multiples
generally in the 1×–2× range. The fixed 2× value also predates this study in
AlphaPilot and was not selected from current outcomes:

- https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/atr
- https://workplace.schwab.com/story/4-volatility-metrics-to-inform-your-trades

### Candidate C

None. No structure-plus-volatility hybrid is declared.

## Dataset and fixed portfolio assumptions

- Frozen snapshot: `5dd60f87-8947-4850-ba87-4a7df655528c`.
- Dataset SHA-256:
  `b77ba749182fb4408394eed6d47c7d39dcfcb52a4555683c8a0b9fa7cb91374b`.
- Universe SHA-256:
  `369350debc5b9649a0f24f6bda863aa8c8d7f85a73965ea16616712d1c5a4ec8`.
- Frozen current-constituent S&P 500 snapshot plus SPY; survivorship biased and
  not point-in-time membership; provenance `LEGACY_PARTIAL`.
- Strategy: `ema20-pullback-v1`, HYBRID 2%.
- Ranking: RS20.
- Sizing: equal-slot, unchanged.
- Initial capital: $100,000.
- Maximum positions: 10.
- Costs: COST_LOW, zero commission, 5 bps slippage per side.
- Final open positions: marked to market, not force-liquidated.

Development evidence: 2021-08-20 through 2024-12-31.

Reused/previously observed validation evidence: 2025-01-01 through 2026-08-20.

Temporal folds:

1. 2021-08-20 through 2022-12-31.
2. 2023-01-01 through 2024-12-31.
3. 2025-01-01 through 2026-08-20.

All periods have been seen in prior AlphaPilot work and are research evidence,
not pristine out-of-sample evidence. The immutable snapshot prevents operational
candle changes from altering the experiment.

## Stage discipline

The new EMA50 arm and a configuration-identical control run in development.
Candidate B uses the existing Sprint 20 frozen artifacts. Candidate A may
advance to reused validation and all three folds only if it passes every
development gate. Failure at development ends its lifecycle; validation is not
opened merely to search for a favorable later period. No gate or policy may be
changed after development or validation is observed.

## Frozen acceptance gates

Candidate A development must satisfy all of the existing Sprint 20 protections:

- retain at least 75% of positive control CAGR;
- worsen max drawdown by no more than 1.5 percentage points;
- retain at least 80% of positive control Sharpe and Calmar;
- increase turnover by no more than 25%;
- improve worst-trade or fifth-percentile loss magnitude by at least 10%;
- provide a valid pre-entry numeric boundary for every entry it accepts;
- entry-to-boundary risk P90 no greater than 10%; and
- maximum entry-to-boundary risk no greater than 20%.

The 10% P90 limit maps a normal 10%-of-equity equal-slot position to roughly a
1%-of-equity planned boundary loss before gaps/costs. The 20% maximum is a hard
tail screen, not a guarantee of realized maximum loss.

If Candidate A advances, validation must satisfy all existing Sprint 20 gates:

- retain at least 70% of positive validation-control CAGR;
- worsen max drawdown by no more than 1.5 percentage points;
- retain at least 80% of positive validation-control Sharpe and Calmar;
- worsen top-five positive-P&L concentration by no more than 5 points;
- increase turnover by no more than 25%;
- improve or equal control return, Sharpe, and drawdown in at least two of three
  folds;
- 20-session recovery rate no greater than 65%;
- maintain complete valid-boundary coverage; and
- continue to satisfy the same P90 and maximum risk-distance limits.

Any hard-gate failure means the candidate is rejected. There is no least-bad
fallback. Candidate B retains its already-frozen `NO_WINNER` result.

## Required diagnostics

For every run: final equity, gross/net return, CAGR, max drawdown, Sharpe,
Calmar, trade count, win rate, average winner, average loser, median loser,
worst trade, expectancy/average trade, profit factor, exposure, turnover,
transaction friction, realized/unrealized P&L, final-open positions,
concentration, stop count/rate, gap stops, re-entry/repeated-stop behavior, and
5/10/20-session post-stop recovery.

For every managed entry: entry reference/actual price, boundary, source,
as-of date, policy version, risk per share, risk percentage, position value,
planned risk dollars, and planned risk percentage of entry equity. Risk-distance
P50/P75/P90/maximum are reported for each candidate using sorted
`floor(q * (n - 1))` percentiles, consistent with the existing portfolio-metric
implementation.

AXON and FAST are incident illustrations only. IBKR and EOG receive current
descriptive boundaries only after this protocol is frozen. None of those four
tickers may tune the policy or become an approved BUY during this research.

## Gap-risk and activation caveat

A numeric boundary does not guarantee execution at that price. An opening gap
through the boundary fills at the worse open in the daily model, followed by
sell slippage. Real spreads, liquidity, market impact, halts, and intraday paths
can produce different outcomes. Planned stop distance must never be described
as a guaranteed maximum loss.

## Completion decision

Passing evidence can produce only a proposed EMA20 loss-control policy for
independent human review. It is not activated in the Strategy Profile,
ExecutionReadiness, Portfolio Plan, UI, Paper workflow, or broker layer by this
research branch. If no candidate passes, the decision is
`NO_APPROVED_EMA20_LOSS_CONTROL_POLICY` and EMA20 BUYs remain non-actionable.
