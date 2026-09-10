# Achia_strat_ema20 V1 — research results

Completed locally: 2026-09-08. Final Strategy Lab classification: **REJECTED at
development**. Validation and folds were **NOT OPENED**. No parameter sweep,
validation retuning, operational activation, application-data mutation, commit,
or push occurred. This is a completed negative research result, not an unfinished
implementation or an approved replacement for EMA20 Pullback.

The new strategy returned 15.46% with 40.95% drawdown, Sharpe 0.3080 and Calmar
0.1066. Independent-ticker expectancy was -0.0969% per completed trade. Maximum
planned stop distance was 26.30%, exceeding the frozen 20% screen. These are
independent reasons not to advance, even before the conservative coverage gate.
The unchanged EMA20 HYBRID 2% reference returned 80.15% with 26.43% drawdown.

## 1. Identity, implementation, and frozen hypothesis

Display name: `Achia_strat_ema20`. Canonical research identity:
`achia-strat-ema20-v1`, version 1, LONG_ONLY. Native stop-policy identity:
`achia-ema20-atr14-plus-1pct-stop-v1`.

This is separate from `ema20-pullback-v1` and `micho-150-v1`. The new class uses
the existing strategy interface and a distinct Strategy Lab specification. It is
deliberately NOT registered in the operational StrategyProfile registry/factory,
Scanner defaults, Portfolio Plan, UI, Paper, or broker paths.

The exact frozen rules in [the protocol](ACHIA_STRAT_EMA20_PROTOCOL.md) are:

1. On completed signal session T, EMA20[T] > EMA50[T], strictly.
2. Inclusive BUY zone: `0.90 * EMA20[T] <= Close[T] <= 1.01 * EMA20[T]`.
   The entire -10% through +1% interval is eligible. No slope, SPY SMA200,
   HYBRID, low-touch/reclaim, RS20, or News technical condition is inherited.
3. Enter at the ticker's next available U OPEN with existing BUY slippage.
   No signal-close fill, favorable intraday selection, or fabricated last-bar fill.
4. EMA uses the existing SMA-seeded recursion with alpha `2/(N+1)`, periods
   20/50. Minimum technical history is 50 valid bars. Stock warm-up is 120
   calendar days; SPY warm-up is 400, matching the reference service.
5. Authoritative ATR is `portfolio.risk.AverageTrueRangeCalculator`: 14 simple-
   mean true ranges, requiring 15 candles; NOT Wilder smoothing.
   `TR = max(high-low, abs(high-previous_close), abs(low-previous_close))`.
   All signal features use only candles through T and the completed-session policy.
6. `stop = entry_fill - ATR14[T] - entry_fill * 0.01`. ATR must be positive;
   the boundary must satisfy `0 < stop < entry_fill`. Missing/invalid input
   rejects a managed entry. Stop provenance retains the original signal day.
7. The stop is static and active immediately AFTER the entry OPEN fill,
   including that session's remaining LOW. No trailing, breakeven, profit target,
   partial exit, or moving EMA/ATR stop exists.
8. For an existing holding: OPEN <= stop exits at raw OPEN; otherwise LOW <=
   stop exits at raw stop. SELL slippage is then applied. This is not a guaranteed
   stop-price fill. A new position cannot have a pre-entry opening gap stop.
9. A position surviving its stop exits on completed `Close[V] < EMA20[V]`, at
   the next available OPEN. Equality does not exit; intraday LOW below EMA alone
   does not exit. The next opening gap-stop precedes a pending strategy exit;
   otherwise that pending OPEN exit precedes a later intraday LOW. A stop during
   V precedes V's later close signal. Never double-exit.
10. Flat-entry and held-exit conditions overlap below EMA20. They are separate
    facts in `StrategyEvaluation`; the simulator applies the appropriate fact to
    position state. It does not discard below-EMA BUYs or recycle a BUY generated
    while held into same-OPEN re-entry. A new completed valid signal after full
    exit can enter at the following OPEN, with no arbitrary cooldown.

Existing trade-management policies retain their original activation behavior.
No historical EMA20 or Micho rule was modified. This comparison changes an entire
strategy hypothesis; it is not a causal, isolated comparison of stop policies.

## 2. Data, fingerprints, and reproducibility

| Item | Frozen value |
|---|---|
| Snapshot | `5dd60f87-8947-4850-ba87-4a7df655528c` |
| Dataset SHA-256 | `b77ba749182fb4408394eed6d47c7d39dcfcb52a4555683c8a0b9fa7cb91374b` |
| Universe SHA-256 | `369350debc5b9649a0f24f6bda863aa8c8d7f85a73965ea16616712d1c5a4ec8` |
| Protocol fingerprint | `82b3e903820009ef53455c431a93001340216d4914de9c249cfd093d581ea06f` |
| Candidate/configuration fingerprint | `1b6f103a0394f76755c56671bdc64a8653195c7873a975b3690c2d4c4c88f6cf` |
| Snapshot state | FINALIZED; value-reproducible; LEGACY_PARTIAL provenance |
| Verified contents | 502 constituents plus SPY; 745,232 candle versions |
| Manifest history | 2019-07-17 through 2026-08-20 |
| Actual development curve | 2021-08-20 through 2024-12-31; 846 sessions |
| Git HEAD | `decc7d1321cad512d8196f367a84848bf59355ac`, dirty local tree |
| Branch | `research/ema20-loss-control`, unchanged |

The source manifest and canonical protocol were saved before performance in
`backend/backtest_reports/achia_strat_ema20/freeze.json` at 06:19:06 UTC on
2026-09-08. The formal run reverified every snapshot hash/row (24,514 ms), used
`SET TRANSACTION READ ONLY`, and finished at 06:56:28 UTC. It verified that all
frozen source hashes remained unchanged DURING execution. No mutable fallback,
provider refresh, or external market-data API was used.

Both strategies prepared 497/502 tickers. The same five had no development-
period historical candles: **FDXF, HONA, PSKY, Q, SNDK**. These match the previous
snapshot research's documented exclusions. They are explained missing-history
cases, not five unexplained strategy exceptions. Achia additionally recorded
425 insufficient-history evaluation bars; the reference recorded 470 because
their technical minimum histories differ. No invalid-OHLC evaluation was reported.
All 97,434 Achia technical BUY rows had a signal ATR available.

The machine-frozen preparation screen requires `failed_tickers == 0`; its label
"no unexplained failed tickers" is broader-sounding than that literal rule.
No exemption for these five known exclusions was declared in the executable
protocol. It therefore fails conservatively. This limitation is explicit, not
hidden as an unexplained runtime failure, and was not relaxed after results.
Four separate economic/risk gates fail even if these five exclusions are set aside.

### Reporting-only Decimal correction after the run

The original report checked a stop using `fill * 0.99 - ATR`, while execution
uses the frozen literal expression `fill - ATR - fill * 0.01`. Repeating ATR
decimals make those algebraic forms differ in the last Decimal place. Six of
1,514 portfolio entries were falsely marked invalid, with differences no greater
than **3e-26 dollars**. Their ATR, policy, signal dates, positive boundaries, and
actual execution formula were all correct.

Only the reporting check was corrected to use the IDENTICAL execution operation
order. No tolerance, financial threshold, fill, stop, indicator, parameter,
performance result, or classification changed. No performance was rerun.
The new regression test reproduces the problem with repeating signal ATR.

All original summaries, CSVs, `freeze.json`, `experiment.json`, and gate-failure
records remain untouched; their artifact hashes were checked. The original
99.6037% coverage and extra coverage-failure reason are historical reporting
defects, superseded only for that diagnostic by:

`backend/backtest_reports/achia_strat_ema20/post_run_boundary_audit/`

That audit contains corrected entry CSVs and `audit.json`:

- Portfolio: 1,514/1,514 valid; six false flags corrected.
- Independent tickers: 41,167/41,167 valid; 178 false flags corrected.
- Corrected native stop/provenance coverage: **100%** in both analyses.
- Remaining failed gates: Sharpe, Calmar, independent expectancy, maximum stop
  distance, and the literal preparation-failure screen. Classification: REJECTED.
- The only changed file in the frozen source manifest after performance is
  `src/alphapilot/backtesting/achia_reporting.py`:
  frozen `e4eaf09c895fe405950c0789714cce62b20b512f6f0032e9e59a201731fd28c2`;
  corrected `3073eb152665d0e9e643317c4d9a6f94539bcd5a494ae0e2b4aabf1093472f76`.
  The new regression test is separate from the runtime source manifest.

This chronology is intentional: the corrected reporter is not falsely claimed
to have existed at the original freeze. A reproduction with current source must
use a fresh output directory/freeze; the CLI refuses to overwrite a completed
experiment or silently replace a differing freeze.

## 3. Portfolio assumptions and analysis levels

Shared portfolio: $100,000; ten positions; unchanged equal-slot whole shares;
shared nonnegative cash; no leverage. COST_LOW is $0 commission and 5 bps per
side. RS20 is signal-time stock 20-bar return minus SPY 20-bar return, used ONLY
for allocation competition; descending score, deterministic ticker ties/fallback.
There is no News filter, risk-based sizing, reserve, or sector-cap overlay.
Opening exits precede new OPEN entries; later intraday proceeds cannot fund them.
Final positions are marked to final close, not liquidated.

Independent analysis: each of the same 497 prepared tickers is simulated with
its own $100,000, one equal slot, one position maximum, identical strategy/stop/
costs, and no cross-ticker/RS20 competition. Pooled trade diagnostics are not a
realizable shared-capital portfolio. Aggregate pooled CAGR/turnover is therefore
not fabricated; each ticker's full metrics are in its CSV.

Gross return means gross P&L of the SAME executed holdings, before their observed
friction. It is not a zero-cost rerun or a zero-cost counterfactual allocation.
Sharpe uses the existing daily-return/252-session convention with zero risk-free
rate; Calmar is CAGR divided by maximum drawdown. Turnover is cumulative two-sided
traded notional divided by initial capital, NOT annualized. Percentiles use the
existing floor-index convention; the ordinary median is shown separately.

## 4. Development portfolio comparison

All percentages below are percentage units; raw Decimal precision is preserved
in JSON/CSV. The reference is unchanged EMA20 Pullback HYBRID 2%, not a candidate
for selection in this experiment.

| Metric | Achia V1 | EMA20 HYBRID 2% reference |
|---|---:|---:|
| Technical BUY facts | 97,434 | 42,906 |
| Flat executable candidates considered | 94,783 | 41,512 |
| Accepted entries, including final open | 1,514 | 263 |
| Completed trades | 1,504 | 253 |
| Final open positions | 10 | 10 |
| Rejected candidates | 93,269 | 41,249 |
| No subsequent session for BUY | 189 | 27 |
| Held/not-fresh BUY facts excluded before selection | 2,462 | 1,367 |
| Final equity | $115,461.11 | $180,145.51 |
| Net return | 15.4611% | 80.1455% |
| Same-holdings gross return | 29.1743% | 82.9015% |
| CAGR | 4.3651% | 19.1158% |
| Maximum drawdown | 40.9528% | 26.4281% |
| Sharpe | 0.3080 | 0.8687 |
| Calmar | 0.1066 | 0.7233 |
| Win rate | 33.5106% | 32.0158% |
| Profit factor, net dollar P&L | 1.0754 | 1.4667 |
| Mean trade / percentage expectancy | 0.1540% | 2.0531% |
| Median trade | -0.8497% | -3.0704% |
| Mean loser | -2.2182% | -5.2655% |
| Median loser | -1.6733% | -5.0713% |
| Worst trade | -22.8203% | -17.5280% |
| P5 trade | -5.0161% | -10.2704% |
| Mean / median holding, calendar days | 7.97 / 3 | 36.94 / 27 |
| Cumulative turnover | 27,426.35% | 5,511.94% |
| Observed transaction friction | $13,713.15 | $2,755.94 |
| Mean invested exposure | 97.7338% | 78.7860% |
| Mean open positions / maximum | 9.81 / 10 | 7.89 / 10 |
| Mean cash | $2,171.37 | $20,991.85 |
| Mean cash as equity share | 2.2662% | 21.2140% |
| Final cash | $287.40 | $86.85 |
| Net realized P&L | $15,371.20 | $45,251.47 |
| Net final-open unrealized P&L | $89.91 | $34,894.04 |

Achia produced 2.27 times as many technical BUY facts, 5.94 times as many
completed trades, and 4.98 times the turnover. Return was **64.68 percentage
points lower**, CAGR 14.75 points lower, and drawdown **14.52 points worse**.
A slightly higher win rate and smaller typical loser did not translate into a
better portfolio. Its wider entry eligibility plus strict EMA20 close exit
produce substantial short-holding turnover; this is descriptive evidence, not
permission to change the entry band or exit.

Friction consumed 47.00% of same-holdings gross gain: $29,174.26 gross P&L less
$13,713.15 friction equals $15,461.11 net gain. That is a serious weakness even
under the fixed 5 bps model, without any additional liquidity/capacity stress.

SPY buy-and-hold over the same actual curve period, with the same entry friction
and final mark-to-market, finished at **$133,057.98**: return **33.0580%**, CAGR
8.8589%, drawdown 25.3564%, Sharpe 0.5711. Achia lagged its price return and had
worse drawdown. SPY is not a dividend-reinvested total-return or risk-matched
benchmark and has no forced final sale cost.

## 5. Signal funnel and independent trade evidence

Main candidate rejections: **93,203 slots-full**, **66 insufficient-allocation**.
Reference: 41,227 slots-full and 22 insufficient-allocation. The latter is the
existing simulator's generic allocation-rejection code, not a newly inferred
financial reason. Missing history is separately reported above. All accepted
native stops are valid; no fabricated ATR was used. No invalid-OHLC reason was
observed. All 846 equity rows have nonnegative cash and at most ten positions.

| Independent-ticker diagnostic | Achia | Reference |
|---|---:|---:|
| Prepared tickers | 497 | 497 |
| Accepted entries | 41,167 | 7,886 |
| Completed trades | 41,065 | 7,806 |
| Final open positions across separate simulations | 102 | 80 |
| Net percentage expectancy per trade | -0.0969% | 0.0019% |
| Net dollar profit factor | 0.9016 | 1.0061 |
| Win rate | 39.9148% | 28.1706% |

Achia independent outcomes: 16,391 winners and 24,674 losers; loss rate 60.0852%;
median trade -0.3845%; P5 -3.5676%; mean/median winner +2.1675%/+0.9939%;
mean/median loser -1.6011%/-1.2184%; worst -30.2075%; mean dollar expectancy
-$88.75. Mean/median calendar holding was 4.60/1 days; mean/median observed
trading sessions was 4.16/2. Mean/median MFE was 2.2205%/1.0066%; mean/median
MAE was -1.5591%/-1.2671%. There were 3,595 protective stops (8.7544% of trades)
and 37,470 close-below-EMA20 exits. Only 145/497 independent ticker simulations
had positive total return. These results do not demonstrate a broad standalone
edge. Differences from the ranked portfolio combine ranking, capital constraints,
and different executed holdings; they are not a clean causal RS20 experiment.

## 6. Trade outcomes, stops, and loss-control risk

Main portfolio: 504 winners, 1,000 losers, no breakevens. Loss rate 66.4894%.
Dollar expectancy is $10.22 per completed trade. Mean/median winner is
4.8606%/1.7348%; mean/median loser is -2.2182%/-1.6733%. Best trade is 273.8122%,
worst -22.8203%; P5 is -5.0161%. Mean/median observed holding is 6.49/2 ticker
sessions, or 7.97/3 calendar days.

All 1,504 completed trades have one authoritative exit family:

| Exit | Trades | Win rate | Mean return | Median return | Worst | Mean / median calendar days |
|---|---:|---:|---:|---:|---:|---:|
| PROTECTIVE_STOP | 207 | 0% | -4.6333% | -4.2126% | -22.8203% | 2.73 / 1 |
| CLOSE_BELOW_EMA20 | 1,297 | 38.8589% | 0.9180% | -0.5105% | -8.7372% | 8.80 / 3 |

Stop rate: **13.7633%**. Gap-through stops: **55**; non-gap intraday stops: **152**.
**76 stops occurred on entry day**, proving that the configured first-day
activation matters in actual replay as well as tests. No double-exit or duplicate
entry ID was found. Re-entry counts are diagnostic only; no cooldown was added.

| Initial stop-risk diagnostic, 1,514 entries | Value |
|---|---:|
| Mean stop distance / entry fill | 4.3141% |
| Ordinary median | 3.8836% |
| Floor-index P50 | 3.8825% |
| P75 | 4.7642% |
| P90 | 6.2393% |
| Maximum | 26.3026% |
| Entries above 20% | 2 |
| Mean / median planned risk dollars | $394.30 / $352.37 |
| Maximum planned risk dollars | $2,499.90 |
| Mean / median planned risk as entry equity | 0.4111% / 0.3706% |
| Maximum planned risk as entry equity | 2.6299% |
| Corrected native boundary/provenance coverage | 100% |

Each entry artifact includes shares, position value, entry equity, actual/raw
fill, signal ATR/date, 1% component, stop, risk/share, risk%, risk dollars and
portfolio-risk%. Generic equal-slot risk-overlay fields remain inactive; their
zero placeholders do NOT imply zero financial risk. Use these native stop-risk
fields, not the inactive risk-sizing overlay fields.

Maximum planned distance was CVNA, signal 2023-02-21, entry 2023-02-22:
fill 2.063031, ATR 0.5220, stop 1.52040069, risk 26.3026%. Another CVNA entry on
2023-02-24 had 23.4137% planned distance. No ad hoc cap or exclusion was imposed.

The worst trade demonstrates gap risk: DDOG entered 2023-08-07 at 109.27461,
with stop 103.1965996143. On 2023-08-08 it opened at 84.38; the raw gap exit was
that OPEN, then the 5 bps sell fill was 84.33781. Actual net loss was 22.8203%,
not a fictitious fill at the stop. Smaller typical stop losses do not eliminate
overnight tail losses or prove the boundary is economically adequate.

## 7. Post-stop recovery and MFE/MAE

Recovery is descriptive, never an execution input. Returns below compare the
5th/10th/20th subsequent ticker close with the actual stop exit fill, within
development only. Recovery requires a completed close >= original entry fill.

| Horizon | Available observations | Mean return | Median return |
|---|---:|---:|---:|
| 5 sessions | 206 | 0.1376% | 0.3743% |
| 10 sessions | 201 | 0.6764% | 0.7329% |
| 20 sessions | 196 | 2.3628% | 2.5324% |

121/196 known observations recovered entry within 20 sessions: **61.7347%**.
Eleven observations are censored, not recorded as failed recovery. Recovery
dispersion remains wide: 20-session returns range from -30.5462% to +69.0929%.
Frequent recovery is consistent with some stop/whipsaw cost, but it neither
proves stops should be removed nor creates a re-entry instruction.

| Group | Mean MFE | Median MFE | Mean MAE | Median MAE |
|---|---:|---:|---:|---:|
| All completed | 4.3395% | 1.5265% | -2.2584% | -1.8593% |
| Winners | 9.5632% | 5.4684% | -1.1753% | -0.9186% |
| Losers | 1.7068% | 0.9255% | -2.8042% | -2.4793% |
| Protective stops | 1.3873% | 0.3730% | -4.5856% | -4.1647% |
| EMA20 close exits | 4.8107% | 1.7329% | -1.8869% | -1.6425% |

All-trade MFE P90 is 10.2245%, maximum 376.7862%; MAE P5 is -5.4295%, minimum
-22.7817%. These use the existing observed held-session extrema and raw exit
reference, relative to slipped entry fill. A surviving entry-day range is known;
the exit day's post-exit path is not. In particular, 152 intraday-stop trades
have censored exit-day excursions; no full-day HIGH is passed off as known
pre-stop MFE. Thus these are conservative observed excursions, not complete
intraday path reconstruction.

## 8. Entry location, trend spread, and stop-risk buckets

Signal-day distance is `(Close / EMA20 - 1) * 100`. These buckets were declared
before results and remain descriptive; the strategy still permits the entire
inclusive -10% through +1% zone.

| Entry-distance bucket | Technical BUYs | Completed portfolio trades | Win rate | Mean return | Stop rate |
|---|---:|---:|---:|---:|---:|
| [-10,-7.5) | 1,148 | 10 | 30.00% | -1.2862% | 20.00% |
| [-7.5,-5) | 4,027 | 13 | 76.92% | 1.0631% | 0% |
| [-5,-2.5) | 16,329 | 89 | 39.33% | -0.3869% | 7.87% |
| [-2.5,0) | 46,784 | 556 | 35.97% | 0.0493% | 12.41% |
| [0,1] | 29,146 | 836 | 30.62% | 0.2842% | 15.43% |

No Achia BUY was outside the zone. Small samples in the deeper buckets cannot
justify selecting a winning sub-band; ranking/portfolio constraints heavily
change the executed mix. No bucket was removed or used to retune V1.

Signal-day EMA spread `(EMA20-EMA50)/EMA50*100` at the 1,504 completed entries:
mean 3.6352%, median 3.0673%, P75 4.7197%, P90 6.8076%, minimum 0.0030%, maximum
24.7953%. No minimum-spread filter beyond strictly >0 was added.

| Initial stop-risk bucket | Completed trades | Mean return | Mean MFE | Mean MAE | Stop rate |
|---|---:|---:|---:|---:|---:|
| (0,2]% | 1 | -1.1708% | 0.1286% | -1.2292% | 0% |
| (2,4]% | 822 | 0.1138% | 3.5760% | -1.7538% | 12.77% |
| (4,6]% | 506 | 0.3946% | 5.0903% | -2.6065% | 16.60% |
| (6,10]% | 155 | -0.2787% | 5.7292% | -3.4198% | 11.61% |
| >10% | 20 | -0.8641% | 6.1687% | -5.2359% | 0% |

Wider initial risk coincides with greater average adverse excursion in these
samples, but stop probability is not monotonic: EMA20 close exits can occur
before a wide static boundary. This is not evidence to select a new ATR factor,
percentage component, or risk cap within this task.

## 9. Attribution and concentration

Exact reconciliation, dollars:

`100000 + 29026.84340121392857142857159 + 147.4200
 - 13713.15263600060696428571430
 = 115461.1107652133216071428572`, within a -1e-22 residual.

Equivalently: initial equity + net realized $15,371.2039102133 + net unrealized
$89.906855 = final equity. Cash $287.4007652133 + marked holdings $115,173.71
also equals final equity. The reference reconciles exactly to reported precision.
Principal cash flows are not double-counted as P&L; open positions are included.

Achia held 422 unique tickers; 141 contributed positive net P&L and 281 negative.
Top contributors were APP $23,828.59; EQT $8,776.15; MOS $5,905.43; VRT $3,960.77;
HIG $3,327.72. Top-one/top-five/top-ten net contribution sums were $23,828.59 /
$45,798.67 / $59,410.37, or 154.12% / 296.22% / 384.26% of total net gain.
Shares above 100% reflect losses elsewhere, not an additive-attribution error.

Top-one/top-five share of total positive ticker P&L was 17.69% / 34.00%; positive-
P&L HHI was 0.04574. The reference was more positively concentrated (27.47% /
61.48%; HHI 0.11499), yet Achia's smaller net gain still depends strongly on large
winners: APP alone exceeded total net gain. Subtracting its contribution is a
descriptive P&L decomposition, not a re-simulated exclusion experiment.
All 12 observed sector buckets and ticker contributions are in the attribution
CSVs; no sector allocation rule was introduced.

## 10. Frozen gates and final decision

| Development screen | Observed | Result |
|---|---|---|
| Verified snapshot | Exact hashes; 745,232 rows | PASS |
| Positive return and CAGR | 15.4611%; 4.3651% | PASS |
| At least 100 completed portfolio trades | 1,504 | PASS |
| Sharpe >=0.50 | 0.3080 | FAIL |
| Calmar >=0.50 | 0.1066 | FAIL |
| Profit factor >1 | 1.0754 | PASS |
| Positive pooled independent expectancy | -0.0969% | FAIL |
| 100% valid native boundary/provenance | 100%, corrected audited diagnostic | PASS |
| Stop-distance P90 <=10% | 6.2393% | PASS |
| Maximum stop distance <=20% | 26.3026% | FAIL |
| Literal zero-preparation-failure screen | Five explained absent-history tickers | FAIL |

Development: **REJECTED**. Validation 2025-01-01 through 2026-08-20:
**NOT OPENED**, no classification inferred. Folds 2021-08-20–2022-12-31,
2023-01-01–2024-12-31, and 2025-01-01–2026-08-20: **NOT OPENED**.

The strategy improves typical loser/P5 statistics versus the reference, but
destroys much of return, worsens portfolio drawdown, creates heavy turnover,
and has negative broad independent-ticker expectancy. Numeric stop availability
is engineering capability, not proof of economically acceptable loss control.
Recommend **do not promote or activate V1**. Return this evidence for independent
user review. A future hypothesis or a revised data-coverage protocol would need
separate approval before any new research; none was started here.

## 11. Current illustrative facts — not performance inputs or actionable plans

The fixed example list was declared before results. Stored completed data was
read after the formal run, through 2026-09-04 for every example. No live quote or
future OPEN was fetched. These mutable operational illustrations are separate
from the immutable formal snapshot, and may differ on a later reproduction.

| Ticker | Close | EMA20 | EMA50 | Trend valid | Distance | Zone valid | ATR14 |
|---|---:|---:|---:|---|---:|---|---:|
| APA | 42.7800 | 41.9130 | 39.5925 | Yes | 2.0686% | No | 1.4489 |
| APO | 133.5600 | 132.8816 | 130.8350 | Yes | 0.5105% | Yes | 3.3479 |
| IBKR | 92.6000 | 92.7591 | 91.4015 | Yes | -0.1715% | Yes | 3.3014 |
| EOG | 145.1300 | 145.6567 | 142.8727 | Yes | -0.3616% | Yes | 3.0468 |
| AXON | 516.0500 | 569.9601 | 547.8354 | Yes | -9.4586% | Yes | 28.9564 |
| FAST | 49.6200 | 49.8365 | 48.7840 | Yes | -0.4345% | Yes | 0.9811 |
| AAPL | 319.9500 | 316.9315 | 313.0231 | Yes | 0.9524% | Yes | 7.3796 |
| MSFT | 499.5450 | 490.1149 | 461.9162 | Yes | 1.9241% | No | 9.9136 |

For EVERY row: **STOP PRICE NOT YET KNOWABLE UNTIL ENTRY FILL**.
If a future fill is E, the expression is `E - displayed signal ATR14 - 0.01E`.
No close is substituted for E. A below-EMA example may qualify for flat entry
and held exit simultaneously; the real production strategy/profile is unchanged.
These facts do not authorize buying AXON or any other ticker.

## 12. Commands, tests, artifacts, and implementation audit

Exact formal research commands from repository root:

```powershell
cd backend
$env:DEBUG='false'
uv run python -m alphapilot.cli.research_achia_ema20 --freeze-only
uv run python -m alphapilot.cli.research_achia_ema20
```

The second command ran ONCE. It prepared Achia and the unchanged reference on
development, simulated each shared portfolio, replayed the 497 separate ticker
portfolios per strategy, enforced stage gates, and wrote the current examples.
No validation/fold, cost-zero, parameter-sweep, or additional strategy command
was executed. Preflight snapshot verification was read-only; initial diagnostic
scripts needed the repository's Windows selector event loop and manifest `start`/
`end` fields. Those preflight errors did not execute a performance backtest.

Final focused command (also run before performance without the added rounding
regression):

```powershell
cd backend
$env:DEBUG='false'
uv run pytest tests/strategy/test_achia_ema20.py tests/backtesting/test_achia_execution.py tests/backtesting/test_achia_reporting.py tests/strategy_lab/test_achia_protocol.py tests/backtesting/test_trade_management.py tests/strategy/test_ema20_pullback.py tests/strategy/test_micho150.py -q
.\run_checks.ps1
```

Results:

- Early strategy/execution/unchanged-strategy subset: 78 passed.
- Pre-performance final focused suite: **93 passed in 9.23 s**.
- Pre-performance full gate: **515 passed in 63.06 s**, Ruff/formatting PASS,
  mypy PASS across **194 source files**.
- After reporting-only Decimal correction: **94 focused passed in 11.04 s**;
  **516 full pytest passed in 73.39 s**; Ruff/formatting PASS; mypy PASS across
  **194 source files**. Final formatting check changed no files.
- `git diff --check`: PASS (Git's LF/CRLF notices are not whitespace errors).

During development, targeted `uv run ruff check ... --fix`, `uv run ruff format ...`,
and `uv run mypy src` resolved new-file style/type issues before the freeze.
Two initially identically named new test modules caused a collection collision;
the backtesting module was renamed to `test_achia_execution.py`, not suppressed.
No existing assertion was weakened. There are **53 new regression cases** in
four new test files. Existing single-stock, EMA/Micho, portfolio, ranking,
attribution, operational API and Strategy Lab tests all remain green.

Coverage includes exact/inclusive bounds, strict trend/equality exits, invalid/
missing candles/ATR, completed-session cutoff, future feature isolation, slipped
fill provenance, stop touch/gap/first-day activation, static stops, pending OPEN
exit precedence, overlapping entry/exit facts, fresh re-entry, no final-day fill,
shared cash/slots/ranking, no reuse of intraday proceeds for prior OPENs, repeatable
results/report bytes, native boundary rounding, and early Lab rejection.

The reporting-only audit was run using a bounded `@' ... '@ | uv run python -`
post-processing command. It read existing CSV/JSON, compared each stop with the
literal execution expression, checked original SHA-256 manifests, wrote separate
corrected entry CSVs/audit JSON using existing report writers, and reassessed the
same gates. It did not load market data or call any simulator. A second read-only
artifact inspection parsed every CSV, checked counts/IDs/cash/slots/equity/P&L,
and produced the tables above. Neither was a new performance experiment.

Artifact root (Git-ignored): `backend/backtest_reports/achia_strat_ema20/`.
It contains `freeze.json`, `dataset_verification.json`, `run_git.json`,
`experiment.json`, original `gate_failures.json`, `completed.json`,
`current_examples.json`, the separate corrected-boundary audit, and:

| Artifact per strategy folder | Achia rows | Reference rows |
|---|---:|---:|
| signals.csv | 97,434 | 42,906 |
| entries.csv | 1,514 | 263 |
| trades.csv | 1,504 | 253 |
| open_positions.csv | 10 | 10 |
| equity.csv | 846 | 846 |
| selection_audit.csv | 94,783 | 41,512 |
| attribution.csv | 422 | 182 |
| sector_attribution.csv | 12 | 12 |
| stop_recovery.csv | 207 | 0 |
| independent_ticker_metrics.csv | 497 | 497 |
| independent_entries.csv | 41,167 | 7,886 |
| independent_trades.csv | 41,065 | 7,806 |
| independent_stop_recovery.csv | 3,595 | 0 |

Folders: `achia_2021-08-20_2024-12-31` and
`ema_reference_2021-08-20_2024-12-31`, each with `summary.json` and SHA-256 artifact
manifest. All CSVs were parsed; all accepted-entry counts reconcile to completed
plus open positions and selected audits; all entry IDs are unique; every equity
row reconciles cash plus holdings; realized trade P&L matches attribution within
normal Decimal precision. No original artifact was overwritten by the correction.

### Files created for this task

- `backend/src/alphapilot/strategy/achia_ema20.py`
- `backend/src/alphapilot/backtesting/achia_reporting.py`
- `backend/src/alphapilot/strategy_lab/achia_ema20_protocol.py`
- `backend/src/alphapilot/cli/research_achia_ema20.py`
- `backend/tests/strategy/test_achia_ema20.py`
- `backend/tests/backtesting/test_achia_execution.py`
- `backend/tests/backtesting/test_achia_reporting.py`
- `backend/tests/strategy_lab/test_achia_protocol.py`
- `docs/research/ACHIA_STRAT_EMA20_PROTOCOL.md`
- `docs/research/ACHIA_STRAT_EMA20_RESULTS.md`

### Existing files modified for this task

- `backend/src/alphapilot/strategy/evaluation.py`: additive reason codes and
  independent held-exit evidence, defaulting to None for existing strategies.
- `backend/src/alphapilot/backtesting/trade_management.py`: isolated native
  Achia stop identity/formula/activation, retaining previous policies.
- `backend/src/alphapilot/backtesting/multi_portfolio.py`: consume independent
  exit facts, native entry-day management, fresh-signal re-entry, and exit counts.
- `backend/src/alphapilot/backtesting/multi_portfolio_service.py`: recognize the
  new stop reason in existing diagnostics; new recovery reports implement the
  predeclared censoring explicitly.
- `AGENTS.md`, `docs/PROJECT_STATE.md`, `docs/DECISIONS.md`: continuity, frozen
  rules, final rejection, audit correction, and non-activation boundaries.

Previous EMA50 research changes in shared files were preserved. In particular,
the already-dirty portfolio model/provenance work was reused, not newly invented
here. No frontend file, existing strategy implementation, operational profile,
configuration secret, dependency manifest, migration, or broker integration was
changed in this task.

## 13. Limitations, debt, and safety

- Survivorship bias: frozen CURRENT constituents, not point-in-time membership;
  five absent development histories; listing availability changes within a period.
- Snapshot hashes prove reproducibility, not perfect provider prices or corporate-
  action provenance. LEGACY_PARTIAL provenance and split-adjusted historical
  prices remain explicit. No mutable-price repair or data substitution occurred.
- These development/validation/fold windows were observed in previous AlphaPilot
  research; they are not pristine future OOS. This new strategy did not enter its
  validation or folds, so no temporal robustness claim is available.
- Fixed 5 bps per side and zero commission are assumptions, not capacity/liquidity,
  spread, halt, or real stop-fill models. Large gaps can exceed initial risk.
- Daily OHLC cannot identify the full path before an intraday stop. MFE/MAE
  censoring and right-censored recovery are material, documented limitations.
- SPY is a split-adjusted price benchmark, not total return; no risk matching or
  final liquidation cost. Final open positions contribute marked unrealized P&L.
- High turnover, negative independent expectancy and large-winner dependence
  weaken economic credibility despite positive shared-portfolio net gain.
- Technical debt: the replay engine repeatedly calculates history/indicators and
  is slow; a future causal, equivalence-tested precomputation/progress mechanism
  could help, but it was not introduced during this experiment.
- The frozen zero-preparation-failure screen should distinguish predeclared
  absent-history exclusions from unexpected errors in a separately approved
  future protocol. It was not changed opportunistically here.
- Generic equal-slot selection diagnostics have inactive risk-overlay placeholders
  and a broad insufficient-allocation code. The native entry-risk artifacts are
  authoritative for this research; zero placeholders are not zero risk.
- A research-only identity is not a production StrategyProfile or an actionable
  loss-control approval. EMA20 Pullback's prior NO_APPROVED policy conclusion is
  unchanged. No UI/API activation work is included.

The application database transaction was read-only and rolled back. No current
ResearchPortfolio, positions, Paper records, trade events, News, DailyCandles,
Alpaca, or broker state was mutated. Pytest used the separate verified test
database with its normal isolated setup/cleanup; it did not target development.
No `.env` value was printed or changed. DEBUG=false was scoped to child shells.
No frontend, Sprint 25, or further experiment was started.

## 14. Git status and handoff

Branch remains `research/ema20-loss-control`; HEAD remains `decc7d1`.
No branch switch, staging, commit, push, merge, PR, tag, or history rewrite.
The worktree was dirty before this task and remains dirty. Current tracked
modifications (14) include both this task and preserved prior work:

```text
M AGENTS.md
M backend/src/alphapilot/backtesting/multi_portfolio.py
M backend/src/alphapilot/backtesting/multi_portfolio_models.py
M backend/src/alphapilot/backtesting/multi_portfolio_service.py
M backend/src/alphapilot/backtesting/sprint12_protocol.py
M backend/src/alphapilot/backtesting/sprint12_reporting.py
M backend/src/alphapilot/backtesting/trade_management.py
M backend/src/alphapilot/cli/backtest_strategy_exits.py
M backend/src/alphapilot/strategy/evaluation.py
M docs/DECISIONS.md
M docs/PROJECT_STATE.md
M frontend/src/features/portfolio/PortfolioAllocationDonut.test.tsx
M frontend/src/features/portfolio/PortfolioAllocationDonut.tsx
M frontend/src/styles.css
```

Untracked (15, including this report): the ten task-created files listed above,
plus preserved prior work:

```text
backend/src/alphapilot/strategy_lab/ema20_loss_control_protocol.py
backend/tests/backtesting/test_ema20_loss_control.py
docs/research/EMA20_LOSS_CONTROL_PROTOCOL.md
docs/research/EMA20_LOSS_CONTROL_RESEARCH.md
frontend/scripts/portfolio-allocation-donut-smoke.mjs
```

`git diff --stat` for tracked files, excluding new/untracked files and ignored
research artifacts: **14 files changed, 611 insertions(+), 45 deletions(-)**.
This is the whole mixed worktree, not a claim that this task changed the frontend
or authored all earlier research edits. The source/test/report files for this
task are ready for user review and a possible commit of research evidence;
shared hunks and prior work must be reviewed together before the user stages them.

Recommended commit message, only if the user approves recording the research:

`feat(research): evaluate Achia EMA20 V1 with native static stops`

## 15. Required final answers (1–50)

1. Canonical ID/version: `achia-strat-ema20-v1`, version 1.
2. Separate from EMA20 Pullback V1: YES.
3. LONG only: YES.
4. Bullish trend: completed EMA20[T] > EMA50[T], strictly.
5. Entry: inclusive `0.90*EMA20[T] <= Close[T] <= 1.01*EMA20[T]`.
6. T+1: next available ticker OPEN plus 5 bps BUY friction; no fabricated fill.
7. ATR14: existing simple mean of 14 true ranges, requiring 15 candles, through T.
8. Stop: actual entry fill minus ATR14[T] minus 1% of actual entry fill.
9. Active on entry day: YES, immediately after the OPEN fill.
10. Gap-through: existing-position OPEN <= stop exits at raw OPEN, then SELL friction.
11. Static: YES; no daily ATR/EMA reset, trail, target, or breakeven.
12. Strategy exit: completed Close[V] < EMA20[V], next available OPEN execution.
13. Daily Close based: YES.
14. Close == EMA20 exits: NO.
15. Intraday LOW below EMA20 alone exits: NO; protective stop is separate.
16. Precedence: opening gap stop, pending OPEN strategy exit, later intraday stop,
    then surviving completed-close evaluation; no double exit.
17. Parameter sweep: NO.
18. Validation retuning: NO; validation was not opened.
19. Snapshot/hash: `5dd60f87-8947-4850-ba87-4a7df655528c` /
    `b77ba749182fb4408394eed6d47c7d39dcfcb52a4555683c8a0b9fa7cb91374b`.
20. Development: 2021-08-20 through 2024-12-31.
21. Validation: NOT OPENED; planned 2025-01-01 through 2026-08-20.
22. Technical BUY facts: 97,434; 94,783 considered by the shared portfolio.
23. Trades: 1,514 accepted entries, 1,504 completed, 10 open; independent 41,065 completed.
24. Net return/CAGR: 15.4611% / 4.3651%.
25. Maximum drawdown: 40.9528%.
26. Sharpe/Calmar: 0.3080 / 0.1066.
27. Win rate: 33.5106% portfolio; 39.9148% independent pooled.
28. PF/expectancy: 1.0754 / +0.1540% portfolio; 0.9016 / -0.0969% independent.
29. Mean/median/worst loser: -2.2182% / -1.6733% / -22.8203%.
30. Turnover/friction: 27,426.35% cumulative / $13,713.15.
31. Protective stops: 207 / 13.7633% of completed trades.
32. Gap stops: 55.
33. Stop-distance floor P50/P75/P90/max: 3.8825% / 4.7642% / 6.2393% / 26.3026%.
34. CLOSE_BELOW_EMA20 exits: 1,297.
35. Mean 5/10/20-session post-stop returns: +0.1376% / +0.6764% / +2.3628%;
    entry recovered in 121/196 known cases; 11 censored.
36. Mean/median MFE: 4.3395% / 1.5265%; MAE: -2.2584% / -1.8593%;
    group distributions and exit-day censoring are in section 7 and artifacts.
37. Entry buckets: mixed descriptive results, sparse deep-zone samples; no retuning.
38. EMA spread: mean 3.6352%, median 3.0673%, P90 6.8076%; no added filter.
39. Reference: 80.1455% return, 19.1158% CAGR, 26.4281% DD, 0.8687 Sharpe;
    Achia traded far more with much weaker overall risk-adjusted performance.
40. Development classification: REJECTED.
41. Validation classification: NONE / NOT OPENED.
42. Final Strategy Lab classification: REJECTED, unchanged by the reporting correction.
43. Next step: independent/user review; do not activate or tune V1 in this task.
44. Activated in production Portfolio Plan: NO.
45. Current Portfolio mutation: NO.
46. Paper mutation: NO.
47. Broker action: NO.
48. Final backend gate: PASS; 516 tests, Ruff/formatting, mypy 194 source files.
49. Git: unchanged local branch/HEAD; 14 tracked modifications and 15 untracked
    files including preserved earlier work; no commit/push.
50. Recommended commit if approved:
    `feat(research): evaluate Achia EMA20 V1 with native static stops`.

STOP: no further experiment, parameter change, or production integration is approved.
