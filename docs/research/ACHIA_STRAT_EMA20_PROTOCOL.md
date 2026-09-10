# Achia_strat_ema20 V1 — frozen research protocol

Status: FROZEN BEFORE PERFORMANCE RESULTS, 2026-09-07.
This is one new, long-only hypothesis, not EMA20 Pullback tuning or approval for
Portfolio Plan. No parameter search, production registration, migration, provider
refresh, portfolio/Paper mutation, or broker action is authorized.

## Identity and exact rules

- Display: `Achia_strat_ema20`; canonical research profile/strategy identity:
  `achia-strat-ema20-v1`, version 1, LONG_ONLY.
- Technical BUY on completed session T iff `EMA20[T] > EMA50[T]` AND
  `0.90 * EMA20[T] <= Close[T] <= 1.01 * EMA20[T]`, inclusive.
- No slope, SPY regime, low/touch, reclaim, HYBRID, RS20, or News entry filter.
- Entry and held-position exit eligibility are independent facts. A below-EMA20
  close may qualify for entry while flat and for exit while held; SELL-first
  technical evaluation must not erase the requested lower entry zone.
- Entry uses the ticker's next available session U OPEN, then existing BUY
  slippage. No subsequent bar means no fill; no high/low/close selects the entry.
- Native policy: `achia-ema20-atr14-plus-1pct-stop-v1`.
  `stop = entry_fill - ATR14[T] - 0.01 * entry_fill`.
  ATR must be positive, and `0 < stop < entry_fill`; otherwise reject the entry.
- Stop is static and active immediately after entry at U OPEN, including U's
  remaining session. For an existing stop, OPEN <= stop exits at raw OPEN;
  otherwise LOW <= stop exits at raw stop. Apply existing SELL slippage afterward.
  For a newly opened position the stop only exists after the opening fill: test
  its remaining-session LOW, not a fabricated pre-entry gap.
- A surviving held position exits when completed `Close[V] < EMA20[V]`, strictly.
  Execute at the next available OPEN. Equality and intraday EMA breaches alone
  are not strategy exits. A pending previous-close exit executes at OPEN unless
  a simultaneous opening gap-stop takes precedence; a later intraday low cannot
  override an already executed opening exit. No double exit.
- A stop on V takes precedence over V's later closing signal. No same-open
  re-entry from a signal generated while held: another completed valid signal
  after full exit is needed, including the close of an intraday-stop session.
- No trailing, breakeven, target, partial exit, or cooldown.

## Indicators, data, and timing

Use `strategy.indicators.calculate_ema_series`: SMA seed over the first N closes,
then alpha `2/(N+1)`, periods 20 and 50. Minimum technical history: 50 valid bars.
Use `portfolio.risk.AverageTrueRangeCalculator`, not Wilder smoothing:
`TR = max(high-low, abs(high-previous_close), abs(low-previous_close))`;
ATR14 is the mean of the last 14 TRs and requires 15 candles. Missing or invalid
OHLC is explicit unavailability, not fabricated prices/volatility. Histories are
sorted, bounded through the signal date, and use the completed-session policy.
Stock warm-up is 120 calendar days and SPY warm-up 400 days, matching the existing
EMA research service. EMA seed/window differences must not be hidden.

Frozen snapshot: `5dd60f87-8947-4850-ba87-4a7df655528c`.

Dataset SHA-256:
`b77ba749182fb4408394eed6d47c7d39dcfcb52a4555683c8a0b9fa7cb91374b`.

Universe SHA-256:
`369350debc5b9649a0f24f6bda863aa8c8d7f85a73965ea16616712d1c5a4ec8`.

The finalized manifest contains 502 constituents plus SPY, 745,232 candle versions,
2019-07-17–2026-08-20, `LEGACY_PARTIAL` provenance. Verify actual frozen rows and
hashes before formal execution; mismatches stop the run without mutable fallback.
All development, validation, and fold periods have been observed in prior
AlphaPilot research: they are NOT pristine future out-of-sample evidence.

## Fixed experiment and comparison

Development: 2021-08-20–2024-12-31.
Validation, only after all development gates pass: 2025-01-01–2026-08-20.
Folds, only after validation gates pass:
1. 2021-08-20–2022-12-31;
2. 2023-01-01–2024-12-31;
3. 2025-01-01–2026-08-20.

Each authorized period runs Achia V1 and the unchanged EMA20 Pullback V1 HYBRID
2% reference. The reference is descriptive context, not a candidate to tune.
Identical verified artifacts may be reused for fold 3. No validation is opened
merely to seek a better result after development failure.

Main portfolio: $100,000, 10 positions, existing equal-slot whole-share sizing,
no leverage, shared nonnegative cash, no forced rebalancing. COST_LOW: $0/order,
5 bps per side. All normal opening exits precede entries; intraday proceeds do
not retroactively fund that session's OPEN entries. No sector/reserve/risk sizing
overlay is added to equal-slot. Final open positions remain marked to final close.
RS20 is PORTFOLIO ALLOCATION/RANKING ONLY: fixed stock 20-bar return minus SPY
20-bar return at signal time, descending, ticker ties and missing-score fallback.

Signal/trade analysis: count all technical BUY facts independently of ranking.
Replay each ticker independently with the same simulator/native stop, $100,000,
one equal slot, no RS20 competition. This preserves one position per ticker and
fresh-signal re-entry semantics without cross-stock capital competition. Report
per-ticker metrics and pooled completed-trade diagnostics. Pooled trade returns
are not a realizable shared-capital portfolio; do not compound them into one CAGR.

Gross P&L/return adds observed transaction friction back to the same executed
holdings; it is NOT a separately simulated zero-cost counterfactual.

## Frozen gates and lifecycle

Reuse Strategy Lab canonical identities and DEFINED → DEVELOPMENT → FROZEN →
VALIDATION → FOLDS → CLASSIFIED lifecycle; hard failure terminates early with
explicit reasons. There is only one Achia candidate; no selection sweep.

Development must pass ALL these predeclared screens:

- verified dataset, no unexplained ticker execution/preparation failure, and
  complete valid stop/provenance coverage for accepted entries;
- at least 100 completed main-portfolio trades (avoid tiny-sample promotion);
- positive net return and CAGR, Sharpe >= 0.50, Calmar >= 0.50, profit factor > 1;
- positive pooled independent-ticker net trade expectancy;
- planned entry-stop risk P90 <= 10% and maximum <= 20%, retaining the preceding
  research's explicit native-boundary risk screens (not guaranteed loss caps).

Failure means REJECTED at development, with validation/folds NOT OPENED. This new
strategy uses absolute evidence screens, not the prior stop-overlay's return-
retention or turnover-improvement tests; the reference is a different strategy.

Validation must satisfy the same profitability, risk coverage/distance, and
sample screens; additionally max drawdown <= 30%. If passed, run all folds.
Existing Strategy Lab classification requires at least 2/3 positive-return folds,
validation Sharpe >= 0.50, Calmar >= 0.50, and drawdown <= 30%.
PROMISING_RESEARCH_BASELINE requires all gates plus 3/3 positive folds;
2/3 positive folds is at most RESEARCH_ONLY. Any hard gate failure is REJECTED.
No result may be called PRODUCTION_READY or change an operational profile.

## Predeclared diagnostics

Persist signal/day facts, trades, open positions, equity curve, selection audit,
attribution/reconciliation, run metadata, and stage/classification evidence in
Git-ignored `backend/backtest_reports/achia_strat_ema20/`.

Report signals, entries, completed/open trades, no-next-bar/held/constraint/
missing-data counts, net/gross return, CAGR, DD, Sharpe, Calmar, PF, expectancy,
win/loss rates, mean/median trades/winners/losers, worst and P5 trade, mean/median
holding calendar days and trading sessions, turnover/friction/exposure/final cash.
Report realized and final-open unrealized P&L, SPY, positive-P&L concentration,
and stop count/rate, gap count, risk-distance mean/P50/P75/P90/max. Every accepted
entry includes actual/reference fill, signal ATR/date, 1% component, stop/risk per
share, shares/value, entry equity, planned dollar and portfolio-percent risk.

Every completed Achia trade has exit family PROTECTIVE_STOP or CLOSE_BELOW_EMA20;
report counts, win rate, mean/median/worst return and holding duration by family.

Post-stop returns use the 5th/10th/20th subsequent ticker-session close versus
actual exit fill, limited to the authorized period. Recovery means a completed
close at/above original entry within those 20 sessions. Unrecovered observations
with fewer than 20 remaining sessions are censored/unknown, not false.

MFE/MAE use held-session OHLC, excluding the exit day's unknown post-exit path;
entry OPEN is known, so surviving entry-session high/low is valid. For an
intraday stop, pre-stop high is unknowable: report conservative observed MFE
(prior held sessions plus exit reference) and flag exit-day censoring. A full
exit-session-range envelope may be reported separately, never as known pre-exit
excursion. Group diagnostics by winners, losers, stop, and strategy exit.

Entry location is `(Close[T]/EMA20[T]-1)*100`: [-10,-7.5), [-7.5,-5),
[-5,-2.5), [-2.5,0), [0,1], final endpoint inclusive. Report signal/trade counts,
win rate, average return, stop rate. Report `(EMA20-EMA50)/EMA50*100` distribution
and descriptive stop-risk buckets (0,2], (2,4], (4,6], (6,10], >10 with return,
MAE/MFE/stop rates. These buckets cannot change V1 or select a new candidate.

Current illustrations after freeze: fixed APA, APO, IBKR, EOG, AXON, FAST, AAPL,
MSFT where stored completed data exists. These are descriptive only and cannot
enter formal snapshot performance. Show date/close/EMAs/ATR/trend/zone/distance;
an unknown future fill means STOP PRICE NOT YET KNOWABLE UNTIL ENTRY FILL.

## Fingerprints, tests, and handoff

Serialize the exact StrategySpecification, candidate, dataset, periods, costs,
execution rules, portfolio settings, gates, and diagnostic conventions using
Strategy Lab canonical JSON/SHA-256. Record protocol/configuration fingerprints,
source-file hashes, Git HEAD/dirty state and artifact hashes before/after runs.
No future-data indicator/entry/exit dependency is allowed; tests must explicitly
cover overlapping BUY/held-exit facts, first-day stops, simultaneous exits,
fresh-signal re-entry, costs, invalid ATR, and preservation of old strategies.
Run focused tests, then `cd backend; $env:DEBUG='false'; .\run_checks.ps1`.

Final report: `docs/research/ACHIA_STRAT_EMA20_RESULTS.md`. Disclose survivorship
bias, current rather than point-in-time membership, legacy/feed limitations,
split-adjusted price returns rather than dividend total returns, reused windows,
fixed 5 bps friction, daily OHLC ambiguity/gap risk, and open-position handling.
No activation in StrategyProfile defaults, Scanner, Portfolio Plan, UI, Paper,
or broker. Independent/user review owns every next decision and Git publishing.

## Recorded pre-performance freeze

Implementation passed 93 focused tests and the complete backend gate (515 tests,
Ruff/formatting, mypy 194 source files) before performance execution.
The immutable local `backend/backtest_reports/achia_strat_ema20/freeze.json`
contains the complete canonical protocol and per-source-file SHA-256 manifest.

- Protocol fingerprint:
  `82b3e903820009ef53455c431a93001340216d4914de9c249cfd093d581ea06f`.
- Candidate/configuration fingerprint:
  `1b6f103a0394f76755c56671bdc64a8653195c7873a975b3690c2d4c4c88f6cf`.
- Git HEAD at freeze: `decc7d1`, branch `research/ema20-loss-control`, dirty local
  worktree with earlier research/UI changes preserved. No commit or push.
- Command: `uv run python -m alphapilot.cli.research_achia_ema20 --freeze-only`
  from `backend`, with child-process `DEBUG=false`.

The runner refuses mismatched source/protocol fingerprints and refuses to
overwrite a completed experiment. No performance results were inspected before
this freeze was recorded.

## Post-run reporting correction — not a protocol amendment

The single development execution completed on 2026-09-08 with all frozen sources
unchanged during execution. No strategy/risk/cost parameter was changed afterward.
A reporting-only exact-equality check used the algebraic rearrangement
`fill * 0.99 - ATR` instead of execution's `fill - ATR - fill * 0.01`. Repeating
ATR decimals caused false invalid-boundary flags at at most 3e-26 dollars for six
portfolio entries. The check now uses the identical execution operation order;
no tolerance/threshold was introduced and the stop calculator is unchanged.
Original `freeze.json`, run summaries, CSVs and classification evidence remain
untouched. `post_run_boundary_audit/` separately records corrected 100% coverage,
source hashes and the remaining failed gates. Validation and folds remain closed.
Final checks after this correction: 94 focused tests; 516 full backend tests,
Ruff/formatting and mypy (194 source files). This note preserves chronology rather
than pretending the reporting fix existed at the initial freeze.
