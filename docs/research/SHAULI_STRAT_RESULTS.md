# Shauli_strat DAILY V1 — results and final research handoff

Status: **COMPLETE LOCALLY / REJECTED AT DEVELOPMENT**.
Performance run: 2026-09-08 UTC. Final handoff: 2026-09-09 local date.

The approved frozen `shauli-strat-v1` implementation and tests are complete.
Development produced **7,895 setups, 1,353 sweeps, 104 structural confirmations,
zero displacement/POI plans, and zero entries/trades**. Final equity remained
$100,000. Ten mandatory Development checks failed; Validation and folds were
**not opened**. No parameter, source rule, or executable was changed after freeze.

This is a rejected **DAILY/LONG_ONLY mechanical research variant**, not a finding
that every interpretation of the conceptual or intraday Shauli strategy fails.
Zero drawdown here means zero market exposure, not successful loss control.
The new ambiguity exclusion is implemented/tested but had no eligible empirical
observations. It did not cause this zero-trade result.

## 1. Authority, freeze and reproducibility

The source request is attachment
`d324b963-f6a0-4246-a635-621579b1e5e5/pasted-text.txt`, followed by the user's
explicit approval of `AMBIGUOUS_ENTRY_TARGET_ORDER`. Its source SHA-256 is
`ffb0a09aee2d8ca22edcd31d2b9f04fb906cdcf257975add483e8918a5313792`.
The conceptual [source draft](SHAULI_STRAT_SPEC_DRAFT.md) was read and preserved.
The [frozen protocol](SHAULI_STRAT_PROTOCOL.md) incorporates the supplied V1 rules,
approved exclusion, measurement conventions and gates. Its old blocker sections
are labeled historical; they are not the current status.

| Identity | Exact value |
|---|---|
| Canonical strategy/version | `shauli-strat-v1` / `1` |
| Display name | `Shauli_strat` |
| Scope | DAILY (`1Day`), LONG_ONLY, frozen S&P 500, RESEARCH_ONLY |
| Executable protocol SHA-256 | `b62842660be41ebe5ef12d01d7855684aebfd4beb14b2aa726ac7fdf329f56c3` |
| Single configuration SHA-256 | `2d556432cb736d860df2a7322041a774bf7fa8f3b636db251d0f3d99b187229a` |
| Strategy source SHA-256 | `947fea4605d5e4a3e9a1a9a6f46456b64dd73a53a38d3b4e2a7f6e3557ff5784` |
| Execution adapter SHA-256 | `e55e5d60014b5122ad93eda284709dadc6da58214c682f3afb4bc3c55ac3feeb` |
| Frozen protocol document SHA-256 | `47941a935c3ca7097db6417a0e737f4e9863b1fdd1881fe721a66b793f5a8998` |
| Artifact manifest SHA-256 | `a44305b1f2a46d26216aa740c42951c2f8b7aecce64360fa1e0a13d6d75dc84f` |
| Git HEAD | `decc7d1321cad512d8196f367a84848bf59355ac` |
| Branch | `research/ema20-loss-control` (unchanged) |
| Final source freeze, UTC | `2026-09-08T19:23:30.986563+00:00` |
| Run start, UTC | `2026-09-08T19:23:32.570002+00:00` |
| Run finish, UTC | `2026-09-08T19:34:58.233887+00:00` |

The numerical rules were documented before implementation/performance. After
implementation and green tests, `freeze.json` sealed 66 executable/dependency/
protocol-document paths before the first performance command. It also records
typed configuration, protocol identity, UTC timestamp, Git revision/dirty state,
untracked inventory and command. The run refuses source mismatch or an existing
started experiment; there was one performance invocation, not a parameter search.
All 66 hashes matched after the run and at the final read-only audit.

The unchanged EMA reference was reused only after its artifact hashes and matching
snapshot/period/cost/sizing metadata were checked. Its summary SHA-256 is
`cb136448ff77e4a4ef15276447a8713f70cdf3ed333c9bcf566955086a580ceb`.
An equivalent Micho equal-slot reference was not available in the earlier study
(the older reference used volatility-normalized sizing), so the unchanged Micho
BOTH strategy ran once as predeclared descriptive context. Neither reference
selected or changed a Shauli rule.

## 2. Full frozen V1 definition: concept versus executable rule

All rows below are **RESEARCH_ASSUMPTIONS**, not claims about an unambiguous
intraday implementation of the original chart concept.

| Source concept | Frozen deterministic DAILY V1 implementation |
|---|---|
| Market/timeframe/direction | Frozen S&P 500 only; completed Daily OHLC; LONG only. No intraday/short/custom-universe expansion. |
| Structural swings | Strict 2-left/2-right pivots. High must exceed all four neighboring highs; low must be below all four neighboring lows. Equality rejects the corresponding pivot. |
| Confirmation delay | Pivot at session i is usable only at completed i+2. `pivot_at` and `confirmed_at` are separate; BOS/sweep require prior-session confirmation. |
| Equal liquidity pools | EQH/EQL disabled; only confirmed structural swings supply liquidity. |
| Bullish context | Latest confirmed high > preceding high AND latest confirmed low > preceding low. Re-evaluated continuously; no silently frozen bullish bias. |
| Source BOS | Completed Close strictly above the latest eligible high confirmed before that session; wick/equality do not qualify. Each swing is broken at most once. |
| Inducement | Most recent qualifying confirmed higher low formed strictly after source BOS, above preceding structural low, not previously breached. A newer eligible prior-confirmed HL replaces an older one before the sweep. |
| SSLQ | That inducement's exact low, with pivot and confirmation provenance; no fabricated equal-low pool. |
| Sweep/reclaim | Same completed candle Low < SSLQ and Close > SSLQ, with inducement known before the candle. Failed reclaim invalidates. |
| Structural confirmation | Later completed Close strictly above the frozen latest high known before the sweep. No same-sweep hindsight authorization. |
| BOS/CHOCH label | Helper labels prior bearish structure as BULLISH_CHOCH, otherwise BULLISH_BOS. The continuous bullish eligibility gate means no CHOCH path was reached; the label does not change entry rules. |
| Displacement | Three candles all strictly after sweep; bullish middle candle Close > Open and Close > frozen confirmation high. Third candle must establish the bullish FVG. |
| FVG | `Low[C] > High[A]`; zone `[High[A], Low[C]]`, known only at C close. Minimum size is strictly positive, with no additional numerical threshold. |
| Optional OB | Last bearish candle from sweep inclusive to displacement middle exclusive; full Low/High wicks. Missing OB does not by itself invalidate an FVG. |
| POI | Positive-width FVG/OB intersection first; if absent/non-overlapping/zero-width, full FVG. No substitute discretionary zone. |
| Dealing range | Sweep low through highest High from sweep to FVG completion, inclusive. Equilibrium is midpoint of those extremes. |
| Discount | Mandatory `POI midpoint <= equilibrium`; equality passes. Premium LONG entries forbidden. |
| Entry level | Exactly 50% of POI: `(POI low + POI high)/2`. |
| Entry timing | Only a subsequent available ticker session after the complete plan is known. No entry on POI creation candle; no retracement means no trade. |
| Raw/slipped fill | Low <= entry triggers nominal entry level, subject to opening/exclusion rules. No favorable opening-price improvement. BUY fill = raw entry × 1.0005. |
| Structural stop | Sweep low if no OB; otherwise min(sweep low, OB low). No buffer. Require `0 < stop < actual entry fill`. Fixed after plan formation. |
| Target BSLQ | Nearest unconsumed confirmed swing high strictly above actual fill, known before entry. A High touch consumes a high. Target cannot already have been consumed by displacement. |
| Reward/risk | `(target - actual fill)/(actual fill - stop) >= 2.0`; exactly 2 passes. No ATR/fixed-percentage replacement target. |
| Pending lifetime | One active source-BOS/setup per ticker; no arbitrary timeout. Loss of valid structure, structural invalidation or pre-entry target consumption cancels. First valid FVG fixes the zone/geometry; no later replacement to rescue a rejection. |
| Pending invalidation boundary | Sweep low before POI; fixed structural stop once a complete plan exists. Completed-close processing never retroactively removes an actual fill. |
| Opening precedence | Pending OPEN <= stop cancels before entry; OPEN >= target cancels as consumed target. An already-held stop gap exits at OPEN; target gap exits at OPEN before a later intraday low. |
| Entry/stop collision | Entry then structural stop when entry and stop touch on one bar, unless a known opening event already cancelled. If target also touches, STOP_FIRST. |
| Entry/target-only collision | Approved exclusion described in section 3; never infer a favorable intraday sequence. |
| Held intraday collision | With no resolving opening event, Low <= stop wins over High >= target: STOP_FIRST. No double exit. |
| Normal exits | Fixed structural stop or opposing-liquidity target only; SELL fill = raw exit × 0.9995. Stop gaps are explicitly marked. |
| Profit management | No partial exits, breakeven, trailing, EMA exit, time exit or discretionary override. |
| Re-entry | A fresh source BOS and complete new sequence after exit; never recycle the exited setup. |
| Other filters | No EMA/SMA/SPY regime/News/AI technical filter. RS20 is portfolio competition only, not a Shauli setup condition. |

### Additional frozen simulation and measurement assumptions

- Load all earlier snapshot bars for structural/liquidity warm-up. Start each
  measured period flat; no warm-up trades or carried orders. New setup sequences
  start inside the measured period. No candle after the period end is supplied.
- Shared portfolio: $100,000, ten equal slots, whole shares, no leverage,
  COST_LOW: 5 bps per side, zero commission. No risk/sector/reserve overlay.
  Independent ticker simulations: separate $100,000 and one slot each, with no
  cross-ticker competition. They are not one realizable pooled portfolio.
- Before looking at intraday lows, reserve pending-order cash and slots in
  existing RS20 order calculated from the last completed ticker session.
  Score = stock 20-bar return minus SPY as-of 20-bar return. Higher first,
  ticker ascending ties, unscored last/ticker ascending. No current-close ranking.
- Whole-share sizing uses min(unreserved cash, opening equity/max positions)
  divided by slipped entry fill, floored. Untriggered reservations cannot be
  reassigned based on later lows. Opening exits may fund new orders; intraday
  exit proceeds cannot fund same-session orders. Cash remains shared/nonnegative.
- Final held positions are marked to final available close, not force-liquidated.
  There were no such positions in Shauli Development. Reference positions retain
  their existing final-open handling.
- Setup funnel counts unique setup IDs reaching each state, not repeated daily
  observations. Terminal reasons are first terminal outcomes. Pending states at
  period end are censored, not invented losses or successful trades.
- Entry-ready denominator means a unique complete valid POI/Discount/stop/target/
  RR plan before retracement; it is not merely a raw BOS or the eventual fill.
  Would-be trigger denominator counts pending bars whose Low touches entry,
  including cancelled/excluded trigger bars. Zero denominator means unavailable.
- Initial risk/share = slipped entry minus stop; initial risk dollars = shares
  × initial risk/share; realized R = net trade P&L / initial risk dollars.
  Initial RR and stop-risk distributions use executed entry provenance.
- MFE/MAE use only full held sessions strictly between entry and exit; entry/exit
  candles are censored because their path cannot establish precise excursions.
  No interior observation means unavailable. This is not a full-path MFE/MAE.
- Post-stop recovery looks at the next 5/10/20 ticker sessions within the same
  period only, never affecting execution. Incomplete horizons are censored.
- Distribution percentiles use the existing floor-index convention; median is
  the midpoint of middle observations. Reconciliation tolerance is $0.00000001.
  Gross P&L adds measured friction back on the same executions; it is not a
  separately simulated zero-cost counterfactual.
- One hypothesis, no parameter sweep, no changes after Development, no
  Validation retuning. Unavailable mandatory metrics fail. Five explained
  no-history tickers are not silently replaced or treated as strategy exceptions.
- Validation requires every Development check. Validation uses the same checks;
  failure closes folds. Only an eligible candidate could reach the three frozen
  folds and existing final Strategy Lab classification. No such stage was opened.

## 3. Approved ambiguity rule and measured attribution

For a **PENDING LONG**, if entry and target touch, stop does not touch, and
`ENTRY_LEVEL < OPEN < TARGET`, the result is exactly:

`AMBIGUOUS_ENTRY_TARGET_ORDER` → cancel pending setup → NO ENTRY → NO TRADE.

No target win is credited and neither intraday order is inferred. This is a
Daily OHLC research exclusion, not a claim that every excluded path was losing.
Opening causal precedence and all previously frozen ENTRY_THEN_STOP/STOP_FIRST
rules remain intact. OPEN at/below entry but above stop is not the strictly-
between case; nominal entry becomes causally available at the opening event.

| Requested diagnostic | Shared Development | Pooled independent |
|---|---:|---:|
| `ambiguous_entry_target_order_count` | 0 | 0 |
| Entry-ready setups | 0 | 0 |
| `ambiguous_entry_target_order_pct_of_entry_ready_setups` | N/A (0/0) | N/A (0/0) |
| All would-be entry-trigger bars | 0 | 0 |
| Exclusion count relative to would-be trigger bars | 0 of 0 | 0 of 0 |
| `ambiguous_entry_target_order_pct_of_would_be_entry_trigger_bars` | N/A (0/0) | N/A (0/0) |
| Entry-bar stop ambiguity executions | 0 | 0 |
| Already-held stop/target ambiguity executions | 0 | 0 |

Each independent summary contains both denominators and percentages; their zero
counts reconcile to the shared summary. The code path is verified by synthetic
tests, not by a claim of observed ambiguity prevalence or avoided losses.

## 4. Data provenance and run coverage

| Item | Verified result |
|---|---|
| Snapshot | `5dd60f87-8947-4850-ba87-4a7df655528c` |
| Dataset SHA-256 | `b77ba749182fb4408394eed6d47c7d39dcfcb52a4555683c8a0b9fa7cb91374b` |
| Universe SHA-256 | `369350debc5b9649a0f24f6bda863aa8c8d7f85a73965ea16616712d1c5a4ec8` |
| Snapshot validation | Finalized/value-reproducible, expected hashes, Daily timeframe |
| Verified immutable rows / universe members | 745,232 / 502 |
| Requested and actual Development curve | 2021-08-20 through 2024-12-31 |
| Curve sessions | 846 |
| Prepared tickers | 497 |
| Explained unavailable-history tickers | FDXF, HONA, PSKY, Q, SNDK |
| Unexplained preparation failures | 0 |
| Independent ticker simulations completed | 497 |
| Shared Shauli portfolio simulations completed | 1 |
| Validation runs / fold runs | 0 / 0 |

These are frozen **current constituents**, not historical point-in-time members:
survivorship bias and missing/delisted-company bias remain. LEGACY_PARTIAL origin
does not become perfect historical provenance just because values are immutable.
Both named historical periods have already been observed in AlphaPilot research;
they are not pristine future out-of-sample data.

The runner uses `FrozenDatasetMarketDataSource` inside a PostgreSQL
REPEATABLE READ, READ ONLY transaction, verifies the snapshot before performance,
and rolls back on completion. No mutable-current-candle fallback, market-data
refresh, provider call, migration or application-data write occurred. Test database
identity was checked to be distinct from the development database without printing
credentials. Tests use the existing isolated test-database lifecycle.

## 5. Measured setup funnel and why no entry occurred

| Unique setup stage | Shared | Sum of independent |
|---|---:|---:|
| Source BOS / CONTEXT_IDENTIFIED | 7,895 | 7,895 |
| LIQUIDITY_MAPPED | 4,887 | 4,887 |
| INDUCEMENT_IDENTIFIED | 4,887 | 4,887 |
| LIQUIDITY_SWEPT | 1,353 | 1,353 |
| STRUCTURE_CONFIRMED | 104 | 104 |
| DISPLACEMENT_CONFIRMED | 0 | 0 |
| POI_READY | 0 | 0 |
| Discount pass | 0 | 0 |
| Valid target | 0 | 0 |
| RR >= 2 / complete entry-ready plans | 0 | 0 |
| WAITING_FOR_RETRACE | 0 | 0 |
| ENTRY_READY / IN_POSITION | 0 | 0 |
| TARGET_HIT | 0 | 0 |
| INVALIDATED | 7,883 | 7,883 |
| Pending/censored at end | 12 | 12 |

`IDLE` is not counted as a setup: setup IDs begin at source BOS. All 497 prepared
tickers produced at least one source setup. All 497 had zero entries and flat
returns; none had a positive or negative return.

Terminal reconciliation:

| Outcome | Count |
|---|---:|
| NO_VALID_STRUCTURE | 5,863 |
| SWEEP_NOT_CONFIRMED | 1,479 |
| STRUCTURAL_STOP — pending setup cancellation | 541 |
| Pending CONTEXT_IDENTIFIED at period end | 8 |
| Pending INDUCEMENT_IDENTIFIED at period end | 4 |
| Total | 7,895 |

All **1,353 swept setups** terminated before displacement: **812** lost valid
structure and **541** hit the pending sweep boundary. Of the **104** that first
reached structural confirmation, **94** subsequently lost valid structure and
**10** breached the boundary. No swept setup remained pending at the end.

The causal issue is the combination of the frozen continuous latest-HH/HL rule
and the strictly post-sweep three-bar displacement requirement. A sweep undercuts
the latest qualifying confirmed HL. If the next two lows stay above the sweep
extreme, its lower pivot can confirm at S+2 and destroy the required latest-HL
structure. A full three-candle sequence strictly after the sweep cannot complete
before S+3. If price instead revisits/breaches the sweep extreme first, the
pending setup is invalidated by its structural boundary. The frozen protocol
explicitly warned about this interaction before results; it was not relaxed to
manufacture trades. The observed funnel confirms that no swept setup survived
to displacement on this dataset.

Auditable example: `AAPL:2023-03-24:9`. Its final mapped inducement is the
2023-05-12 low 171.0000, confirmed 2023-05-16. The 2023-05-17 sweep reached
170.4201 and reclaimed at 172.6900. The frozen confirmation high was 174.5900
(pivot 2023-05-11, confirmed 2023-05-15). Structural confirmation occurred
2023-05-18; `NO_VALID_STRUCTURE` invalidated the setup on 2023-05-19, before
three strictly post-sweep bars could complete. Full provenance and transitions
are in `setups.json`.

This is a **setup-reachability failure in the frozen V1**, not evidence that
executed Shauli trades have negative expectancy. It cannot be solved within this
completed experiment by freezing bias, allowing earlier FVG candles, changing
swing size or weakening stops. Those would change the hypothesis.

## 6. Independent and shared performance

| Metric | Shared portfolio | Independent ticker analysis |
|---|---:|---|
| Initial / final equity | $100,000 / $100,000 | $100,000 / $100,000 for each of 497 tickers |
| Net / same-execution gross return | 0% / 0% | 0% / 0% each |
| CAGR | 0% | 0% each |
| Maximum drawdown | 0% | 0% each |
| Sharpe / Calmar | N/A / N/A | N/A / N/A each |
| Entries / completed trades / final open | 0 / 0 / 0 | Pooled 0 / 0 / 0 |
| Profit factor | N/A | Pooled N/A |
| Expectancy, percent and dollars | N/A / N/A | Pooled N/A / N/A |
| Win rate | N/A, no trades | N/A, no trades |
| Mean / median / worst loser | N/A / N/A / N/A | N/A / N/A / N/A |
| Worst trade / average holding duration | N/A / N/A | N/A / N/A |
| Exposure / turnover | 0% / 0% | 0% / 0% each |
| Average / maximum concurrent positions | 0 / 0 | 0 / 0 each |
| Average / minimum / final cash | $100,000 / $100,000 / $100,000 | Same for each ticker |
| Cash share | 100% throughout | 100% throughout |
| Realized / unrealized / total P&L | $0 / $0 / $0 | $0 / $0 / $0 each |
| Transaction friction | $0 | $0 each; no fills |
| Reconciliation residual | $0 | $0 each |

The existing common metrics calculator serializes `metrics.win_rate_pct=0` for
an empty trade list. That compatibility behavior was not changed. Shauli's trade
and independent statistics correctly return null; this report interprets win
rate as **N/A**, not measured 0% success. No unavailable quantity is presented as
proof of risk safety. Cash-only zero return/drawdown are real portfolio values.

Dollar reconciliation is exact:

`100000 + realized net P&L 0 + unrealized net P&L 0 = final equity 100000`.

Equivalently, initial equity + gross realized + gross unrealized - measured
transaction friction = final equity. Friction is not subtracted twice from net
P&L. Independent capital is separate per ticker; summing those accounts does
not represent a shared $100,000 investable portfolio.

### Risk, R, stops, targets, excursions and structural attribution

- Executed stop-distance P50/P75/P90/max, risk dollars, risk/share and planned
  portfolio-risk distributions: **N/A**, zero executed entries. Counts above
  5%/10%/20% risk are zero, not proof of compliance. Valid executed stop/target
  provenance percentage is N/A, not a vacuous 100%.
- Initial RR mean/median/P50/P75/P90/max: **N/A**. Realized R mean/median/
  P25/P50/P75/P90/min/max and winner/loser R: **N/A**. There is no observed 2R win.
- Executed structural stops: **0**. Opposing-liquidity target exits: **0**.
  Executed gap-through stops: **0**. The 541 pending STRUCTURAL_STOP cancellations
  must not be described as 541 stopped trades or financial losses.
- MFE/MAE, loss tails, holding distributions and peak giveback: **N/A**.
  No interior-held-session observations exist. Exact full-day-path excursions
  would remain unknowable on an ambiguous entry/exit candle even with trades.
- Post-stop recovery at 5, 10 and 20 sessions: **0 eligible executed stops** at
  every horizon; recovery rates and returns **N/A**. No future stage was opened
  to fill missing recovery history.
- FVG_ONLY versus FVG_OB_OVERLAP: **0 plans and 0 trades** in both groups;
  group PF/expectancy/R/return **N/A**. POI width, distance from equilibrium and
  sweep low at entry are also **N/A**; no Premium entry occurred.
- All 1,353 sweep diagnostics were BULLISH_BOS; 104 reached confirmation.
  BULLISH_CHOCH count is **0**. Both completed-trade groups are empty with
  unavailable performance. Continuous bullish eligibility makes this label
  comparison non-informative; no bearish eligibility was added for coverage.
- Unique held tickers/positive contributors/negative contributors: **0/0/0**.
  Top-1/5/10 dollar P&L is $0; gain shares, positive-P&L shares and HHI are N/A.
  No sector attribution or concentration improvement can be inferred.
- Portfolio allocation rejections: **0**. No ready candidates reached RS20,
  cash or slot competition. The observed rejection is technical, not capital-
  constrained or caused by the approved ambiguity exclusion.

## 7. Frozen Development gates and stage outcome

| Mandatory gate | Actual | Result |
|---|---|---|
| Verified snapshot/hash | Expected hashes, 745,232 rows verified | PASS |
| Completed shared trades >=100 | 0 | FAIL |
| Net return >0 | 0% | FAIL |
| CAGR >0 | 0% | FAIL |
| Sharpe >=0.50 | N/A | FAIL |
| Calmar >=0.50 | N/A | FAIL |
| Profit factor >1 | N/A | FAIL |
| Pooled independent expectancy >0 | N/A | FAIL |
| 100% valid executed stop/target provenance | N/A, no entries | FAIL |
| Planned stop risk P90 <=10% | N/A | FAIL |
| Maximum planned stop risk <=20% | N/A | FAIL |
| Nonnegative cash | Minimum $100,000 | PASS |
| Maximum positions <=10 | 0 | PASS |
| Reconciliation within $1e-8 | $0 residual | PASS |
| No unexplained preparation failures | 0; five explained no-history tickers | PASS |

**5 PASS / 10 FAIL.** Missing evidence fails a required gate; unavailable risk
statistics do not assert that a measured risk threshold was exceeded.
The research-only early-stage adapter records actual Development evidence and
the exact failed reasons in the existing typed Strategy Lab experiment model.
Final stage is CLASSIFIED and classification is **REJECTED**. There is no
profile candidate and no operational promotion.

Validation **2025-01-01–2026-08-20: NOT OPENED**, no results.
Folds **2021-08-20–2022-12-31**, **2023-01-01–2024-12-31**, and
**2025-01-01–2026-08-20: NOT OPENED**, no stability claims.
No alternative candidate, tuning run, validation retry or new experiment followed.

## 8. Unchanged EMA20 and Micho Development context

Same snapshot, requested Development period, $100,000, ten equal slots, RS20
portfolio selection, COST_LOW 5 bps/side and zero commission. EMA is frozen
HYBRID 2%; Micho is frozen BOTH. Their existing next-open strategies are unchanged;
Shauli has its explicitly separate pending-limit semantics and structural warm-up.
This is descriptive context, not matched entry timing or a global strategy contest.

| Metric | Shauli V1 | EMA20 HYBRID 2% | Micho BOTH |
|---|---:|---:|---:|
| Final equity | $100,000.00 | $180,145.51 | $159,916.35 |
| Net return | 0.00% | 80.1455% | 59.9163% |
| CAGR | 0.00% | 19.1158% | 14.9729% |
| Max drawdown | 0.00% | 26.4281% | 19.2698% |
| Sharpe | N/A | 0.8687 | 0.8071 |
| Calmar | N/A | 0.7233 | 0.7770 |
| Profit factor | N/A | 1.4667 | 1.4957 |
| Mean completed-trade return / expectancy | N/A | 2.0531% | 0.9808% |
| Completed trades | 0 | 253 | 254 |
| Win rate | N/A | 32.0158% | 24.0157% |
| Turnover | 0.00% | 5,511.9355% | 5,228.1717% |
| Actual transaction friction | $0.00 | $2,755.94 | $2,614.06 |
| Average loser | N/A | -5.2655% | -3.0485% |
| Worst trade | N/A | -17.5280% | -12.0067% |
| Average holding, calendar days | N/A | 36.9447 | 45.8465 |
| Exposure | 0.00% | 78.7860% | 98.6818% |
| Average positions / maximum | 0 / 0 | 7.8889 / 10 | 9.9267 / 10 |
| Realized net P&L | $0.00 | $45,251.47 | $28,354.44 |
| Final-open unrealized P&L | $0.00 | $34,894.04 | $31,561.91 |

Micho's reference again contains material unrealized contribution; do not treat
all final gain as completed-trade profit. Both references share the five explained
absent-history constituents. No historical EMA/Micho result was rewritten.

SPY Buy & Hold on the same frozen period, $100,000 and existing 5 bps entry
handling: final equity **$133,057.98**, return **33.0580%**, CAGR **8.8589%**,
drawdown **25.3564%**, Sharpe **0.5711**. This is stored-price-return evidence,
not a dividend-total-return benchmark; the final holding is not force-liquidated.
Shauli's flat cash account did not capture the reference returns. Its 0% drawdown
cannot be used to prefer it over invested strategies.

## 9. Architecture, tests and no-lookahead evidence

New research-only source files:

| File under `backend/src/alphapilot/` | Responsibility |
|---|---|
| `strategy/shauli.py` | Typed setup/state/reason models; causal pivots, context, liquidity, sweep, FVG/OB/POI and fixed plan construction. |
| `backtesting/shauli.py` | Pure daily pending/held execution rules and isolated shared-cash pending-limit simulator. Reuses existing position/trade/equity/cost models. |
| `backtesting/shauli_reporting.py` | Unique setup funnel, trade/R/risk/censored excursion/recovery reports and existing metrics/attribution integration. |
| `strategy_lab/shauli_protocol.py` | One immutable candidate/configuration, dataset binding, mandatory gates and typed early rejection. |
| `cli/research_shauli.py` | Freeze/integrity guard, read-only snapshot replay, independent then shared analysis, verified contextual references and gated stages. |

No existing strategy/factory, common portfolio engine, operational profile,
Portfolio Plan or frontend source was changed by this Shauli implementation.
The worktree already contained unrelated research/frontend changes; those were
preserved. Existing Decimal report utilities in `achia_reporting.py` are reused,
not Achia strategy rules. Shauli exit reasons are preserved in its typed execution
sidecar and merged trade artifact, rather than extending production exit enums.

New tests:

- `backend/tests/backtesting/test_shauli.py`: 63 parameterized cases covering
  strict pivots/equality/confirmation delay, HH/HL, BOS versus wick, prior-known
  inducement/sweep/reclaim, exact FVG/OB/POI, Discount, target consumption/RR,
  pending entry timing, opening precedence, approved ambiguity cancellation,
  entry/held stop-target behavior, no double exit/recycled setup, cash/whole shares,
  rank reservations, no intraday proceeds reassignment, reconciliation and censored
  recovery/excursions. Prefix invariance and future-close/SPY perturbation tests
  verify no future information changes prior decisions.
- `backend/tests/strategy_lab/test_shauli_protocol.py`: 13 cases covering the
  one-candidate freeze, exact inclusive/exclusive gate boundaries, missing-data/
  cash/provenance/reconciliation failures and rejection requiring actual evidence.
- Existing execution, EMA and Micho regression tests ran unchanged in the final
  focused selection; the full backend suite also remained green.

The full detector consumes increasing unique candle prefixes. Confirmation
timestamps, fixed pre-sweep level, complete-plan known date and later execution
date are distinct. Three-candle FVG availability cannot be backdated to its first
candle; neither OB nor target permits entry before the plan is complete. Portfolio
ranking uses prior completed stock/SPY information. Tests cover the approved
entry-target-only exclusion and exact 2.0 RR boundary without live data.

Some downstream component tests deliberately seed a swept state or a valid plan
to isolate FVG/POI and execution arithmetic. **Those tests do not demonstrate that
the raw V1 state machine naturally reaches those states.** The real full-sequence
funnel is the separate evidence for reachability, and it failed before POI.

### Exact test and research commands

Working directory `backend`. All environment assignments were scoped to child
PowerShell processes; `.env` and application configuration were not modified.
The host's default uv cache raised an access-denied error before tests could run.
The following ignored workspace cache resolved that environment issue:

```powershell
$env:UV_CACHE_DIR='C:\Users\achia\Projects\AlphaPilot\backend\backtest_reports\.uv-cache'
$env:DEBUG='false'
uv run --no-sync pytest tests/backtesting/test_shauli.py -q
uv run --no-sync pytest tests/backtesting/test_shauli.py tests/strategy_lab/test_shauli_protocol.py -q
uv run --no-sync pytest tests/backtesting/test_shauli.py tests/strategy_lab/test_shauli_protocol.py tests/backtesting/test_trade_management.py tests/strategy/test_ema20_pullback.py tests/strategy/test_micho150.py -q
.\run_checks.ps1
uv run --no-sync python -m alphapilot.cli.research_shauli --freeze-only
uv run --no-sync python -m alphapilot.cli.research_shauli
```

| Gate | Recorded result |
|---|---|
| Initial focused Shauli tests, before additions | 55 passed in 26.75s |
| Final two new test modules | 76 passed in 12.37s |
| Final focused regression selection | 117 passed in 13.92s |
| Full Ruff | PASS |
| Full formatting | PASS, 297 files unchanged |
| Full mypy | PASS, 199 source files |
| Full backend pytest | 592 passed in 85.66s |
| `run_checks.ps1` exit | 0 / ALL PASS |
| `git diff --check` before final report creation | PASS; LF/CRLF informational notices only |

No code changed after the final quality gate. Post-performance actions were
read-only artifact/CSV/JSON/hash and Git inspection plus this report and continuity
documentation. No frontend change/test/build or migration was needed. No real
acceptance provider/API/broker request ran.

## 10. Artifacts and audit results

All generated experiment files remain Git-ignored beneath
`backend/backtest_reports/shauli_strat_v1/`.

- Root: `freeze.json`, `started.json`, `dataset_verification.json`,
  `references.json`, `micho_reference_trades.csv`, `development_gates.json`,
  `experiment.json`, `completed.json`, `artifact_sha256.json`.
- `shauli_2021-08-20_2024-12-31/`: `summary.json`, `setups.json`, `setups.csv`,
  `entries.csv`, `trades.csv`, `order_audit.csv`, `equity.csv`,
  `open_positions.csv`, `attribution.csv`, `stop_recovery.csv`,
  `independent_tickers.csv`, `independent_trades.csv`.
- `independent/{ticker}/`: the corresponding per-ticker summary, setup,
  entry/trade/equity/attribution/order/recovery artifacts for all 497 tickers.

Final read-only audit verified **4,990 artifact hashes**, parsed **1,004 JSON
files** (including the manifest) and **3,987 CSV files**, and rechecked **66
frozen source hashes**. All 498 equity curves (497 independent plus shared) contain
846 sessions with cash/equity exactly $100,000. All independent funnel counts sum
to shared counts. Setup IDs are unique; stored BOS/sweep confirmation chronology
checks passed. All setup plan/POI fields are genuinely absent, not lost trade rows.

Main CSV rows: setups 7,895; independent ticker summaries 497; shared equity 846;
Micho reference completed trades 254. Shauli entries, trades, independent trades,
order audit, open positions, attribution and stop recovery each contain zero data
rows, consistent with the funnel, not missing executed evidence. The runner's
completion artifact confirms READ ONLY transaction rollback, unchanged source,
REJECTED classification, `validation_opened=false`, `folds_opened=false`.

## 11. Interpretation, limitations and next step

What this proved:

- The one frozen DAILY V1 can be implemented, fingerprinted, replayed and audited
  deterministically without operational integration or state mutation.
- The approved daily ambiguity rule has explicit no-trade semantics and both
  required denominators; it does not silently award a target win.
- The real Development sequence fails before displacement/POI. Stage governance
  correctly stops without Validation, folds or attempts to improve the result.
- Portfolio accounting stayed exactly reconciled; existing backend regressions
  remain green. Synthetic execution tests cover paths absent from the real run.

What this did **not** prove:

- No executed-trade expectancy, PF, RR outcome, stop effectiveness, target success,
  loss tail, concentration benefit or ambiguity-exclusion economic benefit.
- No Validation/fold robustness, pristine future-OOS edge, live fill reliability,
  capacity or superiority to EMA/Micho.
- No equivalence to an intraday/discretionary source strategy, production
  readiness or justification to activate Shauli.

Known limitations and research debt:

1. **Survivorship bias/current-constituent universe**, no point-in-time membership,
   five explained missing-history constituents and LEGACY_PARTIAL provenance.
2. Historical periods were already observed; immutable inputs improve
   reproducibility, not independence from previous research exposure.
3. Daily bars cannot resolve true intraday order. STOP_FIRST, entry-then-stop,
   no-favorable-gap limit fills and approved exclusion are declared approximations.
4. Fixed 5 bps/side and zero commission omit spreads, nonlinear impact, capacity,
   queue priority and guaranteed limit/stop execution. Numeric stops do not cap
   real gap losses. No interest is credited to the all-cash account.
5. SPY uses stored price returns, not dividend-total-return equivalence. Final
   open positions remain marked, not forcibly closed; reference unrealized gains,
   especially Micho's, are material and distinct from completed profits.
6. Continuous structural eligibility plus post-sweep sequencing needs conceptual
   user review before any separately authorized version. CHOCH and downstream
   trade diagnostics are unobserved, not evidence to remove inconvenient rules.
7. Pending inducement updates retain final selected inducement provenance; a
   future richer audit could record each replaced candidate swing explicitly.
   Do not confuse original mapping-transition date with final swing confirmation.
8. Existing empty-trade `metrics.win_rate_pct=0` is retained for compatibility;
   report consumers should prefer the null-aware Shauli trade statistic.
9. Research adapter/runner depend on existing uncommitted research utilities in
   this dirty worktree. Source hashes capture the exact dependency set; the user
   must preserve those dependencies when choosing commits. No packaging/refactor
   of unrelated research helpers was attempted.
10. Per-ticker audit files favor traceability over compactness. No additional
    logging, source optimization or report redesign was done after freeze.

**Final Strategy Lab classification: REJECTED.** Preserve the evidence and review
the literal structural interaction with the user. Do not continue V1 research,
change a parameter, add intraday/shorts or activate it. Any future different
interpretation requires an explicit new user-approved protocol/version, not a
retry of this experiment. No Strategy Profile, ExecutionReadiness, Portfolio Plan,
scanner default, Dashboard, frontend, Paper, News or broker behavior was changed.
ResearchPortfolio/current holdings/trade events/Paper/broker state were not mutated.
Sprint 25 was not started.

## 12. Files, Git status and recommended commit

Created by this implementation: the five Shauli source files and two test files
listed in section 9, plus this results report. Modified by this task:
`AGENTS.md`, `docs/PROJECT_STATE.md`, `docs/DECISIONS.md`, and the already-untracked
`docs/research/SHAULI_STRAT_PROTOCOL.md`. The source draft was not modified.
The frozen protocol document was not edited after its source seal. Existing
research/frontend files were preserved; a pre-performance preservation audit
confirmed 26 unrelated pre-existing paths byte-for-byte unchanged.

Final inventory after adding this report: **14 tracked modified, 25 untracked,
nothing staged**, on `research/ema20-loss-control`. No branch switch, stash,
reset/discard, commit, push, merge or PR operation occurred.

Tracked modified files (the backend/frontend entries below predate this task):

```text
AGENTS.md
backend/src/alphapilot/backtesting/multi_portfolio.py
backend/src/alphapilot/backtesting/multi_portfolio_models.py
backend/src/alphapilot/backtesting/multi_portfolio_service.py
backend/src/alphapilot/backtesting/sprint12_protocol.py
backend/src/alphapilot/backtesting/sprint12_reporting.py
backend/src/alphapilot/backtesting/trade_management.py
backend/src/alphapilot/cli/backtest_strategy_exits.py
backend/src/alphapilot/strategy/evaluation.py
docs/DECISIONS.md
docs/PROJECT_STATE.md
frontend/src/features/portfolio/PortfolioAllocationDonut.test.tsx
frontend/src/features/portfolio/PortfolioAllocationDonut.tsx
frontend/src/styles.css
```

All untracked files, including prior work and this report:

```text
backend/src/alphapilot/backtesting/achia_reporting.py
backend/src/alphapilot/backtesting/shauli.py
backend/src/alphapilot/backtesting/shauli_reporting.py
backend/src/alphapilot/cli/research_achia_ema20.py
backend/src/alphapilot/cli/research_shauli.py
backend/src/alphapilot/strategy/achia_ema20.py
backend/src/alphapilot/strategy/shauli.py
backend/src/alphapilot/strategy_lab/achia_ema20_protocol.py
backend/src/alphapilot/strategy_lab/ema20_loss_control_protocol.py
backend/src/alphapilot/strategy_lab/shauli_protocol.py
backend/tests/backtesting/test_achia_execution.py
backend/tests/backtesting/test_achia_reporting.py
backend/tests/backtesting/test_ema20_loss_control.py
backend/tests/backtesting/test_shauli.py
backend/tests/strategy/test_achia_ema20.py
backend/tests/strategy_lab/test_achia_protocol.py
backend/tests/strategy_lab/test_shauli_protocol.py
docs/research/ACHIA_STRAT_EMA20_PROTOCOL.md
docs/research/ACHIA_STRAT_EMA20_RESULTS.md
docs/research/EMA20_LOSS_CONTROL_PROTOCOL.md
docs/research/EMA20_LOSS_CONTROL_RESEARCH.md
docs/research/SHAULI_STRAT_PROTOCOL.md
docs/research/SHAULI_STRAT_RESULTS.md
docs/research/SHAULI_STRAT_SPEC_DRAFT.md
frontend/scripts/portfolio-allocation-donut-smoke.mjs
```

`git diff --stat` at handoff (tracked changes only; excludes all untracked files,
including this report; includes unrelated prior work):

```text
AGENTS.md                                             |  47 ++++-
backend/src/alphapilot/backtesting/multi_portfolio.py   |  72 +++++++-
backend/src/alphapilot/backtesting/multi_portfolio_models.py | 9 +
backend/src/alphapilot/backtesting/multi_portfolio_service.py | 2 +
backend/src/alphapilot/backtesting/sprint12_protocol.py |  41 ++++-
backend/src/alphapilot/backtesting/sprint12_reporting.py | 200 ++++++++++++++++++++-
backend/src/alphapilot/backtesting/trade_management.py  |  78 +++++++-
backend/src/alphapilot/cli/backtest_strategy_exits.py   |  13 +-
backend/src/alphapilot/strategy/evaluation.py          |   9 +
docs/DECISIONS.md                                     | 151 ++++++++++++++++
docs/PROJECT_STATE.md                                 |  68 ++++++-
frontend/src/features/portfolio/PortfolioAllocationDonut.test.tsx | 69 ++++++-
frontend/src/features/portfolio/PortfolioAllocationDonut.tsx | 39 ++--
frontend/src/styles.css                               |   2 +-
14 files changed, 755 insertions(+), 45 deletions(-)
```

The scoped Shauli implementation/tests/protocol/results/continuity changes are
ready for **user review and preservation as rejected research**, not activation.
This does not certify unrelated work as ready to commit. Generated artifacts
remain ignored. The user alone decides staging/commit/push boundaries.

Recommended commit message if the user approves preserving this evidence:

`feat(research): implement frozen Shauli daily V1 and record development rejection`

**STOP. No further experiment or integration was started.**
