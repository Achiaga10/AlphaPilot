# Sprint 17 Plan — Position Monitoring, Reconciliation, and Daily Sync

Status: IN PROGRESS  
Branch: `feature/position-monitoring`

## Goal and scope

Make persistent research positions monitorable under their exact stored Strategy
Profile, add explicit audited reconciliation, and automate safe completed-session
daily candle synchronization. AlphaPilot remains advisory: no automatic trade or
broker order is authorized.

The sprint adds backend-owned HOLD / ATTENTION / SELL monitoring, sticky SELL
triggers, idempotent history, typed policy facts, cash delta/external-position/
position-correction workflows, a safe weekday scheduler, and compact Portfolio,
Dashboard, and Data Management presentation.

## Frozen monitoring semantics

EMA20 Pullback reuses HYBRID 2% exactly:

- `close >= EMA20`: HOLD.
- `EMA50 <= close < EMA20` with the existing 2% strong-trend condition: ATTENTION.
- `close < EMA50`, or loss of EMA20 without that exception: SELL.

Micho 150 reuses close-below-SMA150 exactly:

- `close > SMA150` and `low >= SMA150`: HOLD.
- `low < SMA150` and `close >= SMA150`, including equality: ATTENTION.
- `close < SMA150`: SELL.

No new threshold, stop, trail, or target is introduced. ATTENTION may recover;
a real SELL is latched until full exit.

## Readiness, provenance, and policy facts

Monitoring is READY with a typed status or UNAVAILABLE with no status and a
typed reason. Missing/insufficient data, unsupported profiles, legacy imports,
and manual positions never silently become HOLD. Current normal profiles expose
protective stop, trailing stop, and profit target as NONE; Sprint 12 findings
remain research-only.

## Persistence and reconciliation

Use the smallest additive schema for unique position/day monitoring snapshots,
sticky exit facts, reconciliation audit facts, and scheduler state. Cash changes
are signed Decimal deltas. External positions have `MANUAL_EXTERNAL` provenance
and no fabricated strategy. Position corrections retain before/after values.
Every mutation requires expected revision, locks transactionally, increments the
portfolio revision, and makes old plans stale. No destructive delete or tax lots.

## Daily sync

The scheduler is disabled by default and in tests/CI unless explicitly enabled.
It runs Monday-Friday at 16:30 America/New_York, after the existing 16:15
completed-session boundary, and reuses existing market-sync services for the
active S&P universe, custom tracked tickers, and SPY. No newer completed SPY
session is a safe no-op. Failure preserves prior monitoring, and missing fresh
position data never fabricates HOLD. Manual and scheduled sync share post-sync
monitoring orchestration.

## API, UI, tests, and completion

Add typed monitoring, reconciliation, and scheduler-status APIs while preserving
Sprint 16 contracts. React renders backend facts and refetches authoritative
state after mutation/sync. Focused tests cover frozen semantics, stickiness,
readiness, idempotency, audit/revision, scheduler safety, completed sessions, and
regressions. Completion requires backend and frontend quality gates, one
controlled browser acceptance, and `docs/sprints/SPRINT17_COMPLETION_REPORT.md`.
Sprint 18 is not started.
