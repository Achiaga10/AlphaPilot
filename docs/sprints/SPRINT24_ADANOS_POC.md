# Sprint 24 Adanos News Sentiment API Proof of Concept

> Historical POC evidence: this document records the bounded evaluation that approved
> Option A. Its statements that Adanos was not yet persisted or connected describe that
> earlier implementation stage only. The approved final integration is documented in
> `docs/sprints/SPRINT24_COMPLETION_REPORT.md`; Adanos is now the persisted primary
> aggregate sentiment source for current research use.

## Scope and outcome

This is a non-authoritative proof of concept on
`feature/news-intelligence-foundation`. It does not replace Finnhub or Gemini, does not
change `news-decision-overlay-v1`, and does not connect aggregate sentiment to BUY, SELL,
HOLD, sizing, execution readiness, Daily Portfolio Brief, Copilot, or the frontend.

The implementation adds a provider-neutral in-memory contract and an Adanos adapter. It
adds no migration and persists no Adanos result. After the key was configured privately,
one bounded read-only acceptance measured the current 10 holdings in one compare request.
The key was not printed, logged, copied, or added to this report, and `backend/.env` was not
modified.

The measured recommendation is **OPTION A** for aggregate context only: Adanos should be
the primary aggregate News sentiment source, Finnhub should remain the attributable
drill-down and hard-event evidence source, Gemini should become secondary/deep analysis
when needed, and Ollama should remain disabled. This is an architecture recommendation,
not an activated policy change.

## Official Adanos audit

Official sources audited on 2026-09-01:

- [Adanos machine-readable API reference](https://api.adanos.org/llms.txt), version 1.49.1
- [Adanos interactive API documentation](https://api.adanos.org/docs)
- [Adanos pricing](https://adanos.org/pricing)
- [Adanos terms](https://adanos.org/terms)

The official contract is:

- Base URL: `https://api.adanos.org`.
- Authentication: `X-API-Key` with a `sk_live_...` key on protected endpoints.
- News ticker detail: `GET /news/stocks/v1/stock/{ticker}`.
- News multi-ticker comparison: `GET /news/stocks/v1/compare` with comma-separated
  `tickers`, deduplicated by the provider, maximum 10.
- Date parameters: inclusive UTC `from` and `to`; detail/compare default to the most
  recent seven UTC days. This POC sends explicit dates.
- Compare response: `period_days` and `stocks`, each with `ticker`, `company_name`,
  `buzz_score`, `trend`, `trend_history`, `mentions`, `source_count`, `sentiment_score`,
  `bullish_pct`, and `bearish_pct`.
- Detail additionally documents `daily_trend`, `top_sources`, and `top_mentions`.
- `sentiment_score` is directional aggregate sentiment. The API documentation does not
  define it as trading authority. AlphaPilot gives it none.
- The compare response documents no provider-generated as-of timestamp. AlphaPilot can
  record local `observed_at` and the requested UTC period, but `provider_timestamp` remains
  null. It must not invent a timestamp or claim a 10-minute cadence.
- `neutral_pct` is not documented on the compare response and remains null. It is not
  manufactured from bullish/bearish values.
- Compare errors: 400, 401, 403, 422, 429. Base stock detail distinguishes supported
  tickers with no data (`200`, `found=false`) from unsupported tickers (`404`, structured
  `unsupported_ticker`). Missing compare members are normalized as `UNKNOWN_TICKER`.
- Successful protected GETs expose monthly and burst rate-limit headers plus account type.
- Free: $0, 100 requests/minute, 250 requests/month, 30-day lookback, 41 protected
  endpoints, non-commercial use, no raw mentions and no direct text-sentiment endpoint.
- Hobby: 1,000 requests/minute, 250,000/month, 90-day lookback, non-commercial.
- Professional: 1,000 requests/minute, 2,500,000/month, up to 365 days, commercial use;
  raw News mentions and direct text sentiment are Professional-only.

Commercial deployment therefore cannot rely on the Free or Hobby plan. The API-call
efficiency is attractive, but licensing must be resolved before production use.

## POC architecture and normalized contract

`ExternalNewsSentimentProvider` exposes single- and multi-ticker reads. The concrete
`AdanosNewsSentimentProvider` uses the News compare endpoint and maps provider JSON into
`ExternalNewsSentimentSnapshot`:

- ticker, provider, local observation time;
- nullable provider timestamp;
- requested period start/end;
- sentiment score;
- nullable bullish, bearish, and neutral percentages;
- nullable mentions, source count, buzz score, and trend.

Failure codes are typed: `AUTHENTICATION_FAILED`, `RATE_LIMITED`, `UNKNOWN_TICKER`,
`PROVIDER_UNAVAILABLE`, and `MALFORMED_RESPONSE`. Missing fields remain null rather than
false zero. The adapter is read-only and in-memory. It is not wired into portfolio or News
services. `external_sentiment_has_trade_authority` explicitly returns false, including for
the most bearish possible snapshot.

The POC uses one compare call for up to 10 holdings rather than one call per ticker. A
larger future scope would require deterministic batches of 10, but full-universe use is
outside this task.

## Current portfolio and existing evidence baseline

A read-only query against the authoritative current ResearchPortfolio found:

`APA, APO, AXON, DXCM, ERIE, FAST, INTU, SLB, TSCO, UBER`

Existing persisted Finnhub/Gemini facts for these same tickers:

| Ticker | Articles | Classified | Positive | Negative | Mixed | Neutral | Unknown | Max severity | Coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| APA | 6 | 6 | 0 | 0 | 1 | 3 | 2 | LOW | CURRENT |
| APO | 28 | 15 | 8 | 0 | 0 | 7 | 0 | HIGH | PARTIAL |
| AXON | 17 | 4 | 0 | 0 | 0 | 4 | 0 | LOW | PARTIAL |
| DXCM | 11 | 0 | 0 | 0 | 0 | 0 | 0 | unavailable | PARTIAL |
| ERIE | 5 | 0 | 0 | 0 | 0 | 0 | 0 | unavailable | PARTIAL |
| FAST | 4 | 0 | 0 | 0 | 0 | 0 | 0 | unavailable | PARTIAL |
| INTU | 74 | 19 | 1 | 5 | 1 | 9 | 3 | HIGH | PARTIAL |
| SLB | 25 | 1 | 0 | 0 | 0 | 1 | 0 | LOW | PARTIAL |
| TSCO | 8 | 0 | 0 | 0 | 0 | 0 | 0 | unavailable | PARTIAL |
| UBER | 34 | 0 | 0 | 0 | 0 | 0 | 0 | unavailable | PARTIAL |

Totals: 212 articles and 45 latest successful classifications, or 21.23% article-level
classification coverage. One of 10 tickers has CURRENT complete coverage (10%); nine are
PARTIAL. These figures are a descriptive baseline, not ground truth.

## Real Adanos acceptance

Status: **PASS**.

- Endpoint: `GET /news/stocks/v1/compare`.
- Explicit inclusive UTC period: 2026-08-26 through 2026-09-01 (seven days).
- Tickers requested: APA, APO, AXON, DXCM, ERIE, FAST, INTU, SLB, TSCO, UBER.
- Tickers returned: the same 10 tickers; coverage 10/10 (100%).
- Missing/unsupported: none.
- Total protected API calls: exactly one.
- HTTP status: 200.
- Elapsed time: 1.013333 seconds.
- AlphaPilot `observed_at`: 2026-09-01T20:57:04.167608+00:00.
- Provider timestamp: not supplied in the payload. The HTTP `Date` header was
  2026-09-01T20:57:03 GMT, but that timestamps the response, not the underlying data.
- Account: Free.
- Monthly quota: limit 250, used 1, remaining 249, reset
  2026-10-01T20:55:18Z.
- Burst quota: limit 100, remaining 99, reset 2026-09-01T20:58:00Z.
- Cache control: `private, max-age=30`.

| Ticker | Score | Bullish % | Bearish % | Mentions | Sources | Buzz | Trend |
|---|---:|---:|---:|---:|---:|---:|---|
| APA | 0.273 | 67 | 0 | 12 | 4 | 28.5 | rising |
| APO | 0.286 | 60 | 4 | 50 | 15 | 47.4 | rising |
| AXON | 0.087 | 35 | 20 | 20 | 9 | 31.2 | rising |
| DXCM | 0.299 | 71 | 0 | 17 | 3 | 19.6 | stable |
| ERIE | 0.597 | 100 | 0 | 1 | 1 | 13.0 | rising |
| FAST | 0.240 | 50 | 0 | 18 | 2 | 18.1 | falling |
| INTU | 0.026 | 31 | 34 | 155 | 27 | 43.1 | falling |
| SLB | 0.339 | 73 | 0 | 30 | 12 | 54.2 | rising |
| TSCO | 0.207 | 67 | 7 | 15 | 2 | 16.6 | falling |
| UBER | 0.155 | 43 | 8 | 53 | 11 | 33.9 | falling |

The provider returned all normalized fields expected from the official compare contract.
It did not provide neutral percentage, top-source identities, or a provider-data timestamp.
No value was fabricated for those fields.

## Freshness and use-case audit

The live compare payload exposes the requested seven-day aggregate and seven daily trend
values but no explicit provider generation timestamp. The current response and cache
headers prove request availability, not the age of the underlying News aggregation.

- **A. Daily Portfolio News Context: YES, as aggregate context.** All 10 holdings returned
  in one second and nine had more than one mention. The breadth is useful for a daily
  summary, with an explicit weak-data warning for ERIE.
- **B. BUY Candidate News Gate: NOT YET APPROVED.** Coverage and source counts are
  promising enough to design a future deterministic review/block policy, but one snapshot,
  absent provider-data timestamps, Free-tier non-commercial licensing, and limited raw
  auditability are insufficient to grant financial authority now.
- Intraday position awareness: not established because timestamp/update semantics are
  unclear.
- **C. SELL/EXIT: NO DIRECT AUTHORITY.** Adanos alone can never trigger `EXIT_REQUIRED`.
  The required path remains adverse aggregate signal, targeted investigation, attributable
  Finnhub/primary evidence, existing deterministic hard-event confirmation, and only then
  a possible exit.

## SentiSense documentation-only audit

Official sources:

- [Stocks sentiment API](https://sentisense.ai/docs/api/stocks/)
- [Documents and News API](https://sentisense.ai/docs/api/documents/)
- [Sentiment API overview](https://sentisense.ai/stock-sentiment-api/)

Findings:

- Coverage is described as roughly 1,000 stocks for stock sentiment; ticker lists are
  discoverable through the Stocks API.
- Aggregate inputs cover News, Reddit, X, Substack, and finance YouTube. The stock
  sentiment response includes `bySource`, so News direction, mention share, and (for
  authenticated callers) source value can be separated descriptively from social sources.
- `GET /api/v1/stocks/{ticker}/sentiment` is single-ticker; the reviewed official docs do
  not document a multi-ticker aggregate-sentiment endpoint. Some unrelated stock fields
  support batches, but that must not be assumed for sentiment.
- The response includes `asOf` as an ISO date, score/direction/trend, 30-day comparison,
  mentions, source breakdown, drivers, and a sparkline. This is clearer daily freshness
  metadata than the reviewed Adanos compare contract, but not an intraday timestamp.
- The sentiment endpoints are documented as Free. The official overview states 1,000
  requests/month with no credit card. No real call was made.
- The Documents API is Free and exposes News/social source filtering, per-entity sentiment,
  reliability, URLs, and timestamps. It says News comes from 600+ publishers, while also
  warning that retrievable documents are not a complete audit trail of aggregate metrics.

Potential future role: SentiSense may provide broader conversation/social context with a
separable News slice, but it is not implemented or benchmarked here.

## Provider decision matrix

| Provider | Quality | Coverage/freshness | Efficiency/free tier | Source breadth/audit | Best use | Limitations |
|---|---|---|---|---|---|---|
| Adanos | Useful aggregate direction and breadth in the bounded sample | 10/10 holdings; underlying-data age remains unclear | 10 tickers in one 1.013-second call; Free 250/month, non-commercial | 1-27 sources/ticker; compare omits identities and raw mentions are paid-only | Primary aggregate daily context; future BUY-risk input after policy approval | No compare data timestamp; one-snapshot evidence; commercial use requires Professional |
| Finnhub + Gemini | Existing durable article evidence; classifier quality is imperfect | 212 articles for holdings; 45 classified; 1/10 CURRENT | Finnhub calls plus per-article Gemini calls caused quota pressure | Article/source IDs and timestamps support hard-event audit | Primary drill-down, deterministic hard-event confirmation | Gemini throughput failures and PARTIAL coverage |
| SentiSense | Documentation indicates per-entity/source sentiment | Roughly 1,000 stocks; `asOf` daily date | Free sentiment; overview says 1,000 requests/month; no documented sentiment batch | 600+ News publishers claimed; News/social separation and reliability fields | Possible broader second opinion | No live validation; aggregate score receipts are incomplete by provider disclosure |
| Ollama | Not benchmarked | Not evaluated | Local fallback candidate | Same strict classifier abstraction can preserve provenance | Fallback if external APIs are insufficient | Not started, downloaded, or required in this POC |

## Same-ticker descriptive comparison

Neither provider is treated as ground truth. `Max` is the maximum severity among the
latest persisted successful classifications. The final column uses only the four declared
comparison labels.

| Ticker | Adanos score / bull / bear | Mentions / sources / buzz / trend | AlphaPilot articles / classified | P/N/M/Ntrl/U | Max / coverage | Comparison |
|---|---|---|---|---|---|---|
| APA | 0.273 / 67% / 0% | 12 / 4 / 28.5 / rising | 6 / 6 | 0/0/1/3/2 | LOW / CURRENT | DISAGREEMENT |
| APO | 0.286 / 60% / 4% | 50 / 15 / 47.4 / rising | 28 / 15 | 8/0/0/7/0 | HIGH / PARTIAL | AGREEMENT |
| AXON | 0.087 / 35% / 20% | 20 / 9 / 31.2 / rising | 17 / 4 | 0/0/0/4/0 | LOW / PARTIAL | AGREEMENT |
| DXCM | 0.299 / 71% / 0% | 17 / 3 / 19.6 / stable | 11 / 0 | 0/0/0/0/0 | unavailable / PARTIAL | INSUFFICIENT_EXISTING_CLASSIFICATION |
| ERIE | 0.597 / 100% / 0% | 1 / 1 / 13.0 / rising | 5 / 0 | 0/0/0/0/0 | unavailable / PARTIAL | INSUFFICIENT_ADANOS_DATA |
| FAST | 0.240 / 50% / 0% | 18 / 2 / 18.1 / falling | 4 / 0 | 0/0/0/0/0 | unavailable / PARTIAL | INSUFFICIENT_EXISTING_CLASSIFICATION |
| INTU | 0.026 / 31% / 34% | 155 / 27 / 43.1 / falling | 74 / 19 | 1/5/1/9/3 | HIGH / PARTIAL | AGREEMENT |
| SLB | 0.339 / 73% / 0% | 30 / 12 / 54.2 / rising | 25 / 1 | 0/0/0/1/0 | LOW / PARTIAL | INSUFFICIENT_EXISTING_CLASSIFICATION |
| TSCO | 0.207 / 67% / 7% | 15 / 2 / 16.6 / falling | 8 / 0 | 0/0/0/0/0 | unavailable / PARTIAL | INSUFFICIENT_EXISTING_CLASSIFICATION |
| UBER | 0.155 / 43% / 8% | 53 / 11 / 33.9 / falling | 34 / 0 | 0/0/0/0/0 | unavailable / PARTIAL | INSUFFICIENT_EXISTING_CLASSIFICATION |

APA is the only directional disagreement: Adanos was bullish while existing classified
evidence was mixed/neutral/unknown rather than positive. There was no strong bearish
Adanos result against neutral/positive Gemini evidence and no strong bullish Adanos result
against negative Gemini evidence. INTU was near-balanced in Adanos and predominantly
neutral with some negative classifications, so it was treated as agreement rather than a
strong conflict.

Adanos supplied aggregate context for every ticker whose persisted coverage was PARTIAL.
It especially filled directional context where AlphaPilot had zero successful
classifications: DXCM, FAST, TSCO, and UBER. ERIE also returned, but one mention from one
source is explicitly insufficient Adanos data. SLB had broad Adanos evidence but only one
existing neutral classification. These are coverage improvements, not validation that
Adanos is correct.

## Tests and quality gates

Focused fake-response coverage validates:

1. successful compare normalization;
2. nullable optional fields;
3. absent/unknown ticker mapping;
4. authentication failure;
5. rate limiting;
6. malformed payload failure;
7. ticker normalization/deduplication;
8. batch ordering and maximum size;
9. no secret returned or logged by the result;
10. no direct BUY/SELL authority.

Exact focused command:

`cd backend; $env:DEBUG='false'; uv run pytest tests/news/test_external_sentiment.py -vv`

Result: 8 passed in 1.50 seconds.

Final backend command:

`cd backend; $env:DEBUG='false'; .\run_checks.ps1`

- Ruff and format check: PASS (274 files checked; one POC test file was normalized by the
  gate formatter, then Ruff passed).
- mypy: PASS across 187 source files.
- pytest: PASS, 411 tests in 62.65 seconds.
- Overall backend gate: PASS.

## Decision and next step

Recommendation: **OPTION A**.

Adanos materially improves the aggregate coverage problem: it returned all 10 holdings in
one request, including four useful directional snapshots where Gemini had zero successful
classifications. That is substantially better for broad daily context than the existing
21.23% article-classification completion. It does **not** solve attributable article
classification, provider-timestamp freshness, primary-source confirmation, or hard-event
auditability. Finnhub remains necessary, and Gemini remains useful for targeted/deep
interpretation rather than mandatory classification of every article.

The recommendation is therefore: Adanos primary for aggregate News context; Finnhub for
drill-down and hard-event evidence; Gemini secondary when deeper classification is needed;
Ollama disabled. A future BUY-risk policy is plausible but requires separately declared,
reviewed rules and further time-sampled evidence. No such policy was implemented here.

Ollama does not need evaluation now because the external aggregate API met the bounded
coverage and efficiency objective. It remains only a later fallback candidate if ongoing
Adanos evidence proves stale, unreliable, operationally unavailable, or commercially
unsuitable.

No migration, portfolio mutation, Paper mutation, broker action, frontend change, policy
change, Gemini removal, Ollama call, or full-universe fetch occurred.
