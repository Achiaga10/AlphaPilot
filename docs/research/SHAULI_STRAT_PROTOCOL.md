# Shauli_strat DAILY V1 — frozen research protocol

## Approved executable protocol — frozen before performance, 2026-09-08

Executable protocol SHA-256 (existing canonical Strategy Lab identity):
`b62842660be41ebe5ef12d01d7855684aebfd4beb14b2aa726ac7fdf329f56c3`.
Single-configuration identity:
`2d556432cb736d860df2a7322041a774bf7fa8f3b636db251d0f3d99b187229a`.
The final pre-run `freeze.json` separately seals the exact source/document bytes
and UTC freeze timestamp; these identifiers never substitute for source integrity.

The user approved the final daily-order exclusion. All earlier pending-approval
sections below are historical, not current blockers. The supplied V1 rules in
the next section are incorporated unchanged. Identity `shauli-strat-v1`, version
1; DAILY/LONG_ONLY/S&P 500; RESEARCH_ONLY throughout. The conceptual source draft
is not modified, and no operational registration is authorized.

For a PENDING LONG setup, entry touched AND target touched AND stop NOT touched
AND entry < OPEN < target => `AMBIGUOUS_ENTRY_TARGET_ORDER`: cancel the setup,
NO ENTRY/NO TRADE, no credited target win, no inferred path. This is a research
exclusion. Entry+stop => ENTRY_THEN_STOP; entry+stop+target => STOP_FIRST;
already-held unresolved stop+target => STOP_FIRST. Known opening events retain
causal precedence (opening invalidation/consumed target before pending entry).

### Frozen implementation and measurement conventions

- One causal ticker state machine consumes increasing, unique completed daily
  candles. Pivots carry pivot and confirmation dates; highs/lows remain distinct.
  BOS levels must be confirmed strictly before the breaking session. A level is
  broken at most once. A qualifying inducement pivot is strictly after its BOS,
  strictly above the preceding structural low, and confirmed before the sweep.
- Continuous bullish structure uses the latest two confirmed highs and lows,
  as supplied, not a secretly frozen bias filter. A newly confirmed lower low
  can therefore invalidate a swept setup. Do not relax this to manufacture trades.
  This can also make CHOCH-labeled setups unreachable under the bullish gate;
  zero such observations must be reported, not repaired after results.
- Displacement's three candles occur after the sweep; its bullish middle close
  exceeds the frozen confirmation level. The first qualifying FVG fixes the
  optional last bearish OB (sweep inclusive, middle exclusive), POI, range, stop,
  and nearest unconsumed target. No later zone/target replacement. Liquidity
  high consumption is touch-or-above; inducement breach is strictly below.
- Pending structural invalidation before a POI uses the sweep extreme; after
  POI construction it uses the fixed structural stop. At a completed-session
  invalidation, cancel only unfilled setups, never retrospectively undo a fill.
  Existing positions exit only at the fixed stop or fixed opposing target.
- At most one source-BOS/setup is active per ticker; no new BOS replaces an
  active sequence. Rejected, cancelled, entered or exited setups are not recycled.
  After exit, a fresh BOS and subsequent complete sequence are required.
- Load all snapshot history before each period for confirmed structure/liquidity;
  initialize flat at the period start and start new BOS sequences in-period.
  Warm-up does not create carried orders, trades or performance. Right-side
  confirmation never reads beyond the current close; no stage reads later periods.
- Pending orders are ranked from last completed ticker-session RS20, not the
  current bar's close. Scored descending, ticker ascending ties, unscored last.
  Reserve whole-share equal-slot capital and slots in that order before intraday
  paths are inspected. Untriggered/rejected-order reserves cannot be reassigned
  using knowledge of later lows. Known opening exits may fund entries; intraday
  exit proceeds cannot fund same-session orders. This preserves causal shared
  cash for daily limit orders, not fictitious simultaneous intraday fills.
- Sizing budget is min(available unreserved cash, opening equity/max positions).
  Use actual entry fill with 5 bps adverse BUY friction; SELL friction is 5 bps.
  No reserve/risk/sector cap is added to equal-slot. Portfolio cap is ten, initial
  capital $100,000; independent tickers each have $100,000 and one slot.
- STOP_FIRST does not override an existing position's target gap at OPEN; this
  known opening exit precedes a later low. A pending opening target consumption
  cancels before a later retrace. If OPEN <= entry but > stop, opening entry is
  causally available at the prescribed raw entry level (no favorable improvement).
- Entry-ready denominator: unique setups attaining a complete valid POI/Discount/
  stop/target/RR plan before retrace. Would-be trigger denominator: pending setup
  bars with Low <= entry, including cancellation/exclusion bars. Report exclusion
  count and percentages against both denominators, separately per simulation.
  Zero denominators yield unavailable/null, not fabricated zero success rates.
- Setup funnel is event counts with unique setup IDs and terminal reasons, not
  repeated daily HOLD counts. Ready/waiting/open states at period end are censored.
  Portfolio allocation rejections are distinct from technical setup rejections.
- MFE/MAE use only full held sessions strictly between entry and exit; ambiguous
  entry/exit days are excluded and explicitly censored. No observed interior bar
  means unavailable, not exact zero excursion. Recovery uses next 5/10/20 ticker
  sessions within the same research period only and never influences trading.
- Native stop risk uses actual fill; R outcomes are net P&L/(initial shares ×
  initial risk/share). Dollar attribution reconciles net realized + final open
  unrealized to equity minus initial cash. Gross adds measured friction on the
  same executions; it is not a zero-cost counterfactual. Decimal reconciliation
  tolerance is 1e-8 dollars. Distribution percentiles use existing floor-index
  convention, median uses midpoint of middle observations.
- Required development gates are those supplied below. Known no-period-history
  tickers are explicitly reported/explained, not hidden or replaced; any other
  preparation failure blocks advancement. Unavailable required metrics fail.
  No universal stricter sample gate exists in generic Strategy Lab models.
- Validation, only after every development gate passes, uses the same gates.
  If it fails, reject without folds. Otherwise run the existing three disjoint
  folds (2021-08-20–2022-12-31, 2023-01-01–2024-12-31,
  2025-01-01–2026-08-20); no retuning. Apply generic Lab classification with
  minimum validation Sharpe/Calmar 0.50 and >=2 positive folds; all folds positive
  required for PROMISING_RESEARCH_BASELINE. Early failing stages are REJECTED.
- EMA HYBRID 2% and Micho BOTH, RS20/equal-slot/COST_LOW are contextual development
  references, not competing Shauli candidates. Reuse verified identical artifacts
  when available; otherwise execute unchanged reference strategies on the snapshot.
- Before the first performance run, persist the typed executable protocol and
  canonical SHA-256 identity, source hashes, protocol-document hash, UTC time,
  Git HEAD/dirty inventory, dataset binding and command in `freeze.json` under
  Git-ignored `backend/backtest_reports/shauli_strat_v1/`. Refuse source mismatch
  or an existing started/completed experiment; never silently overwrite/rerun.

All numerical choices above are the supplied fixed V1 research assumptions, not
optimization. Daily path assumptions, current-constituent survivorship bias,
LEGACY_PARTIAL snapshot provenance, previously observed historical periods,
price-return (not dividend-total-return) SPY, fixed friction/no capacity model,
final-open mark-to-market and no production activation remain mandatory caveats.

## Historical approval review (resolved by the approval above)

## Current request: daily/long-only definitions supplied

2026-09-08: attachment `d324b963-f6a0-4246-a635-621579b1e5e5/pasted-text.txt`
supersedes the earlier conceptual-only request below. Its source SHA-256 is
`ffb0a09aee2d8ca22edcd31d2b9f04fb906cdcf257975add483e8918a5313792`.
The full attachment was read. The current repository also contains the
user-provided `SHAULI_STRAT_SPEC_DRAFT.md`; it was read completely and left
unchanged. Its conceptual discussion does not resolve the execution case below.

The earlier blanket definition blockers are no longer current: the user has
explicitly authorized **SHAULI_STRAT DAILY V1**, `shauli-strat-v1`, version 1,
LONG_ONLY, frozen S&P 500 research only. This is not an intraday implementation.
No new timeframe, swing window, entry level, R:R, or risk parameter is requested.

### Supplied V1 rules accepted for the next protocol freeze

- Strict 2-left/2-right high/low pivots, usable only after the second right
  session closes; pivot date and confirmation date remain distinct. EQH/EQL off.
- Bullish context requires both latest confirmed high > preceding high and
  latest confirmed low > preceding low. No EMA/SMA/SPY/RS20 technical filter.
- BOS is a completed close strictly above the relevant previously confirmed
  high, not a wick. Inducement is the most recent qualifying confirmed higher
  low formed after the source BOS, above the preceding structural low and not
  yet traded below. Its price is the setup's SSLQ, known before the sweep.
- Sweep requires same-session Low < SSLQ and Close > SSLQ. One active setup;
  no arbitrary timeout. Structural invalidation, entry, pre-entry target
  consumption, or invalid bullish structure terminates the pending setup.
- A later completed close must break the frozen latest high known before the
  sweep. CHOCH versus BOS is diagnostic, not a different entry rule.
- Displacement follows the sweep: bullish middle candle closes above the
  frozen confirmation level and the third candle confirms Low[C] > High[A].
  FVG is [High[A], Low[C]], positive width only, known at C close.
- Optional OB is the last bearish candle in the sweep-to-displacement sequence
  before the middle candle, using full wicks. Positive-width OB/FVG intersection
  takes precedence; otherwise use the full mandatory FVG.
- Dealing range runs from sweep low to the highest high through FVG completion.
  Entry is the POI midpoint and must be <= range equilibrium (mandatory Discount).
- Entry is eligible only on a later session. Open <= structural stop invalidates
  before entry; otherwise Low <= entry level triggers a raw fill at that level,
  without favorable opening-price improvement, plus existing COST_LOW friction.
- Fixed stop is sweep low, or min(sweep low, OB low) when OB exists. No buffer.
  Require 0 < stop < actual fill. Fixed target is the nearest unswept previously
  confirmed swing high above actual fill, not consumed by displacement.
  Actual-fill reward/risk must be >= 2.0. No ATR/fixed-percentage target.
- No partials, breakeven, trailing, EMA exit, time exit, or reuse of an exited
  setup. Re-entry needs the entire new sequence.
- Entry plus same-bar stop is explicitly entry-then-stop; when target also
  touches, STOP_FIRST. For existing positions, known opening events take
  precedence; unresolved intraday stop/target collisions are STOP_FIRST.
- One hypothesis, $100,000, ten equal slots, whole shares, no leverage, COST_LOW
  (5 bps/side, zero commission). RS20 is portfolio competition only; independent
  ticker analysis is separate. Final open positions remain marked to market.
- Verify snapshot `5dd60f87-8947-4850-ba87-4a7df655528c`, dataset hash
  `b77ba749182fb4408394eed6d47c7d39dcfcb52a4555683c8a0b9fa7cb91374b`, universe hash
  `369350debc5b9649a0f24f6bda863aa8c8d7f85a73965ea16616712d1c5a4ec8` before performance.
  Do not refresh/substitute prices. Development 2021-08-20–2024-12-31;
  validation 2025-01-01–2026-08-20 only after development passes. These are
  previously observed periods, not pristine future out-of-sample data.
- Development requires verified data, >=100 completed portfolio trades (or a
  stricter applicable project gate), positive net return/CAGR, Sharpe/Calmar
  >=0.50, PF >1, positive pooled independent expectancy, 100% valid stop/target
  provenance, maximum planned stop distance <=20%, P90 <=10%, nonnegative cash,
  enforced positions, reconciled accounting, and no unexplained preparation
  failures. Any failure prevents validation; no retuning or operational activation.

These are supplied rules, not new agent-selected research variants. The source
attachment additionally specifies the complete funnel, trade/setup provenance,
independent/portfolio/R/recovery/attribution reports, tests and final 78 answers;
none of those outputs has yet been generated. The source hash is a source identity,
**not** a completed executable-protocol or strategy-code fingerprint.

### Remaining material execution-order question

Status: **SHAULI_V1_PROTOCOL_REQUIRES_USER_APPROVAL — ENTRY/TARGET-ONLY DAILY
AMBIGUITY**. Implementation/performance have not begun; the earlier broad gate is
replaced by this specific question, not by a rejection of the supplied strategy.

Sections 10/23 require cancellation if the opposing target was consumed before
entry. Sections 21/28 permit a later low-triggered entry and high-triggered target
exit. Section 26 explicitly chooses an entry-then-stop assumption for entry/stop
collisions, but does not specify entry/target-only collisions.

Illustrative synthetic prices (not research data or performance): a fully known
pending entry at 100, stop at 95 and target at 112; a later bar has O=105, H=113,
L=99, C=104. COST_LOW yields entry 100.05, risk 5.05 and target room 11.95, so the
initial 2.0 R:R condition is satisfied. The stop is never touched. Both paths fit
exactly the same daily bar:

| Possible path | Causal outcome |
|---|---|
| 105 → 113 → 99 → 104 | Target consumed before the retrace: cancel pending setup |
| 105 → 99 → 113 → 104 | Entry first, then target: completed winning trade |

Automatically crediting a target exit would assume the favorable intraday order.
Cancelling every such case would add a material exclusion absent from the supplied
rules. Merely using STOP_FIRST cannot choose between these paths because no stop
was touched. Existing `ConfiguredTradeManagementPolicy.evaluate` handles already-
held/known-opening positions, not a pending intraday limit entry; it does not
resolve this question without adding an assumption.

**Proposed rule for user approval, NOT implemented:** for a pending setup whose
entry and target both touch during the same daily bar, with no stop touch and
opening price strictly between entry and target, cancel/flag the setup as
`AMBIGUOUS_ENTRY_TARGET_ORDER`, no trade. Keep the explicitly specified entry-
then-stop and STOP_FIRST rules unchanged. This is a research exclusion, not an
assertion of the actual path or a claim that exclusions always lower returns.

Please approve that rule or specify the intended deterministic treatment before
the executable protocol is frozen. No intraday data or parameter search is needed
to resolve the question; the missing item is the approved daily-order assumption.

### Work and validation at this review point

- Read continuity files, full new attachment and existing source draft; inspected
  current dirty Git state, Strategy Lab models/service, prior isolated research
  governance, portfolio models and stop/target execution code.
- Generic Strategy Lab has no universal stricter completed-trade threshold in
  its `ClassificationGates`; prior strategy-specific gates are not silently
  inherited. No numeric generic-gate conflict was found in the inspected code.
- Changed only this protocol and continuity documents (`AGENTS.md`,
  `docs/PROJECT_STATE.md`, `docs/DECISIONS.md`). All other existing tracked and
  untracked research/frontend changes remain untouched, including the source draft.
- No strategy code, tests, performance, snapshot reads/verification, provider
  requests, database writes, migrations, frontend work or production activation.
  Tests/full checks were not run because no code changed. `git diff --check` passed
  at initial and final inspection (only Git line-ending notices). No results file
  is created before performance.
- Branch remains `research/ema20-loss-control`; no switch, commit, push, reset,
  stash or discard. Documentation is ready for review, not a completed research
  implementation. Suggested eventual documentation commit message:
  `docs(research): record Shauli daily V1 rules and entry-target ambiguity`.

Current Git inventory: 14 modified tracked files and 17 untracked files; none
staged. The four documentation files changed in this review are ready for review
only. This does not certify unrelated work as ready to commit. Current untracked
files (all existed at this task's first Git inspection):

```text
backend/src/alphapilot/backtesting/achia_reporting.py
backend/src/alphapilot/cli/research_achia_ema20.py
backend/src/alphapilot/strategy/achia_ema20.py
backend/src/alphapilot/strategy_lab/achia_ema20_protocol.py
backend/src/alphapilot/strategy_lab/ema20_loss_control_protocol.py
backend/tests/backtesting/test_achia_execution.py
backend/tests/backtesting/test_achia_reporting.py
backend/tests/backtesting/test_ema20_loss_control.py
backend/tests/strategy/test_achia_ema20.py
backend/tests/strategy_lab/test_achia_protocol.py
docs/research/ACHIA_STRAT_EMA20_PROTOCOL.md
docs/research/ACHIA_STRAT_EMA20_RESULTS.md
docs/research/EMA20_LOSS_CONTROL_PROTOCOL.md
docs/research/EMA20_LOSS_CONTROL_RESEARCH.md
docs/research/SHAULI_STRAT_PROTOCOL.md
docs/research/SHAULI_STRAT_SPEC_DRAFT.md
frontend/scripts/portfolio-allocation-donut-smoke.mjs
```

## Historical preflight — superseded by the supplied daily V1 specification

The remainder preserves the earlier conceptual-only audit for history. Its
unresolved numerical/timeframe statements and Git counts describe that earlier
stage, not the current request. Its draft fingerprint is not the new V1 freeze.

Date: 2026-09-08. Status: **SHAULI_V1_PROTOCOL_REQUIRES_USER_APPROVAL**.
This is an audited, non-executable protocol draft, **NOT a frozen performance
protocol**. No Shauli detector, strategy implementation, setup counts, P&L,
Development, Validation, folds, or production integration has been run or created.
No `SHAULI_STRAT_RESULTS.md` is created because there are no performance results.

## Identity and source authority

- Requested display name: `Shauli_strat`.
- Requested research identity: `shauli-strat-v1`, version 1.
- Family: `LIQUIDITY_MARKET_STRUCTURE`.
- Intended boundary: RESEARCH_ONLY, never production-selected/actionable here.
- This is NOT a modification of EMA20 Pullback, Micho, or Achia. Achia remains
  the separate completed rejected experiment; its rules are not Shauli defaults.

The user supplied a conceptual specification in attachment
`3140c371-ba7b-4784-9841-254055ed1693/pasted-text.txt`.
Source bytes SHA-256:
`da84882d6175400e076eb53511758249dcda5037881ef056612764a2e1a7841e`.

AGENTS.md, PROJECT_STATE.md, and DECISIONS.md were read completely. Repository
filename/content searches found no separate Shauli specification or implementation
in the inspected docs, backend sources/tests, or README. Searches included
Shauli/שאולי, CHOCH, BSLQ, SSLQ, inducement, order block, fair value gap and dealing
range. The supplied request is therefore the available strategy authority; no
missing chart, screenshot, prior approval, or generic internet SMC definition is
silently treated as an approved numeric rule.

The mandatory conceptual sequence is preserved:

`context → structure → liquidity → inducement → sweep/reclaim → structural
confirmation → displacement → POI → retrace → entry → structural invalidation
/ opposing-liquidity target`.

Missing a mandatory stage means no entry. A breakout alone, POI touch alone, or
sweep alone is not an implementation of this strategy.

## Repository capability audit

| Concern | Actual repository evidence | Consequence |
|---|---|---|
| Strategy contract | `strategy/base.py`: `TradingStrategy.evaluate` consumes `list[DailyCandle]`; `Signal` is BUY/SELL/HOLD | Reusable interface, but not an existing SMC setup definition |
| Production registry | `strategy/name.py` and `strategy/factory.py` contain the existing EMA20 and Micho choices | Do not add Shauli to these operational choices |
| Historical resolution | `database/models/daily_candle.py` uses one OHLCV row per company/date; `DailyCandleVersion` is also date-based | No recorded within-day event order |
| Snapshot creation | `services/research_dataset.py` creates `timeframe="1Day"`; `FrozenDatasetMarketDataSource` reconstructs daily history | Existing frozen snapshot is a daily-research candidate, not an intraday tape |
| Provider history | Existing Alpaca candle provider requests `1Day` | A live provider connection does not imply a frozen intraday research dataset |
| Completed sessions | `market/session.py`: New York 16:15 cutoff; `backtesting/engine.py` passes history only through each evaluated date | Reuse causal information boundaries; do not weaken them |
| Portfolio accounting | `_open_position` requires positive shares and debits entry cash; `MultiPortfolioPosition`/`MultiPortfolioTrade` use long cost basis, proceeds and P&L | Long-only research accounting, not a validated short simulator |
| Short support | No dedicated short/borrow/margin/short-return accounting found in inspected backtesting/research/model code | Never fake short trades with negative long shares; eventual SHORT setup diagnostics must be separate from LONG P&L |
| Management orders | `trade_management.py` supports existing long stop and fixed-R profit overlays, including conservative ambiguous intraday stop-first handling | Not an existing Shauli structural-stop/opposing-liquidity-target policy; do not reuse ATR or fixed-R targets as a shortcut |
| Governance | `strategy_lab/models.py`, `identity.py`: typed specification, explicit candidate set, dataset binding, stage gates, canonical SHA-256 identities | An incomplete definition must not enter the Lab as a supposedly executable frozen protocol |

Existing equal-slot, signal-time portfolio ranking, long cash accounting,
immutable snapshot readers and reporting can be reused after a deterministic
protocol is approved. No engine rewrite, new migration, or short-accounting
implementation is authorized merely to overcome this protocol gate.

## Timeframe is a material approval decision

The request does not establish the exact source chart timeframe or a higher-/
lower-timeframe mapping. It explicitly warns that the original concept may be
intraday. Daily OHLC cannot reveal the causal order of intraday events. For
example, OPEN=100, HIGH=110, LOW=90, CLOSE=105 permits both paths
100→90→110→105 and 100→110→90→105. A low-side sweep and an upper structural
break occur in opposite orders in those paths. Neither order can be asserted
from the daily bar alone. Nor can that bar prove a retrace happened after a POI
was created. STOP_FIRST resolves some already-active order ambiguities; it does
not reconstruct the missing setup sequence.

If the intended source requires that intraday sequencing, the additional blocker
is **INTRADAY_DATA_REQUIRED_FOR_FAITHFUL_SHAULI_BACKTEST**. No new intraday data
has been obtained or a timeframe chosen in this task.

A deliberately different completed-daily, multi-session formalization could be
proposed as **SHAULI DAILY RESEARCH VARIANT**, but only with explicit user approval
and fully specified stage timing. It must not be described as proven equivalent
to the original chart strategy. Merely shifting execution to T+1 does not resolve
the definitions of swings, inducement, structure, displacement, or POI selection.

## Source concept versus deterministic V1 definition

SOURCE means directly specified in the supplied request. RESEARCH_ASSUMPTION
means an additional interpretation, not user-approved strategy truth. No material
assumption below has been adopted into code or performance.

| Source concept | Exact definition needed / current disposition | Authority |
|---|---|---|
| Timeframes | Daily variant versus original intraday timeframes and any cross-timeframe confirmation mapping: UNRESOLVED | RESEARCH_ASSUMPTION requiring approval |
| Swing structure | Algorithm, left/right window sizes or other confirmation rule, strict/non-strict extrema, tied highs/lows, and internal/external hierarchy: UNRESOLVED | RESEARCH_ASSUMPTION requiring approval |
| Swing confirmation | A pivot requiring N right bars is usable only after those bars close; store pivot time separately from confirmed_at. N/algorithm remain UNRESOLVED | SOURCE causality; algorithm is an assumption |
| HH/HL and LL/LH | Which confirmed high/low pairs establish directional context; neutral/tied/interleaved cases and context invalidation: UNRESOLVED | SOURCE concept; selection is an assumption |
| BSLQ / SSLQ | Above confirmed highs / below confirmed lows; select which internal/external pools, their availability, lifecycle, consumption and invalidation: UNRESOLVED | SOURCE concept; exact mapping is an assumption |
| Equal highs/lows | Optional, not mandatory in the request. Enablement, pair count, price tolerance and tie handling are NOT selected | RESEARCH_ASSUMPTION if enabled; no tolerance sweep |
| Inducement | Qualifying intermediate object, distinction from an arbitrary minor swing, associated pool, confirmation time, expiration, and ordering relative to the sweep: UNRESOLVED | RESEARCH_ASSUMPTION requiring approval |
| Sweep | Strict/equal penetration boundary, eligible pre-identified pool, treatment of repeated sweeps and opening gaps, and which extreme is frozen: UNRESOLVED | SOURCE concept; exact rule is an assumption |
| Reclaim/rejection | Same-session versus later reclaim, required completed close or wick, equality and expiration: UNRESOLVED | RESEARCH_ASSUMPTION requiring approval |
| BOS | WICK versus COMPLETED CLOSE; exact relevant confirmed swing and equality boundary: UNRESOLVED. This is an explicit stop-before-performance blocker in the request | User approval required, not an automatic close default |
| CHOCH | Previous local structure, exact break reference, confirmation criterion, first opposing break, and whether/when BOS may substitute: UNRESOLVED | RESEARCH_ASSUMPTION requiring approval |
| Displacement | One deterministic directional measure, its reference/history, numeric threshold if needed, and timing after confirmation: UNRESOLVED | RESEARCH_ASSUMPTION requiring approval; no threshold search |
| Three-candle FVG | A literal candidate definition is bullish `Low[t] > High[t-2]`, bounds `[High[t-2], Low[t]]`; bearish `High[t] < Low[t-2]`, bounds `[High[t], Low[t-2]]`; confirmed only at t close | RESEARCH_ASSUMPTION proposed for review, not an implemented approved rule |
| Minimum FVG size | For that literal candidate definition, strictly positive width only, equality means no gap; no ATR/percent/tick-size filter | Source permits this choice; proposed assumption, no optimization |
| FVG lifecycle | First touch versus partial/full fill, invalidation, reuse, expiry, and required displacement association: UNRESOLVED | RESEARCH_ASSUMPTION requiring approval |
| Order Block | Last opposite candle associated with the confirmed move; body versus full high-low zone, backward search boundary, doji handling and invalidation: UNRESOLVED | SOURCE concept; exact zone/association is an assumption |
| POI selection | Exactly one FVG/OB/confluence policy; multiple-zone precedence, zone stability and invalidation: UNRESOLVED | User approval required |
| Premium/Discount | No deterministic dealing-range anchors were supplied. CONTEXT_ONLY is the permitted fallback; no invented equilibrium filter or numeric range is used here | SOURCE permits context-only; any computed range requires an assumption |
| Retrace and entry | Required later touch versus completed close, inclusive boundaries, no creation-bar entry, market-next-open versus known-zone limit, opening gaps beyond zone/stop/target: UNRESOLVED | RESEARCH_ASSUMPTION requiring approval |
| Structural stop | Exactly one sweep extreme versus POI boundary, strict/touch invalidation, static versus any source-authorized structural update, and pre-fill geometry checks: UNRESOLVED | User approval required; no ATR fallback |
| Stop buffer | No buffer selected or used. Literal approved structural level is preferred; no ATR/percentage buffer may be tested silently | SOURCE restriction; NONE is not a resolved stop-anchor choice |
| Opposing target | Which available opposing pool, internal/external eligibility, nearest versus a specific structural reference, ties, freezing time and consumed targets: UNRESOLVED | User approval required; no fixed-R substitution |
| Target room | Directionally valid positive entry-to-target distance is necessary; exact gap handling remains unresolved. No minimum R:R is authorized | SOURCE restriction; no R:R optimization |
| Ambiguous stop/target | For already-active orders with unknown intraday ordering, STOP_FIRST. Known opening events must be handled causally; entry-session activation still needs a frozen fill rule | SOURCE; not a substitute for setup-order proof |
| Expiration/re-entry | Stage deadlines, reset/invalidation, multiple simultaneous setups, pool reuse and unique setup identity: UNRESOLVED; no arbitrary cooldown or lifetime | SOURCE requires expiry/attribution; exact definitions are assumptions |
| LONG sequence | SSLQ → inducement → sweep/reclaim → bullish structure confirmation → displacement → POI → retrace → entry with structural stop and opposing BSLQ target; contextual stages precede these | SOURCE, but not executable until the missing definitions are approved |
| SHORT sequence | Mirrored BSLQ sweep, bearish confirmation/displacement/POI, retrace, stop above invalidation and opposing SSLQ target | SOURCE; detection-only later unless correct short accounting exists |

No chosen swing window, displacement threshold, buffer, setup lifetime, POI
precedence, target variant, minimum R:R or financial acceptance threshold exists
yet. The literal FVG formula is the only concrete optional interpretation shown;
it is not enough to make the complete strategy deterministic. Helpers/tests were
not created because they would risk encoding unapproved material semantics.

## Required approval decisions

Provide the previously approved numeric/source specification if it exists
outside the repository. Otherwise, approve a single written V1 bundle covering:

1. Source timeframes, or permission to draft a separately labeled daily variant.
2. Swing algorithm/confirmation/ties, structure hierarchy and eligible liquidity.
3. Exact inducement, sweep/reclaim, BOS/CHOCH and displacement definitions.
4. FVG/OB boundaries, association, lifecycle and one POI precedence rule.
5. Retrace trigger, entry/fill timing, gap handling, structural stop and target.
6. State expiry/reset/reuse and multi-setup ordering.
7. Acceptance screens and expected data-exclusion treatment before any P&L.

These are not a menu for testing competing variants. Exactly one approved set
will be frozen; no source ambiguity will be resolved by comparing backtests.

## Pending data and research plan — not executed

Requested immutable snapshot:
`5dd60f87-8947-4850-ba87-4a7df655528c`.
Dataset hash:
`b77ba749182fb4408394eed6d47c7d39dcfcb52a4555683c8a0b9fa7cb91374b`.
Universe hash:
`369350debc5b9649a0f24f6bda863aa8c8d7f85a73965ea16616712d1c5a4ec8`.

This is the requested binding, **not a new verification result**. The completed
Achia research previously verified it, but Shauli has not used or reverified the
data: the protocol/timeframe gate must be resolved first. Before any permitted
daily research, verify the finalized manifest and actual row hashes through the
existing read-only snapshot services; stop on incompatibility or mismatch. Never
substitute mutable candles. Intraday fidelity would require a separately approved
compatible immutable data source, not relabeling these daily rows.

Candidate comparable windows, pending the timeframe/protocol decision:

- Development: 2021-08-20 through 2024-12-31.
- Validation: 2025-01-01 through 2026-08-20, opened once only if all frozen
  development gates pass.
- Existing folds, if authorized by passed gates: 2021-08-20–2022-12-31,
  2023-01-01–2024-12-31, 2025-01-01–2026-08-20.

The requested comparable long portfolio is $100,000, ten equal slots, whole
shares, shared nonnegative cash, no leverage or new sizing hypothesis. The
repository COST_LOW baseline is zero commission / 5 bps per side; it is a
candidate comparable cost assumption, not a cost experiment performed here.
RS20 may be used solely for portfolio slot competition, not as Shauli technical
setup quality. Independent long setup/trade analysis must remain separate from
the shared portfolio. No short P&L or mixed long/short aggregate may be fabricated.

Before any performance, numerical acceptance thresholds must cover minimum setup/
trade samples, positive expectancy, PF, maximum drawdown, Sharpe, Calmar,
turnover/friction, concentration and risk-distance tails. Integrity gates require
100% valid structural stop/provenance, no lookahead, unique reconciled setup
lifecycles and verified data. Expected historical listing exclusions must be
explicitly distinguished from unexpected preparation failures before results;
do not copy Achia's over-broad zero-failure label without a reviewed policy.
These thresholds are **UNSET**, not implicitly inherited from a rejected strategy.

After approval, tests must cover every mandatory state transition and confirm
that a setup cannot jump from mapped liquidity to entry. They must cover confirmed
swing timing, HH/HL/LL/LH, wick/close/equality behavior, sweep/reclaim and missing
stages, displacement, FVG/OB/POI geometry and lifecycle, retrace/fill causality,
gap/stop/target precedence, valid structural risk, expiry and new-setup re-entry.
Both long and diagnostic short detection must be causal. Existing strategy and
portfolio tests must remain green. Focused tests and `backend/run_checks.ps1`
must pass before authorized performance.

Only after these gates may the detection funnel and independent analysis run,
followed by shared portfolio development. Report setup IDs/stage timestamps and
reconciled counts by direction; signal, entry, trade and rejection counts; stop/
target/gap/ambiguous-bar outcomes; R and initial target R:R; risk, MFE/MAE,
structural attribution, recovery and correctly censored final/open outcomes;
net/gross return, CAGR, DD, Sharpe, Calmar, PF, expectancy, holding time,
turnover/friction, cash/exposure and concentration. Comparisons with unchanged
EMA20 and Micho are descriptive, never tuning authority. None of these counts
or metrics is zero merely because this task stopped: they are **NOT RUN**.

Limitations to retain: LEGACY_PARTIAL provenance; current-constituent
survivorship bias rather than point-in-time membership; reused, previously
observed research windows, not pristine OOS; daily OHLC path uncertainty; fixed
friction assumptions; no short accounting; final open-position/censoring rules;
and no inference of original intraday-strategy validity from a daily variant.

## Fingerprint: review identity, not experiment authorization

The review payload below was serialized with existing
`strategy_lab.identity.canonical_json` (sorted keys, compact separators), then
SHA-256 hashed. This fingerprints the source and unresolved approval gate; it is
**NOT** `experiment_identity` for a fully specified StrategyLabProtocol. No fake
lookback, parameter set, candidate or numeric gates were supplied to force an
incomplete draft through that model. A complete approved protocol and source
manifest will require their own pre-performance freeze.

Draft review fingerprint:
`c0b093bda1332479c227985e56b1a5af9c389589687c5d1827955356ff2922b3`.

```json
{
  "document_version": 1,
  "strategy_id": "shauli-strat-v1",
  "strategy_version": 1,
  "family": "LIQUIDITY_MARKET_STRUCTURE",
  "status": "SHAULI_V1_PROTOCOL_REQUIRES_USER_APPROVAL",
  "source_attachment_sha256": "da84882d6175400e076eb53511758249dcda5037881ef056612764a2e1a7841e",
  "performance_authorized": false,
  "protocol_frozen": false,
  "production_activation": false,
  "timeframe": null,
  "unresolved": [
    "TIMEFRAME_AND_DAILY_VARIANT_APPROVAL",
    "SWING_ALGORITHM_CONFIRMATION_AND_TIES",
    "STRUCTURE_HIERARCHY_AND_LIQUIDITY_SELECTION",
    "BOS_CONFIRMATION_WICK_OR_CLOSE",
    "CHOCH_REFERENCE_AND_CONFIRMATION",
    "INDUCEMENT_ASSOCIATION_AND_EXPIRY",
    "SWEEP_RECLAIM_AND_EVENT_ORDER",
    "DISPLACEMENT_RULE",
    "ORDER_BLOCK_ZONE_AND_SEARCH_WINDOW",
    "POI_PRECEDENCE_RETRACE_AND_FILL",
    "STRUCTURAL_STOP_AND_TARGET_SELECTION",
    "SETUP_EXPIRATION_AND_REUSE",
    "ACCEPTANCE_THRESHOLDS_AND_EXPECTED_DATA_EXCLUSIONS"
  ],
  "snapshot_requested": {
    "snapshot_id": "5dd60f87-8947-4850-ba87-4a7df655528c",
    "dataset_sha256": "b77ba749182fb4408394eed6d47c7d39dcfcb52a4555683c8a0b9fa7cb91374b",
    "universe_sha256": "369350debc5b9649a0f24f6bda863aa8c8d7f85a73965ea16616712d1c5a4ec8",
    "verification_this_task": "NOT_RUN_NO_DATA_USE"
  }
}
```

## Required-answer disposition and stop

For the request's final questions 1–31, the identity, source sequence, research-
only boundary, literal FVG proposal, no-lookahead constraints and unresolved
rules are explicitly mapped above. SHORT has NOT been backtested; there is no
parameter sweep or validation retuning. No additional research assumption was
implemented or used for returns. Question 32's binding is requested, not newly
verified; question 33's development dates are pending authorization.

Questions 34–51 (funnel, trades, long/short split, performance, risk/R, execution
and attribution): **NOT RUN / NOT AVAILABLE**, not zero. Question 52: development
gate not reached. Questions 53–55: validation/folds NOT OPENED. Questions 56–57:
no Shauli-versus-EMA/Micho performance comparison. Question 58: no Strategy Lab
performance classification; the result is the protocol-approval status above,
not REJECTED and not PROMISING_RESEARCH_BASELINE.

Questions 59–62: operational activation, Portfolio mutation, Paper mutation and
broker action are all **NO**. Also no DailyCandle/News/trade-event mutation,
provider request, database connection, secret access, migration or frontend work.

Question 63: no focused tests or full gate were run for this documentation-only
blocked preflight. The prior Achia 516-test gate is historical evidence, not a
fresh Shauli test result. `git diff --check` is the appropriate document check.

Question 64: branch `research/ema20-loss-control`, HEAD
`decc7d1321cad512d8196f367a84848bf59355ac`; existing dirty tree preserved. This
task changes only AGENTS.md, docs/PROJECT_STATE.md, docs/DECISIONS.md and creates
this untracked protocol document. At handoff there are 14 tracked modified files
and 16 untracked files, mostly earlier research/UI work; no staging/commit/push.
The new document and continuity hunks are ready for user review as a blocked
preflight record, **not** as completed strategy implementation.

Question 65: obtain the numeric source specification or explicit permission to
draft one separately labeled daily research variant for approval; resolve the
listed choices and freeze one protocol before any strategy P&L.

Question 66, suggested documentation-only commit if the user wishes to preserve
this record: `docs(research): record Shauli V1 protocol approval blockers`.

**STOP. SHAULI_V1_PROTOCOL_REQUIRES_USER_APPROVAL.** No alternative strategy,
performance experiment, material rule selection or operational activation follows
automatically from this audit.
