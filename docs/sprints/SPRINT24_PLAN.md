# Sprint 24 Plan — News Intelligence and Decision Overlay

## Goal

Add durable, explainable company-news evidence and a versioned deterministic News
Decision Overlay. Preserve the frozen technical strategy decision separately, while
allowing sufficiently strong adverse evidence to block a new BUY or, under a much
narrower rule, require exit review/action for an existing position. The user remains the
only execution authority.

## Existing-system audit

The repository has an empty `database/models/news.py` placeholder and a commented
Company relationship, but no durable News implementation. Finnhub and Polygon market
provider keys are configured; both providers expose company-news capabilities that can
be adapted without publisher scraping. The existing portfolio orchestrator,
ExecutionReadiness, Daily Brief, Position Intelligence, live intelligence, immutable
Paper evidence, deterministic Copilot, and Dashboard are the integration authorities.
No strategy calculation will be duplicated.

The current environment has no configured hosted generative-AI key. Sprint 24 will
therefore keep ingestion and stored-news display useful when classification is
unavailable and will report hosted acceptance honestly unless a key is supplied through
normal settings.

## Scope and non-goals

In scope: normalized articles, provider adapters, idempotent open-position refresh,
strict hosted classification, optional Ollama fallback, classification provenance,
time-aware risk assessment, a deterministic decision overlay, typed APIs, readiness and
brief integration, deterministic Copilot, Dashboard presentation, migration, tests, and
controlled/real acceptance.

Out of scope: changing EMA, Micho, RS20, HYBRID 2%, loss control, ranking or sizing;
publisher scraping; full-universe refresh; autonomous orders; broker trading; strategy
retuning; or allowing an AI model to issue a financial action.

## Provider decisions

News ingestion prefers Finnhub company news because it is already configured, has a
direct per-symbol/date-range contract, and returns provider article ID, headline,
summary, source, URL, image, related symbols, category, and publication time. Polygon
remains a replaceable secondary adapter where its configured entitlement permits it.
Refresh is sequential/bounded and does not aggressively retry.

The primary classifier is `HostedNewsClassifier`, selected through the narrow
`NewsClassifierProvider` protocol. V1 uses Google Gemini REST with model
`gemini-3.5-flash-lite`: it has a practical developer free tier, supports JSON Schema
structured output, and needs no paid-only SDK. Exact active quotas are account/project
specific and are reported by Google AI Studio; the service treats HTTP 429 explicitly.
Free-tier prompts may be used by Google to improve products, so only persisted factual
article fields are sent and no confidential portfolio/account facts are included.

`OllamaNewsClassifier` implements the same protocol but is disabled by default, is never
started by AlphaPilot, and is used only after a hosted failure when the explicit fallback
setting is enabled.

## Configuration

Repository-style settings will cover: classifier enabled flag, provider (`hosted`),
hosted API key/base URL/model, timeout, minimum confidence, classification version, and
the disabled-by-default Ollama fallback. Secrets are environment-only and never logged.
Ingestion is independent of classifier availability.

## Normalized article and deduplication contract

Persist provider, provider article ID, canonical URL, deterministic fallback fingerprint,
ticker/company linkage, headline, provider summary, source, image URL when supplied,
published-at and received-at aware timestamps, and raw provider category/related symbols
needed for provenance. Never scrape or persist publisher page bodies.

Deduplicate in this order: `(provider, provider_article_id)`, canonical URL, then a stable
hash of normalized ticker/headline/source/published instant. Database unique constraints
are authoritative under concurrency. Repeated overlapping refreshes are idempotent and
never erase older evidence.

## Classification contract and taxonomy

Every attempt has a status: `CLASSIFIED`, `UNAVAILABLE`, `RATE_LIMITED`, or `INVALID`.
Valid output is strict schema only:

- `event_type`: `EARNINGS`, `GUIDANCE`, `M_AND_A`, `ANALYST_RATING`, `MANAGEMENT`,
  `LEGAL_REGULATORY`, `ACCOUNTING`, `CAPITAL_RAISE`, `BUYBACK_DIVIDEND`, `PRODUCT`,
  `CUSTOMER_CONTRACT`, `SEC_FILING`, `BANKRUPTCY_DISTRESS`, `DELISTING`,
  `TRADING_HALT`, `CYBERSECURITY`, `LAYOFFS_COST_REDUCTION`, `MACRO_SECTOR`, `OTHER`,
  or `UNKNOWN`;
- `impact`: `POSITIVE`, `NEGATIVE`, `MIXED`, `NEUTRAL`, or `UNKNOWN`;
- `severity`: `LOW`, `MEDIUM`, `HIGH`, `SEVERE`, or `UNKNOWN`;
- `confidence`: finite number from 0 through 1;
- `reason`: concise factual financial/business interpretation, with no trade action.

Server-side validation rejects extra/action fields and invalid enums/ranges. Each attempt
preserves provider, model, classification version, classified-at, status, output or safe
failure code. Attempts are append-only; model/version changes never silently overwrite
history. The AI is forbidden from returning BUY, SELL, HOLD, sizing, prices, stops, or
allocation.

## Source confidence

V1 uses closed backend rules:

- `PRIMARY`: SEC/regulator publication or an identifiable company investor-relations /
  official company release;
- `HIGH_CONFIDENCE`: Reuters, Associated Press, Bloomberg, Dow Jones, or Wall Street
  Journal source metadata delivered by an approved provider;
- `STANDARD`: another named source delivered by Finnhub/Polygon with provider ID and URL;
- `UNKNOWN`: absent or unusable source provenance.

These are evidence-quality rules, not claims that every article is correct. Source facts
remain visible. No publisher reputation is inferred outside this declared list.

## Freshness, relevance, confidence, and no-lookahead

The provider refresh lookback is seven calendar days with overlap. An ordinary risk
assessment considers direct ticker-linked articles no older than seven calendar days as
of the decision. A classification is financially usable only at confidence `>= 0.75`.

Historical assessment requires both `published_at <= decision_as_of` and
`received_at/classified_at <= decision_as_of`; later-ingested evidence cannot be claimed
retroactively. Direct relevance comes from the requested ticker/provider relation and is
persisted; vague sector/macro articles cannot drive a company action.

## NewsRiskAssessment V1

Assessment is backend-owned and records assessment/policy version, as-of time, coverage
status, strongest usable adverse classification, source confidence, freshness, direct
relevance, and supporting article/classification IDs. Low-confidence or invalid/unknown
classification may be displayed but has no strong financial effect. Provider failure
does not delete articles or fabricate low risk.

## Frozen NewsDecisionOverlayPolicy V1

The overlay consumes the separately preserved base technical action.

### New entries

- Base action other than BUY can never be promoted to BUY by news.
- A base BUY remains BUY when a successful assessment has no qualifying adverse evidence.
- A direct, fresh, `STANDARD`-or-better, valid classification with confidence `>= 0.75`,
  `NEGATIVE` impact and `HIGH` or `SEVERE` severity produces `BUY_BLOCKED`, except broad
  `ANALYST_RATING`, `MACRO_SECTOR`, `OTHER`, and `UNKNOWN` events, which produce at most
  attention in V1.
- If refresh/classification coverage is unavailable, a new base BUY is not actionable:
  final effect `NEWS_ASSESSMENT_UNAVAILABLE`. This is an evidence-readiness block, not a
  claim of adverse news and never a news SELL.
- Positive news cannot create BUY or override another portfolio/risk rejection.

### Existing positions

- Base SELL always remains SELL regardless of positive news.
- Direct, fresh, usable adverse evidence below the exit rule produces `ATTENTION` only.
- News-driven `EXIT_REQUIRED` requires all of: `NEGATIVE`, `SEVERE`, confidence `>= 0.90`,
  publication within 72 hours, direct company relevance, `PRIMARY` or
  `HIGH_CONFIDENCE` source, and event type in `BANKRUPTCY_DISTRESS`, `DELISTING`,
  `TRADING_HALT`, `ACCOUNTING`, or `LEGAL_REGULATORY`. This effect has a distinct
  `NEWS_RISK_EXIT` reason and supporting IDs.
- Earnings/guidance, analyst ratings, management changes, capital actions, product news,
  layoffs, rumors, mixed/unknown evidence, and ordinary negative wording cannot force an
  exit in V1. They may block a new BUY or escalate attention when the applicable rule is
  met.

Policy identity is `news-decision-overlay-v1`; assessment/classifier identities are
separate. Thresholds and categories above are frozen before current-news inspection and
will not be tuned to holdings or outcomes.

Compatibility amendment before any successful classifier result: the initially declared
`gemini-2.5-flash-lite` returned HTTP 404 for this new API user, with Google's API
explicitly directing migration to `gemini-3.5-flash-lite`. Current official model docs
identify 3.5 Flash-Lite as stable with structured-output support. Only the unavailable
model identifier changed; the provider, controlled labels, prompt, schema, temperature,
thresholds, taxonomy, and decision policy remained frozen.

## Integration

The normal flow becomes base strategy/risk decision → time-aware NewsRiskAssessment →
versioned overlay → final action. APIs expose `base_action`, `news_effect`, `final_action`,
reason, policy version, coverage, and supporting evidence. ExecutionReadiness blocks
new entries when required news evidence is unavailable or adverse. Daily/Live Brief and
Position Intelligence show technical, news, and final layers without weakening existing
loss control. Future immutable Paper entry/exit evidence can capture policy/version and
supporting IDs; legacy Sprint 23 records remain untouched.

## API, Copilot, and UI

Add portfolio-scoped POST news refresh (open positions only by default) and persisted GET
news with typed filters. Refresh mutates only News evidence. Dashboard cards show source,
publication time, classification/provenance/status, assessment, and the technical/news/
final decision stack. Partial failure and unknown states remain explicit.

Deterministic Copilot answers latest-news, impact/severity, classifier/provider, block,
exit, and evidence questions from persisted facts; it never reclassifies merely to answer
and works with generative Copilot/Ollama disabled. React contains no financial policy.

## Controlled classifier evaluation

Before hosted execution, create one fixed evaluation set covering earnings beat/miss,
guidance raise/cut, bankruptcy, analyst upgrade/downgrade, dilution, buyback, regulatory
investigation, CEO resignation, major contract, layoffs/cost reduction, ambiguous mixed,
and irrelevant/no-impact news. Expected event/impact labels and reasonable severity
ranges are fixed manually. Report event accuracy, impact accuracy, severity
reasonableness, unknown handling, schema reliability, failures, unknowns, and latency.
Do not prompt/label tune after results. Ollama comparison occurs only if hosted quality is
materially poor and is documented first.

## Migration and testing

Use one additive asyncpg-safe Alembic migration with normalized article,
article-ticker, and append-only classification tables plus uniqueness/indexes. Verify
empty-PostgreSQL upgrade/current and Sprint 24 downgrade/upgrade.

Tests cover normalization/provenance/timezones/failures, all dedupe tiers and concurrency,
strict classifier validation/failure/fallback, no lookahead, buy/exit invariants, strategy
separation, readiness/brief/Paper provenance, deterministic Copilot, typed APIs, and UI
states. Controlled policy fixtures prove BUY_BLOCKED, EXIT_REQUIRED, positive-news-no-BUY,
and base-SELL-not-cancelled. Full backend/frontend gates and Edge/Playwright acceptance
run with generative Copilot disabled. Real provider acceptance is limited to current open
holdings and is repeated to prove dedupe; no portfolio, Paper, broker, or market-data state
is mutated.

## Completion criteria

Sprint 24 completes only when durable evidence, hosted-primary abstraction, deterministic
overlay, integrations, APIs/UI/Copilot, controlled acceptance, real provider acceptance
where credentials permit, migration checks, full gates, documentation, and the completion
report are finished. Limitations or hosted-key blockers are reported, never concealed.
No automatic order, scraping, strategy retuning, commit, push, or Sprint 25 work occurs.

## Final safety and BUY-coverage hardening addendum (frozen before acceptance)

The original controlled classifier result is useful interpretation evidence but is not
accurate enough for one model label to be the sole factual basis of `EXIT_REQUIRED`.
Sprint 24 therefore adds the following frozen safety gate without changing the taxonomy,
classifier prompt, confidence thresholds, or technical strategies.

### Hard-event confirmation V1

AI classification alone can never confirm a hard event. `EXIT_REQUIRED` retains all
original requirements and additionally requires deterministic `hard_event_confirmed`.
V1 confirmation requires both:

1. `PRIMARY` source provenance (SEC/regulator or identifiable official company/IR notice);
2. an explicit closed phrase associated with the same classified hard-event category in
   the persisted headline/provider summary.

Closed confirmations are: an explicit Chapter 7/11 or bankruptcy filing for
`BANKRUPTCY_DISTRESS`; an explicit exchange/regulator delisting notice for `DELISTING`;
an explicit regulator/exchange trading suspension or non-volatility halt for
`TRADING_HALT`; an explicit regulator enforcement/charge/finding of accounting fraud or
material financial misstatement for `ACCOUNTING`; and an explicit regulator order that
revokes/suspends authorization or operations for `LEGAL_REGULATORY`. Rumors, possible/
considered events, going-concern warnings without a filing, investigations/inquiries,
ordinary lawsuits, ordinary volatility halts, and AI labels without those facts are not
confirmed. They may produce `ATTENTION`, never a News exit.

V1 deliberately does not infer independent-source agreement or implement semantic
clustering. This narrower PRIMARY-source rule preserves a safe News exit path while
preventing a single model classification from supplying both interpretation and factual
confirmation.

### Refresh scopes and bounds

Refresh scope is explicit and typed:

- `OPEN_POSITIONS` (default): distinct current open holdings;
- `CANDIDATES`: caller supplies the already-filtered/ranked candidate tickers;
- `EXPLICIT_TICKERS`: caller supplies a deliberate small ticker list.

Candidate and explicit scopes accept at most 25 distinct normalized tickers and never
expand to the S&P 500. Empty explicit scopes are rejected. Provider calls remain
sequential. The portfolio plan remains deterministic and does not hide an external fetch;
the client/backend workflow explicitly refreshes the bounded final candidate set before
regenerating an actionable plan.

### Current coverage and actionable BUY

Stored articles are evidence history, not proof of current coverage. Each ticker refresh
persists provider window, attempt/completion time, provider success/failure, received
count, classified/unclassified count, and failure status. Assessment states are:
`CURRENT`, `STALE`, `PARTIAL`, `RATE_LIMITED`, `UNAVAILABLE`, and `NEVER_REFRESHED`.

For a new BUY, coverage is `CURRENT` only when the most recent provider attempt known by
the decision time:

- succeeded no more than 24 hours before `decision_as_of`;
- queried the full frozen seven-calendar-day window ending on the decision date; and
- has no unclassified/invalid/rate-limited fetched articles for that ticker under the
  active classifier identity.

A successful zero-article response is current provider and complete classifier coverage
(0/0); it is not a claim that the provider has universal news coverage. `STALE`,
`PARTIAL`, `RATE_LIMITED`, `UNAVAILABLE`, and `NEVER_REFRESHED` all fail closed for a new
BUY as `NEWS_ASSESSMENT_UNAVAILABLE`. Existing positions keep the authoritative technical
state; incomplete News coverage is exposed and may cause attention, but cannot fabricate
`EXIT_REQUIRED`.

Provider coverage and classifier coverage are separate. A successful provider fetch with
material unclassified articles is never represented as `NO_EFFECT` or no risk.

### Hosted rate-limit behavior

Only articles lacking a successful classification for the active provider/model/version
are eligible. They are ordered newest first. V1 has a configurable maximum of 10 hosted
classification attempts per explicit refresh and an optional 250 ms inter-request delay.
HTTP 429 is recorded, any `Retry-After` hint is captured for reporting, further attempts
stop immediately, and remaining articles remain pending for a later explicit refresh.
There is no busy retry or background worker. Gemini remains primary and Ollama fallback
remains disabled by default.

### Independent exit-safety evaluation

A second immutable fixture of 30 cases will be declared before hosted execution. It
freezes expected event type, impact, severity, and `eligible_for_hard_exit_evidence` and
focuses on false-positive exit risk. Classifier quality and final deterministic policy
false positives are reported separately. News-driven `EXIT_REQUIRED` stays enabled only
if unsupported EXIT_REQUIRED count is zero; otherwise V1 falls back to attention/review.

## Final Adanos aggregate policy V1 (predeclared)

This closed policy is fixed before integration acceptance and is not tuned against the
current holdings. Adanos is aggregate context and triage, never direct trade authority.

- An observation is `AVAILABLE` when it was observed within 24 hours and includes a score.
  This is AlphaPilot observation freshness only; Adanos supplies no provider data-generation
  timestamp, so `PROVIDER_DATA_TIMESTAMP_UNAVAILABLE` is always disclosed when absent.
- Evidence is `SUFFICIENT` only with at least 5 mentions and at least 2 sources. Otherwise
  it is `WEAK_EVIDENCE`, regardless of directional percentages. This prevents one mention
  from becoming strong authority.
- Broad adverse aggregate context requires sufficient evidence, `sentiment_score <= -0.25`,
  and `bearish_pct >= 60`. It produces `TARGETED_NEWS_REVIEW`, never BUY_BLOCKED or SELL.
- Broad positive context requires sufficient evidence, `sentiment_score >= 0.25`, and
  `bullish_pct >= 60`. It provides context only and cannot create BUY or cancel SELL.
- Everything else is `MIXED_OR_NEUTRAL`. Missing, stale, or invalid observations remain
  explicitly unavailable and never fabricate neutral sentiment.
- Targeted Gemini eligibility is deterministic: the article lacks a successful current
  classification, is within the seven-day window, and either the aggregate screen requests
  targeted review or persisted headline/summary contains a closed potential hard-event term
  (bankruptcy/Chapter 7/11, delisting, trading suspension, accounting fraud/material
  misstatement, or revoked/suspended authorization). Model output never selects model input.
- Aggregate adverse context can request investigation. Only attributable Finnhub evidence,
  optional targeted Gemini interpretation, and the unchanged `news-decision-overlay-v1`
  can ultimately block BUY or confirm an exit. Adanos alone cannot BUY, SELL, or exit.
