# Sprint 23 Plan — Forward Paper Analytics

## Goal

Turn manual Alpaca Paper Validation into immutable, backend-owned forward execution
evidence and descriptive analytics: AlphaPilot plan versus actual entry, actual exit,
outcome, excursions, and fixed post-exit observations. Forward Paper Evidence remains
separate from Historical Research and cannot promote, reject, or retune a strategy.

## Existing model audit

`PaperValidationRecord` currently stores an immutable aggregated manual entry and a
one-time full exit. Entry facts are ticker/company/position, actual quantity/fill/aware
timestamp/note, position provenance, strategy/profile/version, entry decision/reason,
recommendation day, planned quantity, and reference price. Exit facts are actual full
quantity/fill/aware timestamp/note plus sticky AlphaPilot exit day/reason and trigger
close when available. Service-derived facts are entry difference/bps, quantity
difference, entry/exit notional, gross P&L, and gross return.

Already authoritative and immutable: actual fills, quantities, timestamps, notes, and
fields copied into the record. Safely derivable: Decimal execution metrics and outcomes
from those stored facts. Not safely reconstructable for existing rows: historical live
quote/provisional indicators, complete indicator/loss-control snapshot, provider
freshness, source plan ID, or facts absent at record time. These remain unavailable.

Read-only local audit before implementation: 11 records, 10 OPEN and 1 CLOSED; all are
`ema20-pullback-v1` v1; planned price/quantity/profile are present. This audit did not
alter data.

## Scope and non-goals

In scope: versioned immutable entry/exit evidence, exact execution/outcome analytics,
open/closed detail, profile-version aggregates, evidence maturity, typed read APIs,
Portfolio UI, deterministic Copilot facts, legacy compatibility, and controlled
acceptance.

Out of scope: backtests, EMA Round 3, parameter/rule changes, profile promotion,
automatic re-entry, partial exits/tax lots, fees not actually recorded, broker API/account
sync/orders, news, TASE, multi-currency, LangChain, and LangGraph.

## Persistence and migration decision

Create one additive Alembic revision extending `paper_validation_records` with:

- `entry_evidence_schema_version` nullable integer;
- `entry_evidence` nullable versioned JSON object;
- `exit_evidence_schema_version` nullable integer;
- `exit_evidence` nullable versioned JSON object.

JSON is justified because evidence contains a typed snapshot whose strategy-specific
indicator fields vary, while an explicit schema version prevents ungoverned JSON.
Existing stable execution columns remain normalized. New records use schema v1. Legacy
rows retain null evidence and are exposed as `LEGACY` or `PARTIAL`; no migration backfill
fabricates facts. Service workflows write entry evidence once and exit evidence once.
No generic evidence update/delete endpoint is added.

## Entry evidence v1

Capture available identity, profile/version, immutable opening-event action identity,
portfolio revision at capture, decision/reason, selection policy, recommendation/completed
session, planned/reference price and quantity, sizing/readiness when authoritative,
sector, loss-control policy/boundary/trigger/broker-stop flag and strategy references,
completed close/EMA20/EMA50/SMA150/ATR14 and confirmed monitoring, plus optional cached
Sprint 22 live quote/provider timestamp/provider/feed/freshness, provisional indicators,
live status, and non-official projection. Missing optional facts are null, never a
recording blocker or fabricated value. A later live refresh or candle update cannot
rewrite this snapshot.

Source plan ID is captured only if supplied through an authoritative future linkage; the
current persisted position/open event does not contain it. The immutable opening
`ResearchTradeEvent.action_id` is used where available. No ticker/date matching invents a
link.

## Exit evidence v1

Atomically capture actual exit columns plus latest authoritative completed monitoring,
earliest stored confirmed sticky SELL session/reason/close, strategy reference and active
loss-control facts, completed session, and optional valid cached live/provisional state.
Entry evidence is untouched. A daily-close SELL has a session, not a fabricated intraday
signal timestamp. Calendar latency and completed-session counts are labeled by their
exact conventions.

## Exact formulas

All financial calculations use `Decimal` in the backend.

- BUY entry slippage/share = `actual_entry_fill - planned_entry_price`; positive is worse.
- entry slippage % = `(actual_entry_fill / planned_entry_price - 1) * 100`.
- adverse BUY slippage/share = the same signed value; negative means price improvement.
- quantity difference = `actual_quantity - planned_quantity`.
- quantity adherence % = `actual_quantity / planned_quantity * 100`; unavailable for
  null/non-positive planned quantity.
- planned notional = `planned_quantity * planned_entry_price`.
- actual entry notional = `actual_quantity * actual_entry_fill`.
- gross P&L = `(actual_exit_fill - actual_entry_fill) * actual_quantity` for a valid full
  exit.
- gross return % = `(actual_exit_fill / actual_entry_fill - 1) * 100`.
- net P&L is unavailable because actual fees are not captured; no 5-bps assumption.
- calendar days held = exit date minus entry date for CLOSED; current UTC date minus entry
  date for OPEN and explicitly mark-to-market.
- completed sessions held count unambiguous completed `DailyCandle` dates strictly after
  entry and strictly before exit for CLOSED (or through latest completed date for OPEN).
- signal-close comparison = `actual_exit_fill - confirmed_signal_close`, labeled
  `actual_exit_vs_signal_close`, never “exit slippage.”
- expectancy return = `(win_rate_fraction * average_winner_return) +
  (loss_rate_fraction * average_loser_return)`; breakevens contribute zero and rates use
  all closed consistent trades.

## MFE, MAE, and fixed post-exit observations

For a long CLOSED trade, exclude both entry-day and exit-day ambiguous OHLC. Use completed
operational `DailyCandle` sessions strictly after entry date and strictly before exit date:

- MFE % = `(maximum high / actual entry fill - 1) * 100`.
- MAE % = `(minimum low / actual entry fill - 1) * 100`.

No qualifying session means MFE/MAE are unavailable, not zero. OPEN trades include only
completed sessions after entry. No current incomplete-session OHLC or Sprint 22 live
snapshot is used. Missing coverage produces explicit unavailable/partial analytics. The
candle source is the completed operational stream; it is not a frozen
historical research dataset, and later provider corrections are a documented limitation.

Post-exit horizons are frozen before inspection at exactly 5, 10, and 20 completed
sessions after the exit date. For each complete horizon report close return from actual
exit, maximum close/high, whether exit fill was exceeded, and whether original entry fill
was revisited. Incomplete future coverage is `INCOMPLETE`, never false. Micho recovery is
descriptive only and creates no re-entry or rule change.

## Aggregation and evidence maturity

Group by exact `(strategy_profile_id, strategy_profile_version)`; missing profile is an
explicit group and versions never merge. OPEN records are excluded from realized win
rate, expectancy, return, and gross realized P&L.

Closed metrics: counts/wins/losses/breakeven, win rate, average/median return, average
winner/loser, gross total P&L, average calendar holding days, average entry adverse
slippage, quantity adherence, MFE/MAE with availability counts, and expectancy.

Frozen maturity thresholds by eligible closed-trade count:

- 0: `NO_DATA`
- 1–4: `VERY_LOW_SAMPLE`
- 5–19: `LOW_SAMPLE`
- 20–49: `DEVELOPING`
- 50+: `MEANINGFUL_SAMPLE`

These labels do not claim statistical significance or production readiness.

## API design

Add read-only endpoints under existing portfolio ownership:

- `GET /api/v1/portfolio/{portfolio_id}/paper-analytics`
- `GET /api/v1/portfolio/{portfolio_id}/paper-analytics/{validation_id}`

Summary supports optional profile, ticker, and OPEN/CLOSED filters. Typed responses expose
summary, strategy breakdown, open/closed trades, evidence quality, generated time, and
the explicit `FORWARD_PAPER_EVIDENCE` domain. Detail exposes immutable plan/entry/exit
snapshots, backend execution comparison, current OPEN state or CLOSED outcome, excursions,
and fixed observations. Unknown IDs return 404. Reads do not mutate or automatically
refresh live/provider data.

## UI design

Extend Portfolio/Paper Validation with **Forward Paper Analytics** rather than a generic
BI dashboard. Render Summary, Strategy Breakdown, Execution Quality, Open Paper Trades,
Closed Paper Trades, and drill-down plan/actual/entry evidence/current-or-outcome/post-exit
sections. Label Forward Paper Evidence separately from Historical Research. React formats
typed backend facts only; unavailable is never numeric zero and tiny samples remain
prominent.

## Copilot

Add deterministic Paper analytics intents/facts for counts, gross P&L, profile win rate,
actual/planned fill, slippage, adherence, holding period, maturity, post-exit observations,
and legacy missing evidence. These paths never call an LLM. Optional open-ended prose
receives server-computed metrics only and respects
`AI_GENERATIVE_EXPLANATIONS_ENABLED`; disabled generation cannot disable analytics.
Copilot never promotes/rejects a strategy from Paper data.

## Testing and acceptance

Cover the protocol's evidence capture/immutability/separation, exact Decimal metrics,
closed/open behavior, MFE/MAE, 5/10/20 observations, version-separated aggregation,
maturity, typed API/filter/error/legacy paths, deterministic Copilot with a provider that
raises, UI presentation, and Ollama-off behavior. Preserve all Sprint 22 and earlier tests.

Run focused backend/frontend tests, migration upgrade/downgrade on a verified safe test
target, `backend/run_checks.ps1`, frontend lint/test/build, controlled workflow and legacy
acceptance, real read-only aggregate/performance inspection, and controlled browser
acceptance. Never mutate existing real Paper history or call a broker.

## Expected files

Expected additions: one Alembic revision; Paper evidence/analytics domain, schema/service,
tests, frontend analytics components/tests, and this sprint's completion report. Expected
targeted modifications: Paper model/repository/service/routes/schemas, Copilot
intent/context/direct answers, frontend portfolio API/hooks/types/Position Intelligence or
Portfolio surface, test fixtures, and continuity docs.

## Completion criteria

Immutable versioned forward evidence is captured atomically; legacy remains honest;
analytics formulas and maturity are backend-owned; historical research stays separate;
Paper workflows never mutate ResearchPortfolio or call a broker; API/UI/Copilot work with
Ollama off; migrations and all gates pass; controlled/browser acceptance passes; and
`docs/sprints/SPRINT23_COMPLETION_REPORT.md` records the full handoff. Stop before Sprint
24 and leave Git publishing to the user.
