# AlphaPilot Sprint 11C Plan

## 1. Goal

Complete the combined Sprint 11 UI handoff by fixing the remaining manual-review
issues: clipped contextual help, ambiguous SELL categories, safe one-at-a-time
research portfolio actions, true non-S&P custom ticker tracking, discoverable
and separated data operations, explicit Alpaca feed entitlement behavior, and
complete decision-metric explanations. Sprint 12 is not started.

## 2. Preserved Boundaries and Non-goals

- Preserve EMA20 HYBRID 2%, Micho BOTH, RS20, ATR14, sizing, constraints,
  portfolio accounting, no-lookahead, and T+1 backtest semantics.
- Preserve the lower-level and high-level portfolio APIs compatibly.
- Do not add broker execution, live orders, stop-loss execution, authentication,
  account persistence, AI/ML, new strategy research, or a UI redesign.
- Do not hard-delete Company or DailyCandle data.
- Do not silently mix Alpaca feeds or expose credentials.

## 3. Tooltip Architecture

Replace native `details` positioning with a small React portal popover mounted
under `document.body`. A keyboard-operable button-role trigger owns `aria-expanded` and
`aria-describedby`. The popover is positioned from the trigger rectangle,
clamped to the viewport, rendered above overflow/stacking contexts, and supports
hover, focus, click/tap, Escape, outside click, desktop, and narrow viewports.
The real-browser smoke will compare trigger/popover/card/viewport bounds.

## 4. Decision Categories and Apply Workflow

Categories are Approved Buys (`decision=BUY`), Approved Sells
(`decision=SELL`), Sell Signals (`signal=SELL`), Skipped, All Decisions, and All
Evaluated. Approved BUY order retains backend priority; All Evaluated remains
explicit A-Z browsing.

Backend decision responses will add explicit workflow fields for exact estimated
BUY outlay, modeled stop reference, and cash after applying that one advisory
decision to the submitted research state. SELL retains exact estimated proceeds.
React will use these values verbatim. After confirmation, one clean-plan action
updates cash and a position, records a user-visible message, makes the plan
stale, and blocks every further action until regeneration. No Apply All exists.

## 5. Custom Tracking Model

Add the smallest explicit database change: `Company.is_custom_tracked`, false by
default. This flag is independent of `Company.is_active` and
`IndexConstituent.is_active`. Deactivation changes only custom tracking; it does
not delete Company/candles or modify S&P membership. Re-adding a deactivated
company reactivates the same row. A current S&P ticker is never duplicated or
marked custom by the Add flow.

## 6. Metadata and Custom Onboarding

Introduce a small `CompanyMetadataProvider` boundary and use the already-
configured Finnhub company-profile endpoint. Required ticker/name/exchange must
be valid; optional sector/industry may remain null and display as unavailable.
The service discovers metadata before persistence, creates/updates through
CompanyService, marks non-S&P coverage custom, then syncs a bounded 400-day
history sufficient for current strategy orchestration. Candle failure is a
typed partial onboarding result; metadata failure leaves no garbage row.

`SBET` is only the real acceptance symbol and will never be special-cased.
Explicit portfolio scopes accept any stored company; blank scope remains the
current active S&P 500 universe.

## 7. Alpaca Feed Hardening

Add validated `ALPACA_DATA_FEED` with allowed values `iex` and `sip`, defaulting
to `iex` in example/local research guidance. `AlpacaProvider` sends exactly the
configured value. HTTP 403 becomes a typed `MARKET_DATA_FEED_NOT_AUTHORIZED`
failure with provider/feed and safe copy. There is no SIP-to-IEX retry.

If mandatory SPY synchronization fails, the admin job fails with operation,
stage `benchmark`, ticker `SPY`, provider `Alpaca`, configured feed, code, and
safe reason. DailyCandle has no per-row feed field; job metadata/logging provides
the current provenance boundary and the database limitation remains explicit.

## 8. Admin Operations and Job Model

Data Management navigation remains visible even when disabled and displays a
Locked badge plus non-secret enable/restart guidance. All writes still return
403 unless `ADMIN_TOOLS_ENABLED=true`.

Typed job operations are `UNIVERSE_SYNC`, `MARKET_CANDLES_SYNC`, `TICKER_SYNC`,
and `FULL_SYNC`. Universe sync refreshes Wikipedia constituent details,
membership, and Company metadata without candles and reports requested/added/
updated/unchanged/removed/failed. Candle sync targets mandatory SPY, active S&P
members, and active custom tracked tickers through Alpaca bulk services. Full
sync composes universe then candles. Conflicting expensive jobs are prevented;
state remains process-local.

## 9. Freshness and Explainability

Admin summary adds active custom count, last universe/candle success, active
provider/feed, tracked freshness, and latest job. Dashboard receives a compact
read-only stored-data health view. Decision Details uses one centralized glossary
for every rendered signal/rank/price/ATR/allocation/risk/sector/proceeds/reason
datum. The modeled stop reference is labeled research-only and never “Stop
Loss.”

## 10. Testing and Validation

Focused backend tests cover feed propagation/validation/403 safety, mandatory
SPY failure metadata, custom onboarding/reactivation/deactivation/membership,
split operations/targets, exact decision workflow values, stop reference,
compatibility, and no-lookahead. Frontend tests cover popover semantics,
categories, apply safety, manual positions, admin discoverability and split
jobs, custom workflows, freshness, glossary, and mobile-safe structure.

Final gates:

```powershell
cd frontend
npm run lint
npm run test
npm run build

cd ../backend
$env:DEBUG='false'
.\run_checks.ps1
```

Real validation uses a small configured-feed SPY/ticker request and the SBET
Add & Sync/evaluate flow if provider access permits. It never launches a full
500-stock sync merely for UI validation and never prints credentials.

## 11. Completion Criteria

Sprint 11C completes when the portal tooltip is visibly unclipped at desktop and
mobile; decision semantics/actions are exact and sequentially safe; SBET-like
non-S&P onboarding works without special cases; S&P and candle jobs are
independent; feed selection and 403 behavior are explicit with no fallback;
decision/stop information is fully explained; all focused/full/browser gates
pass; the completion report records any real-provider limitation honestly; all
work remains local; and Sprint 12 is not started.
