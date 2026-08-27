# AlphaPilot Sprint 15 Plan — Strategy Lab Foundation

## Goal

Create a deterministic, reusable Strategy Lab that governs future strategy
research from predeclared specification through frozen-snapshot evidence and a
human-reviewed profile candidate. Sprint 15 validates the laboratory with
fixtures and existing infrastructure; it does not create or tune a strategy.

## Scope and non-goals

Scope includes typed strategy specifications, immutable protocols and workflow
state, parameter declaration enforcement, finalized Sprint 13 snapshot binding,
canonical experiment identity, structured result evidence, deterministic
classification gates, a profile-candidate handoff, a thin CLI, and focused
regression coverage.

There will be no new strategy, parameter search, profile/default mutation,
Sprint 12 stop promotion, database migration, frontend work, provider access,
broker integration, or Sprint 16 implementation.

## Architecture

```text
StrategyLabProtocol + StrategySpecification
    -> validate declarations and finalized frozen dataset
    -> StrategyLabExperiment (DEFINED)
    -> development evidence
    -> explicit immutable configuration freeze
    -> untouched validation evidence
    -> predeclared fold evidence
    -> rule-based classification
    -> optional StrategyProfileCandidate for human review
```

The domain service owns validation and transitions. Execution is injected
through a typed runner boundary so existing backtesting infrastructure or a
deterministic fixture can supply results without coupling governance to
portfolio accounting.

## Strategy specification and parameter candidates

A specification contains strategy key/version/name/description, entry and exit
configuration, required lookback, allowed selection and sizing policies,
declared parameter candidates, and research notes. Each tunable parameter has a
closed set of canonical JSON-compatible values. Unknown parameters, missing
parameters, and undeclared values fail before a run.

## Frozen dataset requirement

Formal runs require the UUID, dataset SHA-256, and universe SHA-256 of a
finalized, value-reproducible Sprint 13 `ResearchDatasetSnapshot`. The service
validates the manifest through an injected dataset boundary. Operational-current
data is never accepted as formal evidence, and no provider is called.

## Period and fold protocol

The protocol declares a development range, a later non-overlapping validation
range, and uniquely named temporal folds. Dates must be ordered; validation
cannot overlap development; folds cannot overlap one another. These periods are
fixed before results and an inconvenient fold cannot be removed afterward.

## Stages and anti-retuning semantics

Stages are `DEFINED`, `DEVELOPMENT`, `FROZEN`, `VALIDATION`, `FOLDS`, and
`CLASSIFIED`. Development runs declared configurations only. Freeze explicitly
selects exactly one previously evaluated configuration and returns immutable
state. Validation and every fold reject configuration drift. Studying another
value requires a new predeclared experiment identity.

## Experiment identity and Git metadata

Identity is lowercase SHA-256 of canonical UTF-8 JSON with sorted keys and
stable Decimal/date/enum encoding. It includes protocol version, strategy
identity/version, snapshot UUID and hashes, periods/folds, declared candidate
space, selection, sizing, and cost. Semantically unordered candidate values are
sorted canonically. Each execution records Git HEAD and dirty state using Sprint
13 conventions; source diffs are not stored.

## Cost and result metrics

Configurations reference existing `CostScenarioName` definitions and preserve
commission and per-side slippage metadata. Result summaries reuse current
portfolio outputs: final equity, total return, CAGR, max drawdown, Sharpe,
Calmar, profit factor, win rate, completed trades, exposure, turnover, realized
and unrealized P&L, and top-five positive-P&L concentration.

## Classification gates

Allowed classifications are `REJECTED`, `RESEARCH_ONLY`, and
`PROMISING_RESEARCH_BASELINE`. A typed gate set may require minimum return
retention, drawdown, Sharpe/Calmar, and fold consistency. Classification requires
deterministic reasons, complete development/validation/fold evidence, and known
limitations. It is not a universal quality formula and uses no AI judgment.

## Profile-candidate boundary

A promising classification may emit a typed `StrategyProfileCandidate` with
the frozen configuration and evidence for human review. It cannot write to or
mutate the Sprint 14 profile registry. Promotion is a future explicit code-review
decision.

## CLI and reporting

`alphapilot-strategy-lab` will be a thin adapter over the service. It consumes
JSON-compatible inputs, performs protocol/identity/stage operations, and writes
structured JSON under `backend/backtest_reports/strategy_lab/` by default.
Business rules remain outside argument parsing; the report root is Git-ignored.

## Testing and acceptance

Focused tests cover protocol dates/folds, parameter declarations, snapshot
requirements, all stage guards, immutable freeze, validation/fold reuse,
identity determinism and sensitivity, operational-data isolation, metric
mapping, classification prerequisites/gates/reasons/limitations, profile
candidate non-mutation, CLI JSON, and reproducibility. Existing Sprint 12,
Sprint 13, Strategy Profile, Scanner, and orchestration regressions must remain
green.

Acceptance uses a deterministic fake result executor bound to a frozen Sprint
13 fixture. Repeated identical inputs must produce the same identity and result;
one changed material input must change identity; operational candle mutation
must not affect snapshot-bound evidence. No live provider or frontend smoke is
needed.

## Completion criteria

- protocol, service, CLI, artifacts, and focused tests are complete;
- frozen-dataset and anti-retuning controls are proven;
- one final `$env:DEBUG='false'; .\run_checks.ps1` passes;
- no migration, frontend, strategy, profile, stop, Scanner, or provider behavior
  changes;
- `docs/SPRINT15_COMPLETION_REPORT.md` records exact evidence and Git state;
- Sprint 16 remains not started.
