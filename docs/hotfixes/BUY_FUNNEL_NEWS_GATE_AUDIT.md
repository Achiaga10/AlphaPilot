# BUY Funnel / News Gate Audit

## Status and scope

COMPLETE LOCALLY on `fix/portfolio-plan-consistency-ux`. This is a focused
post-Sprint-24 audit/hotfix, not Sprint 25. No commit, push, strategy research,
broker action, threshold tuning, or strategy/loss-control change was performed.

The outcome is deliberately not “make a ticker pass.” The corrected plan still
has zero final approved BUYs. The difference is that its reasons are now truthful,
mutually exclusive, and evaluated in the right order.

## Predeclared Option A correction

The following rule was written before corrected current-plan acceptance and was
not changed after observing the result:

1. Adanos aggregate coverage and Finnhub/Gemini article-classification coverage
   are separate facts. Routine unclassified Finnhub articles do not make a
   current, sufficient, non-adverse Adanos aggregate check incomplete.
2. A current Adanos observation with sufficient breadth and no adverse aggregate
   trigger passes only the News aggregate screen. It cannot create a BUY, cannot
   certify `NO_RISK`, and does not require routine Gemini classification.
3. Frozen Adanos thresholds remain unchanged. A sufficient adverse aggregate
   trigger requires bounded attributable Finnhub review, with Gemini used only
   in the deterministic deep-review path.
4. Weak Adanos evidence remains explicitly weak and follows a bounded attributable
   review path. It is never silently promoted to positive/neutral or demoted to
   adverse evidence.
5. Missing, stale, failed, or unsupported aggregate evidence remains typed
   unavailability. Generate Portfolio attempts one bounded candidate refresh when
   a candidate reaches News; there is no hidden manual-refresh prerequisite.
6. User-excluded, EMA20-entry-blocked, already-held, loss-control-ineligible, and
   portfolio/allocation-rejected BUYs stop before candidate News work.
7. Candidate refresh receives only the backend-selected final BUY shortlist, never
   the full universe. Existing candidate scope remains capped at 25 and the Adanos
   adapter batches no more than 10 tickers per request.
8. Positive aggregate sentiment cannot create a BUY. Aggregate sentiment alone
   cannot create a SELL or `EXIT_REQUIRED`. Existing PRIMARY-source hard-event,
   freshness, direct-relevance, SEVERE/NEGATIVE, and deterministic-confirmation
   requirements remain unchanged.

## Root cause

Three independent facts had been collapsed into “News blocked the last two BUYs”:

- `POST /api/v1/portfolio/plan` assessed persisted News but did not perform a
  candidate-scope refresh. A new candidate could remain `NEVER_REFRESHED` until a
  user discovered and ran a separate News refresh workflow.
- The post-Adanos service still computed readiness from every unclassified routine
  Finnhub article. That inherited all-article Gemini-completeness requirement made
  a sufficient non-adverse aggregate observation appear incomplete.
- The route sent two equal-slot allocation BUY rows to News even though EMA20 has
  no approved numeric loss-control policy. They were research allocations, not
  final execution-ready BUYs. The authoritative first blocker for both was therefore
  loss-control readiness, before News.

The first two items were real Option A workflow/readiness defects. The third was a
first-blocker attribution defect. Fixing all three removes accidental News deadlock
without weakening any safety rule.

## Pre-fix real reproduction

The real persistent ResearchPortfolio was evaluated read-only with EMA20 Pullback
HYBRID 2%, RS20, equal-slot sizing, and requested date `2026-09-02`.

| Fact | Result |
|---|---:|
| Plan ID | `ae2c73ac9bd962f2e06eda33` |
| Portfolio revision | 17 |
| Requested date | 2026-09-02 |
| Completed analysis session | 2026-09-02 |
| Evaluated tickers | 502 |
| Technical BUY signals | 65 |
| Pre-News allocation BUY rows | 2 |
| Final approved BUYs | 0 |

The old displayed rejection split was 37
`ENTRY_TOO_EXTENDED_ABOVE_EMA20`, 2 `ALREADY_HELD`, 24 `MAX_POSITIONS`,
and 2 `NEWS_ASSESSMENT_UNAVAILABLE`. That split described the last mutation of
each allocation row, not the authoritative hard-gate order.

## Exact two pre-News allocation candidates

### UBER

- Rank among the two selected allocation rows: 1.
- RS20: `0.1279350196381401545848695147`.
- Technical signal: BUY.
- EMA20 entry safety: `ELIGIBLE`.
- Entry/reference price: `76.4450`.
- Fixed completed signal-session EMA20: approximately `76.239966918`.
- Distance: approximately `0.205033082`, or `0.268931%`; inside the unchanged
  1% upper boundary.
- Loss control: policy `NONE`, no approved boundary, research-only execution
  readiness.
- Portfolio state: it fit one of the two remaining slots and passed sizing, cash,
  position-weight, and sector allocation checks. Its allocation-level reason was
  `BUY_APPROVED`, but it was not a final actionable BUY because loss control was
  unavailable.
- Adanos: an observation existed, observed
  `2026-09-01T21:15:32.762900Z`, requested period `2026-08-26` through
  `2026-09-01`; score `0.15500`, bullish `43.000%`, bearish `8.000%`,
  53 mentions, 11 sources, buzz `33.900`, trend `falling`, and no provider
  timestamp. It had been sufficient/non-adverse when current but was `STALE` at
  the September 4 audit decision instant.
- Finnhub: latest persisted state was `PARTIAL`; 38 ticker-associated articles
  existed. There was no policy-usable classified adverse article.
- Gemini: 14 persisted classification attempts were all `RATE_LIMITED`; zero
  successful classifications and zero usable adverse classifications. No Gemini
  call was made by Generate Portfolio itself—the attempts came from an earlier
  refresh. Under the old all-article rule these routine failures kept coverage
  partial; under corrected Option A semantics routine completion would not be
  required for a current sufficient non-adverse aggregate check.
- Pre-fix `NewsRiskAssessment`: coverage `PARTIAL`, effect
  `NEWS_ASSESSMENT_PARTIAL`, reason `News assessment coverage is PARTIAL`.
- Pre-fix overlay: base decision BUY, final action `DO_NOT_BUY`, route reason
  `NEWS_ASSESSMENT_UNAVAILABLE`.
- Why it became SKIP before the correction: partial persisted article/classifier
  coverage was treated as mandatory BUY readiness. Why it cannot be a final BUY
  after the correction: the earlier authoritative blocker is no approved loss
  control, so News is not consulted.

### CPRT

- Rank among the two selected allocation rows: 2.
- RS20: `0.1188173486011263032114635707`.
- Technical signal: BUY.
- EMA20 entry safety: `ELIGIBLE`.
- Entry/reference price: `32.1700`.
- Fixed completed signal-session EMA20: approximately `31.917492`.
- Distance: approximately `0.252508`, or `0.791126%`; inside the unchanged
  1% upper boundary.
- Loss control: policy `NONE`, no approved boundary, research-only execution
  readiness.
- Portfolio state: it fit the second remaining slot and passed sizing, cash,
  position-weight, and sector allocation checks. Its allocation-level reason was
  `BUY_APPROVED`, but it was not a final actionable BUY.
- Adanos: no persisted observation; no observed/provider timestamp, requested
  period, score, distribution, breadth, buzz, or trend existed. State was
  `UNAVAILABLE`/`NEVER_REFRESHED`, not bearish.
- Finnhub: zero persisted articles and no current attributable review.
- Gemini: not attempted. There was no article to classify and the plan endpoint
  did not own candidate refresh.
- Pre-fix `NewsRiskAssessment`: coverage `NEVER_REFRESHED`, effect
  `NEWS_ASSESSMENT_UNAVAILABLE`, reason
  `News assessment coverage is NEVER_REFRESHED`.
- Pre-fix overlay: base decision BUY, final action `DO_NOT_BUY`, reason
  `NEWS_ASSESSMENT_UNAVAILABLE`.
- Why it became SKIP before the correction: the missing hidden/manual candidate
  refresh left it permanently never-refreshed. Why it cannot be a final BUY after
  the correction: its earlier authoritative blocker is also no approved loss
  control, so it does not consume a provider call.

Neither candidate was rejected by confirmed adverse News. The old News result was
coverage/classifier unavailability in both cases.

## Implemented architecture

The plan route now delegates the News stage to a narrow `PortfolioNewsGate` after
strategy, current-entry revalidation, preferences, execution readiness, ranking,
and allocation. It derives a shortlist only from BUY decisions already marked
final-actionable by every cheaper gate. If the shortlist is nonempty, the route
automatically calls the existing `NewsService.refresh_portfolio` with
`CANDIDATES` and those exact tickers, then assesses the persisted result.

The service separates aggregate and attributable work:

- missing/stale Adanos -> typed aggregate unavailable/stale;
- sufficient current non-adverse Adanos -> `CURRENT`, `NO_EFFECT`, reason
  `NO_ADVERSE_AGGREGATE_EVIDENCE`, with no Finnhub/Gemini requirement;
- frozen adverse aggregate -> bounded Finnhub review and deterministic targeted
  Gemini classification;
- weak aggregate -> explicit weak/targeted review, never positive or adverse by
  inference;
- targeted Finnhub/Gemini failure -> an exact attributable or Gemini-unavailable
  reason, not adverse sentiment.

The response exposes compact `news_enrichment` diagnostics: shortlist and assessed
BUY tickers, Adanos requested/returned/reused/missing tickers and call count,
Finnhub target/call count, and Gemini attempt count.

The backend also returns `BuyFunnelSummary`. Every technical BUY is placed into one
terminal group in this precedence:

1. EMA20 entry safety blocked/unavailable;
2. explicit user exclusion;
3. already held;
4. loss-control unavailable;
5. position, sector, or cash/allocation constraint;
6. exact News aggregate/review/adverse blocker;
7. final approved BUY when all gates are complete;
8. other typed fallback.

The service asserts that the group total equals the technical BUY total. The UI
shows the backend totals and lets the user expand a group to see its backend-owned
ticker list; React does not infer financial classifications.

## Corrected real first-blocker waterfall

The single bounded post-fix Generate Portfolio request used the same persistent
portfolio and requested `2026-09-02` session:

| First/terminal stage | Count |
|---|---:|
| `TECHNICAL_BUY_SIGNAL` | 65 |
| `EMA20_ENTRY_SAFETY_BLOCKED` | 37 |
| `EMA20_ENTRY_REVALIDATION_UNAVAILABLE` | 0 |
| `USER_EXCLUDED` | 0 |
| `PORTFOLIO_POSITION_CONSTRAINT` (already held) | 2 |
| `LOSS_CONTROL_UNAVAILABLE` | 26 |
| `SECTOR_CONSTRAINT` | 0 |
| `CASH_ALLOCATION_CONSTRAINT` | 0 |
| `NEWS_AGGREGATE_UNAVAILABLE` | 0 |
| `NEWS_AGGREGATE_STALE` | 0 |
| `NEWS_WEAK_EVIDENCE` | 0 |
| `TARGETED_NEWS_REVIEW_REQUIRED` | 0 |
| `ATTRIBUTABLE_NEWS_UNAVAILABLE` | 0 |
| `GEMINI_REQUIRED_BUT_UNAVAILABLE` | 0 |
| `NEWS_BUY_BLOCKED_ADVERSE_EVIDENCE` | 0 |
| `OTHER` | 0 |
| `FINAL_APPROVED_BUY` | 0 |
| Rejected before News | 65 |
| Reached News | 0 |

Reconciliation: `37 + 2 + 26 + 0 = 65`. The former 24 max-position rows and
the two allocation BUY rows all lacked an approved EMA loss-control policy; that
earlier execution-readiness fact supersedes their later allocation/News outcomes.

## Single bounded real acceptance

- Real FastAPI health: succeeded.
- Real current ResearchPortfolio: loaded at revision 17.
- Real Paper Analytics: loaded.
- Real plan response: HTTP success; 502 evaluated, 65 technical BUYs, 65 stopped
  before News, 0 reached News, and 0 final BUYs; funnel reconciled exactly.
- Adanos candidate tickers requested: none.
- Adanos API calls: 0.
- Adanos returned/reused: none/none.
- Finnhub target calls: 0.
- Gemini targeted attempts: 0.
- Candidates reaching News but not BUY: none.
- Final approved BUY details: none.
- UI: Microsoft Edge loaded the real Vite app, submitted the real request, rendered
  `Portfolio plan generated`, rendered the backend BUY-funnel heading and the two
  matching 65-signal summaries. A redundant smoke assertion initially used a
  non-unique text locator and ended the harness after those product assertions;
  the reusable selector was corrected without issuing a second Generate request,
  preserving the one-request/quota constraint. The expandable ticker behavior is
  independently green in the frontend test suite.
- Post-run read-only state: ResearchPortfolio revision 17, cash `19711.7850`,
  8 positions; Paper Analytics 11 total / 10 open / 1 closed. No mutation endpoint
  was called and these values matched the captured pre-run state.
- Portfolio mutation: NO.
- Paper mutation: NO.
- Broker action: NO.

The real acceptance made no provider request because no candidate truthfully
survived the earlier loss-control gate. This is correct quota behavior, not a News
provider acceptance claim; provider branch behavior is covered with controlled
service and gate tests.

## Tests and commands

Focused backend verification:

```powershell
cd backend
$env:DEBUG='false'
uv run ruff check src tests/news tests/portfolio/test_news_gate.py
uv run mypy src
uv run pytest tests/news tests/portfolio/test_news_gate.py tests/portfolio/test_plan_consistency_and_exclusions.py tests/portfolio/test_daily_portfolio_brief.py tests/portfolio/test_orchestration.py tests/api/test_portfolio_decisions.py -q
```

Result: Ruff PASS; mypy PASS (189 source files); 85 tests PASS.

Full backend gate:

```powershell
cd backend
$env:DEBUG='false'
.\run_checks.ps1
```

Result: Ruff PASS; mypy PASS (189 source files); `452 passed`.

Full frontend gate:

```powershell
cd frontend
npm run lint
npm test -- --run
npm run build
```

Result: lint PASS; 16 files / 85 tests PASS; production build PASS. A final
`npm run lint` after adding/correcting the reusable smoke script also passed.

Real browser command (generative AI was not involved):

```powershell
cd frontend
node scripts/buy-funnel-news-gate-smoke.mjs
```

Read-only evidence inspection used only the existing current portfolio, Paper
Analytics, portfolio News, and News sentiment GET endpoints. No refresh or mutation
endpoint was called outside the single plan request.

## Files changed for this audit/hotfix

Created:

- `backend/src/alphapilot/portfolio/news_gate.py`
- `backend/tests/portfolio/test_news_gate.py`
- `docs/hotfixes/BUY_FUNNEL_NEWS_GATE_AUDIT.md`
- `frontend/scripts/buy-funnel-news-gate-smoke.mjs`

Modified for this audit/hotfix:

- `AGENTS.md`
- `backend/src/alphapilot/api/routes/portfolio.py`
- `backend/src/alphapilot/news/policy.py`
- `backend/src/alphapilot/news/service.py`
- `backend/src/alphapilot/portfolio/decisions.py`
- `backend/src/alphapilot/portfolio/orchestration.py`
- `backend/src/alphapilot/portfolio/sizing.py`
- `backend/src/alphapilot/schemas/news.py`
- `backend/src/alphapilot/schemas/portfolio.py`
- `backend/src/alphapilot/services/daily_portfolio_brief.py`
- `backend/tests/news/test_service.py`
- `backend/tests/portfolio/test_daily_portfolio_brief.py`
- `backend/tests/portfolio/test_orchestration.py`
- `backend/tests/portfolio/test_plan_consistency_and_exclusions.py`
- `docs/DECISIONS.md`
- `docs/PROJECT_STATE.md`
- `frontend/src/api/portfolio.ts`
- `frontend/src/features/portfolio/PlanReadinessBanner.tsx`
- `frontend/src/features/portfolio/PlanReadinessBanner.test.tsx`
- `frontend/src/test/fixtures.ts`
- `frontend/src/test/server.ts`
- `frontend/src/types/portfolio.ts`
- `frontend/src/utils/format.ts`

The working tree also contains approved, uncommitted files from the immediately
preceding portfolio-consistency/exclusion/UX hotfix. They were preserved and are
not misrepresented as new work in this section.

## Required final answers

1. **Technical BUY signals:** 65.
2. **Final approved BUYs before fix:** 0.
3. **Exact first-blocker waterfall:** 37 EMA20 entry-safety blocked, 2 already-held
   position constraints, 26 loss-control unavailable, every other blocker 0,
   final approved 0.
4. **Blocked before News:** 65.
5. **Tickers that reached News after correction:** none.
6. **The former two pre-News allocation candidates:** UBER and CPRT.
7. **Why each formerly became SKIP:** UBER had old `PARTIAL` all-article Gemini
   coverage (14/14 stored attempts rate-limited); CPRT was `NEVER_REFRESHED` because
   Generate Portfolio did not refresh candidates. Neither had adverse evidence.
   Both actually lacked approved loss control and now stop earlier.
8. **Was Adanos candidate coverage current?** UBER's old observation was stale at
   audit time; CPRT had none.
9. **Is candidate refresh automatic now?** YES, for the bounded shortlist that
   survives all cheaper gates.
10. **Was a hidden manual prerequisite involved?** YES before the correction; NO now.
11. **Did old all-article Gemini completeness affect readiness?** YES for UBER.
12. **Can sufficient current non-adverse Adanos continue without routine Gemini?** YES.
13. **Does adverse Adanos still trigger targeted review?** YES, with frozen thresholds.
14. **Does weak evidence remain explicit?** YES; it takes bounded targeted review.
15. **Does unavailable News remain explicit?** YES; it is not labeled bearish.
16. **Gemini calls before vs after:** the pre-fix stored UBER history had 14
   rate-limited attempts from an earlier refresh and plan generation itself made
   zero; the one corrected real plan made zero because zero candidates reached News.
17. **Adanos calls in real acceptance:** 0, correctly, with an empty final shortlist.
18. **Final approved BUYs after correction:** 0.
19. **Why still zero:** 37 failed unchanged EMA20 entry safety, 2 were already held,
   and 26 lacked an approved numeric loss-control policy.
20. **Is News/sentiment over-blocking?** **PARTIALLY before the fix.** It wrongly
   acted as the displayed final blocker for two candidates because of a hidden
   refresh dependency and inherited Gemini-completeness rule. It did not explain
   the economically correct final zero: both candidates already failed loss-control
   readiness. After the fix, News blocks none of this plan and is not over-blocking.
21. **Thresholds changed?** NO.
22. **EMA20 entry safety changed?** NO.
23. **Loss control weakened?** NO.
24. **SELL safety weakened?** NO.
25. **Backend full gate:** PASS, 452 tests; Ruff and mypy clean.
26. **Frontend full gate:** PASS, lint; 16 files / 85 tests; production build.
27. **Browser acceptance:** real Edge/FastAPI/Vite request and rendering passed;
   the post-render harness locator ambiguity is disclosed above and corrected
   without a second real request.
28. **Portfolio mutation?** NO.
29. **Paper mutation?** NO.
30. **Broker action?** NO.
31. **Git status:** `fix/portfolio-plan-consistency-ux`; 42 tracked files modified
   and 9 untracked files (51 entries total), combining the approved preceding hotfix
   with this audit. Untracked files are
   `backend/migrations/versions/d3f8a1b6c204_add_portfolio_ticker_preferences.py`,
   `backend/src/alphapilot/portfolio/news_gate.py`,
   `backend/tests/api/test_portfolio_ticker_preferences.py`,
   `backend/tests/portfolio/test_news_gate.py`,
   `backend/tests/portfolio/test_plan_consistency_and_exclusions.py`,
   `docs/hotfixes/BUY_FUNNEL_NEWS_GATE_AUDIT.md`,
   `docs/hotfixes/PORTFOLIO_PLAN_CONSISTENCY_UX.md`,
   `frontend/scripts/buy-funnel-news-gate-smoke.mjs`, and
   `frontend/src/features/portfolio/ExcludedTickersPanel.tsx`. No commit or push
   was made.
32. **Recommended commit message:**
   `fix: reconcile buy funnel and automate bounded news gating`

## Bottom line

The original zero-BUY result was not evidence that adverse sentiment rejected every
opportunity. News incorrectly appeared to reject two rows because candidate refresh
was not orchestrated and old Gemini-completeness semantics survived the move to
Adanos-first Option A. That architecture is now corrected. The same real plan still
has zero approved BUYs, but all 65 are stopped before News for explicit unchanged
safety reasons. The product can now explain that result without double counting,
without wasting provider quota, and without weakening entry, loss-control, or exit
safety.

## Subsequent final-action semantics clarification

The later IBKR/EOG UI audit found that this correctly reconciled zero-BUY result still
displayed intermediate `decision=BUY` / `reason=BUY_APPROVED` fields as though they were
terminal approval. The follow-up semantics hotfix does not change this audit's financial
result or gate order. It makes `final_action`, `terminal_reason`, and actionability the
sole action authority; preserves the allocation reason separately; and aligns counts,
filters, rendering, and apply controls. See
`docs/hotfixes/FINAL_BUY_ACTIONABILITY_SEMANTICS.md`.
