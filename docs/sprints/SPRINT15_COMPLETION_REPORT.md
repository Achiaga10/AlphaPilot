# AlphaPilot Sprint 15 Completion Report

## 1. Goal and outcome

Sprint 15 completed successfully. AlphaPilot now has a deterministic Strategy
Lab foundation that governs a future strategy from a predeclared specification
through frozen-data development, explicit configuration freeze, untouched
validation, temporal folds, classification, and a human-reviewed profile
candidate. No new trading strategy was created or tuned.

## 2. Architecture

The implemented flow is:

```text
StrategySpecification + StrategyLabProtocol
  -> validate finalized frozen dataset and declarations
  -> DEFINED
  -> DEVELOPMENT evidence
  -> explicit immutable FROZEN configuration
  -> VALIDATION evidence
  -> FOLDS evidence
  -> CLASSIFIED
  -> optional StrategyProfileCandidate for human review
```

`StrategyLabService` owns lifecycle rules. A typed `StrategyLabRunner` boundary
supplies results, keeping governance separate from strategy execution and
portfolio accounting. The CLI is only an adapter.

## 3. Typed protocol

The JSON-compatible protocol records protocol version, typed strategy
specification, frozen dataset binding, development/validation periods, named
folds, closed candidate configurations, classification gates, and limitations.
The specification records strategy key/version/name/description, entry/exit
facts, lookback, allowed selection/sizing policies, declared parameters and
values, and research notes.

## 4. Frozen dataset requirement

Formal research requires a non-null `DatasetBinding` whose snapshot UUID,
dataset SHA-256, and universe SHA-256 exactly match a finalized,
value-reproducible Sprint 13 manifest resolved through an injected boundary.
Missing, unknown/mismatched, draft, or non-reproducible datasets fail before an
experiment is defined. Operational-current data is not a formal Lab input.

## 5. Stages

Stages are exactly `DEFINED`, `DEVELOPMENT`, `FROZEN`, `VALIDATION`, `FOLDS`,
and `CLASSIFIED`. Each transition accepts only its immediate predecessor.
Validation cannot run before freeze; folds cannot run before validation;
classification cannot run before complete fold evidence.

## 6. Declared parameters and anti-retuning

Every parameter name and allowed value is closed in the specification.
Candidates with unknown/missing parameters, undeclared values, disallowed
selection/sizing policies, duplicate labels, or duplicate parameter names are
rejected. Development runs only declared candidates. Freeze selects exactly one
candidate with development evidence. Validation/folds accept only that exact
immutable object, preventing post-development retuning.

## 7. Period and fold rules

Dates must be well formed. Development and validation cannot overlap, and
validation must follow development. Fold labels must be unique and fold ranges
must not overlap. All folds are predeclared and all must be present before
classification.

## 8. Experiment identity

Identity is lowercase SHA-256 over canonical UTF-8 JSON with sorted keys and
stable date/Decimal/UUID/enum encoding. It includes protocol/strategy versions,
snapshot UUID and hashes, periods/folds, declared candidate space, selection,
sizing, costs, gates, limitations, and—after freeze—the selected frozen
configuration. Semantically unordered candidate/parameter collections are
canonicalized. Identical inputs reproduce; any material strategy, dataset,
cost, period, or frozen-configuration change changes identity.

## 9. Cost metadata

Candidate configurations use the existing `CostScenarioName` registry. Every
run evidence record expands the scenario to exact commission per order and
slippage bps per side. No cost formula was duplicated or changed.

## 10. Results and existing metric reuse

`StrategyLabResultSummary` records final equity, return, CAGR, max drawdown,
Sharpe, Calmar, profit factor, win rate, completed trades, exposure, turnover,
realized/unrealized P&L, and top-five positive-P&L concentration.
`summarize_portfolio_result()` maps existing `MultiPortfolioRunResult` metrics
and attribution directly; it does not recalculate financial formulas.

## 11. Git provenance

Each development/validation/fold evidence record captures run Git HEAD and
dirty status through Sprint 13's existing `capture_git_revision()` convention.
Source diffs are not stored.

## 12. Classification model

The only classifications are `REJECTED`, `RESEARCH_ONLY`, and
`PROMISING_RESEARCH_BASELINE`; `PRODUCTION_READY` cannot be constructed. Typed
gates support minimum validation-return retention, maximum drawdown, minimum
Sharpe/Calmar, and minimum positive-fold consistency. This is a configurable
research governance mechanism, not a universal strategy-quality formula.
Classification requires complete evidence, deterministic reasons, and declared
limitations.

## 13. StrategyProfileCandidate and human boundary

Only a qualifying `PROMISING_RESEARCH_BASELINE` classification creates a typed
`StrategyProfileCandidate`. It contains experiment/strategy identity, the exact
frozen configuration, classification, evidence summary, and
`requires_human_review=true`. The existing Sprint 14 profile tuple/registry is
never imported for mutation and remained object-identical in regression tests.

## 14. CLI

Added `alphapilot-strategy-lab`. It accepts `--protocol`, `--stage`, optional
`--results`, `--freeze-configuration`, and `--output`. Supported stages are
`validate-protocol`, `defined`, `development`, `freeze`, `validation`, `folds`,
and `classify`. It validates the snapshot against the existing repository and
replays later stages from typed deterministic result summaries. Default output
is `backtest_reports/strategy_lab/experiment.json`, already Git-ignored.

## 15. Files created

- `backend/src/alphapilot/strategy_lab/__init__.py`
- `backend/src/alphapilot/strategy_lab/models.py`
- `backend/src/alphapilot/strategy_lab/identity.py`
- `backend/src/alphapilot/strategy_lab/service.py`
- `backend/src/alphapilot/strategy_lab/results.py`
- `backend/src/alphapilot/strategy_lab/reporting.py`
- `backend/src/alphapilot/strategy_lab/parsing.py`
- `backend/src/alphapilot/cli/strategy_lab.py`
- `backend/tests/strategy_lab/conftest.py`
- `backend/tests/strategy_lab/test_protocol.py`
- `backend/tests/strategy_lab/test_stages.py`
- `backend/tests/strategy_lab/test_identity_and_classification.py`
- `backend/tests/strategy_lab/test_cli.py`
- `docs/SPRINT15_PLAN.md`
- `docs/SPRINT15_COMPLETION_REPORT.md`

## 16. Files modified

- `AGENTS.md`
- `backend/pyproject.toml`
- `docs/PROJECT_STATE.md`
- `docs/DECISIONS.md`

No frontend, migration, database model, strategy, profile, Scanner, portfolio
accounting, trade-management, risk, ranking, or market-provider file changed.

## 17. Tests created

Forty-two collected Strategy Lab test cases cover the requested protocol, stage governance,
identity/reproducibility, classification, result mapping, serialization, and CLI
behaviors. They include missing/unknown/finalization snapshot failures,
date/fold overlap, undeclared parameters/values, exact freeze enforcement,
immutable configuration, deterministic identity/results, changed-input
sensitivity, operational-state isolation, metadata, all three classifications,
impossible production-ready classification, profile non-mutation, and every CLI
stage.

## 18. Exact commands

```powershell
git status --short
git branch --show-current
git log --oneline -10
git checkout main
git pull
git checkout -b feature/strategy-lab

cd backend
$env:DEBUG='false'
uv run ruff check src/alphapilot/strategy_lab src/alphapilot/cli/strategy_lab.py tests/strategy_lab
uv run ruff format --check src/alphapilot/strategy_lab src/alphapilot/cli/strategy_lab.py tests/strategy_lab
uv run mypy src/alphapilot/strategy_lab src/alphapilot/cli/strategy_lab.py
uv run pytest tests/strategy_lab -q
uv run pytest tests/strategy_lab tests/strategy/test_profiles.py tests/backtesting/test_sprint12_protocol.py tests/research_data tests/api/test_research_datasets.py tests/api/test_scanner.py tests/portfolio/test_orchestration.py -q
uv run ruff check src tests
uv run mypy src
uv run pytest tests/strategy_lab -q
./run_checks.ps1

git diff --check
git diff --stat
git status --short
```

Formatting was applied mechanically with `uv run ruff format` during focused
development. `DEBUG=false` was scoped to child commands only.

## 19. Focused test results

- Strategy Lab focused suite before the final frozen-identity regression:
  **41 passed**; the full gate included all **42** final Lab cases.
- Required Lab + Strategy Profile + Sprint 12 + Sprint 13 + Scanner + portfolio
  orchestration regression slice: **80 passed in 10.28s**.
- Focused Ruff: PASS.
- Focused mypy: PASS.

## 20. Full quality gate

`$env:DEBUG='false'; .\run_checks.ps1`:

- Ruff lint: PASS.
- Ruff format: PASS (`218 files left unchanged`).
- mypy: PASS across **149 source files**.
- pytest: **281 passed in 28.14s**.
- aggregate: **All checks passed**.

## 21. Reproducibility acceptance

The deterministic fixture binds a Sprint 13-shaped finalized snapshot UUID and
exact dataset/universe hashes. Two complete definitions/development/freezes/
validations with identical strategy, frozen configuration, dataset, costs, and
Git facts produced identical experiment IDs and evidence. Reordering candidate
declarations did not change identity. Changing strategy version, dataset hash,
cost scenario, validation period, or selected frozen configuration did.

An operational-state mutation between two snapshot-bound executions did not
change result evidence. Existing Sprint 13 PostgreSQL regressions additionally
proved immutable snapshot replay remains isolated from operational candle
mutation. No live provider was called.

## 22. Regression status

Strategy Profiles, Sprint 12 protocol/trade management, Sprint 13 versioning and
snapshot APIs, Scanner completed-session behavior, portfolio orchestration,
single-stock strategies, and the entire backend suite remain green.

## 23. Frozen-behavior confirmations

- No strategy was added or changed.
- EMA20 Pullback, HYBRID 2%, Micho V1 BOTH, and RS20 are unchanged.
- No Strategy Profile or normal Portfolio Plan default changed.
- No Sprint 12 stop became active/default.
- Sprint 13 versioning, hashing, provenance, and completed-session semantics are
  unchanged.
- No transaction-cost, T+1 execution, risk, sizing, or accounting rule changed.

## 24. Database, provider, frontend, and CI status

No migration or schema was needed. No external market-data/provider call ran.
The frontend was untouched, so no frontend/browser gate was run. Existing CI
already executes backend Ruff/format/mypy/full pytest and needs no change for
these dependency-free modules and script entry point.

## 25. What Sprint 15 proved

AlphaPilot can predeclare a closed research space, bind it to exact immutable
data, reject invalid periods/configuration drift, freeze one developed choice,
run untouched later evidence through a reusable boundary, reproduce canonical
identity/result artifacts, classify only after complete evidence, and generate
a human-review candidate without changing normal product configuration.

## 26. What Sprint 15 did not prove

It did not create alpha, validate a third strategy, run a new full-universe
experiment, prove any strategy production-ready, automate subjective research
judgment, promote a profile, eliminate survivorship bias, or implement an API,
agent, UI, broker, or Sprint 16 feature.

## 27. Known limitations

- Strategy Lab V1 is code/config/artifact driven; experiments are not persisted
  as database workflow entities.
- The CLI consumes precomputed typed result summaries for execution stages; a
  future concrete strategy registers an execution adapter to the same service.
- Gates are deliberately simple and require protocol-specific human judgment.
- Frozen current-constituent snapshots retain survivorship bias and are not
  point-in-time S&P membership.
- Legacy snapshot provenance may be partial even when values are reproducible.
- SPY remains an imperfect benchmark; daily OHLC retains intraday ambiguity;
  final open positions use existing mark-to-market semantics.
- Git SHA plus dirty state does not capture/store a source diff or environment
  image fingerprint.

## 28. Sprint 16 recommendation

After user review and Git publishing, use the Strategy Lab to define and test
the first new strategy through the full governed lifecycle. The strategy and
candidate space must be chosen and predeclared separately; Sprint 15 does not
choose or implement it.

## 29. Git status

Branch: `feature/strategy-lab`. The working tree contains only local,
uncommitted Sprint 15 changes. Raw report output would be ignored under
`backend/backtest_reports/`. No commit, push, PR, merge, force-push, or tag was
performed.

Modified tracked files:

- `AGENTS.md`
- `backend/pyproject.toml`
- `docs/DECISIONS.md`
- `docs/PROJECT_STATE.md`

Untracked files/directories:

- `backend/src/alphapilot/cli/strategy_lab.py`
- `backend/src/alphapilot/strategy_lab/`
- `backend/tests/strategy_lab/`
- `docs/SPRINT15_PLAN.md`
- `docs/SPRINT15_COMPLETION_REPORT.md`

## 30. Git diff stat

Final tracked `git diff --stat` reported **4 files changed, 43 insertions, 17
deletions**. Git does not count untracked source,
tests, plan, or this report in that statistic; the file lists above are
authoritative. `git diff --check` passed with only expected Windows LF-to-CRLF
working-copy notices.

## 31. Recommended commit message

`feat(research): add governed Strategy Lab foundation`

Sprint 16 has not been started.
