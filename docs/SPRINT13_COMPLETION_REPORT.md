# AlphaPilot Sprint 13 Completion Report

## 1. Sprint goal

Sprint 13 separated mutable operational market data from immutable,
provenance-aware research inputs. A future experiment can now bind an exact
dataset snapshot, exact universe, exact candle-version mapping, canonical
hashes, Git revision, and strategy configuration. No strategy, ranking, sizing,
trade-management, transaction-cost, completed-session, or T+1 rule changed.

## 2. Reproducibility problem discovered in Sprint 12

Sprint 12 reproduced unchanged configurations against refreshed operational
`DailyCandle` values and obtained materially different baselines from archived
Sprint 10B results. The old mutable schema could neither recover overwritten
OHLCV values nor prove their provider/feed/batch. Hashing current rows alone
would detect drift but could not replay an old input.

## 3. Architecture selected

The selected design uses:

- mutable `DailyCandle` as the operational latest materialization;
- immutable `DailyCandleVersion` rows for every material completed-session
  OHLCV observation;
- immutable `MarketDataIngestionBatch` provenance for sync request groups;
- `ResearchDatasetSnapshot` manifests;
- exact `ResearchDatasetUniverseMember` rows, including a separate benchmark
  role and company facts at snapshot time;
- exact `ResearchDatasetCandleMember` mappings from a snapshot to version IDs;
- `OperationalMarketDataSource` and `FrozenDatasetMarketDataSource` behind a
  shared research-loading contract.

The explicit snapshot-to-version mapping was chosen over a hash-only or
watermark-only design because it makes the replay boundary direct and auditable.

## 4. Why old candle values are preserved

Every materially changed completed candle appends a version before/updating the
operational row. A frozen snapshot references the immutable version UUID, never
the mutable `DailyCandle`. Database triggers reject update/delete of version
rows. Automated acceptance coverage proved that an operational OHLCV revision
does not change an old snapshot, hash, or portfolio result, while a new snapshot
captures the new value and receives a different hash/result.

## 5. Operational versus frozen research semantics

- `OPERATIONAL_CURRENT`: UI, Scanner, evaluation, and unbound research continue
  using current completed `DailyCandle` rows and current universe resolution.
- `FROZEN_SNAPSHOT`: research uses exact member rows and exact immutable candle
  versions, including SPY, strictly within the manifest range.

Normal product workflows are not forced to use snapshots. New strategy research
should prefer frozen snapshots.

## 6. Ingestion batch model

`MarketDataIngestionBatch` records provider, feed, timeframe, adjustment,
requested range, benchmark, sanitized request metadata, requested/succeeded/
failed symbol counts, timestamps, and `RUNNING`/`COMPLETED`/`FAILED` status.
Terminal batches cannot be mutated through the repository and are protected by
a database trigger. A write failure rolls back the failed transaction and then
marks the durable batch `FAILED` rather than leaving it `RUNNING`.

## 7. Candle version model

`DailyCandleVersion` stores company/day, exact Decimal OHLC, integer volume,
provider, feed, provenance status, ingestion batch, observed timestamp, and a
positive per-company/day sequence. A database constraint requires `COMPLETE`
provenance to reference an ingestion batch; `LEGACY_UNKNOWN` has no batch.
Indexes support company/day/sequence, batch, and observation-time access.

Exact Decimal/integer comparisons cover open, high, low, close, and volume.
Identical values create no duplicate version; any changed research value creates
the next immutable version and updates operational latest state.

## 8. Dataset snapshot model

`ResearchDatasetSnapshot` records label, state, timestamps/watermark, expected
provider/feed, timeframe/adjustment, requested and observed ranges, benchmark,
universe identity/count/hash, candle/company counts, dataset hash, provenance
status, value-reproducibility status, Git SHA/dirty flag, notes, and creation
duration. Creation freezes explicit members/version IDs in `DRAFT`, hashes the
mapping, then finalizes once.

## 9. Universe snapshot model

Each member preserves company ID, ticker, name, exchange, sector, membership
source, and role (`UNIVERSE` or `BENCHMARK`). Current-universe mode freezes the
then-active `^GSPC` member set and explicitly adds SPY. Explicit-ticker mode is
available for controlled research/tests. Replay ignores later
`IndexConstituent` changes.

## 10. Canonical dataset hashing specification

Rows are ordered by uppercase ticker and ISO trading day. Each UTF-8 row is:

```text
TICKER|YYYY-MM-DD|OPEN|HIGH|LOW|CLOSE|VOLUME\n
```

Decimals use locale-independent, non-exponent strings; redundant fractional
zeroes are removed and negative zero becomes zero. No float conversion occurs.
SHA-256 consumes the streamed rows in that canonical order.

## 11. Canonical universe hashing specification

Universe tickers are stripped, uppercased, deduplicated, sorted ordinally, and
encoded as one UTF-8 ticker plus `\n` per member. SPY is the explicit benchmark
and is not included in the S&P universe hash.

## 12. Snapshot immutability guarantees

The service exposes no update/delete workflow. Database triggers reject changes
or deletion of finalized manifests and reject insert/update/delete of their
universe/candle mappings. `DailyCandleVersion` rows are append-only at the
database layer. Verification recalculates hashes and fails loudly; it never
repairs a manifest.

## 13. Legacy provenance treatment

Existing candles were copied exactly into version 1 with provider
`LEGACY_UNKNOWN`, feed `UNKNOWN`, status `LEGACY_UNKNOWN`, and no fabricated
batch. A snapshot containing any such row is `LEGACY_PARTIAL`, while
`value_reproducible=true` truthfully states that the frozen values can replay.

Version history is reliable from Sprint 13 onward. Overwritten pre-Sprint 13
versions and their historical sources cannot be reconstructed.

## 14. Exact migration

Added Alembic revision:

`b7a9d4f2c613_add_research_data_versioning.py`

Revision: `b7a9d4f2c613`; previous head: `6e1464ffb227`. It creates the five new
tables, constraints, query-driven indexes, immutability triggers, and legacy
backfill. `migrations/env.py` imports the models into Alembic metadata.

## 15. Backfill approach

The migration uses one database-native `INSERT ... SELECT` with a defensive
`NOT EXISTS` clause. It does not load candles into Python, rewrite/truncate/drop
`daily_candles`, or perform destructive cleanup. The UUID of each operational
candle is reused for its initial immutable version.

## 16. Backfill row counts

Development audit after upgrade:

- operational `daily_candles`: **748,958**
- initial `daily_candle_versions`: **748,958**
- reconciliation difference: **0**
- ingestion batches before subsequent provider sync: **0**
- snapshots before real creation: **0**

The exact original development backfill wall-clock duration was not recoverable:
after the interrupted session resumed, the verified development target already
reported revision `b7a9d4f2c613 (head)`. No downgrade/replay was attempted on
user data merely to manufacture a timing number. The migration itself was also
validated safely by downgrading/upgrading only the dedicated empty test database.

## 17. Provider/feed provenance behavior

Generic single-company sync and the shared Alpaca bulk service now create
sanitized batches and pass one `CandleVersionProvenance` through the common
versioned upsert. Full universe, candle-only, single ticker, and custom Add &
Sync already converge on these services. Real Alpaca records provider `alpaca`,
configured feed (`iex`/`sip`), `1Day`, and split adjustment. Secrets and
authorization-like metadata keys are removed. An unchanged check still records
the batch but creates no meaningless candle revision.

## 18. Completed-session compatibility

`CompletedDailySessionPolicy` filters provider results before version creation,
and `DailyCandleRepository` defensively filters again. Tests prove an incomplete
current-session bar creates neither an operational row nor an immutable version.
Scanner and all prior completed-session regression tests remained green.

## 19. Snapshot service, API, and CLI

`ResearchDatasetService` supports create, list, manifest lookup, dataset load,
and hash verification. Typed endpoints are:

- `POST /api/v1/research-datasets` (admin-tools gated)
- `GET /api/v1/research-datasets`
- `GET /api/v1/research-datasets/{snapshot_id}`
- `POST /api/v1/research-datasets/{snapshot_id}/verify`

The `alphapilot-research-dataset` CLI supports `create`, `list`, `show`, and
`verify`, emitting typed JSON without secrets.

## 20. Backtesting integration

`MultiPortfolioBacktestService` accepts an optional shared
`ResearchMarketDataSource`. Frozen mode supplies company-at-snapshot facts,
exact universe members, exact stock/benchmark versions, and manifest metadata.
The Sprint 12 exit runner accepts `--dataset-snapshot UUID`. Its strategy,
RS20, ATR, sizing, costs, portfolio accounting, and T+1 execution logic were not
changed.

## 21. Exact snapshot CLI usage

```powershell
$env:DEBUG='false'
uv run alphapilot-research-dataset create --start 2019-07-17 --end 2026-08-20 --label research-v1-2026-08-27 --provider-expectation legacy-unknown --feed-expectation unknown --notes "First Sprint 13 frozen current-universe snapshot; values frozen from legacy backfill; source provenance partially unknown; survivorship-biased current constituent universe."
uv run alphapilot-research-dataset list
uv run alphapilot-research-dataset show <snapshot-id>
uv run alphapilot-research-dataset verify <snapshot-id>
```

`list` and `show` are implemented and parser-covered; creation and verification
were executed against the real development snapshot.

## 22. Research report metadata changes

Sprint 12 summary metadata now contains data mode, snapshot UUID, dataset hash,
universe hash, provenance status, snapshot Git SHA/dirty flag, and run Git
SHA/dirty flag. Frozen reports identify the universe as a frozen snapshot;
operational reports explicitly say `OPERATIONAL_CURRENT` and
`UNVERSIONED_CURRENT`.

## 23. Git revision metadata

Snapshot creation and research execution capture `git rev-parse HEAD` plus
`git status --porcelain` dirty state. The first snapshot records
`695892ccc73009f7565b5b1d4ce00ba0a440fa1b` and `git_dirty=true`, as expected
for local pre-commit validation. Source diffs are not stored in the database.

## 24. Tests created

- `tests/research_data/test_candle_versioning.py`
- `tests/research_data/test_hashing.py`
- `tests/research_data/test_research_dataset.py`
- `tests/research_data/test_research_dataset_cli.py`
- `tests/api/test_research_datasets.py`

Coverage includes batch lifecycle/secrecy, exact version comparison, immutable
versions, legacy truthfulness, current-session rejection, canonical hash
determinism/sensitivity, exact universe/benchmark freeze, finalized
immutability, corruption failure, API/CLI contracts, snapshot isolation, old
versus new snapshots, deterministic backtest replay, and report metadata.

## 25. Focused test results

Final focused command:

```powershell
$env:DEBUG='false'
uv run pytest tests/research_data tests/api/test_research_datasets.py tests/services/test_alpaca_bulk_market_sync.py tests/integration/test_market_sync.py tests/backtesting/test_sprint12_protocol.py -vv
```

Result: **32 passed in 6.83s**. An earlier focused slice passed **21/21**.

## 26. Full `run_checks` result

Command:

```powershell
$env:DEBUG='false'
.\run_checks.ps1
```

Result:

- Ruff lint/format: **PASS**
- mypy: **PASS**, 140 source files
- pytest: **PASS**, 235 tests in 26.53s
- aggregate gate: **All checks passed**

`DEBUG=false` was scoped only to child processes because the Codex host exposed
the invalid value `DEBUG=release`; application configuration was not weakened.

## 27. Frontend result

Commands from `frontend/`:

```powershell
npm run lint
npm test -- --run
npm run build
```

Results: ESLint **PASS**; Vitest **16 files / 67 tests PASS**; TypeScript/Vite
production build **PASS** (104 modules transformed). No frontend application
code was changed.

## 28. CI workflow before and after

Before Sprint 13, the single backend job ran Ruff lint, mypy, migrations, and
pytest but omitted Ruff format and all frontend gates; database names were the
generic `alphapilot`/`alphapilot_test`.

After Sprint 13:

- `backend-quality` uses isolated ephemeral `alphapilot_ci` and
  `alphapilot_ci_test`, sets safe `DEBUG=false`, runs Ruff lint, Ruff format
  check, mypy, clean Alembic upgrades, and pytest;
- `frontend-quality` uses Node 22 and the lockfile for `npm ci`, ESLint, Vitest,
  and build.

## 29. Migration CI coverage

The backend CI PostgreSQL service starts clean, creates a separate CI test
database, verifies the two configured database identities differ, and runs
`alembic upgrade head` against both ephemeral CI databases before pytest. The
Sprint 13 migration is therefore exercised on every normal PR/push run.

## 30. Backend CI coverage

Backend CI runs the Linux-native equivalent of local `run_checks.ps1`: `uv
sync`, `ruff check`, `ruff format --check`, `mypy src`, and the complete pytest
suite with PostgreSQL integration coverage.

## 31. Frontend CI coverage

Frontend CI runs `npm ci`, `npm run lint`, `npm test -- --run`, and `npm run
build` from `frontend/` using `package-lock.json`.

## 32. CI external-API independence

Normal CI contains no real Alpaca, Finnhub, Polygon, or Wikimedia credentials
and does not invoke real-provider smoke commands. Provider tests and sync tests
use deterministic fakes/mocks. No secrets were added to workflow YAML.

## 33. First real snapshot ID

`5dd60f87-8947-4850-ba87-4a7df655528c`

Label: `research-v1-2026-08-27`.

## 34. First real dataset hash

`b77ba749182fb4408394eed6d47c7d39dcfcb52a4555683c8a0b9fa7cb91374b`

## 35. First real universe hash

`369350debc5b9649a0f24f6bda863aa8c8d7f85a73965ea16616712d1c5a4ec8`

## 36. Snapshot member count

- universe role: **502** exact frozen current S&P members
- benchmark role: **1** (SPY)
- companies with mapped candle data: **503**

This remains a survivorship-biased frozen current-universe snapshot, not a
historical point-in-time S&P 500 universe.

## 37. Candle/version row count

The snapshot maps **745,232** exact immutable versions from 2019-07-17 through
2026-08-20. This is smaller than the 748,958 full operational/backfill count
because it excludes post-cutoff sessions and companies outside the frozen
universe/benchmark.

## 38. Provenance completeness status

`LEGACY_PARTIAL`, with `value_reproducible=true`. The snapshot must not be
described as Alpaca/IEX-source-complete. Future provider observations have full
batch provenance, but selected legacy rows remain honestly unknown.

## 39. Snapshot creation time

**51,027 ms** for exact membership/version mapping, canonical dataset/universe
hashing, statistics, and finalization over 745,232 rows.

## 40. Snapshot verification result

Verification passed after creation and again after both research runs. The
final verification streamed all 745,232 rows, matched both hashes and the 502
member count, and completed in **21,656 ms** (the first verification took
19,866 ms).

## 41. Same-snapshot repeated backtest result

Exact command, executed twice with only the ignored output directory changed:

```powershell
$env:DEBUG='false'
uv run alphapilot-backtest-strategy-exits --strategy ema20-pullback --start 2021-08-20 --end 2024-12-31 --stage baseline --fold-label sprint13-replay --configuration control --dataset-snapshot 5dd60f87-8947-4850-ba87-4a7df655528c --output-dir backtest_reports/sprint13/repeat1

$env:DEBUG='false'
uv run alphapilot-backtest-strategy-exits --strategy ema20-pullback --start 2021-08-20 --end 2024-12-31 --stage baseline --fold-label sprint13-replay --configuration control --dataset-snapshot 5dd60f87-8947-4850-ba87-4a7df655528c --output-dir backtest_reports/sprint13/repeat2
```

Both runs produced:

- final equity: **$180,145.51345345**
- total return: **80.1455134534500%**
- CAGR: **19.115823931956566%**
- max drawdown: **26.42807152869096517735270389%**
- Sharpe: **0.8686919227475418**
- completed trades: **253**
- successful/failed tickers: **497 / 5**
- SPY buy-and-hold return: **33.05798389500%**
- dataset/universe hashes: exact manifest hashes above

The five identical failures had no historical candles: FDXF, HONA, PSKY, Q,
and SNDK. Run durations were 697.606s and 731.110s. All eight artifacts
(summary, equity, trades, open positions, selection audit, attribution, sector
attribution, and stop recovery) were byte-identical. The summary JSON SHA-256
was `99c0a29372066af9796be42e04ab8dfda0cfe2c621a959083b7265489948ce70`.
This is reproducibility evidence only, not new EMA strategy evidence.

## 42. Operational mutation isolation confirmation

Automated PostgreSQL acceptance coverage created snapshot S, ran a portfolio,
changed a controlled operational candle through the versioned repository, and
reran S. S contents, verification hash, portfolio object, and metrics were
unchanged. New snapshot S2 received a different dataset hash and changed
portfolio result. Real development candles were not modified for this test.

## 43. Known limitations

- Pre-Sprint 13 overwritten OHLCV revisions and original source provenance are
  irrecoverable.
- The current-universe snapshot has survivorship bias and lacks point-in-time
  constituent history.
- Daily OHLC cannot resolve intraday path ambiguity.
- SPY is a practical benchmark, not a total-return index with dividends fully
  modeled.
- The real snapshot was created from a dirty working tree; SHA plus dirty status
  is disclosed, but arbitrary source diffs are intentionally not stored.
- Snapshot mappings add substantial storage for each large snapshot.
- Five current members had no candles in this snapshot and failed explicitly.
- Snapshot provider/feed expectation fields describe the requested boundary;
  completeness is derived from actual selected version/batch provenance.

## 44. Can pre-Sprint 13 revisions be recovered?

**No.** Sprint 13 freezes the values present at installation and guarantees
append-only history from that boundary onward. It cannot reconstruct data that
the earlier mutable table already overwrote.

## 45. Survivorship-bias limitation

The first dataset freezes the **current** 502-member S&P research universe and
then applies it historically. It therefore contains survivorship bias. Freezing
prevents future membership drift but does not create historical point-in-time
membership. Future research must continue carrying this warning.

## 46. Performance and scalability observations

- set-based backfill reconciled 748,958 rows without Python materialization;
- snapshot creation: 51.027s for 745,232 mappings/hashing;
- verification: 19.866s and 21.656s;
- full snapshot-backed EMA control: 697.606s and 731.110s;
- observed replay working set reached roughly 1 GB.

The main replay cost remains per-ticker history loading plus the existing
strategy engine's repeated prefix evaluation. A future optimization should bulk
load/partition frozen histories and/or cache deterministic indicator series,
with equivalence tests. It was deliberately not mixed into Sprint 13.

## 47. Technical debt

- Optimize frozen full-universe loading/evaluation without changing results.
- Define retention/storage monitoring as snapshots and versions accumulate.
- Consider serializing concurrent writes for the same company/day to avoid a
  rare version-sequence conflict during overlapping sync jobs.
- Add historical point-in-time universe data as a separate research project.
- Consider artifact/code-package fingerprints beyond Git SHA/dirty state.
- Optionally expose compact latest-batch provenance in Data Management UI; the
  backend record is complete, but Sprint 13 intentionally avoided UI expansion.
- Capture migration timing explicitly in future data-heavy revisions; the
  original development backfill time was unavailable after session recovery.

## 48. What Sprint 13 proved

AlphaPilot can preserve every new material completed-candle revision, record its
sync provenance, freeze an exact current universe plus benchmark and exact
version IDs, verify deterministic hashes, and replay the same full-universe
research result byte-for-byte even after operational data later changes. Legacy
values are reproducible without dishonest source claims. CI protects migrations
and both application stacks without live credentials.

## 49. What Sprint 13 did not prove

It did not recover lost historical revisions, eliminate survivorship bias,
establish point-in-time membership, prove provider correctness, model dividends
or intraday paths, make the repeated EMA result new strategy evidence, tune any
strategy/ranking/risk rule, or make research replay fast enough for interactive
use.

## 50. Recommendation for Sprint 14

Proceed, only after user review/publishing, to **Strategy-Specific Configuration
Profiles**. The normal UI should primarily select strategy and selection policy,
while backend profiles bind the frozen research defaults for sizing, strategy
exit, protective-stop default, profit management, and risk configuration.
Existing strategy exits remain defaults; EMA 3x ATR and Micho 1.5x ATR remain
research-only rather than being automatically enabled. Sprint 14 was not
implemented.

## 51. Exact commands executed

Material commands, in execution order:

```powershell
git status
git branch
git log --oneline -15
git checkout main
git pull
git checkout -b feature/research-data-versioning

# Dedicated test DB only (DATABASE_URL scoped to TEST_DATABASE_URL)
uv run alembic downgrade 6e1464ffb227
uv run alembic upgrade head

uv run pytest tests/research_data tests/services/test_alpaca_bulk_market_sync.py tests/integration/test_market_sync.py -q
uv run pytest tests/research_data tests/api/test_research_datasets.py tests/services/test_alpaca_bulk_market_sync.py tests/integration/test_market_sync.py tests/backtesting/test_sprint12_protocol.py -vv
uv run ruff check src tests
uv run mypy src

$env:DEBUG='false'
.\run_checks.ps1

cd ..\frontend
npm run lint
npm test -- --run
npm run build

cd ..\backend
$env:DEBUG='false'
uv run alembic current
uv run alphapilot-research-dataset create --start 2019-07-17 --end 2026-08-20 --label research-v1-2026-08-27 --provider-expectation legacy-unknown --feed-expectation unknown --notes "First Sprint 13 frozen current-universe snapshot; values frozen from legacy backfill; source provenance partially unknown; survivorship-biased current constituent universe."
uv run alphapilot-research-dataset verify 5dd60f87-8947-4850-ba87-4a7df655528c

# Repeated once with repeat1 and once with repeat2 output directories
uv run alphapilot-backtest-strategy-exits --strategy ema20-pullback --start 2021-08-20 --end 2024-12-31 --stage baseline --fold-label sprint13-replay --configuration control --dataset-snapshot 5dd60f87-8947-4850-ba87-4a7df655528c --output-dir backtest_reports/sprint13/repeat1
uv run alphapilot-backtest-strategy-exits --strategy ema20-pullback --start 2021-08-20 --end 2024-12-31 --stage baseline --fold-label sprint13-replay --configuration control --dataset-snapshot 5dd60f87-8947-4850-ba87-4a7df655528c --output-dir backtest_reports/sprint13/repeat2

git diff --check
git diff --stat
git status --short
```

Read-only database audit scripts also verified host/database identity, distinct
development/test targets, schema revision, operational/version/batch/snapshot
counts, available date range, current universe count, artifact SHA-256 values,
and exact summary metrics without printing credentials.

## 52. Git status

Branch: `feature/research-data-versioning`.

The worktree is intentionally uncommitted. Sprint 13 source, migration, tests,
documentation, README, and CI changes are modified/untracked and ready for user
review. Git-ignored `backend/backtest_reports/sprint13/` contains the snapshot
replay artifacts. A pre-existing/user-added untracked `docs/images/` directory
is preserved and was not modified or treated as Sprint 13 work.

## 53. Git diff stat

Final tracked diff stat: **25 files changed, 721 insertions, 119 deletions**.
Git does not include untracked new files (including this report) in `git diff
--stat`; the created-file list in this report is authoritative for Sprint 13
scope. `git diff --check` passed; its only messages were expected Windows
LF-to-CRLF working-copy notices, not whitespace errors.

### Source files created

- `backend/migrations/versions/b7a9d4f2c613_add_research_data_versioning.py`
- `backend/src/alphapilot/api/routes/research_datasets.py`
- `backend/src/alphapilot/backtesting/research_data_source.py`
- `backend/src/alphapilot/cli/research_dataset.py`
- `backend/src/alphapilot/database/models/daily_candle_version.py`
- `backend/src/alphapilot/database/models/market_data_ingestion.py`
- `backend/src/alphapilot/database/models/research_dataset.py`
- `backend/src/alphapilot/market/provenance.py`
- `backend/src/alphapilot/repositories/market_data_ingestion.py`
- `backend/src/alphapilot/repositories/research_dataset.py`
- `backend/src/alphapilot/research_data/__init__.py`
- `backend/src/alphapilot/research_data/hashing.py`
- `backend/src/alphapilot/schemas/research_dataset.py`
- `backend/src/alphapilot/services/market_data_ingestion.py`
- `backend/src/alphapilot/services/research_dataset.py`

### Tests created

- `backend/tests/api/test_research_datasets.py`
- `backend/tests/research_data/test_candle_versioning.py`
- `backend/tests/research_data/test_hashing.py`
- `backend/tests/research_data/test_research_dataset.py`
- `backend/tests/research_data/test_research_dataset_cli.py`

### Documentation created

- `docs/SPRINT13_PLAN.md`
- `docs/SPRINT13_COMPLETION_REPORT.md`

### Files modified

- `.github/workflows/ci.yml`
- `AGENTS.md`
- `README.md`
- `backend/migrations/env.py`
- `backend/pyproject.toml`
- `backend/src/alphapilot/api/router.py`
- `backend/src/alphapilot/api/routes/admin_data.py`
- `backend/src/alphapilot/api/routes/market.py`
- `backend/src/alphapilot/backtesting/multi_portfolio_service.py`
- `backend/src/alphapilot/backtesting/sprint12_reporting.py`
- `backend/src/alphapilot/cli/backtest_strategy_exits.py`
- `backend/src/alphapilot/cli/universe_market_sync.py`
- `backend/src/alphapilot/database/models/__init__.py`
- `backend/src/alphapilot/market/providers/alpaca.py`
- `backend/src/alphapilot/repositories/daily_candle.py`
- `backend/src/alphapilot/services/alpaca_bulk_market_sync.py`
- `backend/src/alphapilot/services/daily_candle.py`
- `backend/src/alphapilot/services/market_batch_sync.py`
- `backend/src/alphapilot/services/market_sync.py`
- `backend/tests/backtesting/test_sprint12_protocol.py`
- `backend/tests/conftest.py`
- `backend/tests/integration/test_market_sync.py`
- `backend/tests/services/test_alpaca_bulk_market_sync.py`
- `docs/DECISIONS.md`
- `docs/PROJECT_STATE.md`

## 54. Recommended commit message

`feat(research): add immutable versioned dataset snapshots`

No commit, push, PR, merge, force-push, or tag operation was performed.
