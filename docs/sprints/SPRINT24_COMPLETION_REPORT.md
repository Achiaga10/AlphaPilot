# Sprint 24 Completion Report

## Status

Sprint 24 — News Intelligence and Decision Overlay — completed successfully on the local
branch `feature/news-intelligence-foundation`. Sprint 25 was not started. No commit, push,
PR, merge, broker action, or automatic trade was performed.

## Final Option A integration (supersedes the earlier classifier-only stage)

The approved Adanos POC was integrated into the Sprint 24 production path for current
research use. The final architecture is:

- **Adanos:** primary aggregate News sentiment/context.
- **Finnhub:** attributable raw News, drill-down, and hard-event evidence.
- **Gemini:** targeted deep interpretation only when deterministic backend rules require
  it; it is no longer mandatory for every routine article.
- **Ollama:** disabled and reserved only as a future fallback.
- **AlphaPilot backend:** sole financial decision authority.

Adanos observations are immutable and time-aware. They persist company/ticker, provider,
observation time, requested seven-day period, score, bullish/bearish percentages,
mentions, source count, buzz, trend, and nullable provider timestamp. Adanos does not
supply a data-generation timestamp, so that field remains null; HTTP response time is not
misrepresented as market-data freshness. Ordinary GET and Dashboard rendering read the
persisted observations and never call Adanos.

The frozen aggregate evidence policy requires at least five mentions and two sources for
`SUFFICIENT` evidence. Otherwise directional percentages remain visible but are explicitly
`WEAK_EVIDENCE`. A sufficiently broad adverse observation (score at most -0.25 and bearish
breadth at least 60%) creates `TARGETED_NEWS_REVIEW`, never a trade. Positive aggregate
sentiment is context only. Missing, stale, unavailable, or weak evidence is never silently
converted to neutral.

The final BUY path is technical candidate -> aggregate risk screen -> attributable
Finnhub evidence -> targeted Gemini when deterministically selected -> existing
`news-decision-overlay-v1`. The final SELL path retains the stricter PRIMARY-source,
fresh/direct, confirmed hard-event gate. Adanos alone cannot BUY, SELL, or produce
`EXIT_REQUIRED`; positive Adanos cannot create a BUY or cancel loss control.

Explicit refresh deduplicates scope and batches a maximum of ten tickers per Adanos compare
request. Open-position refresh is bounded to current holdings; candidate refresh remains
bounded by the existing safety limit and never expands implicitly to the S&P 500. The UI,
Daily Portfolio Brief, execution readiness, and deterministic Copilot expose aggregate
sentiment separately from Finnhub article coverage and Gemini classification coverage.

Adanos Free/Hobby was observed/documented as 250 protected requests per month and is
non-commercial. Any commercial deployment requires a licensing review.

## Goal and outcome

Sprint 24 added durable company-news evidence and made it an explicit, separately visible
input to AlphaPilot's final advisory portfolio decisions. The frozen EMA20 Pullback,
Micho 150, RS20, HYBRID 2%, completed-session, T+1, ranking, sizing, and accounting rules
were not changed.

The completed decision path is:

`base technical/portfolio decision -> persisted validated News evidence -> NewsRiskAssessment -> news-decision-overlay-v1 -> final advisory action`

The base decision remains preserved. Hosted AI stops at typed financial-event
interpretation and has no schema field or authority for BUY, SELL, HOLD, price, sizing,
stop, or allocation. Financial effects are produced only by deterministic backend policy.

## Architecture implemented

- `NewsClassifierProvider` is a narrow provider protocol.
- `HostedNewsClassifier` uses the external Google Gemini API as the primary provider.
- `OllamaNewsClassifier` implements the same contract as an optional fallback and is
  disabled by default; AlphaPilot neither starts nor requires Ollama.
- `NewsArticle` stores normalized provider evidence with provider ID, canonical URL,
  deterministic fingerprint, source, publication time, receipt time, company, and ticker.
- `NewsClassification` stores append-only classification attempts and provenance:
  provider, model, classifier version, status, event type, impact, severity, confidence,
  reason, failure code, and classification time.
- `NewsService` fetches only open holdings by default, normalizes, deduplicates, persists,
  classifies, and builds assessments. A hosted 429 stops further classification attempts
  in that refresh; ingestion continues.
- `NewsRiskAssessment` applies publication-time, ingestion-time, classification-time,
  direct-relevance, source, freshness, and confidence rules as of the decision time.
- `news-decision-overlay-v1` creates typed effects: `NO_EFFECT`, `POSITIVE_CONTEXT`,
  `BUY_BLOCKED`, `ATTENTION`, `EXIT_REQUIRED`, and
  `NEWS_ASSESSMENT_UNAVAILABLE`.
- Portfolio plans, execution readiness, Daily Portfolio Brief positions, future Paper
  evidence, deterministic Copilot, and the Dashboard consume stored News facts.
- The Portfolio decision UI now shows base technical decision, News effect, final action,
  reason, policy version, and supporting article IDs separately.

## Frozen V1 policy

The protocol was written in `docs/sprints/SPRINT24_PLAN.md` before current-portfolio
outcomes were inspected.

- Lookback: 7 calendar days.
- Minimum usable classifier confidence: 0.75.
- BUY: adverse HIGH or SEVERE, direct, fresh, classified evidence at or above the minimum
  confidence blocks an otherwise eligible BUY. Missing News assessment also fails closed
  for a new BUY.
- Existing position: ordinary adverse evidence may escalate HOLD to ATTENTION.
- EXIT_REQUIRED: confidence at least 0.90, age no more than 72 hours, direct relevance,
  PRIMARY source, NEGATIVE impact, SEVERE severity, a closed severe event category, and
  deterministic explicit hard-event confirmation from the persisted headline/provider
  summary. Gemini classification alone is insufficient.
- Positive News cannot create a technical BUY, promote a blocked candidate, or cancel a
  technical/loss-control SELL.
- UNKNOWN, invalid, low-confidence, unavailable, late-published, or late-ingested evidence
  cannot create BUY_BLOCKED or EXIT_REQUIRED.
- News never changes the RS20 numeric formula.

## Hosted classifier

### Selection

- Provider: Google Gemini Developer API.
- Model: `gemini-3.5-flash-lite`.
- Structured-output mechanism: Gemini `responseMimeType=application/json` with a declared
  response JSON schema, followed by strict server-side Pydantic enum/range validation.
- Classifier version: configured and persisted separately from provider/model provenance.
- Commercial posture: the model documentation exposes free-tier pricing; no paid-only
  dependency was accepted. Actual quota remains account/project dependent.
- Privacy: only ticker/company, headline, provider summary, source, and publication time
  are sent. Portfolio/account/broker/database credentials and full publisher pages are not.

Official references used during selection:

- https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite
- https://ai.google.dev/gemini-api/docs/generate-content/structured-output
- https://ai.google.dev/gemini-api/docs/pricing
- https://ai.google.dev/gemini-api/docs/rate-limits
- https://ai.google.dev/gemini-api/terms

The initially declared `gemini-2.5-flash-lite` endpoint returned a provider 404 stating it
was unavailable to new users. The compatibility amendment changed only the hosted model
identifier to the provider's current stable Flash-Lite model. The evaluation labels,
prompt, output schema, thresholds, and decision policy were not retuned.

### Predeclared controlled evaluation

The fixed 15-case set was created before model results and covers earnings beat/miss,
guidance raise/cut, distress, analyst upgrade/downgrade, dilution, buyback, regulatory
investigation, CEO resignation, contract, layoffs, mixed evidence, and irrelevant News.

Command:

`uv run python -m alphapilot.cli.evaluate_news_classifier --fixture tests/news/fixtures/financial_news_evaluation_v1.json`

Results on `gemini-3.5-flash-lite`:

- cases: 15
- valid structured classifications: 13
- event-type accuracy: 86.67%
- impact accuracy: 80.00%
- severity reasonableness: 73.33%
- structured/request failures: 2 (`HOSTED_REQUEST_FAILED`)
- UNKNOWN results: 0
- mean latency: 1.223 seconds per case
- layoffs example: MIXED / MEDIUM / 0.90, demonstrating impact reasoning rather than
  wording-only sentiment

The two failures were retained as failures; labels and prompt were not repeatedly changed
to manufacture a perfect score. Hosted quality was adequate for the research foundation,
so Ollama was not evaluated or required.

## News provider and real acceptance

Finnhub was reused for company-specific News because the configured integration supplies
ticker scope, provider article ID, headline, summary, source, URL, and publication time.
No scraping or new paid data dependency was introduced.

Real refresh scope was the ten current open holdings only: APA, APO, AXON, DXCM, ERIE,
FAST, INTU, SLB, TSCO, and UBER. It did not fetch the S&P 500.

Observed initial implementation-stage acceptance (superseded by the final hardening
acceptance below for coverage conclusions):

- First provider refresh: 102 received, 96 inserted, 6 duplicates.
- Immediate repeat: 102 received, 0 inserted, 102 duplicates, proving idempotence.
- Hosted reclassification pass: 36 classified before quota pressure; persisted listing
  contained 96 articles, 36 CLASSIFIED, and 60 RATE_LIMITED latest attempts.
- The provider returned HTTP 429 during the real batch. Ingestion and persisted article
  reads remained usable, no classification was fabricated, no automatic fallback occurred,
  and no financial action was fabricated.
- Configuration stops after a rate limit and the final hardening also imposes a 10-attempt
  newest-first batch with a 250 ms inter-request delay.

The user portfolio stayed at revision 10 with 10 positions and one trade event; the 11
Paper records were unchanged. News refresh did not mutate ResearchPortfolio, Paper history,
broker state, or market data.

## API and UI

Added endpoints:

- `POST /api/v1/portfolio/{portfolio_id}/news-refresh` — explicit open-holdings refresh;
  ingestion only, no financial mutation.
- `GET /api/v1/portfolio/{portfolio_id}/news` — persisted evidence only, with ticker,
  time, taxonomy, and decision-effect filters; it never calls an external provider.

Existing portfolio-plan output now includes `base_decision`, `news_effect`, `final_action`,
`news_reason`, `news_policy_version`, and `supporting_news_article_ids`. News-blocked BUYs
are SKIP/non-actionable with stable News readiness reasons. Technical SELL remains SELL.

The Dashboard News Intelligence panel shows headline, source link, publication time,
event type, impact, severity, classifier provenance/status, and the explicit reminder that
AI interprets event impact only. Existing portfolio decision details show the technical,
News, and final action stack. React does not calculate financial effects.

Deterministic News Copilot answers stored-fact questions without reclassifying an article
and without generative AI. Missing ticker context receives clarification.

## Time and provenance rules

An article can influence a decision only when both `published_at <= decision_as_of` and
`received_at <= decision_as_of`; its valid classification must also exist by that time and
the article must remain inside the frozen freshness window. Therefore future News and News
ingested later cannot be retroactively claimed as historical decision evidence.

Every effect exposes source/timestamps, policy version, and supporting persisted article
IDs. Future ResearchPortfolio BUY evidence and Paper entry capture preserve the News trace.
Legacy Sprint 23 records remain null/unchanged rather than being backfilled. Open-position
and future exit evidence distinguish News policy exits from EMA/Micho exits.

## Files created

- `backend/migrations/versions/d7f4a2c9e810_add_news_intelligence.py`
- `backend/migrations/versions/e8a1c5d4f920_allow_news_classification_attempt_history.py`
- `backend/migrations/versions/f9b2d6e5a031_add_position_news_decision_evidence.py`
- `backend/migrations/versions/a0c3e7f6b142_add_news_refresh_coverage.py`
- `backend/migrations/versions/c1d4e7f9a250_add_external_news_sentiment.py`
- `backend/src/alphapilot/api/routes/news.py`
- `backend/src/alphapilot/cli/evaluate_news_classifier.py`
- `backend/src/alphapilot/news/__init__.py`
- `backend/src/alphapilot/news/classifier.py`
- `backend/src/alphapilot/news/external_sentiment.py`
- `backend/src/alphapilot/news/models.py`
- `backend/src/alphapilot/news/policy.py`
- `backend/src/alphapilot/news/service.py`
- `backend/src/alphapilot/schemas/news.py`
- `backend/tests/news/fixtures/financial_news_evaluation_v1.json`
- `backend/tests/news/test_classifier.py`
- `backend/tests/news/test_external_sentiment.py`
- `backend/tests/news/test_normalization.py`
- `backend/tests/news/test_policy.py`
- `backend/tests/news/test_service.py`
- `backend/tests/news/test_exit_safety_fixture.py`
- `backend/tests/news/fixtures/financial_news_exit_safety_v1.json`
- `docs/sprints/SPRINT24_PLAN.md`
- `docs/sprints/SPRINT24_COMPLETION_REPORT.md`
- `docs/sprints/SPRINT24_ADANOS_POC.md`
- `frontend/scripts/sprint24-news-smoke.mjs`
- `frontend/src/features/dashboard/NewsIntelligencePanel.tsx`

## Files modified

- `AGENTS.md`
- `backend/.env.example`
- `backend/src/alphapilot/api/router.py`
- `backend/src/alphapilot/api/routes/copilot.py`
- `backend/src/alphapilot/api/routes/portfolio.py`
- `backend/src/alphapilot/core/config.py`
- `backend/src/alphapilot/database/models/__init__.py`
- `backend/src/alphapilot/database/models/news.py`
- `backend/src/alphapilot/database/models/research_portfolio.py`
- `backend/src/alphapilot/market/providers/finnhub.py`
- `backend/src/alphapilot/portfolio/daily_brief.py`
- `backend/src/alphapilot/portfolio/decisions.py`
- `backend/src/alphapilot/portfolio/execution_readiness.py`
- `backend/src/alphapilot/portfolio/sizing.py`
- `backend/src/alphapilot/schemas/daily_brief.py`
- `backend/src/alphapilot/schemas/portfolio.py`
- `backend/src/alphapilot/services/daily_portfolio_brief.py`
- `backend/src/alphapilot/services/paper_validation.py`
- `backend/src/alphapilot/services/research_portfolio.py`
- `backend/tests/market/providers/test_finnhub.py`
- `backend/tests/conftest.py`
- `docs/DECISIONS.md`
- `docs/PROJECT_STATE.md`
- `frontend/src/api/portfolio.ts`
- `frontend/src/features/dashboard/DailyPortfolioManager.tsx`
- `frontend/src/features/portfolio/DecisionTable.test.tsx`
- `frontend/src/features/portfolio/DecisionTable.tsx`
- `frontend/src/hooks/usePortfolioApi.ts`
- `frontend/src/pages/DashboardPage.test.tsx`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/styles.css`
- `frontend/src/test/server.ts`
- `frontend/src/types/portfolio.ts`

## Tests and commands

Focused commands included:

- `$env:DEBUG='false'; uv run pytest tests/news tests/portfolio/test_execution_readiness.py -q`
  — 13 passed.
- `npm test -- --run src/features/portfolio/DecisionTable.test.tsx` — 3 passed.
- Additional focused News, portfolio, Daily Brief, Copilot, provider, Paper, and Dashboard
  selections passed during implementation (including a 48-test integration selection).

Final backend command:

`cd backend; $env:DEBUG='false'; .\run_checks.ps1`

- Ruff: PASS; formatter check: PASS (270 files unchanged).
- mypy: PASS across 186 source files.
- pytest: 403 passed in 112.71 seconds.

Final frontend commands:

- `npm run lint` — PASS.
- `npm test -- --run` — 16 files / 81 tests PASS.
- `npm run build` — PASS; 108 modules transformed and the official logo asset bundled.

## Migration verification

The development database was upgraded to head `a0c3e7f6b142`. A separately created empty
PostgreSQL database was then validated with:

- `uv run alembic upgrade head`
- `uv run alembic current`
- downgrade of the three Sprint 24 revisions to pre-Sprint-24 revision `e23f1a2b3c4d`
- `uv run alembic upgrade head`
- `uv run alembic current`

Fresh upgrade, downgrade, and re-upgrade all passed with asyncpg; the isolated database
was removed after verification. No development database was reset or destructively
recreated.

## Edge/Playwright acceptance

Command:

`cd frontend; node scripts/sprint24-news-smoke.mjs`

The script used local FastAPI on port 8010, local Vite on port 5174, Microsoft Edge via
Playwright, and generative AI disabled. It performed read-only health/current portfolio/
persisted News/Copilot requests and rendered the real Dashboard.

Result:

`SPRINT24_BROWSER_ACCEPTANCE PASS articles=212 classified=45 copilot=deterministic-news-v1`

The UI showed News Intelligence, classification provenance, source/time facts, and its AI
authority boundary. The before/after ResearchPortfolio representation was identical. The
screenshot is a Git-ignored local artifact at
`backend/backtest_reports/sprint24/browser-acceptance.png`.

## Controlled decision-policy acceptance

Automated policy tests prove:

- technical BUY + NO_EFFECT remains BUY;
- technical BUY + qualifying adverse evidence becomes BUY_BLOCKED/DO_NOT_BUY;
- positive News without a technical entry does not create BUY;
- base blocked decisions cannot be promoted;
- ordinary negative News escalates attention but does not force SELL;
- qualifying severe, fresh, direct, PRIMARY-source confirmed hard-event evidence can
  create EXIT_REQUIRED;
- UNKNOWN/invalid/late evidence cannot force SELL;
- base SELL remains SELL despite positive News;
- supporting IDs and the versioned policy are preserved;
- future publication/receipt/classification cannot affect a prior decision.

## Final acceptance answers

1. News Intelligence implemented: YES.
2. News affects final BUY/SELL decisions: YES, through deterministic policy.
3. Base technical decisions preserved: YES.
4. Adverse News can block a valid BUY: YES.
5. Positive News alone can create BUY: NO.
6. Positive News can cancel technical SELL: NO.
7. Narrow severe verified and deterministically confirmed News can create EXIT_REQUIRED:
   YES; AI classification alone cannot.
8. Ordinary negative sentiment automatically sells: NO.
9. UNKNOWN classification can sell: NO.
10. Every News-driven financial action is backend-owned: YES.
11. AI directly returns BUY/SELL authority: NO.
12. News policy versioned: YES, `news-decision-overlay-v1`.
13. Supporting article IDs preserved: YES.
14. Source and timestamps preserved: YES.
15. No-lookahead enforced: YES.
16. Later-published article can affect prior decision: NO.
17. Later-ingested article can be retroactively claimed: NO.
18. News affects execution readiness/new BUY actionability: YES.
19. BUY_BLOCKED explicitly visible: YES.
20. NEWS_RISK_EXIT distinct from EMA/Micho exits: YES.
21. Micho completed-close SMA150 logic unchanged: YES.
22. EMA logic unchanged: YES.
23. RS20 unchanged: YES.
24. HYBRID 2% unchanged: YES.
25. Refresh defaults to relevant open holdings: YES.
26. Full S&P fetched: NO.
27. Refresh idempotent: YES.
28. Duplicate articles deduplicated: YES.
29. Provider failure erases old News: NO.
30. News works with Ollama off: YES.
31. Deterministic Copilot works with Ollama off: YES.
32. Dashboard works with Ollama off: YES.
33. Future Paper evidence can preserve News provenance: YES.
34. Sprint 23 historical records changed/backfilled: NO.
35. Automatic broker order: NO.
36. Scraping: NO.
37. Strategy parameter retuning: NO.
38. Provider: Finnhub for News; Google Gemini for classification.
39. Real provider acceptance: PASS with partial hosted rate limiting disclosed.
40. Controlled BUY_BLOCKED acceptance: PASS.
41. Controlled EXIT_REQUIRED acceptance: PASS.
42. Positive-News-no-BUY acceptance: PASS.
43. Base-SELL-not-cancelled acceptance: PASS.
44. Backend full gate: PASS, 403 tests.
45. Frontend full gate: PASS, 16 files / 81 tests.
46. Fresh database migration: PASS, including downgrade/re-upgrade.
47. Edge/Playwright acceptance: PASS.
48. Git status: local modified and untracked Sprint 24 files; no commit.
49. Recommended commit message: `feat: add durable news intelligence and decision overlay`.

## Final safety and BUY-coverage hardening

This section supersedes the earlier implementation-stage exit and coverage semantics.
The architecture remained unchanged; the final approval hardening narrowed sell authority
and added an explicit coverage authority.

### Final News exit policy

Gemini supplies only typed interpretation evidence. A News exit requires every original
freshness, direct relevance, NEGATIVE/SEVERE, confidence `>= 0.90`, event-category, and
no-lookahead condition plus deterministic `hard_event_confirmed`.

Hard-event confirmation V1 requires PRIMARY source provenance and a matching explicit
closed phrase in the persisted headline/provider summary:

- filed Chapter 7/11 or filed bankruptcy petition;
- exchange/regulator notice/order of delisting;
- regulator/exchange trading suspension (not an ordinary volatility halt);
- regulator charge/finding of accounting fraud or material financial misstatement;
- regulator revocation/suspension of authorization or core operations.

Rumors, possible/considered events, going-concern warnings without a filing,
investigations/inquiries without a finding, lawsuits, ordinary volatility halts, and
secondary reporting are not hard-event confirmation. They can create attention but not
`EXIT_REQUIRED`. V1 did not invent multi-source semantic clustering. News-driven exits
remain enabled because the independent safety set produced zero unsupported exits.

### Independent 30-case exit-safety evaluation

The immutable fixture
`backend/tests/news/fixtures/financial_news_exit_safety_v1.json` was created and its
expected event type, impact, severity range, and hard-exit eligibility were frozen before
the hosted run. It contains six supported hard events and 24 false-positive controls.

Exact hosted command:

`uv run python -m alphapilot.cli.evaluate_news_classifier tests/news/fixtures/financial_news_exit_safety_v1.json`

Gemini 3.5 Flash-Lite result:

- cases: 30
- event-type accuracy: 63.33%
- impact accuracy: 56.67%
- severity reasonableness: 63.33%
- request/structured failures: 10 (`HOSTED_REQUEST_FAILED`)
- UNKNOWN results: 1
- average latency: 9.705 seconds
- unsupported `EXIT_REQUIRED`: **0**
- supported hard exits activated: 2 of 6

Classifier quality was materially weaker than the original set. The deterministic policy
nevertheless achieved the safety objective: no rumor, warning, investigation, lawsuit,
ordinary halt, strong wording, or secondary-source hard-event report became an exit.
Four eligible controls failed safe because the hosted call failed or the model did not
return the required SEVERE classification. This is false-negative/availability risk, not
false-positive sell authority, and remains a disclosed limitation.

### BUY coverage architecture

`NewsRefreshScope` is explicit:

- `OPEN_POSITIONS` remains the default;
- `CANDIDATES` accepts the backend/client's already-filtered final candidate tickers;
- `EXPLICIT_TICKERS` accepts a deliberate bounded list.

Candidate/explicit requests normalize and deduplicate tickers, reject empty lists, and
hard-limit the request to 25. They never expand into the S&P 500. The plan/Daily Brief
then assesses the persisted coverage before exposing actionability.

`NewsRefreshCoverage` persists each ticker's provider window, scope, attempt/completion
times, provider result, received/classified/unclassified counts, failure code, and
Retry-After seconds when available. States are `CURRENT`, `STALE`, `PARTIAL`,
`RATE_LIMITED`, `UNAVAILABLE`, and `NEVER_REFRESHED`.

Actionable BUY requires a provider-success record no older than 24 hours, covering the
full seven-day window ending on the decision date, with every returned article carrying a
successful current provider/model/version classification. Stored articles alone are not
current coverage. Partial/rate-limited/stale/unavailable/never-refreshed candidates fail
closed as not actionable. For held positions incomplete coverage is explicit and cannot
fabricate an exit; partial/rate-limited coverage can escalate attention while the
technical state remains preserved.

Daily Brief and portfolio decisions now expose technical/base decision, News coverage,
News effect, final action, reason, policy, and supporting IDs. Deterministic Copilot can
answer currentness, last-refresh, classifier completeness, availability blocks, and why
AI alone cannot trigger a sell.

### Rate-aware hosted behavior and final real acceptance

The classifier processes only articles without a successful current classification,
newest first, with at most 10 attempts per explicit refresh and 250 ms between calls. It
stops on HTTP 429, captures integer `Retry-After`, performs no busy retry, and leaves the
remainder pending for a later explicit refresh. Ollama remains disabled by default.

Final real open-holdings refresh:

- scope: OPEN_POSITIONS; 10 distinct holdings; no S&P expansion
- articles fetched: 224
- inserted: 116; duplicates: 108
- hosted attempts: 10
- classified: 9; failures: 1; observed 429s: 0
- coverage: APA CURRENT; APO, AXON, DXCM, ERIE, FAST, INTU, SLB, TSCO, UBER PARTIAL
- portfolio representation unchanged: YES
- Paper representation unchanged: YES

The bounded strategy avoided another quota-exhaustion burst, but one of ten holdings
became fully current in this single run. Hosted free-tier throughput therefore remains
practically limiting for ordinary holdings plus candidate coverage. The existing Ollama
fallback should be considered by the user (or hosted quota/batch workflow revisited), but
it was not enabled or invoked automatically.

### Final hardening acceptance answers

1. Final exit policy: strict AI evidence plus PRIMARY-source deterministic hard-event
   confirmation under `news-decision-overlay-v1`.
2. Hard-event confirmation: closed explicit filing/delisting/suspension/accounting-fraud/
   revoked-operations facts from PRIMARY evidence only.
3. Can Gemini classification alone SELL? **NO**.
4. Can verified severe News still cause EXIT_REQUIRED? **YES**, when every gate passes.
5. Independent safety set: 30 frozen cases; hosted quality 63.33% event, 56.67% impact,
   63.33% severity reasonableness, 10 failures, 1 UNKNOWN.
6. Unsupported EXIT_REQUIRED false positives: **ZERO**; News exit V1 remains enabled.
7. Candidate workflow: explicit bounded final-candidate refresh, persisted coverage,
   assessment, then overlay/actionability.
8. Candidate refresh fetches S&P 500: **NO**; maximum 25 supplied tickers.
9. Coverage states: CURRENT, STALE, PARTIAL, RATE_LIMITED, UNAVAILABLE, NEVER_REFRESHED.
10. BUY freshness: successful full-window provider refresh within 24 hours plus complete
    active-classifier coverage.
11. Provider vs classifier coverage: persisted and exposed separately; incomplete
    classification is never NO_RISK/NO_EFFECT authority.
12. Real Gemini after hardening: 9/10 attempts classified, no 429, but only 1/10 holdings
    fully CURRENT in that bounded run.
13. Ollama disabled by default: **YES**.
14. Consider Ollama fallback: **YES, for user review**, because measured hosted throughput
    remains limiting; do not auto-enable it.
15. Backend gate: PASS — Ruff/format, mypy 186 files, pytest 403 passed.
16. Frontend gate: PASS — lint, 16 files / 81 tests, production build.
17. Migration: PASS — empty PostgreSQL upgrade to `a0c3e7f6b142`, current, downgrade to
    `f9b2d6e5a031`, re-upgrade/current, isolated database removed.
18. Browser: PASS — real FastAPI/persisted News/Vite/Edge, 212 articles, 45 classified,
    deterministic News Copilot, controlled coverage rendering.
19. Real portfolio/Paper mutation: **NO**. News evidence/coverage alone was appended.
20. Git status: local Sprint 24 modified/untracked files only; no commit or push.
21. Recommended commit: `feat: harden news decisions and candidate coverage`.

## Limitations and technical debt

- Finnhub entitlements, coverage, source metadata, and historical depth constrain evidence.
- Gemini free/project quota caused real HTTP 429 responses; classification completion needs
  deliberate rate-aware batching or a background queue before broader scale.
- Two of 15 controlled hosted calls failed, and severity reasonableness was 73.33%; the
  classifier is research evidence, not infallible truth.
- Source-confidence mapping is an explicit V1 policy and needs governance as providers and
  publishers evolve.
- Manual refresh is implemented; durable scheduling/background retries are future work.
- A successful refresh with no usable classifications remains conservatively unavailable.
- There is no authenticated account persistence, broker synchronization, automatic order
  path, scraping, or live publisher-page ingestion.
- Current S&P historical research still has current-constituent survivorship bias. Sprint 24
  did not rerun or retune historical research.
- News coverage and the SPY benchmark have different purposes; News acceptance does not
  validate strategy alpha or production trading performance.

## Conclusion

Sprint 24 proved that AlphaPilot can ingest durable, deduplicated News for current holdings,
obtain strict hosted financial-impact classifications, preserve classification provenance,
and apply those facts through a conservative deterministic decision policy while retaining
the original strategy result. It also proved safe degradation: provider/classifier failure
leaves News readable and never fabricates a decision.

It did not prove that AI classifications are always correct, that free-tier capacity is
sufficient at production scale, that News improves returns, or that automated execution is
appropriate. Sprint 25 should not begin until this implementation and its disclosed quality/
quota limitations are independently reviewed.

## Git handoff

Current branch: `feature/news-intelligence-foundation`.

All modified and untracked files listed above are local Sprint 24 work and are ready for
user review. Nothing was committed or pushed.

Recommended commit message:

`feat: add durable news intelligence and decision overlay`

## Final Adanos integration acceptance (authoritative final state)

This section supersedes earlier POC/classifier-only wording, earlier quality-gate counts,
and the earlier suggestion that Ollama needed immediate evaluation. Option A is fully
integrated for current research use; the POC remains a historical decision record.

### Durable model, API, and coverage separation

- New revision: `c1d4e7f9a250_add_external_news_sentiment`.
- New model/table: immutable `ExternalNewsSentimentObservation` /
  `external_news_sentiment_observations`.
- New read-only endpoint:
  `GET /api/v1/portfolio/{portfolio_id}/news-sentiment`. It returns persisted observations
  only and performs no provider call.
- Explicit `POST .../news-refresh` now reports Adanos requested/returned/missing tickers,
  API-call count, persisted observations, and targeted Gemini attempts.
- Aggregate sentiment coverage (Adanos), attributable article coverage (Finnhub), and
  classification coverage (Gemini) remain separate typed facts. One never implies that
  either of the others is complete.

### Controlled policy and efficiency acceptance

Controlled fixtures/tests cover broad positive, broad negative, mixed, single-source
positive/negative, rising/falling trend, missing, unavailable, and stale observations.
They prove positive Adanos alone cannot BUY; negative Adanos alone cannot SELL or
`EXIT_REQUIRED`; one mention/one source stays `WEAK_EVIDENCE`; sufficient broad adverse
evidence can trigger `TARGETED_NEWS_REVIEW`; confirmed Finnhub/PRIMARY hard-event evidence
can still pass the existing exit gate; technical SELL and loss control cannot be cancelled;
missing sentiment does not become neutral; and absent provider timestamp remains null.

Batch/service tests prove ticker deduplication, <=10 tickers in one compare call, 11-20 in
two calls, no implicit S&P fetch, routine articles bypass Gemini, only deterministically
targeted articles reach Gemini, and prior successful classifications are reused. Controlled
BUY tests preserve eligibility for sufficient non-adverse aggregate context, route broad
adverse evidence to review, allow attributable confirmed adverse evidence to produce
`BUY_BLOCKED`, and prevent a single-source bearish percentage from blocking by itself.
Controlled SELL tests keep very bearish aggregate context at attention/review until the
existing independently confirmed hard-event gate is satisfied.

### Real bounded integration acceptance

One forced, batched Adanos compare request was made after integration for the authoritative
open portfolio. No second provider request was made during tests, GETs, Dashboard rendering,
or browser acceptance.

- Portfolio: `1c1d6732-e290-475d-9b1f-47149876cdf1`.
- Tickers: APA, APO, AXON, DXCM, ERIE, FAST, INTU, SLB, TSCO, UBER.
- Adanos calls: 1.
- Adanos returned: 10/10; missing: none.
- Persisted aggregate observations: 10.
- Finnhub company drill-down requests: 10 bounded holding-ticker requests; 199 articles
  fetched, 12 inserted, and 187 deduplicated.
- Targeted Gemini calls: 0. No routine article required deep interpretation under the
  frozen rules.
- Old baseline: 212 stored articles, 45 successfully classified, and only 1/10 CURRENT
  article-classification coverage. Final persisted browser read: 224 articles and the same
  45 successful classifications.
- Routine Gemini demand in this acceptance fell from the previous bounded 10-attempt
  workflow to 0 attempts (100% reduction for this run). This demonstrates workload
  reduction, not classifier-quality or trading-alpha improvement.
- The standalone POC measured the one compare call at 1.013 seconds. The final refresh did
  not separately instrument end-to-end elapsed time, so no fabricated integration latency
  is reported.
- ResearchPortfolio revision/cash/positions, Paper records, trade events, and position
  signatures were identical before and after. No broker action or market-data mutation
  occurred.

### Final quality gates and browser acceptance

- Backend: `cd backend; $env:DEBUG='false'; .\run_checks.ps1` — PASS. Ruff and formatting
  PASS; mypy PASS across 187 source files; pytest **421 passed in 63.75 seconds**.
- Frontend: `npm run lint` PASS; `npm test -- --run` PASS (**16 files / 81 tests**);
  `npm run build` PASS (108 modules, production asset bundle).
- Migration: fresh isolated PostgreSQL upgrade/current to `c1d4e7f9a250`, downgrade to
  `a0c3e7f6b142`, re-upgrade/current to `c1d4e7f9a250`, then exact isolated database removal
  — PASS. The development database was not reset.
- Browser: local FastAPI + Vite + Microsoft Edge/Playwright with generative Copilot AI
  disabled — PASS:
  `SPRINT24_BROWSER_ACCEPTANCE PASS articles=224 classified=45 adanos=10 copilot=deterministic-news-v1`.
  The Dashboard visibly separated Adanos aggregate sentiment, Finnhub attributable News,
  and targeted Gemini provenance; rendered persisted weak evidence; showed the existing
  technical/News/final decision stack; and made no automatic trade. UTF-8 source inspection
  confirmed `·`, `—`, and `…` are stored correctly; apparent mojibake was PowerShell default
  display decoding only.

### Final acceptance answers

1. Adanos production-path integrated for current research use: **YES**.
2. Adanos is primary aggregate sentiment: **YES**.
3. Sentiment is persisted: **YES**, append-only/time-aware observations.
4. Finnhub retained: **YES**, for attributable and hard-event evidence.
5. Gemini retained: **YES**, for targeted deep interpretation.
6. Gemini mandatory for every article: **NO**.
7. Ollama used: **NO**; it remains disabled/future fallback only.
8. Adanos alone can BUY: **NO**.
9. Adanos alone can SELL: **NO**.
10. Adanos alone can create `EXIT_REQUIRED`: **NO**.
11. Adverse sufficient Adanos can trigger targeted review: **YES**.
12. Confirmed severe attributable evidence can still create `EXIT_REQUIRED`: **YES**, only
    through every existing deterministic hard-event gate.
13. Weak evidence explicitly handled: **YES**.
14. Provider timestamp unavailable when not supplied: **YES**, persisted/exposed as null.
15. Ordinary GET calls Adanos: **NO**.
16. Dashboard rendering burns quota: **NO**.
17. Up to ten tickers use one compare request: **YES**.
18. Full S&P implicitly fetched: **NO**.
19. Real post-integration Adanos calls: **1**.
20. Real holdings returned: **10/10**.
21. Targeted Gemini calls in final real acceptance: **0**.
22. Gemini workload reduction: **10 bounded attempts to 0 (100%) in the comparable final
    routine refresh**; historical stored classifications remain available.
23. Controlled BUY acceptance: **PASS**.
24. Controlled SELL acceptance: **PASS**.
25. Migration revision: **`c1d4e7f9a250`**.
26. Fresh database migration: **PASS**, including downgrade/re-upgrade.
27. Backend full gate: **PASS — 421 tests, mypy 187 files**.
28. Frontend full gate: **PASS — 16 files / 81 tests, build PASS**.
29. Edge/Playwright: **PASS**.
30. Portfolio mutation: **NO**.
31. Paper mutation: **NO**.
32. Broker action: **NO**.
33. Commercial Adanos licensing limitation documented: **YES**; Free/Hobby is
    non-commercial and commercial deployment needs licensing review.
34. Git status: local Sprint 24 modified/untracked files only; no commit or push.
35. Recommended commit message:
    **`feat: integrate aggregate news sentiment into decision overlay`**.
