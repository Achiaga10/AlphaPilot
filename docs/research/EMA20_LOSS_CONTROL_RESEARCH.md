# EMA20 Pre-entry Numeric Loss-Control Research

## Outcome

The research completed reproducibly, but it produced **no approved EMA20
loss-control policy**.

`ema20-fixed-signal-ema50-stop-v1` failed two frozen development gates: its
entry-to-boundary risk was 11.0638% at P90 (10% maximum allowed) and 20.6438%
at the maximum (20% maximum allowed). Its validation and fold stages therefore
remained closed. The exact prior `ema20-static-atr14-2x-v1` result was reused,
not rerun; it retains Sprint 20's `NO_WINNER` classification because validation
drawdown worsened by 1.62 percentage points, beyond the frozen 1.50-point limit.

Final decision:

```text
NO_APPROVED_EMA20_LOSS_CONTROL_POLICY
```

This result does not enable EMA20 BUYs, change production actionability, or
alter Strategy Profiles, ExecutionReadiness, Portfolio Plan, UI, Paper, News,
portfolio state, or broker behavior.

## Frozen protocol and governance

The candidate space, trigger semantics, immutable dataset, stages, metrics, and
hard gates were frozen in
[EMA20_LOSS_CONTROL_PROTOCOL.md](EMA20_LOSS_CONTROL_PROTOCOL.md) on 2026-09-06,
before inspecting the new candidate's results.

- Protocol fingerprint:
  `47dc814a331567efb15f0605de7257d601292907cadb6ab1c62646239881156c`.
- Control fingerprint:
  `d1b5a13c243a77705e4c4ac8cff26cae156062654a5eec6dfe05e3bad2b323f0`.
- Fixed EMA50 fingerprint:
  `d6a7b25fc4e4fd35b7d3b0f992a75ddf4a91c80eb48a30bd5dec7aba786f65d1`.
- Reused ATR14 2× fingerprint:
  `3a4a51c09f5c2cae5ce3d6638746f4fcf6d626ca9707e1d7d9c3fa1c57a72fce`.
- No parameter sweep was performed.
- No validation retuning was performed.
- No third candidate was declared.
- No least-bad fallback is permitted.

The existing historical strategy remained frozen: EMA20 Pullback V1, the 1%
entry-safety ceiling, EMA20/EMA50 periods, HYBRID 2%, RS20, equal-slot sizing,
ten positions, News rules, portfolio constraints, and T+1 execution.

## Prior AlphaPilot loss-control evidence

The study audited Sprint 12 and both Sprint 20 EMA rounds before declaring a
new candidate. The important closed evidence is summarized below; “not opened”
means the arm did not advance under the protocol then in force.

| Prior EMA policy | Parameters | Development result | Validation result | Classification / reason |
|---|---|---|---|---|
| Strategy-exit control | HYBRID 2%; no protective stop | 80.15% return; 19.12% CAGR; 26.43% DD | 18.06% return; 10.73% CAGR; 23.74% DD | Frozen comparison; no numeric protective boundary |
| Static ATR stop | ATR14, 1.5× | 63.16% return; 31.21% DD; 158 stops; materially worse return/DD | Not opened | Rejected/not selected; tight-stop whipsaw and deterioration |
| Static ATR stop | ATR14, 2.0× | 70.39% return; 17.16% CAGR; 25.77% DD; 87 stops | 38.29% return; 22.02% CAGR; 25.36% DD | Sprint 20 `NO_WINNER`; validation DD +1.62 points exceeded 1.50 cap |
| Static ATR stop | ATR14, 2.5× | 53.88% return; 13.67% CAGR; 27.69% DD | Not opened | Rejected; failed development CAGR retention |
| Static ATR stop | ATR14, 3.0× | 84.65% return; 19.99% CAGR; 26.47% DD; 26 stops | 37.54% return; 21.61% CAGR; 22.48% DD | Sprint 12 `RESEARCH_ONLY`; only 1/3 folds improved return/Sharpe/Calmar. Sprint 20 also found insufficient tail improvement for advancement |
| ATR trailing stop | ATR14, 2.0× over selected static stop | 10.64% return; 22.84% DD; 470 stops | Not opened | Rejected; severe whipsaw and return destruction |
| ATR trailing stop | ATR14, 3.0× over selected static stop | 74.04% return; 27.17% DD; 245 stops | Not opened | `RESEARCH_ONLY`, not selected; worse DD/Calmar and substantial churn |
| Partial profit | 50% whole shares at +2R | 46.25% return; 23.34% DD | Not opened | Rejected; retained only 59.83% of positive stop-only CAGR and truncated the right tail |
| Full profit | Full exit at +3R | 45.42% return; 27.09% DD | Not opened | Rejected; return/CAGR and drawdown profile deteriorated |
| Signal-day-low invalidation | Frozen BUY signal-candle low | 63.08% return; 25.32% DD; turnover 9,507.98% | Not opened | Rejected; turnover rose about 72.5%, far beyond the 25% cap |

The exact ATR14 2× rule is Candidate B in this study only by reuse. Rerunning
it as a new hypothesis would have been misleading. Trailing stops, targets,
alternate ATR periods/multiples, moving future EMA50, percent stops, and the
signal-day-low rule remained closed.

## Candidate definitions

### Control

The existing HYBRID 2% strategy exit remains active with no protective numeric
boundary. It is the comparison arm, not an approved loss-control policy.

### Candidate A — fixed signal-day EMA50

Policy: `ema20-fixed-signal-ema50-stop-v1`.

For a BUY signal on completed session T and the slipped fill at the next
available open U:

```text
boundary = EMA50 calculated only from completed candles through T
risk_per_share = slipped_entry_price[U] - boundary
risk_pct = risk_per_share / slipped_entry_price[U] × 100
```

The boundary is immutable after T. It is a protective **price-breach** rule,
not a completed-close rule and not a future-moving EMA50. It activates on the
session after entry. On an active session V:

```text
if open[V] <= boundary: raw exit = open[V] (gap-through)
else if low[V] <= boundary: raw exit = boundary
else: no protective exit
```

Existing sell slippage then applies. The protective boundary has conservative
same-bar priority; otherwise the frozen HYBRID 2% exit continues. A missing or
nonpositive EMA50, or EMA50 at/above the actual entry, rejects the managed entry
rather than fabricating risk. The source, as-of day, policy version, boundary,
actual entry, risk/share, risk percent, position value, and planned portfolio
risk are preserved in trade/open-position artifacts.

### Candidate B — reused ATR14 2×

Policy: `ema20-static-atr14-2x-v1`.

```text
ATR = mean of the latest 14 true ranges through signal day T
K = 2.0
boundary = slipped_entry_price[U] - 2.0 × ATR14[T]
```

The ATR period is 14 and the multiplier is exactly 2.0. Both predate this
study. The same activation, daily-low/gap-open, stop-first, friction, missing
input, and existing-strategy-exit semantics apply. Fidelity documents 14
periods as a typical ATR convention and ATR stops as volatility-adaptive;
Schwab describes common ATR-stop multiples in the 1×–2× range. These references
support defensibility, not performance selection:

- https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/atr
- https://workplace.schwab.com/story/4-volatility-metrics-to-inform-your-trades

### Candidate C

None. Prior evidence did not justify introducing a structure-plus-volatility
hybrid without turning this study into a search.

## Data, execution, and portfolio assumptions

- Frozen snapshot: `5dd60f87-8947-4850-ba87-4a7df655528c`.
- Dataset SHA-256:
  `b77ba749182fb4408394eed6d47c7d39dcfcb52a4555683c8a0b9fa7cb91374b`.
- Universe SHA-256:
  `369350debc5b9649a0f24f6bda863aa8c8d7f85a73965ea16616712d1c5a4ec8`.
- Provenance: `LEGACY_PARTIAL`.
- Development: 2021-08-20 through 2024-12-31.
- Reused validation: 2025-01-01 through 2026-08-20.
- Folds: 2021-08-20–2022-12-31, 2023-01-01–2024-12-31, and
  2025-01-01–2026-08-20.
- Current-constituent S&P 500 universe plus SPY.
- Initial capital $100,000; maximum 10 positions; equal-slot sizing.
- RS20 ranking; COST_LOW; $0 commission; 5 bps slippage per side.
- Final positions marked to final close, not force-liquidated.
- Development processed 497 tickers successfully and failed five with no
  historical candles: FDXF, HONA, PSKY, Q, and SNDK. Failures matched control
  and candidate.

The current-constituent history is survivorship biased, not a point-in-time
universe. All periods were observed in prior AlphaPilot work and are not pristine
out-of-sample evidence. SPY is an imperfect benchmark. Daily OHLC cannot resolve
intraday path ordering, and a numeric stop cannot guarantee its price through a
gap, halt, spread, liquidity shortfall, or market impact.

## Exact commands and verification

The only new portfolio experiment was the frozen development command below,
run from `backend/` with `DEBUG=false`:

```powershell
uv run alphapilot-backtest-strategy-exits --strategy ema20-pullback --start 2021-08-20 --end 2024-12-31 --stage ema20-loss-control-development --dataset-snapshot 5dd60f87-8947-4850-ba87-4a7df655528c --fold-label development --configuration control --configuration fixed-signal-ema50-stop --output-dir backtest_reports/ema20-loss-control
```

Candidate A failed development, so no `ema20-loss-control-validation` or
`ema20-loss-control-fold` command was run. Candidate B was not rerun; its exact
Sprint 20 artifacts were inspected under
`backend/backtest_reports/sprint20/ema-round2/`.

Focused validation:

```powershell
uv run pytest tests/backtesting/test_ema20_loss_control.py tests/backtesting/test_trade_management.py tests/backtesting/test_sprint20_protocol.py tests/strategy_lab/test_sprint20_stop_protocol.py -q
```

Result: **39 passed**. Targeted Ruff/formatting and mypy over the changed source
set also passed.

Final backend gate:

```powershell
$env:DEBUG='false'
.\run_checks.ps1
```

Result:

- Ruff and formatting: PASS; 282 files unchanged by the format check.
- mypy: PASS; 190 source files.
- pytest: PASS; 463 tests in 66.11 seconds.
- Overall: **all checks passed**.

## New development results

| Metric | HYBRID 2% control | Fixed signal-day EMA50 | Candidate minus control / interpretation |
|---|---:|---:|---:|
| Final equity | $180,145.51 | $176,806.46 | -$3,339.06 |
| Net return | 80.15% | 76.81% | -3.34 points |
| Gross return | 82.90% | 79.67% | -3.23 points |
| CAGR | 19.12% | 18.46% | 96.54% retained |
| Max drawdown | 26.43% | 25.27% | 1.16 points better |
| Sharpe | 0.869 | 0.869 | 100.06% retained |
| Calmar | 0.723 | 0.730 | 100.98% retained |
| Completed trades | 253 | 262 | +9 |
| Win rate | 32.02% | 28.63% | -3.39 points |
| Profit factor | 1.467 | 1.409 | lower |
| Average trade / expectancy | 2.05% | 2.07% | nearly flat |
| Median trade | -3.07% | -3.06% | nearly flat |
| Average winner | 17.59% | 19.21% | higher |
| Average loser | -5.27% | -4.81% | improved |
| Median loser | -5.08% | -4.37% | improved |
| Worst trade | -17.53% | -15.19% | magnitude improved 13.32% |
| Fifth-percentile trade | -10.27% | -9.85% | magnitude improved 4.14% |
| Median MAE / MFE | -5.15% / 5.38% | -4.23% / 4.57% | both tails compressed |
| Exposure | 78.79% | 78.23% | -0.55 points |
| Average / max positions | 7.89 / 10 | 7.81 / 10 | nearly flat |
| Average holding sessions | 36.94 | 35.18 | shorter |
| Turnover | 5,511.94% | 5,724.99% | +3.87% relative |
| Transaction friction | $2,755.94 | $2,862.47 | +$106.53 |
| Realized P&L | $45,251.47 | $39,677.15 | lower |
| Final-open unrealized P&L | $34,894.04 | $37,129.30 | higher dependence |
| Final open positions | 10 | 10 | unchanged |
| Top-1 / top-5 positive-P&L share | 27.47% / 61.48% | 27.90% / 60.78% | no material new pathology |
| Positive-P&L HHI | 0.11499 | 0.11420 | slightly less concentrated |
| Final cash | $86.85 | $50.87 | both near fully allocated |

Single-ticker comparison was balanced rather than broad: 247 tickers improved,
245 worsened, and five were unchanged. The best return differences included
ADSK (+1.66 points) and ARES (+1.64); the worst included ECHO (-2.53) and TRMB
(-2.20). Portfolio-path effects, ranking, and freed slots therefore matter.

## Frozen development gates

| Gate | Required | Observed | Result |
|---|---:|---:|---|
| Positive CAGR retention | ≥75% | 96.5449% | PASS |
| Drawdown worsening | ≤1.50 points | -1.1596 points (improved) | PASS |
| Positive Sharpe retention | ≥80% | 100.0630% | PASS |
| Positive Calmar retention | ≥80% | 100.9753% | PASS |
| Turnover increase | ≤25% | 3.8653% | PASS |
| Worst or P5 loss-tail improvement | ≥10% | Worst improved 13.3239% | PASS |
| Valid boundary coverage | 100% | 100% (272/272) | PASS |
| Risk-distance P90 | ≤10% | **11.0638%** | **FAIL** |
| Maximum risk distance | ≤20% | **20.6438%** | **FAIL** |

All hard gates are conjunctive. The two failures reject Candidate A even though
aggregate performance was otherwise tolerable.

## Risk distance and stop/recovery diagnostics

### Candidate A — fixed signal-day EMA50

| Diagnostic | Result |
|---|---:|
| Portfolio entries / valid boundaries | 272 / 272 |
| Entry-risk P50 | 5.8798% |
| Entry-risk P75 | 8.2445% |
| Entry-risk P90 | 11.0638% |
| Entry-risk maximum | 20.6438% |
| Average planned risk | $685.25 |
| Average planned risk / entry equity | 0.5820% |
| Protective stops / stop-out rate | 104 / 38.24% |
| Gap-through stops | 29 |
| Strategy exits | 158 |
| Re-entries / repeated stop-outs | 36 / 13 |
| Average sessions to re-entry | 294.28 |
| Average post-stop return at 5 sessions | +0.88% |
| Average post-stop return at 10 sessions | +1.99% |
| Average post-stop return at 20 sessions | +2.29% |
| Recovered original entry within 20 sessions | 57/104 (54.81%) |

The 5/10/20 return figures are closes relative to the stop exit price. The
54.81% recovery figure is the separate existing hindsight diagnostic asking
whether any close in the following 20 sessions regained the original entry.
Neither is an execution or re-entry rule.

The EMA50 boundary is typically 5.88% below entry, but one quarter of entries
are wider than 8.24% and at least one tenth are wider than 11.06%. The 20.64%
maximum demonstrates that fixed EMA50 sometimes behaves more like a late trend
invalidation than practical pre-entry loss containment. Gap risk can make the
realized loss wider still.

### Candidate B — exact reused ATR14 2× evidence

| Diagnostic | Development | Reused validation |
|---|---:|---:|
| Entries / valid boundaries | 290 / 290 | 179 / 179 |
| Entry-risk P50 | 5.7289% | 6.7095% |
| Entry-risk P75 | 8.1600% | 9.5330% |
| Entry-risk P90 | 10.3746% | 12.7789% |
| Entry-risk maximum | 30.0861% | 23.2189% |
| Average planned risk | $708.83 | $825.34 |
| Average planned risk / entry equity | 0.6130% | 0.7132% |
| Protective stops / stop-out rate | 87 / 30.00% | 67 / 37.43% |
| Gap-through stops | 29 | not separately required by prior summary |
| Average post-stop return at 5 sessions | +0.24% | +1.67% |
| Average post-stop return at 10 sessions | +1.83% | +2.82% |
| Average post-stop return at 20 sessions | +2.76% | +4.61% |
| Recovered original entry within 20 sessions | 43/87 (49.43%) | 37/67 (55.22%) |

ATR2 sat outside more normal noise than ATR1.5 and stopped less often, but its
distance was not tightly bounded: development P90 exceeded 10% and maximum was
30.09%; validation P90 was 12.78% and maximum 23.22%. These newly reported risk
diagnostics are descriptive and do not rewrite the reason for its original
Sprint 20 rejection. Its existing validation drawdown hard failure remains
decisive.

## Reused ATR14 2× performance and fold evidence

| Metric | Development control | Development ATR2 | Validation control | Validation ATR2 |
|---|---:|---:|---:|---:|
| Final equity | $180,145.51 | $170,387.79 | $118,058.42 | $138,285.39 |
| Net return | 80.15% | 70.39% | 18.06% | 38.29% |
| CAGR | 19.12% | 17.16% | 10.73% | 22.02% |
| Max drawdown | 26.43% | 25.77% | 23.74% | **25.36%** |
| Sharpe | 0.869 | 0.813 | 0.478 | 0.738 |
| Calmar | 0.723 | 0.666 | 0.452 | 0.868 |
| Trades | 253 | 280 | 158 | 169 |
| Win rate | 32.02% | 28.93% | not decisive | 28.99% |
| Profit factor | 1.467 | 1.335 | not decisive | 1.235 |
| Average trade | 2.05% | 1.46% | not decisive | 2.01% |
| Turnover | 5,511.94% | 6,044.22% | 3,110.64% | 3,544.38% |
| Transaction friction | $2,755.94 | $3,022.09 | not separately reused here | $1,772.17 |
| Realized / final-open P&L | $45,251 / $34,894 | $33,438 / $36,950 | $3,631 / $14,427 | $19,081 / $19,204 |
| Top-1 / top-5 positive share | 27.47% / 61.48% | 28.63% / 58.89% | 11.95% / 44.34% | 13.19% / 46.43% |
| Positive-P&L HHI | 0.11499 | 0.11884 | 0.0569 | 0.05988 |

ATR2 improved return, Sharpe, and drawdown in two of three folds, but not in the
same fold consistently:

| Fold | Control return / ATR2 | Control Sharpe / ATR2 | Control DD / ATR2 |
|---|---:|---:|---:|
| 2021-08-20–2022-12-31 | -10.35% / -8.39% | -0.394 / -0.316 | 21.18% / 19.07% |
| 2023-01-01–2024-12-31 | 97.60% / 80.67% | 1.401 / 1.334 | 25.95% / 24.48% |
| 2025-01-01–2026-08-20 | 18.06% / 38.29% | 0.478 / 0.738 | 23.74% / 25.36% |

The validation drawdown increase of 1.62 points exceeded the frozen 1.50-point
ceiling. Two-of-three directional counts, stronger validation return, and
acceptable concentration/turnover/recovery could not override that failure.

## AXON and FAST incident illustrations

These calculations were performed only after protocol freeze and use the
historically reconstructable 2026-08-27 completed session with the recorded
Paper fill as the entry reference. They are explanatory, not tuning or outcome
evidence.

| Ticker | Entry reference | EMA20 | Fixed EMA50 boundary / risk | ATR14 | ATR2 boundary / risk |
|---|---:|---:|---:|---:|---:|
| AXON | $609.00 | $597.14 | $557.47 / 8.46% | $30.70 | $547.60 / 10.08% |
| FAST | $50.28 | $50.45 | $48.82 / 2.91% | $0.87 | $48.54 / 3.45% |

The contrast is useful but not a selection rule: both candidates were relatively
tight for FAST and much wider for AXON. The experiment was not altered to make
AXON stop earlier or FAST survive.

## IBKR and EOG descriptive boundaries

These are current descriptive illustrations only, computed after protocol
freeze from completed data through 2026-09-03. Because neither is an executed
research trade, the illustration uses completed close plus the existing 5 bps
BUY slippage as its entry reference. It does not approve either BUY.

| Ticker | Completed close | Illustrative entry | EMA20 | EMA50 boundary / risk | ATR14 | ATR2 boundary / risk |
|---|---:|---:|---:|---:|---:|---:|
| IBKR | $92.96 | $93.0065 | $92.7749 | $91.2595 / 1.88% | $3.4014 | $86.2036 / 7.31% |
| EOG | $145.94 | $146.0130 | $145.7132 | $142.6488 / 2.30% | $3.1032 | $139.8065 / 4.25% |

Both examples show a usable number can be calculated, but a current example
cannot validate a policy and may not be used to relax the gates. IBKR and EOG
remain subject to the existing `NO_APPROVED_LOSS_CONTROL_POLICY` actionability
block.

## Implementation and artifacts

Created:

- `docs/research/EMA20_LOSS_CONTROL_PROTOCOL.md`
- `docs/research/EMA20_LOSS_CONTROL_RESEARCH.md`
- `backend/src/alphapilot/strategy_lab/ema20_loss_control_protocol.py`
- `backend/tests/backtesting/test_ema20_loss_control.py`

Modified:

- `AGENTS.md`
- `docs/PROJECT_STATE.md`
- `docs/DECISIONS.md`
- `backend/src/alphapilot/backtesting/trade_management.py`
- `backend/src/alphapilot/backtesting/multi_portfolio_models.py`
- `backend/src/alphapilot/backtesting/multi_portfolio.py`
- `backend/src/alphapilot/backtesting/multi_portfolio_service.py`
- `backend/src/alphapilot/backtesting/sprint12_protocol.py`
- `backend/src/alphapilot/backtesting/sprint12_reporting.py`
- `backend/src/alphapilot/cli/backtest_strategy_exits.py`

Git-ignored research artifacts were written beneath
`backend/backtest_reports/ema20-loss-control/`. They include JSON summaries,
equity curves, trades, final open positions, attribution, sector attribution,
selection audit, stop recovery, and universe comparison.

The implementation adds one closed policy identity and stage-guarded research
path without modifying the old Sprint 20 candidate space. Tests cover the fixed
boundary, provenance, invalid inputs, no lookahead, post-entry activation,
gap-through execution, risk calculations, deterministic fingerprints, stage
closedness, no fallback, and repeated deterministic execution. Existing ATR
boundary and execution tests remain green.

## Interpretation and decision

Fixed signal-day EMA50 provides a deterministic, auditable, pre-entry number
and modestly improves aggregate drawdown and loser severity without excessive
turnover. It nevertheless does not bound normal entry risk tightly enough for
the frozen policy: its P90 and maximum both fail. It is often a useful structural
reference, but sometimes only a distant trend boundary.

ATR14 2× adapts to volatility, yet “adaptive” does not mean sufficiently tight
or validated. It stopped 30.00% of development entries, showed meaningful
post-stop recovery, had still-wider risk tails, and previously failed validation
drawdown. Its fold behavior was mixed rather than uniformly stable.

Neither candidate establishes a safe production loss-control policy. There is
no recommended policy to integrate. EMA20 BUYs must remain non-actionable where
the existing backend requires approved numeric loss-control evidence. A future
study, if the user authorizes one, needs a separately frozen hypothesis and must
not retrofit these gates.

## Explicit final answers

1. Prior research included static ATR14 stops at 1.5×/2×/2.5×/3× across Sprints
   12/20, ATR14 trails at 2×/3×, partial +2R, full +3R, and signal-day-low
   invalidation, all against the frozen strategy-exit control.
2. ATR1.5 was too tight/deteriorative; ATR2 failed validation DD; ATR2.5 failed
   development CAGR retention; ATR3 was fold-dependent and later failed the
   tail-improvement gate; trails whipsawed; profit exits truncated the right
   tail; signal-day-low exceeded turnover limits.
3. The closed set was control, new fixed signal-day EMA50, and exact reused
   ATR14 2× evidence. No other policy was allowed.
4. EMA50 is frozen from completed signal day T, activates after entry, and
   triggers on an active daily low breach or worse opening gap; it is not a
   completed-close or moving-EMA rule.
5. ATR period: **14 completed trading bars**.
6. ATR multiplier: **2.0×**.
7. Parameter sweep performed: **NO**.
8. Validation retuning performed: **NO**.
9. Development completed trades: control 253; fixed EMA50 262; reused ATR2 280.
   Reused validation: control 158; ATR2 169.
10. Development net return: control 80.15%; fixed EMA50 76.81%; reused ATR2
    70.39%. Reused validation: control 18.06%; ATR2 38.29%.
11. Development maximum DD: control 26.43%; fixed EMA50 25.27%; reused ATR2
    25.77%. Reused validation: control 23.74%; ATR2 25.36%.
12. Fixed EMA50 average/median/worst loser: -4.81% / -4.37% / -15.19%.
    Control: -5.27% / -5.08% / -17.53%. ATR2 development average/median/worst:
    -4.64% / -4.47% / -14.04%.
13. Development turnover: control 5,511.94%; fixed EMA50 5,724.99%; ATR2
    6,044.22%.
14. Stop frequency: fixed EMA50 104/272 entries (38.24%); ATR2 development
    87/290 (30.00%) and validation 67/179 (37.43%).
15. Fixed EMA50 average post-stop returns at 5/10/20 sessions were
    +0.88%/+1.99%/+2.29%; 54.81% regained entry within 20 sessions. ATR2
    development was +0.24%/+1.83%/+2.76% and 49.43%; validation was
    +1.67%/+2.82%/+4.61% and 55.22%.
16. EMA50 development entry-risk P50/P75/P90/max:
    5.8798%/8.2445%/11.0638%/20.6438%.
17. ATR2 entry-risk P50/P75/P90/max: development
    5.7289%/8.1600%/10.3746%/30.0861%; validation
    6.7095%/9.5330%/12.7789%/23.2189%.
18. AXON at the $609 Paper reference: fixed EMA50 $557.47 (8.46% risk); ATR2
    $547.60 (10.08%).
19. FAST at the $50.28 Paper reference: fixed EMA50 $48.82 (2.91%); ATR2
    $48.54 (3.45%).
20. IBKR descriptive $93.0065 entry: fixed EMA50 $91.2595 (1.88%); ATR2
    $86.2036 (7.31%).
21. EOG descriptive $146.0130 entry: fixed EMA50 $142.6488 (2.30%); ATR2
    $139.8065 (4.25%).
22. Did fixed EMA50 pass? **NO; it failed both development risk-tail gates.**
23. Did ATR2 pass? **NO; its existing validation drawdown hard failure remains.**
24. Third policy: **NO**.
25. Final classification: **`NO_APPROVED_EMA20_LOSS_CONTROL_POLICY`**.
26. Recommended policy: **none**.
27. Safe to proceed to production integration: **NO**.
28. Production BUY semantics changed: **NO**.
29. Portfolio mutation: **NO**.
30. Paper mutation: **NO**.
31. Broker action: **NO**.
32. Backend gate: **PASS — Ruff/formatting, mypy 190 files, pytest 463 passed.**
33. Git status: local branch `research/ema20-loss-control`; no commit or push
    was made. Modified files are `AGENTS.md`, `docs/PROJECT_STATE.md`,
    `docs/DECISIONS.md`, `backend/src/alphapilot/backtesting/multi_portfolio.py`,
    `multi_portfolio_models.py`, `multi_portfolio_service.py`,
    `sprint12_protocol.py`, `sprint12_reporting.py`, `trade_management.py`, and
    `backend/src/alphapilot/cli/backtest_strategy_exits.py`. Untracked files are
    `backend/src/alphapilot/strategy_lab/ema20_loss_control_protocol.py`,
    `backend/tests/backtesting/test_ema20_loss_control.py`, this report, and the
    frozen protocol. `git diff --check` passes; its only output is Git's existing
    LF-to-CRLF working-copy warning for the three continuity Markdown files.

Recommended commit message, for the user if approved:

```text
research: evaluate fixed EMA50 loss-control boundary
```
