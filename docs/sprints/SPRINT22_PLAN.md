# Sprint 22 Plan — Intraday Market Intelligence

## Goal

Add a read-only live market monitor for open research positions and deterministic
Copilot answers for exact price/indicator/strategy facts while preserving completed-session
strategy authority. Sprint 23 is out of scope.

## Existing provider capability

AlphaPilot's configured operational market-data provider is Alpaca. Its existing adapter
supports authenticated batched daily bars. Sprint 22 will add a separate batched stock
snapshot read using Alpaca's latest trade, current daily bar, and previous daily bar.
The configured `iex` feed is real-time IEX-only coverage, not consolidated SIP; `sip`
depends on account entitlement. Finnhub and Polygon do not currently provide a complete
implemented live snapshot path in this repository. No silent provider switch is allowed.

## Completed versus live constitution

- `DailyCandle` remains completed-session/research data only.
- Live snapshots use a separate immutable `LiveMarketSnapshot` contract and are never
  persisted as candles or candle versions.
- Completed monitoring and stored strategy facts remain authoritative.
- Live indicators and “if the session closed now” results are provisional and explicitly
  non-official.
- No portfolio, trade-event, Paper Validation, sync, or broker mutation occurs.

## Live data contract and freshness

Each snapshot carries ticker/company identity, session date, last trade, session OHLCV,
previous completed close, provider timestamp, receipt timestamp, provider/feed, age,
freshness, and session classification. The provider timestamp is primary. Default maximum
quote age is 120 seconds and is configurable as `LIVE_QUOTE_MAX_AGE_SECONDS`.

Readiness values are `LIVE`, `DELAYED`, `STALE`, `OUTSIDE_REGULAR_SESSION`, `PARTIAL`,
and `UNAVAILABLE`. IEX is labeled `LIVE_IEX_LIMITED_COVERAGE`; it is never called
consolidated real-time. Provider errors are per ticker and do not erase successful quotes.
Regular-session V1 is 09:30–16:00 America/New_York, with conservative wording because
AlphaPilot has no exchange-calendar/authoritative market-status feed.

## Indicators and projection

- Completed EMA20/EMA50 use the existing SMA-seeded EMA implementation.
- Provisional EMA appends the live price as a provisional current-session close and uses
  that same implementation.
- Completed/provisional SMA150 use the existing SMA function; provisional SMA150 appends
  the live price.
- Completed ATR14 uses AlphaPilot's existing true-range/ATR convention. Provisional ATR14
  uses current-session high/low and the previous completed close; it is unavailable when
  those provider facts are absent.
- A non-persistent candle-shaped projection input is appended only in memory and passed to
  the existing frozen strategy evaluator. No second EMA/Micho strategy implementation is
  created.

## Live monitoring states

`NO_ACTION`, `ATTENTION`, `CRITICAL_ATTENTION`, `SELL_REQUIRED`, and `UNAVAILABLE` are
separate from official completed monitoring. Current EMA/Micho profiles have no approved
intraday trigger, so they cannot emit `SELL_REQUIRED`. EMA below provisional EMA20 is
attention; below provisional EMA50 is critical attention. Micho below provisional SMA150
is critical attention. A projected SELL remains provisional until a completed session.

## Refresh workflow and API

`POST /api/v1/portfolio/{portfolio_id}/live-refresh` loads only open positions, batch
fetches Alpaca snapshots, calculates all facts server-side, and returns a typed
`PortfolioLiveBrief`. It does not scan the S&P 500. A short-lived in-process cache supports
deterministic Copilot questions after explicit refresh; it is operational state, not
research persistence.

The Dashboard button becomes **Refresh Market & Brief**: call live refresh, retain prior
live values while loading, refetch the completed core, and leave the independent expensive
opportunity query alone.

## Copilot and optional generative AI

Deterministic intents cover completed/live EMA20, EMA50, SMA150, ATR14, live price,
high/low, distances, live status, and projected-close state. They use cached backend facts
and never call an LLM. Ticker resolution remains backend-owned. Generative explanations
are controlled independently by `AI_GENERATIVE_EXPLANATIONS_ENABLED`; when disabled,
only open-ended prose returns `GENERATIVE_EXPLANATION_UNAVAILABLE`. Operational product
features remain available and Ollama is not pinged on startup/dashboard/live refresh.

## Frontend

Extend, do not replace, the Daily Portfolio Manager with a clearly separated Live Market
Monitor. Cards distinguish completed and provisional timestamps/indicators, live attention,
projected non-official SELL, and confirmed SELL. React performs no financial calculations.

## Testing

Focused backend tests cover provider parsing/batching/failures, timestamp/freshness,
no persistence/mutation/full-universe sync, exact Decimal indicators, EMA/Micho states,
projection safety, and deterministic Copilot with a provider that fails if called.
Frontend tests cover refresh behavior, retained completed content, partial/stale states,
completed/provisional labels, and confirmed-versus-projected SELL semantics.

Then run backend `run_checks.ps1`, frontend lint/Vitest/build, controlled browser smoke,
safe real-provider acceptance for current open positions, Ollama-off deterministic API
acceptance, and local timing. No fragile CI time assertion is added; practical target is
single-digit seconds for approximately ten positions.

## Expected files and migration decision

Expected changes are limited to live market domain/provider/service/schema/API files,
Copilot deterministic routing/context, Dashboard API/types/components/tests/styles, and
Sprint continuity documents. **No migration:** live market state is ephemeral and must not
contaminate completed/research data.

## Completion criteria

All exact facts work without Ollama; live refresh is open-position-only and read-only;
completed rules remain authoritative; provisional values are unmistakable; all gates and
acceptance checks pass; `SPRINT22_COMPLETION_REPORT.md` is complete; Sprint 23 is not begun.
