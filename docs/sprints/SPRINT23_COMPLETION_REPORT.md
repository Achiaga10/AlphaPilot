# Sprint 23 Completion Report — Forward Paper Analytics

## Outcome

Sprint 23 is complete locally. AlphaPilot now preserves schema-versioned Forward Paper
Evidence at manual entry and exit, calculates execution/outcome analytics in the backend,
exposes typed read-only APIs, presents the evidence separately from Historical Research,
and answers exact Paper questions deterministically without Ollama. No research rule,
Strategy Profile, ResearchPortfolio accounting, broker state, or Paper order was changed.

## Architecture and existing-model audit

The pre-change read-only audit found 11 Paper records: 10 OPEN, 1 CLOSED, all
`ema20-pullback-v1` v1. Planned price/quantity/profile were present, but the records
predated versioned context snapshots. They remain readable as `LEGACY`; nothing was
backfilled or inferred from current data.

`PaperValidationRecord` remains separate from `ResearchPortfolio`. Migration
`e23f1a2b3c4d` adds nullable entry/exit evidence JSON plus schema-version columns. New
snapshots use schema v1. A PostgreSQL trigger permits the initial entry and exit snapshot
but rejects rewriting either once present. Legacy rows remain null. Paper entry/exit does
not change portfolio cash, positions, revision, ResearchTradeEvents, market sync, or any
broker account.

Entry evidence captures identity, exact profile ID/version, authoritative opening action
ID when available, plan facts, loss-control facts, latest completed state/indicators, and
optional valid cached live/provisional facts with provider timestamp/feed/freshness. It
also preserves actual manual quantity, fill, timestamp, and source. Source plan ID,
sizing/readiness, sector, or live facts remain null when no authoritative linkage exists.
Exit evidence independently captures the same as-of context plus exact actual full-exit
facts. Later candles or live refreshes cannot mutate either historical snapshot.

## Exact formulas and semantics

- BUY fill difference = `actual entry fill - planned reference price`.
- Entry slippage % = `fill difference / planned reference price × 100`; positive is
  adverse for a BUY.
- Entry adverse slippage dollars/share equals that signed BUY fill difference.
- Quantity difference = `actual quantity - planned quantity`.
- Quantity adherence % = `actual quantity / planned quantity × 100` when planned quantity
  is positive; otherwise unavailable.
- Planned notional = `planned quantity × planned reference price`.
- Actual entry notional = `actual quantity × actual entry fill`.
- Gross realized P&L = `actual exit quantity × actual exit fill - actual quantity × actual
  entry fill`.
- Gross return % = `gross realized P&L / actual entry notional × 100`.
- Fees are unavailable and are never fabricated; therefore net P&L is unavailable.
- Calendar duration = exit date (or current date for OPEN analytics) minus entry date.
- MFE % = `(maximum unambiguous completed-session high / actual entry fill - 1) × 100`.
- MAE % = `(minimum unambiguous completed-session low / actual entry fill - 1) × 100`.
- The final hardened V1 window excludes both entry-day and exit-day OHLC for normal
  intraday Paper executions because the daily bar cannot prove whether its high/low
  occurred while the position was held. CLOSED excursions therefore use only completed
  sessions strictly after entry and strictly before exit. If that set is empty, MFE and
  MAE are unavailable, never zero. This corrects the earlier implementation stage, which
  included exit-day OHLC and was not conservative enough.
- OPEN excursions exclude entry day and include only completed sessions after entry.
  `CompletedDailySessionPolicy` excludes a current incomplete session. Sprint 22 live
  state remains a separate current observation and never enters historical MFE/MAE.
- Post-exit observations use the predeclared 5/10/20 completed-session horizons. An
  immature horizon is `INCOMPLETE`, not false. These observations are descriptive only.
- Expectancy % = `win rate × average winner + loss rate × average loser`, with an absent
  winner/loser side contributing zero and no closed sample returning unavailable.

Exact `Decimal` arithmetic is backend-owned. OPEN trades are excluded from realized P&L,
win rate, returns, and expectancy. Groups use the exact profile ID/version and never merge
versions. Maturity is fixed: 0 `NO_DATA`; 1–4 `VERY_LOW_SAMPLE`; 5–19 `LOW_SAMPLE`; 20–49
`DEVELOPING`; 50+ `MEANINGFUL_SAMPLE`. Missing metric availability is explicit.

## API, UI, and Copilot

Added read-only endpoints:

- `GET /api/v1/portfolio/{portfolio_id}/paper-analytics` with optional profile, ticker,
  and OPEN/CLOSED filters.
- `GET /api/v1/portfolio/{portfolio_id}/paper-analytics/{validation_id}`.

Typed schemas return aggregate maturity, evidence completeness counts, separately grouped
profile versions, OPEN/current observations, CLOSED outcomes, MFE/MAE, and fixed post-exit
horizons. Unknown details return 404 and invalid status filters return 422.

The Portfolio page now includes a clearly labeled “Forward Paper Evidence — separate from
Historical Research” panel. It shows OPEN/CLOSED counts, maturity beside performance,
gross realized P&L, win rate, evidence quality, profile-version groups, and drill-downs for
plan versus actual entry, slippage/adherence, at-entry evidence, current/open facts, closed
outcome, excursions, and 5/10/20 horizons. Missing/legacy facts display `Unavailable`, not
a fabricated zero. React displays server results and performs no financial calculations.

Copilot has a deterministic `PAPER_ANALYTICS` intent and server facts for Paper counts,
gross realized P&L, win rate, maturity, planned/actual entry, slippage, adherence, and
record status. Exact answers do not call Ollama. Generative explanations remain optional
and cannot promote a strategy; evidence maturity and numeric facts remain server-owned.

## Validation and performance

Commands executed:

```powershell
cd backend
$env:DEBUG='false'
uv run pytest tests/portfolio/test_paper_analytics.py tests/portfolio/test_position_intelligence.py tests/portfolio/test_copilot.py tests/portfolio/test_live_copilot.py -q
.\run_checks.ps1

cd frontend
npm run lint
npm test -- --run
npm run build
```

Initial focused backend result: 53 passed. Final semantic regression command reported 5
Paper Analytics tests passed, covering entry/exit boundary exclusion, extreme exit-day
high/low isolation, unavailable short-trade excursions, strictly-between sessions, OPEN
completed-session filtering, and post-exit horizon boundaries. Final backend gate: Ruff
PASS; mypy PASS on 178 source files; pytest 381 passed. Final frontend gate: ESLint PASS;
16 files / 79 tests PASS;
TypeScript/Vite production build PASS. Migration upgrade/downgrade/upgrade was verified on
the isolated test database, then upgrade was verified on development. The first local
downgrade exposed that the already-applied development revision predated the new trigger;
`IF EXISTS` made downgrade compatibility explicit, after which downgrade/upgrade passed.

Read-only real-data acceptance after migration: 11 total, 10 OPEN, 1 CLOSED, 0 FULL, 0
PARTIAL, 11 LEGACY, `VERY_LOW_SAMPLE`; response time 278.61 ms. No row was altered.
Controlled workflow/API acceptance is covered on the isolated test database: full entry
and exit snapshots, exact metrics, immutability, no portfolio mutation, filtering, detail,
unknown ID, incomplete/complete horizons, and deterministic Copilot all passed. Automated
browser-level component acceptance passed in Vitest. Final real browser acceptance also
passed using local Vite, local FastAPI with generative explanations disabled, and headless
Microsoft Edge/Playwright. The real backend returned all 11 user Paper records read-only;
a browser-only controlled response supplied one FULL and one LEGACY display case without
mutating user history. Edge verified domain separation, OPEN/CLOSED counts, tiny-sample
warning, profile/version grouping, unavailable legacy facts, plan versus actual fill,
slippage, adherence, immutable at-entry facts, closed P&L/return/duration/MFE/MAE,
5/10/20 horizons, and deterministic Paper Copilot. Screenshot:
`backend/backtest_reports/sprint23/browser-acceptance.png` (Git-ignored).

Final smoke-script consistency review confirmed that `current` was not undefined: the
source already assigns it from the authoritative read-only
`GET /api/v1/portfolio/current` request immediately before `current.ok()` and
`current.json()`. The apparent omission was from an incomplete file excerpt, not the
executed script. UTF-8 byte inspection found the intended `·` and `—` characters, no
`Â`/`â` mojibake markers, no replacement characters, and an exact UTF-8 round trip; the
earlier garbling was PowerShell display decoding. The retained smoke now also compares
portfolio revision/cash/positions and Paper OPEN/CLOSED/total counts before and after the
browser flow, failing if any user state changes.

## Files

Created:

- `backend/migrations/versions/e23f1a2b3c4d_add_forward_paper_evidence.py`
- `backend/src/alphapilot/schemas/paper_analytics.py`
- `backend/src/alphapilot/services/paper_analytics.py`
- `backend/tests/portfolio/test_paper_analytics.py`
- `frontend/src/features/portfolio/ForwardPaperAnalyticsPanel.tsx`
- `frontend/scripts/sprint23-forward-paper-smoke.mjs`
- `docs/sprints/SPRINT23_PLAN.md`
- `docs/sprints/SPRINT23_COMPLETION_REPORT.md`

Modified: `AGENTS.md`, `docs/PROJECT_STATE.md`, `docs/DECISIONS.md`, Paper database model,
validation service/schemas/routes, Copilot intent/context/direct answer, frontend portfolio
types/API/hooks/test server/Portfolio panel/test.

## Limitations

- Existing records are honestly legacy and cannot acquire facts that were never captured.
- Manual Alpaca Paper recording is not broker sync; fills, fees, partial exits, and account
  state are not imported automatically. V1 continues to require one aggregated full exit.
- Operational `DailyCandle` history is used for descriptive excursions; it is completed
  daily data but not an immutable research snapshot.
- Entry-day OHLC is excluded, which is conservative but omits possible same-day movement.
- The real local sample is tiny (one closed trade), current-constituent/survivorship and
  SPY historical-research caveats remain, and no inference about deployability is valid.
- No EMA Round 3, Micho recovery rule, protective-stop change, re-entry, strategy tuning,
  broker integration, order submission, or automatic promotion was introduced.

## Final acceptance answers

1. Forward Paper Analytics: YES.
2. Paper Validation separate from ResearchPortfolio: YES.
3. Paper entry mutates research portfolio: NO.
4. Paper exit mutates research portfolio: NO.
5–6. Entry and exit evidence immutable: YES, service plus database trigger.
7. Profile ID/version captured: YES.
8. Source action/plan: action YES when authoritative; plan remains unavailable when not.
9–12. Planned price/quantity and actual fill/quantity preserved: YES.
13–16. Slippage sign, quantity adherence, and separate notionals backend-owned: YES.
17. Loss-control entry facts captured: YES when available.
18–19. Sprint 22 live/provisional facts captured optionally: YES.
20. Future refresh can mutate entry evidence: NO.
21–23. Legacy readable, missing facts unavailable, no backfill: YES.
24. Gross realized P&L uses actual fills: YES.
25. Fees fabricated: NO.
26. OPEN trades excluded from realized win rate: YES.
27–29. Holding duration/MFE/MAE available when evidence permits: YES.
30. Entry- and exit-day ambiguity conservative: YES, both excluded for normal intraday
    executions; post-exit movement cannot inflate MFE or MAE.
31. Fixed horizons: 5/10/20.
32. Observations automatically change strategy: NO.
33. Micho recovery descriptive only: YES.
34. EMA became actionable: NO.
35. EMA Round 3 run: NO.
36–38. Versions separate, maturity shown, tiny samples labeled: YES.
39. Backtests mixed into Paper returns: NO.
40. UI separates Forward Paper Evidence and Historical Research: YES.
41. Exact Paper analytics with Ollama off: YES.
42. LLM calculates finance: NO.
43–44. Broker integration/order submission: NO/NO.
45. Strategy/research rule changed: NO.
46. Migration: YES, required for durable immutable capture without fabricating legacy data.
47. Controlled workflow: PASS on isolated test DB; read-only real audit PASS.
48. Legacy acceptance: PASS, 11/11 explicitly LEGACY.
49. Backend full gate: PASS, 381 tests.
50. Frontend full gate: PASS, 79 tests.
51. Browser acceptance: PASS with real local Vite + FastAPI + Edge/Playwright; no Paper
    order and no user Paper or ResearchPortfolio mutation.
52. Analytics response time: 278.61 ms on 11 local records.
53. Git status: local Sprint 23 modifications/untracked files; no commit or push.
54. Recommended commit: `feat: add immutable forward paper analytics`.

## Conclusion

Sprint 23 proved that AlphaPilot can accumulate honest, immutable, explainable forward
Paper execution evidence without contaminating Historical Research or portfolio authority.
It did not prove any strategy edge or production readiness. Sprint 24 was not started.

## Final evidence-hardening questions

1. Entry-day OHLC excluded from MFE/MAE: YES.
2. Exit-day OHLC excluded from MFE/MAE: YES for normal intraday Paper execution.
3. Why: daily OHLC cannot establish whether an extreme occurred before entry or after
   exit, so attributing either boundary session would invent the held intraday path.
4. Post-exit movement can inflate trade MFE: NO.
5. Post-exit movement can inflate trade MAE: NO.
6. No unambiguous completed session yields unavailable rather than zero: YES.
7. Five-session post-exit horizon starts after exit day: YES.
8. Sprint 22 live data enters historical MFE/MAE: NO.
9. Strategy rule changed: NO.
10. Other analytics formulas changed: NO; only excursion-window/availability semantics.
11. Focused tests: PASS, 5 Paper Analytics tests with exact Decimal boundary fixtures.
12. Full backend gate: PASS — Ruff, mypy (178 source files), pytest (381 passed).
13. Frontend gate: PASS — ESLint, 16 Vitest files / 79 tests, production build.
14. Real Edge/Playwright: PASS with real local FastAPI and Vite; controlled FULL/LEGACY
    display evidence and generative-disabled deterministic Copilot were verified.
15. User Paper history mutated: NO.
16. Git status: local Sprint 23 modified/untracked files only; no commit or push.
17. Recommended commit: `feat: add immutable forward paper analytics`.
