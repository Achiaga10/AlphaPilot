# AlphaPilot Sprint 14 Completion Report

## 1. Sprint goal

Sprint 14 moved normal strategy configuration authority from the browser into
an immutable, versioned backend Strategy Profile layer. Portfolio Plan clients
now choose a strategy and selection policy; the backend resolves sizing and the
frozen strategy parameters. Sprint 15 was not started.

## 2. Previous client-owned configuration problem

The high-level browser request previously supplied `sizing_policy`, EMA exit
mode/threshold, and Micho entry mode. The backend validated some frozen values,
but the browser still appeared authoritative and duplicated research
classifications in `policyClassifications.ts`. A stale or modified client could
therefore attempt to select a sizing policy that did not match the approved
strategy-specific research baseline.

## 3. Final Strategy Profile architecture

`strategy/profile.py` contains frozen `StrategyProfile` dataclasses, stable
enums, a deterministic ordered registry, and strict strategy/identity
resolvers. The normal flow is:

`PortfolioPlanRequest -> resolve profile -> explicit orchestrator -> decision plan`.

The existing orchestrator remains explicit and reusable. The lower-level
decision API remains configurable. Global risk configuration remains separate.

## 4. Exact EMA profile

- ID/version: `ema20-pullback-v1` / `1`
- classification: `PROMISING_RESEARCH_BASELINE`
- entry: existing EMA20 Pullback reclaim entry
- selection: user-selectable; recommended `relative-strength-20`
- sizing: `equal-slot`
- strategy exit: `HYBRID`, frozen threshold `2%`
- default protective stop: `NONE`
- default profit management: `NONE`
- informational research-only stop candidate: static `3 × ATR14`

## 5. Exact Micho profile

- ID/version: `micho-150-v1` / `1`
- classification: `PROMISING_RESEARCH_BASELINE`
- entry: Micho V1 `BOTH`
- selection: user-selectable; recommended `relative-strength-20`
- sizing: `atr-volatility-normalized`
- strategy exit: existing close below SMA150
- default protective stop: `NONE`
- default profit management: `NONE`
- informational research-only stop candidate: static `1.5 × ATR14`

## 6. Profile identity/versioning semantics

Profile IDs are stable semantic identifiers and `version` is an explicit
positive integer. The resolver rejects unknown IDs and stale versions. Frozen
dataclasses and tuple-backed registry output prevent accidental mutation. A
profile configuration change must produce a new version and therefore a new
plan fingerprint.

## 7. Research classifications

Both normal profiles are `PROMISING_RESEARCH_BASELINE`. This is a research
classification, not `PRODUCTION_READY`. ATR-risk remains available through
explicit research interfaces but is not either normal profile.

## 8. Default protective-stop status

Both profiles explicitly return `protective_stop_default = NONE`. No automatic
or broker stop was introduced.

## 9. Research-only stop overlays

EMA static 3× ATR14 and Micho static 1.5× ATR14 are returned only as
informational `research_only_stop_candidate` facts. They are not active plan
rules or defaults.

## 10. Profit-management status

Both profiles explicitly return `profit_management_default = NONE`. Sprint 12
profit candidates remain inactive.

## 11. Selection-policy behavior

Selection remains a normal user choice between RS20 and ticker-ascending.
Profiles recommend RS20 and list both allowed policies. Ticker-ascending remains
the deterministic non-alpha control. RS20 remains Research Ranking Baseline V1,
not universal production alpha.

## 12. Global risk-config treatment

`PortfolioRiskConfig` and `/portfolio/risk-config` are unchanged and remain
global inputs. No strategy-specific risk percentages, ATR periods, cash
reserves, sector limits, or position limits were invented.

## 13. Backend files created

- `backend/src/alphapilot/strategy/profile.py`
- `backend/tests/strategy/test_profiles.py`

## 14. Backend files modified

- `backend/src/alphapilot/api/routes/portfolio.py`
- `backend/src/alphapilot/schemas/portfolio.py`
- `backend/tests/api/test_portfolio_decisions.py`

## 15. Frontend files created

None. Existing typed API, state, page, and test modules were extended.

## 16. Frontend files modified

- `frontend/scripts/real-smoke.mjs`
- `frontend/src/api/portfolio.ts`
- `frontend/src/features/dashboard/PlanOverview.tsx`
- `frontend/src/features/portfolio/PlanForm.test.tsx`
- `frontend/src/features/portfolio/PlanForm.tsx`
- `frontend/src/features/portfolio/PortfolioWorkspace.tsx`
- `frontend/src/hooks/usePortfolioApi.ts`
- `frontend/src/pages/EvaluatePage.tsx`
- `frontend/src/pages/PlanDirtyState.test.tsx`
- `frontend/src/pages/PortfolioPage.test.tsx`
- `frontend/src/pages/PortfolioPage.tsx`
- `frontend/src/pages/SettingsPage.test.tsx`
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/test/fixtures.ts`
- `frontend/src/test/server.ts`
- `frontend/src/types/portfolio.ts`

## 17. Files deleted

- `frontend/src/features/portfolio/policyClassifications.ts`

The browser-owned classification/sizing matrix was deleted rather than renamed
or duplicated elsewhere.

## 18. Profile API contract

`GET /api/v1/portfolio/strategy-profiles` returns an ordered typed list with
identity/version, strategy/display name, classification, entry description,
recommended and allowed selection policies, sizing policy, strategy exit,
EMA/Micho parameters where applicable, default stop/profit state, and the
research-only stop candidate. Frontend runtime validation rejects malformed or
internally unsupported profile values.

## 19. Portfolio Plan request contract before/after

Before, the normal request included strategy, selection, sizing, EMA exit,
HYBRID threshold, and Micho entry mode. After, it includes strategy, selection,
as-of date, optional ticker scope, current portfolio state, and global risk
config only. Pydantic `extra="forbid"` rejects stale/malicious normal requests
that still try to supply sizing or strategy-rule overrides.

## 20. Portfolio Plan response contract before/after

The response retains applied strategy, selection, sizing, config, decisions,
readiness, dates, and evaluation identity. It now additionally returns the full
authoritative `strategy_profile`, including its stable ID and version. The
frontend also checks that response strategy and sizing agree with the profile.

## 21. Plan ID profile-version behavior

The SHA-256 plan fingerprint includes canonical JSON for the high-level request
and the full resolved profile. A focused regression proves that changing only
the profile version changes the plan ID.

## 22. Action preview/apply profile validation

Action requests now include `strategy_profile_id` and
`strategy_profile_version`. The backend resolves that exact identity and rejects
unknown/stale versions, sizing mismatches, and decision exit-context strategy
mismatches with HTTP 422. The UI sends response-owned profile identity, sizing,
and risk config. This is stateless mismatch protection; it is not durable plan
storage or cryptographic client authentication.

## 23. Lower-level research compatibility

`POST /api/v1/portfolio/decisions`, the explicit decision engine, and the
explicit orchestrator interface retain selectable sizing/configuration. Existing
equal-slot, ATR-risk, and ATR-volatility-normalized implementations remain
available for research and backtesting.

## 24. Backtesting compatibility

No backtesting class, CLI, accounting model, candidate ranking implementation,
T+1 execution rule, stop overlay, or frozen protocol changed. The full backend
suite, including Sprint 12 and Sprint 13 tests, passed.

## 25. Scanner compatibility

Strategy factory defaults were not changed. Scanner code and schemas were not
modified. All three Scanner API regressions passed in focused and full runs,
including completed-session filtering.

## 26. Evaluate identity regression status

Evaluate Stock continues to use the high-level plan request and now receives
profile-owned configuration. Exact requested ticker/backend target/rendered
ticker matching and latest-request-wins logic were untouched. All Evaluate
frontend regressions passed.

## 27. localStorage compatibility

The key remains `alphapilot.plan-draft.v1`. Loading is now explicitly parsed:
cash, positions, strategy, selection, as-of date, and ticker scope survive.
Legacy `sizingPolicy` is intentionally ignored. Controlled browser acceptance
loaded an old draft containing `sizingPolicy: atr-risk`, preserved its Micho,
ticker-control, cash, and other state, and displayed no sizing selector.

## 28. Settings-page changes

Settings loads profiles from the backend query/API layer. It displays profile
ID/version, resolved sizing, classification, strategy exit, NONE stop/profit
defaults, and research-only stop candidate, alongside the unchanged global risk
configuration. Malformed profile data renders a safe error.

## 29. Plan-form changes

The sizing selector was removed. The form retains Strategy and Selection
Policy, then shows the selected backend profile, classification, sizing, exit,
default stop/profit, and research-only stop note. The generated request contains
none of the removed authoritative fields.

## 30. Frontend domain-calculation audit

The frontend performs presentation, input normalization, draft bookkeeping,
and typed/runtime response validation only. It does not calculate strategy
signals, EMA/SMA rules, RS20, ATR, profile sizing, risk budgets, portfolio
constraints, or decision reasons. Generated-plan and action displays continue
using response-owned sizing and decision facts.

## 31. Backend focused test results

Command covered profiles, API plans, orchestration, actions, and Scanner:

`29 passed in 4.44s`; focused Ruff and mypy also passed. Coverage includes exact
profile facts/order/immutability, unknown/version errors, profile endpoint,
backend-resolved EMA sizing/exit, forbidden client sizing override, response
identity, profile-version plan fingerprint, and action mismatch rejection.

## 32. Full backend run_checks result

`$env:DEBUG='false'; .\run_checks.ps1` passed:

- Ruff check: PASS
- Ruff format check: PASS (`205 files left unchanged` on the final run)
- mypy: PASS across 141 source files
- pytest: 239 passed in 26.01s
- final result: `All checks passed!`

## 33. Frontend lint result

`npm run lint`: PASS with zero warnings.

## 34. Frontend test count/result

`npm test -- --run`: 16 test files and 68 tests passed.

## 35. Frontend production-build result

`npm run build`: PASS. TypeScript project build and Vite production bundling
completed successfully; 103 modules transformed.

## 36. Browser acceptance result

PASS. Headless Edge exercised the real built application workflow with
controlled API data and no live provider dependency. It verified legacy draft
migration, no sizing selector, both Micho and EMA profile displays, normal plan
requests without sizing/exit/entry overrides, three profile-bound actions,
reactive dashboard state, stale-plan behavior, partial/full manual sells,
responsive official logo rendering, admin progress, and no broker/order network
request. A separate read-only real-backend acceptance loaded the actual profile
endpoint and stored LDOS plans:

- EMA resolved `ema20-pullback-v1` v1 and `equal-slot`.
- Micho resolved `micho-150-v1` v1 and `atr-volatility-normalized`.
- both returned evaluation target `LDOS` from stored data without external fetch.

## 37. Confirmation no strategy rule changed

Confirmed. EMA20 Pullback, HYBRID 2%, Micho V1 BOTH, close-below-SMA150, RS20,
ATR calculations, risk constraints, signal generation, and T+1 semantics are
unchanged.

## 38. Confirmation no Sprint 12 stop became default

Confirmed. Both profile defaults are `NONE`; 3× and 1.5× ATR14 remain clearly
labelled research-only information.

## 39. Confirmation Sprint 13 reproducibility remained unchanged

Confirmed. No Sprint 13 model, repository, service, API, migration, snapshot,
hashing, provenance, completed-session, or replay file changed. All Sprint 13
tests passed within the 239-test full gate.

## 40. CI review/result

`.github/workflows/ci.yml` was inspected. It already runs backend Ruff, format,
mypy, migrations, full pytest, and frontend lint/test/build on Linux. No CI
change was required because Sprint 14 adds no dependency, service, migration,
or uncovered quality command.

## 41. Current limitations

- Profiles are code-versioned, not persisted or administered dynamically.
- Stateless action validation cannot replace durable authenticated plan/account
  storage or cryptographic request integrity.
- Current portfolio state remains browser supplied; there is no live broker
  synchronization or authenticated account persistence.
- Normal historical research retains current-constituent survivorship bias and
  the point-in-time universe limitation.
- RS20 remains a research baseline; SPY remains an imperfect benchmark.
- Daily bars retain intraday path ambiguity; final open positions remain marked
  to market according to existing semantics.
- Research-only stop candidates are informational and not executable orders.

## 42. What Sprint 14 proved

AlphaPilot can centrally bind a strategy to an immutable, explainable,
versioned normal research configuration; expose it through typed APIs; prevent
the normal browser from selecting sizing or strategy exits; incorporate it into
plan identity; carry it through stateless action validation; migrate old local
drafts safely; and preserve all existing research, Scanner, Evaluate, and data
reproducibility behavior.

## 43. What Sprint 14 did NOT prove

It did not prove either profile production-ready, create new alpha, validate a
new strategy, tune a parameter, activate Sprint 12 stops, provide live broker
state, establish durable plan/account security, eliminate survivorship bias, or
create the Sprint 15 Strategy Lab.

## 44. Recommendation for Sprint 15 Strategy Lab

After user review and Git publishing, proceed to a formal Strategy Lab workflow
that starts from a frozen dataset snapshot and requires deterministic rules,
declared development, configuration freeze, untouched validation, temporal
folds, costs, trade diagnostics, and an explicit classification. Do not add a
new strategy until that protocol exists.

## 45. Exact commands executed

Material commands included:

```powershell
git status --short
git branch --show-current
git log --oneline -10
git pull
git checkout -b feature/strategy-profiles

cd backend
$env:DEBUG='false'
uv run pytest tests/strategy/test_profiles.py tests/api/test_portfolio_decisions.py tests/portfolio/test_orchestration.py tests/portfolio/test_actions.py tests/api/test_scanner.py -q
uv run ruff check src tests --fix
uv run mypy src
.\run_checks.ps1

cd ..\frontend
npm run lint
npm test -- --run
npm run build
npm run smoke:real

# Read-only actual backend acceptance, stored data only
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/portfolio/strategy-profiles
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/portfolio/plan `
  -ContentType application/json -Body <EMA-or-Micho-high-level-request>

git diff --check
git diff --stat
git status --short
```

Temporary local Vite processes started for browser acceptance were identified by
exact process tree and stopped afterward. The user's pre-existing local servers
were not stopped. No external market-data provider or broker endpoint was used.

## 46. Git status

Branch: `feature/strategy-profiles`.

The worktree is intentionally uncommitted. Modified Sprint 14 files, the deleted
client-owned policy table, and new profile/plan/report/test files are ready for
user review. No commit, push, PR, merge, force-push, or tag operation occurred.

## 47. Git diff stat

Before adding this untracked report, tracked diff stat was **23 files changed,
442 insertions, 144 deletions**. Untracked files are not counted by `git diff
--stat`; the created-file sections above and final `git status` are
authoritative. `git diff --check` passed; output contained only expected Windows
LF-to-CRLF working-copy notices.

Untracked files:

- `backend/src/alphapilot/strategy/profile.py`
- `backend/tests/strategy/test_profiles.py`
- `docs/SPRINT14_PLAN.md`
- `docs/SPRINT14_COMPLETION_REPORT.md`

## 48. Recommended commit message

`feat(strategy): add backend-owned versioned strategy profiles`
