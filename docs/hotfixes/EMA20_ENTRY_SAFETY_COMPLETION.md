# EMA20 Entry Safety Hotfix — Completion Report

## Status

The focused post-Sprint-24 EMA20 entry-safety hotfix is **complete locally** on
`fix/ema20-entry-safety`. Sprint 25 was not started. No commit or push was performed.

This was execution/readiness hardening, not strategy research. The frozen EMA20 Pullback
signal, EMA periods, HYBRID 2%, RS20, sizing rules, Micho, and News Decision Overlay were
not changed. The existing 1% upper pullback-zone boundary was reused without tuning.

## What was implemented

AlphaPilot now keeps the historical technical signal separate from current entry
actionability:

1. The frozen strategy evaluates its completed-session signal exactly as before.
2. A backend-owned `Ema20EntrySafety` assessment compares the authoritative entry price
   with the fixed completed signal-session EMA20.
3. At or below `1.01 × EMA20` is eligible geometry; above it is blocked.
4. Missing, invalid, or stale price/EMA evidence fails closed.
5. During regular market hours for a current-date plan, one batched Alpaca live-snapshot
   request revalidates EMA BUY candidates. A quote must be from the current session,
   within the existing live-quote maximum age, and not delayed SIP.
6. Outside that path, the authoritative completed-session close is used with its explicit
   timestamp. The EMA anchor remains fixed; current price cannot move its own anchor.
7. The hard gate is applied before allocation and before expensive News investigation.
   Ranking and positive News cannot override it.
8. Preview/apply rejects blocked, unavailable, or stale live EMA entry evidence.
9. Future Paper entries preserve a versioned entry-safety snapshot. Historical Paper
   evidence is not rewritten or backfilled.
10. Typed API responses, Daily Portfolio Manager, Portfolio Plan details, and deterministic
    Copilot direct answers expose the backend facts. React performs no financial math.

Policy identifier: `ema20-entry-safety-v1`.

## Files created

- `backend/src/alphapilot/portfolio/entry_safety.py`
- `backend/migrations/versions/b4e2c8a1d903_allow_paper_entry_safety_evidence.py`
- `backend/tests/portfolio/test_ema20_entry_safety.py`
- `frontend/scripts/ema20-entry-safety-smoke.mjs`
- `docs/incidents/EMA20_ENTRY_EXTENSION_AXON_FAST.md`
- `docs/hotfixes/EMA20_ENTRY_SAFETY_COMPLETION.md`

## Files modified

- `AGENTS.md`
- `docs/PROJECT_STATE.md`
- `docs/DECISIONS.md`
- `backend/src/alphapilot/strategy/ema20_pullback.py`
- `backend/src/alphapilot/portfolio/orchestration.py`
- `backend/src/alphapilot/portfolio/decisions.py`
- `backend/src/alphapilot/portfolio/actions.py`
- `backend/src/alphapilot/portfolio/sizing.py`
- `backend/src/alphapilot/portfolio/execution_readiness.py`
- `backend/src/alphapilot/portfolio/daily_brief.py`
- `backend/src/alphapilot/services/daily_portfolio_brief.py`
- `backend/src/alphapilot/services/paper_validation.py`
- `backend/src/alphapilot/api/routes/portfolio.py`
- `backend/src/alphapilot/schemas/portfolio.py`
- `backend/src/alphapilot/schemas/daily_brief.py`
- `backend/src/alphapilot/copilot/intent.py`
- `backend/src/alphapilot/copilot/direct_answer.py`
- `backend/tests/portfolio/test_orchestration.py`
- `backend/tests/portfolio/test_daily_portfolio_brief.py`
- `backend/tests/portfolio/test_paper_analytics.py`
- `backend/tests/api/test_portfolio_decisions.py`
- `frontend/src/types/portfolio.ts`
- `frontend/src/test/fixtures.ts`
- `frontend/src/features/portfolio/DecisionTable.tsx`
- `frontend/src/features/portfolio/DecisionTable.test.tsx`
- `frontend/src/features/dashboard/DailyPortfolioManager.tsx`

## Forensic result

### AXON

- Frozen profile: `ema20-pullback-v1` version 1, HYBRID 2%, RS20, equal-slot.
- Signal/recommendation session: 2026-08-27.
- Stored recommendation/reference close: **$611.16**.
- Completed signal-session EMA20: **$597.1382581750427727951172336**.
- OHLC: $613.12 / $614.84 / $600.00 / $611.16.
- Low-to-EMA20: approximately **+0.479%**, inside the frozen low-touch zone.
- Recommendation-close-to-EMA20: approximately **+2.348%**, outside the 1% ceiling.
- Stored manual Paper fill: **16 shares at $609.00**, 2026-08-28 05:13 UTC.
- Fill-to-signal-EMA20: approximately **+1.986%**, therefore blocked by the new gate.
- Exact live quote at the historical moment of user action: **UNAVAILABLE**; it was not
  persisted and was not fabricated from a later price.

AXON was allowed because the completed candle legitimately satisfied the frozen strategy's
low-touch-and-reclaim signal, while the downstream portfolio path had no separate fresh
current-price-to-EMA entry gate. This is an entry-safety gap; the evidence does not prove
that extension caused the later loss.

### FAST

- Same frozen profile/configuration and 2026-08-27 signal session.
- Stored recommendation/reference close: **$51.12**.
- Completed signal-session EMA20: **$50.44696835243861901010882936**.
- OHLC: $50.73 / $51.305 / $50.55 / $51.12.
- Low-to-EMA20: approximately **+0.204%**, inside the frozen low-touch zone.
- Recommendation-close-to-EMA20: approximately **+1.334%**, outside the 1% ceiling.
- Stored manual Paper fill: **195 shares at $50.28**, 2026-08-28 05:14 UTC.
- Fill-to-signal-EMA20: approximately **-0.331%**, below EMA20 and eligible geometry.
- Exact live quote at the historical moment of user action: **UNAVAILABLE**.

FAST is a positive control only for its stored fill geometry. Its recommendation close
would have been blocked, while its actual stored fill was eligible. That does not prove
the trade was good and does not override any other portfolio gate.

## Tests and validation

### Focused backend tests

The final focused entry-safety/API/orchestration/Daily Brief/Paper group passed:

```powershell
cd backend
$env:DEBUG='false'
uv run pytest tests/portfolio/test_ema20_entry_safety.py tests/portfolio/test_orchestration.py tests/api/test_portfolio_decisions.py tests/portfolio/test_daily_portfolio_brief.py tests/portfolio/test_paper_analytics.py -q
```

Result: **53 passed**. An earlier broader focused run also passed 62 tests.

Coverage includes below/equal/inside/exact-ceiling/outside/materially-above boundaries;
missing price; missing EMA; stale quote; valid signal followed by a rally and later return;
AXON incident-shaped facts; FAST stored-fill geometry; positive-News and excellent-RS20
non-override; action-time stale-live rejection; Paper evidence v2; Daily Brief precedence;
typed API serialization; and deterministic Copilot answers.

### Full backend gate

```powershell
cd backend
$env:DEBUG='false'
.\run_checks.ps1
```

- Ruff: **PASS**
- Ruff format check: **PASS**
- mypy: **PASS — 188 source files**
- pytest: **PASS — 439 passed in 66.52s**

### Full frontend gate

```powershell
cd frontend
npm run lint
npm test -- --run
npm run build
```

- ESLint: **PASS**
- Vitest: **PASS — 16 files / 82 tests**
- TypeScript/Vite production build: **PASS — 108 modules transformed**

The final frontend gate was rerun after adding the reproducible Edge smoke script.

### Migration validation

Prospective immutable Paper evidence required a narrow constraint migration because entry
evidence schema version 2 adds `entry_safety`. The existing exit evidence remains version
1 and old entry rows remain unchanged.

On the explicitly isolated PostgreSQL database
`alphapilot_ema_entry_safety_migration_test`:

```powershell
uv run alembic upgrade head
uv run alembic current
uv run alembic downgrade c1d4e7f9a250
uv run alembic upgrade head
uv run alembic current
```

Result: **PASS**. Head was `b4e2c8a1d903`; downgrade and re-upgrade both passed. The exact
temporary database target was verified before cleanup; no development database reset was
performed.

### Real read-only and browser acceptance

Earlier read-only stored-data reconstruction found these latest completed 2026-09-01
facts for the then-held incident tickers:

| Ticker | Completed close | EMA20 | Distance | Geometry-only result |
|---|---:|---:|---:|---|
| AXON | $518.28 | $587.2708058334 | -11.748% | Eligible/below; already held |
| FAST | $48.75 | $50.1340099265 | -2.761% | Eligible/below; already held |

These current values were not substituted for historical action-time facts.

The final reproducible browser command used local FastAPI on 8010, Vite on 5174, and the
installed Microsoft Edge executable through Playwright:

```powershell
cd frontend
$env:ALPHAPILOT_FRONTEND_URL='http://127.0.0.1:5174'
$env:ALPHAPILOT_BACKEND_URL='http://127.0.0.1:8010'
node scripts/ema20-entry-safety-smoke.mjs
```

Result:

```text
EMA20_ENTRY_SAFETY_BROWSER_ACCEPTANCE PASS blocked=ERIE eligible=UBER decisions=10
```

The real plan displayed the backend price, fixed EMA20 anchor, dollar/percentage distance,
source, timestamps, status, and reason. ERIE was visibly `BLOCKED` with
`ENTRY_TOO_EXTENDED_ABOVE_EMA20` and final `DO_NOT_BUY`; UBER was an `ELIGIBLE` geometry
control. The smoke invoked no apply/preview/mutation endpoint and asserted the current
portfolio and Paper Analytics signatures were identical before and after. At the final
read-only check the user-controlled current state was revision 15, cash $2,166.3550,
10 open positions, 12 trade events, and 11 Paper records (10 open / 1 closed). The browser
run did not change those values. No broker endpoint or Alpaca order was invoked.

Screenshot: `backend/backtest_reports/ema20_entry_safety/browser-acceptance.png`
(Git-ignored research artifact).

## Required answers

1. **What exactly allowed AXON through?** A valid frozen low-touch/reclaim technical signal
   was treated as actionable without a separate fresh current-price entry-geometry gate.
2. **Was AXON historical geometry fully reconstructable?** The completed signal candle,
   EMA, plan reference, and Paper fill were reconstructable; the exact action-time live
   quote was not persisted and remains unavailable.
3. **AXON recommendation price:** $611.16.
4. **AXON EMA20:** $597.1382581750427727951172336 on 2026-08-27.
5. **AXON distance:** recommendation +2.348%; stored fill +1.986%; low +0.479%.
6. **AXON current/fill revalidation:** the $609 fill is extended and blocked. The later
   2026-09-01 close was below its then-current EMA, but is not historical entry evidence.
7. **Was FAST historical geometry reconstructable?** The same fields were reconstructable;
   its exact action-time live quote was not.
8. **FAST recommendation price:** $51.12.
9. **FAST EMA20:** $50.44696835243861901010882936 on 2026-08-27.
10. **FAST distance:** recommendation +1.334%; stored fill -0.331%; low +0.204%.
11. **Did FAST satisfy the approved geometry?** Its stored $50.28 fill did; its $51.12
    recommendation close did not. This is geometry-only, not final BUY approval.
12. **Existing upper tolerance:** `PULLBACK_UPPER_BOUND = Decimal("1.01")`, or 1% above
    EMA20.
13. **Was the tolerance changed?** **NO.** Constants were exported for shared use without
    changing the frozen evaluator.
14. **Authoritative EMA anchor:** the completed signal/analysis-session EMA20, kept fixed
    during current-price revalidation.
15. **Authoritative entry price:** a fresh, same-session Alpaca live snapshot for a current
    regular-hours request; otherwise the explicitly timestamped completed-session close.
16. **Typed object:** `Ema20EntrySafety`, including sources, timestamps, EMA, distances,
    relation, status, reason, policy version, and upper-bound multiplier.
17. **Stable blocking reason:** `ENTRY_TOO_EXTENDED_ABOVE_EMA20`; unavailable/stale facts
    use `EMA20_ENTRY_REVALIDATION_UNAVAILABLE`.
18. **Can a stale old signal remain actionable after price rallies?** **NO.** A current
    regular-hours plan revalidates against a fresh quote, and action application rejects a
    stale live assessment.
19. **Can positive News override extension?** **NO.** Entry safety is a prior hard gate;
    News deep investigation is skipped for an already-blocked candidate.
20. **Can RS20 override extension?** **NO.** Rank is preserved for provenance but has no
    authority over the safety result.
21. **Can unavailable price/EMA become actionable?** **NO.** It fails closed.
22. **AXON regression:** the explicitly labeled incident-shaped control using verified
    stored geometry is blocked and non-actionable.
23. **FAST control:** the verified stored-fill geometry remains eligible through this gate;
    other gates may still reject a BUY.
24. **Controlled boundaries:** all predeclared boundary, missing/stale, precedence, and
    intraday-movement cases pass, including exact 1.01 eligibility and immediately-above
    blocking.
25. **Real read-only acceptance:** passed for stored AXON/FAST facts and a real current plan;
    no historical live values were fabricated.
26. **Portfolio mutation?** **NO by this acceptance.** The browser verified identical
    before/after signatures. Current state reflects user-controlled changes made outside
    this read-only smoke, not an AlphaPilot acceptance action.
27. **Paper mutation?** **NO.** Only a prospective schema-v2 allowance was added; no old
    row was modified or backfilled.
28. **Broker action?** **NO.** No order or broker mutation was attempted.
29. **Migration?** **YES**, only to permit prospective Paper entry evidence schema v2.
30. **Fresh database result:** upgrade/current/downgrade/re-upgrade/current all passed on
    the verified isolated PostgreSQL database.
31. **Backend full gate:** **PASS** — Ruff, format, mypy (188 files), pytest (439 tests).
32. **Frontend full gate:** **PASS** — ESLint, 16/16 files and 82/82 tests, production build.
33. **Browser acceptance:** **PASS** in Microsoft Edge/Playwright against real local
    FastAPI/Vite; blocked and eligible states rendered with backend facts and no trade.
34. **Git status:** local modifications and new hotfix files remain uncommitted on
    `fix/ema20-entry-safety`; no commit or push was performed.
35. **Recommended commit message:** `fix: enforce fresh EMA20 entry safety`

## Limitations

- Historical action-time live quotes for AXON and FAST were not persisted, so the report
  distinguishes completed-plan and Paper-fill facts from unavailable live evidence.
- A valid entry-safety result is necessary but not sufficient for a final BUY. Strategy,
  loss-control readiness, News risk, cash, position, sector, and portfolio constraints
  retain their own authority.
- The 1% ceiling is an existing approved strategy semantic reused as a safety invariant;
  this hotfix does not prove it is economically optimal.
- No live broker synchronization or automatic execution was added.
- No proximity backtest, threshold sweep, or new strategy research was performed.

## Conclusion

The AXON incident exposed a genuine orchestration/readiness gap rather than evidence that
the frozen historical signal itself was implemented incorrectly. AlphaPilot can now retain
the truth that an earlier EMA pullback signal occurred while separately refusing a current
entry whose authoritative price is extended, stale, or unavailable. FAST's stored fill
remains a valid near/below-EMA geometry control. Sprint 25 remains not started.
