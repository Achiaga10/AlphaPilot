# AlphaPilot Sprint 13 Plan

## 1. Reproducibility problem

Sprint 12 showed that unchanged code and configuration can produce materially
different historical results after mutable `DailyCandle` rows are refreshed.
The current table stores only the newest OHLCV value and cannot reconstruct an
overwritten value or prove its source/feed. Sprint 13 must make future research
inputs replayable without attempting to reconstruct already-lost history.

## 2. Operational data versus frozen research data

`DailyCandle` remains the latest operational materialization used by normal UI,
Scanner, and current evaluation. Append-only candle versions preserve every
materially distinct completed-session OHLCV observed from Sprint 13 onward.
Frozen research snapshots bind an exact universe and exact version IDs. Snapshot
replay never reads mutable `DailyCandle` values or dynamically resolves current
index membership.

## 3. Provenance model

Provider synchronizations create `MarketDataIngestionBatch` records containing
explicit provider, feed, timeframe, adjustment, requested range, benchmark,
sanitized request metadata, lifecycle timestamps/status, and symbol counts. API
keys, authorization headers, and secrets are forbidden. Version rows carry the
batch, provider/feed, observation time, and provenance status that produced
them. Terminal batches are immutable through the normal repository/service API.

## 4. Candle-versioning model

`DailyCandleVersion` is append-only and indexed by company/day/version sequence
and ingestion batch. Exact Decimal/integer comparisons cover open, high, low,
close, and volume. A new operational candle gets version 1. A materially changed
candle gets the next sequence while the old version remains. An identical
incoming candle creates no duplicate version. Completed-session filtering occurs
before versioning and remains defensive at the repository boundary.

## 5. Ingestion-batch model

Single-ticker, explicit/bulk, current-universe, and custom Add & Sync flows reuse
the same versioned upsert and batch lifecycle. Each provider request group has
one batch. Success/failure counts are recorded even when all checked values are
unchanged. Provider failures finalize the batch as failed without exposing raw
credentials or request headers.

## 6. Dataset-snapshot model

`ResearchDatasetSnapshot` stores label, immutable requested range, benchmark,
timeframe/adjustment, universe identifier/count/hash, dataset hash, exact candle
row/version and company counts, observed range, provenance status, value-
reproducibility status, Git HEAD/dirty metadata, notes, timings, and finalized
state. `ResearchDatasetCandleMember` maps the snapshot to exact immutable candle
version IDs. This explicit mapping is the snapshot boundary; replay cannot drift
when later versions arrive.

## 7. Universe snapshot semantics

`ResearchDatasetUniverseMember` stores each exact member's company ID, ticker,
name, exchange, and sector as observed at snapshot creation plus a role of
`UNIVERSE` or `BENCHMARK`. Current-research-universe mode freezes the active
`^GSPC` member list and explicitly includes SPY as benchmark. Explicit ticker
mode supports deterministic tests/smokes. Replay uses these rows, never current
`IndexConstituent` state. This is a frozen current-universe snapshot and retains
survivorship bias; it is not historical point-in-time membership.

## 8. Canonical hashing rules

Universe SHA-256 hashes uppercase tickers sorted ordinally, UTF-8 encoded as one
ticker per line with a terminal newline. Dataset SHA-256 orders rows by uppercase
ticker then ISO trading day and hashes UTF-8 lines:

```text
TICKER|YYYY-MM-DD|OPEN|HIGH|LOW|CLOSE|VOLUME\n
```

Decimals use non-exponent, locale-independent canonical strings with redundant
trailing fractional zeroes removed and negative zero normalized to zero. No
binary float conversion occurs. Hash verification streams the same immutable
version mapping and fails on any mismatch; it never repairs stored hashes.

## 9. Immutable snapshot rules

Snapshot creation occurs in `DRAFT`, freezes membership/version mappings,
calculates metadata/hashes, then finalizes once. Normal services expose no
member/date/hash mutation. Finalized snapshots reject additions, removals, range
changes, re-finalization, and deletion. Database constraints/triggers reinforce
append-only versions and finalized snapshot/member immutability. A changed
dataset always requires a new snapshot ID.

## 10. Legacy data handling

The migration creates one initial immutable version for every existing
operational candle using database-native `INSERT ... SELECT`. These rows preserve
the values present at Sprint 13 installation and are labeled
`LEGACY_UNKNOWN`/`UNKNOWN`; Alpaca/IEX is never fabricated. Snapshot provenance
is `LEGACY_PARTIAL` when any selected version is legacy. Value replay can still
be complete. Version history is reliable from Sprint 13 onward; earlier
overwritten candle versions cannot be reconstructed.

## 11. Code revision metadata

Snapshot manifests and snapshot-bound research summaries record Git HEAD SHA and
the working-tree dirty flag. Local dirty research is allowed and clearly
identified. Source diffs and secrets are not stored in the database.

## 12. CLI and research-run integration

Add a project CLI supporting dataset `create`, `list`, `show`, and `verify` with
typed JSON manifests. Add `--dataset-snapshot` to the Sprint 12 strategy-exit
runner. Snapshot mode obtains its exact universe, company-at-snapshot facts,
stock/benchmark candle versions, and metadata through a frozen research data
source. Operational mode remains available and explicitly reports
`OPERATIONAL_CURRENT`; snapshot mode reports `FROZEN_SNAPSHOT`, snapshot ID,
hashes, provenance status, and Git revision.

## 13. Migration strategy

One forward Alembic migration creates the batch/version/snapshot/member tables,
their query-driven indexes/constraints, immutability triggers, and the legacy
backfill. Backfill is a set-based database `INSERT ... SELECT`; it does not load
hundreds of thousands of candles into Python, rewrite `DailyCandle`, truncate,
drop, or reset data. The migration is exercised from a clean CI database and
then, after target verification, against the development database.

## 14. Rollback and data-safety plan

No destructive development-data operation is part of validation. Before the
real upgrade, report only safe database identity (database name/host), current
Alembic revision, and row counts without credentials. Automated mutation and
corruption tests use the dedicated test database. Downgrade definitions exist
for schema review but are not run against the user's development data. Existing
operational candles remain untouched and authoritative for current workflows.

## 15. CI changes

Retain PostgreSQL test isolation and require clean `alembic upgrade head` before
pytest. Backend CI must run Ruff check, Ruff format check, mypy, and pytest using
`uv` with fake/syntactic environment values and no live provider calls. Add a
separate frontend job using the lockfile and supported Node version for
`npm ci`, lint, unit tests, and build. No real Alpaca, Finnhub, Polygon, or
Wikimedia credentials/network calls are permitted.

## 16. Testing requirements

Focused tests will cover ingestion lifecycle/provenance/secrecy, exact unchanged
versus changed version behavior, completed-session filtering, old-version
queries, operational latest values, all sync entry points, legacy backfill
truthfulness/counts, canonical hash determinism and sensitivity, exact universe
freeze, snapshot immutability/verification, old/new snapshot isolation, frozen
versus operational research sources, report metadata, unchanged Sprint 12
control semantics, migration availability, and deterministic same-snapshot
backtests. The central acceptance test mutates operational data in the test
database after snapshot S, proves S/hash/result unchanged, then proves new S2
captures the changed version and hash.

## 17. Completion criteria

Sprint 13 completes when migrations and legacy backfill are safe and green;
all real sync paths preserve provenance/version history; snapshots freeze exact
universe and candle versions; hashes verify deterministically; the shared
portfolio/Sprint 12 loader can bind a snapshot; backend and frontend CI gates
cover the new guarantees without external credentials; focused and full local
gates pass; one safe real frozen snapshot is created if practical; one unchanged
Sprint 12 control run repeats identically twice from that snapshot; the complete
evidence is recorded in `docs/SPRINT13_COMPLETION_REPORT.md`; work remains local;
and Sprint 14 is not started.
