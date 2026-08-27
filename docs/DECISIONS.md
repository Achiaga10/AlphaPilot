# AlphaPilot — Current Decisions

This file records decisions that must not be silently changed.

## 0. Current Phase

Sprint 6 is complete and merged.

Sprint 7 — Multi-Stock Portfolio Backtesting — is complete and merged.

Sprint 8 — Candidate Ranking & Portfolio Selection — is complete and merged.

Sprint 9 — Ranking Robustness, Transaction Costs & Return Attribution — is complete and merged.

Sprint 10 — Portfolio Risk, Position Sizing & Decision API — is complete and reviewed.

Sprint 10B — Risk Model Hardening & Decision Orchestration — is complete and merged.

Sprint 11, Sprint 11B, Sprint 11C, and Sprint 11D are complete and merged.
Sprint 12 is complete, reviewed, and merged; its research-only stop candidates
do not replace existing strategy exits. Sprint 13 is complete, reviewed, and
merged. Sprint 14 is complete locally on `feature/strategy-profiles` and awaits
user review/publishing. Sprint 15 is not started.

## 0.13 Sprint 14 Frozen Strategy-Profile Protocol

- The normal Portfolio Plan workflow resolves an immutable, versioned backend
  strategy profile; browser-supplied sizing or strategy-rule parameters are not
  authoritative.
- `ema20-pullback-v1` uses existing EMA20 Pullback entry, HYBRID 2%, equal-slot
  sizing, no default protective stop, and no profit management.
- `micho-150-v1` uses Micho V1 BOTH entry, close-below-SMA150 exit,
  ATR-volatility-normalized sizing, no default protective stop, and no profit
  management.
- Both profiles are `PROMISING_RESEARCH_BASELINE`; selection remains
  user-selectable with RS20 recommended. RS20 remains a research baseline, not
  universal production alpha.
- Sprint 12's EMA static 3× ATR14 and Micho static 1.5× ATR14 stops remain
  informational research-only candidates and are not enabled defaults.
- Global `PortfolioRiskConfig` stays separate and unchanged. Sprint 14 invents
  no strategy-specific risk parameters.
- Profile identity/version/resolved configuration participate in plan identity
  and stateless action validation.
- The lower-level decision endpoint remains explicitly configurable for research
  compatibility. Strategy factory and Scanner defaults remain unchanged.
- Sprint 13 immutable dataset, provenance, completed-session, and snapshot
  semantics remain unchanged.
- Sprint 15 Strategy Lab is recommendation-only and must not begin during
  Sprint 14.

## 0.12 Sprint 13 Frozen Data-Reproducibility Protocol

- `DailyCandle` remains mutable operational latest state; frozen research reads
  explicit immutable `DailyCandleVersion` mappings and never operational rows.
- Every material completed-session OHLCV change creates one append-only version;
  exact duplicates do not. Decimal values are never compared through float.
- Provider sync requests create explicit sanitized ingestion batches with
  provider/feed, range, lifecycle, and counts. Secrets are never persisted.
- Snapshots freeze exact universe/benchmark members and exact candle version IDs.
  Finalized snapshots and their mappings cannot be mutated through normal APIs.
- Dataset hashing is canonical UTF-8, ticker/day sorted, Decimal-string based,
  and SHA-256. Universe hashing uses sorted uppercase tickers.
- Existing rows receive set-based `LEGACY_UNKNOWN` versions. They become value-
  reproducible at installation but their lost pre-Sprint13 revisions and source
  provenance cannot be reconstructed or relabeled Alpaca/IEX.
- Current-universe snapshots retain survivorship bias and must be described as
  frozen current-universe snapshots, never historical point-in-time membership.
- Research output records operational versus frozen data mode, snapshot/hash,
  provenance status, Git HEAD, and dirty state. New research should prefer a
  frozen snapshot.
- Sprint 13 changes no strategy, RS20, sizing, trade-management, cost, or T+1
  execution rule. Sprint 14 configuration profiles are recommendation-only.

## 0.11 Sprint 12 Frozen Research Protocol

- Strategy entries remain EMA20 Pullback and Micho V1 BOTH. EMA control remains
  HYBRID 2%; Micho control remains close-below-SMA150.
- Primary portfolios are EMA RS20/equal-slot and Micho RS20/
  ATR-volatility-normalized at COST_LOW, $100,000, 10 positions.
- Research exits are simulator overlays, never embedded in strategy classes or
  UI during Sprint 12.
- Protective candidates are control, ATR14 1.5x, 2.0x, and 3.0x static stops.
  Highest development Calmar selects, with Sharpe/drawdown/CAGR tie-breaks.
- Stop fills are open on gap-through, otherwise the pre-known stop; stop has
  conservative priority. Entry-created orders activate the following session.
- Trailing candidates are none, ATR 2.0x, and ATR 3.0x; only T-1 closes/ATR may
  move a monotonic stop.
- Profit candidates are none, one 50%-whole-share partial at +2R, and full exit
  at +3R. Same-bar ambiguous stop/target ordering is stop-first.
- At most one trailing or fixed/partial overlay accompanies the selected
  protective stop. Positive-CAGR candidates must retain at least 80% of the
  relevant development control CAGR to be eligible.
- Development is 2021-08-20–2024-12-31; untouched validation is
  2025-01-01–2026-08-20; folds are 2021-08-20–2022-12-31,
  2023-01-01–2024-12-31, and 2025-01-01–2026-08-20.
- No validation retuning, additional multiples, new entry/ranking/sizing
  parameter, or inconvenient-fold removal is permitted.
- All historical results retain current-constituent survivorship bias and daily
  OHLC path ambiguity. Sprint 12 may validly select the existing strategy exit.

### Sprint 12 protective-stop development selection

Phase 0 reproduced both COST_LOW development controls:

- EMA HYBRID 2% + RS20 + equal-slot: 80.15% return, 26.43% max drawdown,
  0.87 Sharpe.
- Micho BOTH + RS20 + ATR-volatility-normalized: 48.43% return, 15.74% max
  drawdown, 0.77 Sharpe.

The predeclared highest-development-Calmar rule selected and froze:

- EMA: `atr-stop-3-0` (Calmar 0.755 versus 0.723 control).
- Micho: `atr-stop-1-5` (Calmar 0.920 versus 0.791 control).

These protective multipliers may not change after later trailing, profit, or
validation results. The final optional overlay remains to be selected from the
already-declared Phase 2/3 candidates before validation.

Phase 2/3 then froze the final development configurations before validation:

- EMA: keep `atr-stop-3-0` with no additional overlay. ATR trailing 2x/3x and
  partial +2R/full +3R all had lower development Calmar; both fixed-profit
  candidates also failed the 80% positive-CAGR-retention gate.
- Micho: keep `atr-stop-1-5` with no additional overlay. Both trailing exits
  severely truncated returns; both fixed-profit candidates failed the 80%
  positive-CAGR-retention gate.

Therefore the selected protective configuration and selected final
configuration are identical for each strategy. These exact choices are encoded
in `FROZEN_EXIT_SELECTIONS`; validation/fold runner stages reject any other
candidate. No validation result was opened before this freeze.

Validation control figures differ materially from Sprint 10B because stored
recent candle data was revised after that Sprint, not because the inactive
control overlay changed execution. Evidence recorded before fold analysis:

- current and Sprint 10B selection audits first diverge on execution day
  2025-07-23 (signal day 2025-07-22), matching the later UI 400-day sync
  boundary;
- 702,853 candle rows for 503 companies were upserted on 2026-08-21, covering
  2019-07-17 through 2026-08-20;
- Sprint 11D records the configured sync source/feed as Alpaca IEX and records
  that individual candle rows lack feed provenance;
- development controls ending 2024-12-31 still reproduced their prior values.

Sprint 12 therefore uses the current stored candles consistently for both
control and frozen candidates. The completion report must disclose the data
revision, mixed/provenance limitation, and non-comparability of current
validation headlines with the older Sprint 10B artifact values.

Daily-candle research decisions use completed U.S. market sessions only. The
backend's `CompletedDailySessionPolicy` uses `America/New_York` and a
conservative 16:15 completion boundary. Before that boundary, today's daily bar
is in progress and is excluded from provider persistence and every normal
research/latest/admin read. Stored SPY dates provide the actual session calendar
for weekends and holidays. Existing partial rows are quarantined, not deleted;
the normal `(company_id, trading_day)` upsert replaces a row with final OHLCV
after completion. Frontends must display backend-provided completed-session
dates and must not infer market completion from browser time.

Sprint 8 compares the non-alpha alphabetical control with fixed RS20. Do not optimize the 20-bar lookback, strategy parameters, portfolio constraints, or use validation to retune the formula.

## 0.3 Sprint 8 Ranking Decisions

- `ticker-ascending` remains the deterministic, economically meaningless control.
- `relative-strength-20` uses stock 20-bar return minus SPY 20-bar return.
- Scores use information through the BUY signal day only and are frozen before next-OPEN execution.
- Higher score ranks first; equal scores use ticker ascending.
- Scored candidates rank before candidates lacking history; unscored candidates use ticker ascending and never receive fabricated scores.
- Ranking features, ordering, allocation, execution, and accounting remain separate concerns.
- Selection decisions must be auditable with signal/execution dates, score, rank, outcome, rejection reason, slots, cash, and equity context.
- The fixed experiment is complete locally. RS20 beat the alphabetical control for both strategies in both development and validation without parameter retuning.
- This validates the ranking infrastructure and supports further research; it does not make RS20 production-ready or change either strategy.

## 0.4 Sprint 9 Robustness Decisions

- RS20 is frozen as Ranking Baseline V1: 20 stock bars minus 20 SPY bars, using signal-day information only.
- Fixed per-side scenarios are COST_0 = 0 bps, COST_LOW = 5 bps, and COST_CONSERVATIVE = 15 bps; all use zero commission.
- Fixed folds are 2021-08-20–2022-12-31, 2023-01-01–2024-12-31, and 2025-01-01–2026-08-20.
- Attribution uses additive dollar P&L and distinguishes gross P&L, friction, net realized P&L, and final open unrealized P&L.
- Positive-contributor HHI is the sum of squared shares of total positive ticker P&L.
- Stored sector values may be reported; missing values are `Unknown` and are never inferred.
- Strategy rules, 2% HYBRID, Micho BOTH, 10 positions, equal-slot sizing, costs, folds, and RS20 may not be retuned after results.
- Sprint 9 completed locally without retuning. RS20 beat control at 5 and 15 bps for both strategies on the validation period.
- Temporal evidence was mixed: RS20 beat control on total return in 2/3 EMA folds and 1/3 Micho folds. RS20 therefore remains a useful research baseline, not a proven universal default.
- Validation performance was materially concentrated, especially for Micho and in final open positions; future research must retain contributor and realized/unrealized attribution.

## 0.5 Sprint 10 Risk and Decision Decisions

- ATR14 uses the latest 14 true ranges through signal day and requires the preceding close; no future candle may affect it.
- ATR-risk sizing uses 1% equity risk, 2× ATR stop proxy, 10% position cap, 8% portfolio risk cap, 10% entry cash reserve, 30% sector cap, 10 positions, and whole shares.
- Equal-slot remains available and unchanged for research compatibility.
- Position modeled risk is frozen at entry as shares × entry stop distance; portfolio risk is the sum across active positions.
- Missing sectors form one explicit `Unclassified` bucket subject to the same sector cap; sectors are never inferred.
- Strategy signals and portfolio decisions are separate typed concepts; entry constraints never block SELL.
- The decision API is advisory only: no broker execution or persistence.
- All V1 parameters are frozen for the Sprint 10 experiments and may not be retuned after results.
- Sprint 10 completed locally without retuning. ATR-risk reduced EMA drawdown but materially reduced return; it did not reduce Micho drawdown and also reduced Micho return.
- All entry risk, cash-reserve, sector, max-position, whole-share, and cash constraints validated without breaches. Sector weights may drift above the entry cap through appreciation; no forced selling occurs.
- The typed decision API is suitable for UI consumption as an advisory contract. Automated market-data/signal enrichment and broker synchronization remain separate adapters.

## 0.6 Sprint 10B Frozen Decisions

- Preserve `equal-slot` and Sprint 10 `atr-risk` without formula changes.
- Add only the predeclared `atr-volatility-normalized` policy: inverse ATR14
  percentage weights normalized across the same eligible candidate group.
- Use 10% reserve, 10% position cap, 8% modeled-risk cap, 30% sector cap, and 10
  positions. Do not search parameters after development or validation results.
- Volatility normalization requires a batch allocation boundary; it must not be
  approximated through unrelated one-candidate normalizations.
- Existing holdings consume investable capital and are not force-rebalanced.
- The high-level portfolio-plan API must calculate strategy signals, RS20, ATR14,
  and sector facts in the backend from stored data as of an explicit date.
- Domain orchestration must use existing service/repository boundaries and must
  not call external providers directly.
- Sprint 10B is not Sprint 11. No UI/frontend implementation is authorized.
- Sprint 10B completed without parameter retuning. Candidate-group weights
  normalized exactly and every audited entry respected risk, reserve, position,
  sector, whole-share, and cash constraints.
- Volatility-normalized sizing improved on ATR-risk V1 consistently for Micho,
  but not for EMA: EMA results were mixed across development and validation.
- Policy classifications are strategy-specific: equal-slot is a promising
  research baseline for EMA and Micho; ATR-risk remains research-only for both;
  volatility-normalized is research-only for EMA and a promising research
  baseline for Micho. None is production-ready.
- The high-level `/api/v1/portfolio/plan` contract passes the UI-readiness gate:
  stored-data strategy evaluation, RS20, ATR14, sectors, risk constraints, and
  reason codes are backend-owned. Broker state and authenticated persistence
  remain future backend adapters.

## 0.7 Sprint 11 UI Decisions

- The frontend is presentation-only. EMA/SMA rules, strategy signals, RS20,
  ATR14, stop/risk calculations, sizing, constraints, and portfolio decisions
  remain exclusively backend-owned.
- The normal UI workflow consumes high-level `POST /api/v1/portfolio/plan`;
  users never supply ATR, RS20, sector, risk distance, or strategy signals.
- Required routes are Dashboard, Portfolio Plan, and Settings/Research
  Configuration. Company detail and backtest explorer are deferred unless the
  existing API supports them without expanding scope.
- React, strict TypeScript, Vite, React Router, TanStack Query, and project-owned
  styling form the UI stack. Server requests go through one typed API layer.
- Research policy classifications are strategy-specific and none may be labeled
  production-ready. UI language must describe advisory research decisions, not
  live trading or submitted orders.
- Current portfolio input remains client-supplied because no broker sync or
  authenticated persistence exists. Local form state is not a live account.
- Small backend presentation-contract additions and configurable local CORS are
  allowed; backend research/strategy architecture must not be redesigned.
- Sprint 11 completed with Dashboard, Portfolio Plan, and Research Settings;
  frontend lint, 17 tests, production build, 142 backend tests, and the real
  stored-data browser smoke all passed.
- The backend response now owns display-ready current-position values and marks
  whether existing-position modeled risk is complete. Missing frozen entry-risk
  facts are disclosed, never fabricated.
- The largest remaining product/backend limitation is manually supplied current
  portfolio state: there is no broker/account adapter, authenticated persistence,
  or original entry-risk recovery for manually entered holdings.

## 0.8 Sprint 11B Hardening Decisions

- Sprint 11B continues Sprint 11 before commit/merge and does not authorize
  Sprint 12 or frontend financial-domain calculations.
- The exact user-provided `frontend/src/assets/images/alphapilot-logo.png` is the
  primary application brand asset and must remain byte-for-byte unchanged.
- Approved BUY results preserve backend priority order. Full universe evaluation
  defaults to visibly disclosed ticker A-Z order, which is not recommendation
  priority.
- The high-level plan endpoint remains the single-stock evaluation engine; React
  does not compute strategy, RS20, ATR, ranking, sizing, or decisions.
- A successful plan records its input snapshot. Any later plan-affecting input
  change makes the visible result explicitly stale until regeneration succeeds.
- Research-admin operations are gated by `ADMIN_TOOLS_ENABLED`, disabled by
  default. This is a feature gate, not authentication or authorization.
- Sync endpoints reuse existing provider/service/repository abstractions,
  prevent duplicate full-sync jobs within the process, and return safe typed
  status without credentials or raw tracebacks.
- Existing services can sync stored companies but cannot reliably discover
  arbitrary custom-ticker metadata. Unknown tickers therefore remain explicit
  `COMPANY_NOT_FOUND`; Sprint 11B must not fabricate company records.
- Full-sync job state is process-local research infrastructure, not a durable or
  distributed production queue.
- Existing-position reference price remains required because the portfolio-state
  contract needs it before orchestration and automatic repricing would not
  recover frozen entry-risk facts.
- Sprint 11B completed locally with the official PNG unchanged, all frontend and
  backend quality gates green, and a successful real stored-data browser smoke.
- Approved BUYs are the default opportunity view when present; all evaluated
  stocks remain searchable and paginated in explicitly disclosed ticker A-Z
  order.
- The research-admin workflow is ready for deliberately enabled local research
  use, but its feature flag is not an authentication boundary and full-sync job
  state remains process-local.

## 0.9 Sprint 11C Decisions

- Research portfolio actions mutate browser draft state only and never send a
  broker order. One exact backend-approved BUY or SELL may be applied from a
  clean plan; the plan then becomes stale and no second action is allowed before
  regeneration.
- React must use backend-provided shares and cash impact. It must not reproduce
  allocation, slippage, cost, sizing, stop, or risk formulas.
- Approved Sells means `decision == SELL`; Sell Signals means `signal == SELL`.
  These concepts may overlap but must never be conflated.
- Custom research tracking is independent of current S&P 500 membership. Use an
  explicit persisted tracking flag; deactivation preserves Company, candles,
  membership, and historical referential integrity.
- Metadata discovery uses a configured provider abstraction. Unknown/invalid
  symbols are rejected before persistence; optional sector/industry may remain
  unavailable and are never fabricated.
- `ALPACA_DATA_FEED` must be explicitly validated as `iex` or `sip`. Historical
  requests use exactly that feed and never silently fall back. Feed entitlement
  failure is safe, typed, and identifies benchmark stage when SPY fails.
- DailyCandle rows do not currently retain per-row Alpaca feed provenance. This
  limitation is disclosed; each admin job records its configured provider/feed.
- S&P universe refresh and market-candle refresh are separate job operations.
  Full sync may compose them. Process-local job state remains a documented
  research limitation.
- The 2×ATR14 stop distance and derived stop reference are research sizing
  proxies only, not executable or validated stop-loss instructions.
- Sprint 11C completed locally with all backend/frontend gates green. Real local
  validation used configured Alpaca IEX successfully; an explicit SIP request
  returned `MARKET_DATA_FEED_NOT_AUTHORIZED` and did not retry another feed.
- Real SBET acceptance created one custom-tracked Company outside S&P membership,
  synchronized 276 stored candles, supported EMA and Micho evaluation, and
  preserved all candles through deactivate/reactivate. SBET remains actively
  custom tracked after the acceptance cycle.
- Sprint 12 remains not started pending user review and Git publication of the
  combined Sprint 11/11B/11C working tree.

## 0.10 Sprint 11D Decisions

- Sprint 11D overrides Sprint 11C's one-action-then-stale rule: approved actions
  from one active plan may be selected in any user-chosen order while each
  remains valid. Candidate rank is advisory recommendation priority; it is not
  an execution dependency. Manual/configuration changes still invalidate the
  plan.
- Freshness is defined against the newest stored SPY trading session on or
  before the requested date, never raw calendar-day age. A stock must have a
  candle on that exact benchmark session to be eligible.
- Stale/no-data tickers remain excluded; missing sessions are never fabricated,
  forward-filled, or bypassed.
- Plan readiness and coverage counts are backend-owned and must distinguish a
  fully evaluated zero-opportunity result from partial/all-unusable data.
- Portfolio allocation values/weights come from a typed backend draft summary;
  React owns only SVG geometry and presentation.
- Each same-plan action is backend-previewed and revalidated against current
  draft cash, positions, duplicate holdings, whole shares, max position count,
  max position/sector weight, and policy-applicable reserve/modeled-risk limits.
  Duplicate application is rejected deterministically.
- A requested BUY quantity equal to the recommendation is a `SAME_PLAN_ACTION`;
  another whole-share quantity is a `USER_QUANTITY_OVERRIDE` and makes the draft
  `DEVIATED_FROM_PLAN` without hiding remaining recommendations. No quantity is
  silently clamped.
- Strategy exit guidance is backend-owned and exposes the actual frozen EMA20
  HYBRID 2% or Micho close-below-SMA150 semantics as of stored daily data. No
  fixed take-profit target exists. The 2×ATR14 reference is research-only, not
  an active stop.
- Equal-slot's sizing formula remains unchanged. Risk-only metrics are not
  represented as zero risk in the UI, and sector before/after uses actual
  current/proposed sector market value.
- Manual partial/full sales are backend-owned bookkeeping using a stored
  DailyCandle close/date or explicit user override. They never submit a broker
  order and always invalidate existing analysis.
- Admin progress uses meaningful totals/stages only; no time-based fake
  percentage is allowed. Job state remains process-local.
- Sprint 11D changes no EMA, Micho, RS20, ATR, sizing, ranking, risk, backtest,
  or T+1 execution rule and does not start Sprint 12.
- Single-stock evaluation identity is an explicit invariant: normalized requested
  ticker must equal the backend evaluation target and the rendered candidate
  ticker. Held positions may remain in the plan for portfolio context, but array
  order never selects the evaluation target. A missing/mismatched target renders
  a safe error, never another company. Candidate status includes authoritative
  Company ID where a Company exists, and only the latest active evaluation
  request may update the displayed snapshot.

## 0.1 Sprint 7 Portfolio Baseline Decisions

- One shared cash balance funds all tickers.
- Long-only, whole shares, no leverage, and cash may not become negative.
- Maximum concurrent positions and transaction assumptions are configurable.
- Signal T executes at that ticker's next available trading-day OPEN.
- Executable exits run before entries so released cash is available that day.
- Open positions are marked to market at the end; they are not force-liquidated.
- Existing Scanner output has no ranking score. Sprint 7 therefore uses a pluggable stable ticker-order baseline selector, explicitly not alpha.
- Baseline sizing uses fixed equal slots based on current equity divided by configured maximum positions, capped by available cash. Existing positions are not rebalanced.
- Baseline results are engine validation only and must disclose current-constituent survivorship bias, benchmark alignment limitations, and transaction-cost assumptions.

## 0.2 Sprint 7 Validation Outcome

Sprint 7's shared-cash engine, tests, reports, and two baseline runs completed successfully.

Both baselines used stable ticker-ascending selection, 10 fixed equal slots, zero commission, and zero slippage. They prove shared capital, deterministic execution, accounting, valuation, metrics, and reporting work end to end. They do not establish a production ranking or strategy winner.

Do not use the fact that Micho BOTH returned more than EMA HYBRID 2% in these particular runs to declare Micho superior. Alphabetical slot priority materially affects which signals receive capital.

Open positions remain open and are marked to market at the final close. They are not included as completed trades or force-liquidated.

## 1. Package / Environment

Use uv.

Primary validation command:

.\run_checks.ps1

Do not introduce unrelated pip-based workflows.

## 2. Git Ownership

The user controls Git publishing.

Codex must NOT:
- git push
- force push
- push tags
- merge to main
- open/merge remote PRs

Codex should not automatically commit.

At the end of work Codex should provide:
- git status
- changed files
- recommended commit message

The user decides when to commit and push.

## 3. Backtesting Execution

Signal produced on trading day T executes at the next trading day's OPEN.

No lookahead is allowed.

Long-only baseline.

BUY while already long:
ignored.

SELL while flat:
ignored.

Final-day signal:
cannot execute.

## 4. Survivorship Bias

Historical S&P 500 experiments currently use the current active constituent list.

Therefore results have survivorship bias.

This must always be disclosed.

## 5. EMA20 vs EMA50

Do not declare either universally superior.

Observed behavior:

EMA20:
- more defensive
- lower drawdown/giveback in many cases

EMA50:
- preserves strong trends
- benefits some large winners

## 6. HYBRID Exit

HYBRID exists to combine EMA20 protection with EMA50 trend persistence.

Development threshold experiment:
1%, 2%, 3%, 4%, 5%.

Selected:
2%

Selection was made on:
2021-08-20 -> 2024-12-31

The threshold is frozen.

Do not retune it on validation data.

## 7. HYBRID Production Status

HYBRID 2% passed later validation as a balanced candidate.

It is NOT yet automatically the Scanner default.

Final strategy/default choice should wait for portfolio-level evidence.

## 8. Micho V1

Micho 150 is currently a mechanical deterministic baseline.

Current core rules:
- SMA150
- trend filter
- breakout
- bounce
- close-below-SMA150 exit

Do not describe it as an exact implementation of discretionary/proprietary rules.

Do not add during current Sprint 6 experiment:
- news
- AI
- volume
- alternative stops
- alternative SMA periods
- new chart patterns

## 9. Do Not Optimize Micho From Validation Data

Micho performed materially better on the full five-year period than on the later validation period.

This suggests possible regime sensitivity.

Do not immediately tune parameters to make validation look better.

First isolate strategy components.

## 10. Executed Entry Reason Analytics

Raw BUY signals are not the same as executed entries.

Completed trade diagnostics must be used when evaluating:
- BREAKOUT
- BOUNCE

This is because BUY signals can occur while already holding a position.

## 11. BOTH-Mode Breakout vs Bounce Was Not Sufficient

Initial completed-trade diagnostics showed Breakout generally stronger than Bounce.

However:
Breakout often opens the position before later Bounce signals can act.

Therefore Bounce had fewer independent opportunities.

Decision:

Do NOT remove Bounce based solely on BOTH-mode diagnostics.

## 12. MichoEntryMode

Implemented:
- both
- breakout-only
- bounce-only

Default:
both

Reason:

Allow controlled isolation of entry logic without changing original V1 behavior.

## 13. Category Isolation

In bounce-only:

a day already classified as Breakout must not fall through and be reclassified as Bounce.

Reason:

The experiment must isolate existing categories rather than invent a different strategy.

## 14. Separate Report Files

Each Micho entry mode must produce a unique report name.

Examples:
- strategy_universe_micho_150_both_...
- strategy_universe_micho_150_breakout_only_...
- strategy_universe_micho_150_bounce_only_...

Experiments must never silently overwrite each other.

## 15. Smoke Test Result

10-stock validation smoke passed for:
- both
- breakout-only
- bounce-only

Preliminary result:

BREAKOUT_ONLY looked strongest.

BOUNCE_ONLY looked weakest.

But:

No strategy decision may be made from the 10-stock smoke.

A full-universe experiment is required.

## 16. Current Final Sprint 6 Experiment

Run:
- BOTH
- BREAKOUT_ONLY
- BOUNCE_ONLY

on the full current S&P 500 universe.

Validation period:
2025-01-01 -> 2026-08-20

Only entry mode may change.

Keep all other assumptions consistent.

## 17. Micho V2 Is Not Yet Approved

Do not change permanent Micho rules until the A/B/C full-universe results have been analyzed.

Potential future V2 work may be justified by the data, but must be a separate experiment.

## 18. Sprint 6 Must Produce a Completion Report

At the end of Sprint 6 create:

docs/SPRINT6_COMPLETION_REPORT.md

The report must contain:
- work completed
- files changed
- tests/checks
- full A/B/C results
- comparison
- final conclusion
- limitations
- Git state
- recommended commit message
- recommendation for Sprint 7

The report must be understandable without access to the Codex conversation.

## 19. Codex Stops After Sprint 6

Codex must NOT begin Sprint 7 automatically.

After producing:

docs/SPRINT6_COMPLETION_REPORT.md

stop.

The user will review the report with ChatGPT.

Sprint 7 begins only after that review.

## 20. Likely Sprint 7 Direction

Current likely next major architectural step:

Multi-Stock Portfolio Backtesting

Possible flow:

Scanner
→ Ranking
→ Candidate Selection
→ Position Sizing
→ Simultaneous Positions
→ Portfolio Constraints
→ Portfolio Equity
→ Portfolio Drawdown
→ Benchmark

This is only a recommendation.

Do not implement it during Sprint 6.

## 21. News Intelligence Is Future Work

Planned future layer:

Technical Strategy
+
News Collection
+
AI News Analysis
+
Risk Layer
→ Decision

Keep it separate from current technical validation.

## 22. Portfolio Manager Is Future Work

Long-term AlphaPilot should eventually create an actionable portfolio report including:
- capital allocation
- cash allocation
- stocks to buy
- stocks to sell
- quantities
- risk/stop rules
- position management
- rationale

This comes after strategy and portfolio validation.
