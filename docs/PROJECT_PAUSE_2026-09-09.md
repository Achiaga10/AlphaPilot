# PROJECT PAUSE — 2026-09-09

This is a state snapshot, not a roadmap. AlphaPilot feature development is paused
after the approved-BUY end-to-end hotfix.

## Current system state

AlphaPilot is an async FastAPI/PostgreSQL research application with a React UI. Its
operational deterministic strategies are EMA20 Pullback and Micho 150. Portfolio
Plans distinguish technical signal, candidate allocation, deterministic safety and
one final action. Only `final_action=BUY && is_final_actionable=true` is an
`APPROVED BUY`.

Micho uses its frozen SMA150 completed-close loss-control boundary and can produce
actionable BUYs. EMA20 retains its frozen HYBRID 2% exit and current-entry proximity
revalidation, but has no approved production numeric loss-control policy for new
BUYs; candidates that reach that gate remain research-only.

News Intelligence remains durable and attributable: Adanos aggregate context,
Finnhub attributable/hard-event evidence and targeted Gemini interpretation are
persisted under the existing provider architecture; Ollama remains disabled. News
is advisory-only for both operational strategies and cannot change any financial
decision or prevent Profile/Plan generation. Explicit bounded refresh remains
available, while normal Plan generation requires no News provider call.

The Portfolio pipeline is:

1. completed-session data/freshness and frozen technical strategy;
2. already-held and persistent user-exclusion checks;
3. EMA current-entry safety when applicable;
4. deterministic numeric loss-control readiness;
5. ranking, sizing, cash, position and sector constraints;
6. final backend action/actionability;
7. optional persisted News advisory context;
8. frontend rendering of the backend final authority.

## Strategy and research status

- Micho 150: operational deterministic profile; current read-only plan produced
  19 technical BUYs and 10 approved BUYs.
- EMA20 Pullback: operational deterministic profile; current plan produced 50
  technical BUYs and zero approved BUYs. Thirty passed entry geometry but correctly
  stopped at missing approved loss control.
- Achia EMA20 V1: isolated research strategy, rejected; not registered operationally.
- Shauli DAILY V1: isolated research strategy, rejected; validation/folds unopened.
- EMA20 protective-stop studies: no approved winner. Research was not reopened.

Historical S&P 500 research uses the current constituent list and therefore retains
survivorship bias.

## Verification snapshot

- Focused backend: 64 passed; Portfolio suite: 198 passed.
- Full backend: Ruff/format passed; mypy 199 source files; 645 tests passed.
- Focused frontend: 27 passed; full lint and 98 tests passed; production build passed.
- Controlled Edge acceptance passed for Micho and EMA20 against real read-only Plan
  generation. It reconciled UI/backend counts and labels and verified no Portfolio,
  Paper or broker mutation.
- No migration, research rerun, application-data write, stage, commit or push.

## Known technical debt and open blockers

- EMA20 has no approved numeric new-entry loss-control policy, so it cannot currently
  produce production-approved new BUYs even when technical and entry-safety gates pass.
- Live EMA entry revalidation depends on a current authoritative price. Unavailable
  evidence fails closed, and the affected ticker set can change between intraday
  read-only snapshots.
- Two current-universe names, FDXF and HONA, lacked sufficient Micho history in this
  snapshot.
- Historical current-constituent backtests retain survivorship bias.
- The working tree intentionally contains this hotfix plus pre-existing uncommitted
  research/backtesting work. Nothing has been staged or published.

## Recommended next decision

Review this snapshot and the dirty diff as one human-controlled handoff. If accepted,
commit/push only the intended coherent changes using the recommended message below;
otherwise separate or discard changes deliberately. Do not begin another strategy,
risk experiment, News project, broker automation or frontend expansion until the user
chooses a new phase.

Recommended commit message:

`fix(portfolio): restore deterministic approved buys for Micho and EMA20`
