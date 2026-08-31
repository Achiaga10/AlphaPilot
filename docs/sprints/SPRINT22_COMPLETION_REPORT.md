# Sprint 22 Completion Report — Intraday Market Intelligence

## Outcome and architecture

Sprint 22 is complete locally on `feature/intraday-market-intelligence`. AlphaPilot now
refreshes ephemeral current-session intelligence for open portfolio positions, displays
completed and provisional facts separately, and answers exact live questions
deterministically. Completed-session decisions remain authoritative. No strategy,
research protocol, portfolio, broker, or completed candle changed. Sprint 23 was not
started.

Flow:

`open positions -> batched Alpaca snapshots -> freshness -> completed histories -> provisional indicators -> frozen-strategy projection -> ephemeral cache -> typed API -> Dashboard/Copilot`

`LiveQuoteProvider` is replaceable. `AlpacaProvider` implements one
`/v2/stocks/snapshots` call for only the distinct open-position tickers.
`LivePortfolioService` bulk-loads companies, latest completed candles, histories, and
stored monitoring state. It never fetches full-universe live quotes.

## Provider, freshness, and live contract

The existing Alpaca provider was reused. Snapshots supply latest trade, current daily
bar, previous daily bar, and provider timestamp. IEX is explicitly labeled
`Real-time IEX-only coverage; not consolidated SIP`; SIP remains subject to entitlement.

The provider timestamp is preserved separately from backend `received_at`. Freshness is:

- outside 09:30–16:00 America/New_York: `OUTSIDE_REGULAR_SESSION`;
- `delayed_sip`: `DELAYED`;
- quote age above `LIVE_QUOTE_MAX_AGE_SECONDS` (default 120): `STALE`;
- otherwise: `LIVE`;
- missing snapshots: explicit per-ticker failure/unavailable state.

Portfolio readiness is `LIVE`, `DELAYED`, `STALE`, `PARTIAL`, `UNAVAILABLE`, or
`OUTSIDE_REGULAR_SESSION`; stale data cannot masquerade as live.

`LiveMarketSnapshot` contains ticker/company, session date, last price, session OHLC,
volume, previous completed close, provider/receipt timestamps, provider, feed, freshness,
age, and coverage note. Position intelligence adds completed/provisional indicators,
distances, stored confirmed monitoring, provisional monitoring/projection, loss-control
facts, and explicit official/confirmed flags.

No migration was created because live market state is ephemeral and must not contaminate
completed/research data. The latest brief is process-local cache only. Refresh does not
write `DailyCandle`, portfolio revision, trade events, ingestion data, or Paper Validation.

## API and UI refresh

Added `POST /api/v1/portfolio/{portfolio_id}/live-refresh`. It returns typed
`PortfolioLiveBrief` after one batch quote call and bulk database reads. The Dashboard
button is **Refresh Market & Brief**. It refreshes live state and the completed Daily
Brief; it does not sync completed market data, fetch the S&P 500, mutate financial state,
or submit orders. Partial live failures leave the completed brief available.

The Live Market Monitor shows quote time/freshness, live price, completed close, session
change, completed/provisional indicators, distances, live attention, provisional
projection, and confirmed completed state.

## Indicators and strategy semantics

Completed EMA20, EMA50, SMA150, and ATR14 use stored completed candles only.
Provisional EMA20/EMA50/SMA150 append one transient current-session close equal to last
price. Provisional ATR14 appends transient current OHLC and reuses the existing ATR
calculator. Nothing transient is persisted.

EMA below provisional EMA20 is `ATTENTION`; below provisional EMA50 is
`CRITICAL_ATTENTION`. Micho below provisional SMA150 is `CRITICAL_ATTENTION`.
Stale/missing live data is `UNAVAILABLE`.

The frozen evaluator runs over the transient bar for **If session closed now**. The result
is always `projection_is_official=false` and shown as “Provisional / not official.” Stored
completed monitoring is separate. EMA20/EMA50 and Micho SMA150 intraday breaches never
become confirmed SELL under current profiles. Micho's completed-close SMA150 trigger is
unchanged. `SELL_REQUIRED` is available for a future explicitly approved intraday policy,
but no current profile emits it.

## Deterministic Copilot and Ollama boundary

New deterministic intents cover indicator values, live price/range, status/distance, and
strategy projection. EMA20, EMA50, SMA150, ATR14, current price, high/low, distance, and
“if closed now” use cached typed facts and never call an LLM. Ticker-specific current
price resolves live; established “my current price” completed-close behavior remains
compatible. Generic indicator definitions remain glossary answers.

Generative explanations are independently controlled by
`AI_GENERATIVE_EXPLANATIONS_ENABLED`. When disabled, open-ended explanation returns
`GENERATIVE_EXPLANATION_UNAVAILABLE`, while deterministic AlphaPilot remains functional.
Copilot status does not ping Ollama in this mode. Ollama is not on the operational
critical path.

## Performance and real acceptance

Acceptance ran 2026-08-31 during the U.S. session against configured Alpaca IEX and the
real local portfolio:

- 10 open tickers requested; 10 succeeded; 0 failed;
- one batched provider call; elapsed time 1.357 seconds;
- 9 `LIVE`; ERIE `STALE` due to its older IEX trade timestamp;
- overall readiness `STALE`, correctly reflecting returned freshness;
- provider timestamps preserved; every projection non-official; no fabricated SELL.

Real EMA positions displayed live price, completed/provisional EMA20 and EMA50,
distances, live status, projected state, and confirmed state. The real FastAPI endpoint
returned HTTP 200.

With `AI_COPILOT_ENABLED=true`, `AI_GENERATIVE_EXPLANATIONS_ENABLED=false`, and Ollama
not started, an exact live EMA20 API query returned HTTP 200,
`LIVE_POSITION_STATUS`, provider `alphapilot`, result `ANSWERED`. Unit acceptance used a
provider whose `available` and `generate` deliberately raise, proving deterministic paths
do not touch it. Open-ended generation returned the typed unavailable result.

Headless Edge exercised real FastAPI + Vite: 10 live cards rendered, provisional and
confirmed states were separate, and unified Copilot answered provisional EMA20 with
Ollama off. Browser acceptance: **PASS**.

## Tests and gates

Focused backend:

```powershell
$env:DEBUG='false'
uv run pytest tests/portfolio/test_live_portfolio.py tests/portfolio/test_live_copilot.py tests/market/providers/test_alpaca.py -q
```

Result: **24 passed**. Coverage includes batched parsing/timestamps, open-position scope,
completed/provisional formulas, no-lookahead transient calculations, fresh/stale/partial
states, no persistence/mutation, typed API serialization, provisional-not-confirmed SELL,
deterministic Copilot, and generation-disabled behavior. Copilot compatibility: **42
passed**.

Final backend:

```powershell
cd backend
$env:DEBUG='false'
.\run_checks.ps1
```

Ruff/format **PASS**; mypy **PASS (176 source files)**; pytest **376 passed**; overall
**PASS**.

Frontend:

```powershell
npm run lint
npm test -- --run
npm test -- --run --maxWorkers=1
npm run build
```

Lint/build passed; Vite bundled 106 modules. Parallel workers repeatedly caused a
timing cascade in three `AppLayout` tests even though that file passed 9/9 alone. The
Vitest configuration now uses one worker for a deterministic Windows gate; the required
`npm test -- --run` command then passed **16 files / 78 tests** without weakening tests or
raising timeouts. Dashboard focused tests passed 7/7.

## Files

Created:

- `backend/src/alphapilot/market/live.py`
- `backend/src/alphapilot/schemas/live_portfolio.py`
- `backend/src/alphapilot/services/live_portfolio.py`
- `backend/tests/portfolio/test_live_copilot.py`
- `backend/tests/portfolio/test_live_portfolio.py`
- `docs/sprints/SPRINT22_PLAN.md`
- `docs/sprints/SPRINT22_COMPLETION_REPORT.md`

Modified:

- `AGENTS.md`
- `backend/src/alphapilot/api/routes/copilot.py`
- `backend/src/alphapilot/api/routes/portfolio.py`
- `backend/src/alphapilot/copilot/context.py`
- `backend/src/alphapilot/copilot/direct_answer.py`
- `backend/src/alphapilot/copilot/intent.py`
- `backend/src/alphapilot/copilot/orchestrator.py`
- `backend/src/alphapilot/core/config.py`
- `backend/src/alphapilot/market/providers/alpaca.py`
- `backend/src/alphapilot/market/providers/base.py`
- `backend/tests/market/providers/test_alpaca.py`
- `docs/DECISIONS.md`, `docs/PROJECT_STATE.md`
- `frontend/src/api/portfolio.ts`
- `frontend/src/features/dashboard/DailyPortfolioManager.tsx`
- `frontend/src/hooks/usePortfolioApi.ts`
- `frontend/src/pages/DashboardPage.test.tsx`, `DashboardPage.tsx`
- `frontend/src/test/server.ts`
- `frontend/src/types/portfolio.ts`
- `frontend/vite.config.ts` (deterministic single-worker test gate)

## Final acceptance answers

1. User-commanded intraday refresh: **Yes**.
2. Endpoint: `POST /api/v1/portfolio/{portfolio_id}/live-refresh`.
3. Open positions only: **Yes**.
4. Entire S&P 500: **No**.
5. Overwrites `DailyCandle`: **No**.
6. Completed/live timestamps distinct: **Yes**.
7. Provider timestamp preserved: **Yes**.
8. Delayed/stale mistaken for real-time: **No**.
9–12. Completed/provisional EMA20 and EMA50: **All available**.
13–16. Deterministic EMA20/EMA50/SMA150/ATR14 questions: **Yes**.
17. Current price question: **Yes, after live refresh**.
18. Exact facts with Ollama off: **Yes**.
19. Below EMA20 automatically confirmed SELL: **No**.
20. Below EMA50 automatically confirmed SELL: **No** under frozen policy.
21. Projected SELL if closed now: **Yes**.
22. Clearly provisional/non-official: **Yes**.
23. Micho intraday SMA150 breach confirmed SELL: **No**.
24. Micho completed-close trigger unchanged: **Yes**.
25. Strategy parameter changed: **No**.
26. Research run: **No**.
27. Protective stop invented: **No**.
28. Future explicit policy can model `SELL_REQUIRED`: **Yes architecturally**.
29. Current profiles can fabricate it: **No**.
30. Refresh mutates portfolio: **No**.
31. Refresh submits broker order: **No**.
32. Refresh creates Paper Validation: **No**.
33. Refresh runs completed-market sync: **No**.
34. Generative AI optional: **Yes**.
35. Dashboard requires Ollama: **No**.
36. Exact facts require Ollama: **No**.
37. Open-ended generation disabled: typed unavailable result; deterministic product works.
38. Real refresh: **10/10, 9 live/1 stale, one batch**.
39. Real EMA acceptance: **PASS**.
40. Backend gate: **PASS — Ruff, format, mypy 176, pytest 376**.
41. Frontend gate: **PASS — lint, 16 files/78 tests, build**.
42. Browser acceptance: **PASS with real provider/backend and Ollama off**.
43. Refresh elapsed time: **1.357 seconds**.
44. Migration: **No; ephemeral state must remain separate**.
45. Git: uncommitted Sprint 22 changes on the feature branch; no publishing action.
46. Commit message: `feat: add intraday portfolio intelligence and deterministic live copilot facts`.

## Limitations and Git handoff

IEX is single-exchange coverage; quiet tickers can look stale despite consolidated
activity. Polling is user-commanded; there is no WebSocket/background stream. Cache is
process-local. Projection uses last trade as a hypothetical close and is not an official
candle or execution instruction. Current exits remain completed-session policies. No
broker state/order, protective stop, autonomous trading, news, TASE, or multi-currency was
added. AlphaPilot remains research/development software. Current-constituent historical
research retains survivorship bias, though Sprint 22 ran no historical research.

No commit, push, PR, merge, force-push, or tag was performed. Recommended commit message:

`feat: add intraday portfolio intelligence and deterministic live copilot facts`
