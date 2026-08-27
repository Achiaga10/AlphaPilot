from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.backtesting.multi_portfolio_models import MultiPortfolioConfig
from alphapilot.backtesting.multi_portfolio_service import MultiPortfolioBacktestService
from alphapilot.backtesting.research_data_source import FrozenDatasetMarketDataSource
from alphapilot.backtesting.sprint12_protocol import (
    Sprint12ExitConfiguration,
    Sprint12ResearchStage,
)
from alphapilot.backtesting.sprint12_reporting import build_metadata
from alphapilot.database.models.company import Company
from alphapilot.database.models.daily_candle import DailyCandle
from alphapilot.database.models.market_data_ingestion import CandleProvenanceStatus
from alphapilot.database.models.research_dataset import (
    ResearchDatasetMemberRole,
    ResearchDatasetUniverseMember,
)
from alphapilot.market.provenance import CandleVersionProvenance
from alphapilot.repositories.daily_candle import DailyCandleRepository
from alphapilot.repositories.market_data_ingestion import MarketDataIngestionBatchRepository
from alphapilot.repositories.research_dataset import ResearchDatasetRepository
from alphapilot.schemas.research_dataset import ResearchDatasetManifestSchema
from alphapilot.services.market_data_ingestion import MarketDataIngestionBatchService
from alphapilot.services.research_dataset import (
    GitRevision,
    ResearchDatasetService,
    ResearchDatasetVerificationError,
)
from alphapilot.strategy.base import TradingStrategy
from alphapilot.strategy.context import StrategyContext
from alphapilot.strategy.evaluation import MarketRegime, SignalReason, StrategyEvaluation
from alphapilot.strategy.name import StrategyName
from alphapilot.strategy.signal import Signal


def git_revision() -> GitRevision:
    return GitRevision(head="a" * 40, dirty=True)


class BuyFirstDayStrategy(TradingStrategy):
    def evaluate(
        self,
        company: Company,
        candles: list[DailyCandle],
        context: StrategyContext | None = None,
    ) -> StrategyEvaluation:
        del company, context
        return StrategyEvaluation(
            signal=(Signal.BUY if candles[-1].trading_day == date(2025, 1, 2) else Signal.HOLD),
            reason=(
                SignalReason.EMA20_PULLBACK_RECLAIM
                if candles[-1].trading_day == date(2025, 1, 2)
                else SignalReason.NO_PULLBACK
            ),
            market_regime=MarketRegime.BULLISH,
        )


async def seed_company(db_session: AsyncSession, ticker: str, sector: str) -> Company:
    company = Company(
        id=uuid4(),
        ticker=ticker,
        name=f"{ticker} Incorporated",
        exchange="NASDAQ",
        sector=sector,
        is_active=True,
    )
    db_session.add(company)
    await db_session.commit()
    return company


def candle(company_id: UUID, day: date, close: str, volume: int = 1000) -> DailyCandle:
    value = Decimal(close)
    return DailyCandle(
        company_id=company_id,
        trading_day=day,
        open=value - Decimal("1"),
        high=value + Decimal("2"),
        low=value - Decimal("2"),
        close=value,
        volume=volume,
    )


async def seeded_repository(
    db_session: AsyncSession,
) -> tuple[ResearchDatasetRepository, DailyCandleRepository, dict[str, Company]]:
    companies = {
        "AAPL": await seed_company(db_session, "AAPL", "Information Technology"),
        "MSFT": await seed_company(db_session, "MSFT", "Information Technology"),
        "SPY": await seed_company(db_session, "SPY", "ETF"),
    }
    batch_service = MarketDataIngestionBatchService(MarketDataIngestionBatchRepository(db_session))
    batch = await batch_service.start(
        provider="fixture",
        feed="test",
        timeframe="1Day",
        adjustment="split",
        requested_start=date(2025, 1, 2),
        requested_end=date(2025, 1, 6),
        symbols_requested=3,
    )
    provenance = CandleVersionProvenance(
        provider="fixture",
        feed="test",
        ingestion_batch_id=batch.id,
        observed_at=datetime.now(UTC),
        status=CandleProvenanceStatus.COMPLETE,
    )
    candle_repository = DailyCandleRepository(db_session)
    await candle_repository.upsert_many(
        [
            candle(company.id, day, str(100 + offset * 2 + index))
            for offset, day in enumerate((date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)))
            for index, company in enumerate(companies.values())
        ],
        provenance=provenance,
    )
    await batch_service.complete(batch, succeeded=3, failed=0)
    return ResearchDatasetRepository(db_session), candle_repository, companies


async def create_snapshot(
    repository: ResearchDatasetRepository,
    *,
    label: str,
) -> ResearchDatasetManifestSchema:
    service = ResearchDatasetService(repository, git_revision_provider=git_revision)
    return await service.create_snapshot(
        start=date(2025, 1, 2),
        end=date(2025, 1, 6),
        universe_mode=ResearchDatasetService.EXPLICIT_TICKERS,
        tickers=["MSFT", "AAPL"],
        benchmark_ticker="SPY",
        label=label,
        provider_expectation="fixture",
        feed_expectation="test",
    )


@pytest.mark.asyncio
async def test_snapshot_freezes_exact_universe_benchmark_and_versions(
    db_session: AsyncSession,
) -> None:
    repository, _, _ = await seeded_repository(db_session)
    manifest = await create_snapshot(repository, label="snapshot-one")
    assert manifest.universe_members == 2
    assert manifest.company_count == 3
    assert manifest.candle_rows == 9
    assert manifest.benchmark == "SPY"
    assert manifest.provenance_status == "COMPLETE"
    assert manifest.value_reproducible is True
    members = await repository.list_members(manifest.snapshot_id)
    assert [(member.role, member.ticker_at_snapshot) for member in members] == [
        (ResearchDatasetMemberRole.UNIVERSE.value, "AAPL"),
        (ResearchDatasetMemberRole.UNIVERSE.value, "MSFT"),
        (ResearchDatasetMemberRole.BENCHMARK.value, "SPY"),
    ]
    source = FrozenDatasetMarketDataSource(repository, manifest.snapshot_id)
    universe = await source.list_active("^GSPC")
    assert [item.ticker for item in universe] == ["AAPL", "MSFT"]
    frozen_aapl = await source.get_company("AAPL")
    assert frozen_aapl is not None
    assert frozen_aapl.sector == "Information Technology"


@pytest.mark.asyncio
async def test_snapshot_reports_legacy_provenance_honestly(db_session: AsyncSession) -> None:
    companies = {
        ticker: await seed_company(db_session, ticker, "Unknown") for ticker in ("AAPL", "SPY")
    }
    candles = DailyCandleRepository(db_session)
    await candles.upsert_many(
        [candle(item.id, date(2025, 1, 2), "100") for item in companies.values()]
    )
    repository = ResearchDatasetRepository(db_session)
    service = ResearchDatasetService(repository, git_revision_provider=git_revision)
    manifest = await service.create_snapshot(
        start=date(2025, 1, 2),
        end=date(2025, 1, 2),
        universe_mode=ResearchDatasetService.EXPLICIT_TICKERS,
        tickers=["AAPL"],
    )
    assert manifest.provenance_status == "LEGACY_PARTIAL"
    assert manifest.value_reproducible is True


@pytest.mark.asyncio
async def test_same_rows_same_hash_and_operational_update_cannot_change_old_snapshot(
    db_session: AsyncSession,
) -> None:
    repository, candle_repository, companies = await seeded_repository(db_session)
    service = ResearchDatasetService(repository, git_revision_provider=git_revision)
    first = await service.create_snapshot(
        start=date(2025, 1, 2),
        end=date(2025, 1, 6),
        universe_mode=ResearchDatasetService.EXPLICIT_TICKERS,
        tickers=["AAPL", "MSFT"],
        label="S1",
    )
    same = await service.create_snapshot(
        start=date(2025, 1, 2),
        end=date(2025, 1, 6),
        universe_mode=ResearchDatasetService.EXPLICIT_TICKERS,
        tickers=["MSFT", "AAPL"],
        label="SAME",
    )
    assert same.dataset_sha256 == first.dataset_sha256
    assert same.universe_sha256 == first.universe_sha256

    old_source = FrozenDatasetMarketDataSource(repository, first.snapshot_id)
    old_before = await old_source.get_history(
        companies["AAPL"].id, date(2025, 1, 2), date(2025, 1, 6)
    )
    changed = candle(companies["AAPL"].id, date(2025, 1, 3), "999", volume=7777)
    batch_service = MarketDataIngestionBatchService(MarketDataIngestionBatchRepository(db_session))
    batch = await batch_service.start(
        provider="fixture",
        feed="test",
        timeframe="1Day",
        adjustment="split",
        requested_start=date(2025, 1, 3),
        requested_end=date(2025, 1, 3),
        symbols_requested=1,
    )
    await candle_repository.upsert_many(
        [changed],
        provenance=CandleVersionProvenance(
            provider="fixture",
            feed="test",
            ingestion_batch_id=batch.id,
            observed_at=datetime.now(UTC),
            status=CandleProvenanceStatus.COMPLETE,
        ),
    )
    await batch_service.complete(batch, succeeded=1, failed=0)
    old_after = await old_source.get_history(
        companies["AAPL"].id, date(2025, 1, 2), date(2025, 1, 6)
    )
    assert [(item.trading_day, item.close, item.volume) for item in old_after] == [
        (item.trading_day, item.close, item.volume) for item in old_before
    ]
    verification = await service.verify(first.snapshot_id)
    assert verification.verified is True
    assert verification.dataset_sha256 == first.dataset_sha256

    second = await service.create_snapshot(
        start=date(2025, 1, 2),
        end=date(2025, 1, 6),
        universe_mode=ResearchDatasetService.EXPLICIT_TICKERS,
        tickers=["AAPL", "MSFT"],
        label="S2",
    )
    assert second.dataset_sha256 != first.dataset_sha256
    new_source = FrozenDatasetMarketDataSource(repository, second.snapshot_id)
    new_history = await new_source.get_history(
        companies["AAPL"].id, date(2025, 1, 2), date(2025, 1, 6)
    )
    assert new_history[1].close == Decimal("999.0000")
    assert new_history[1].volume == 7777


@pytest.mark.asyncio
async def test_finalized_snapshot_rejects_member_mutation(db_session: AsyncSession) -> None:
    repository, _, companies = await seeded_repository(db_session)
    manifest = await create_snapshot(repository, label="immutable")
    db_session.add(
        ResearchDatasetUniverseMember(
            snapshot_id=manifest.snapshot_id,
            company_id=companies["AAPL"].id,
            role=ResearchDatasetMemberRole.BENCHMARK.value,
            ticker_at_snapshot="FAKE",
            company_name_at_snapshot="Fake",
            exchange_at_snapshot="TEST",
            sector_at_snapshot=None,
            membership_source="ILLEGAL_MUTATION",
        )
    )
    with pytest.raises(DBAPIError, match="Finalized research snapshot members are immutable"):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_verification_fails_loudly_for_corrupted_controlled_stream(
    db_session: AsyncSession,
) -> None:
    repository, _, _ = await seeded_repository(db_session)
    manifest = await create_snapshot(repository, label="verify-corruption")
    original_stream = repository.stream_canonical_rows

    async def corrupted(snapshot_id: UUID):
        changed = False
        async for item in original_stream(snapshot_id):
            if not changed:
                changed = True
                yield replace(item, close=item.close + Decimal("1"))
            else:
                yield item

    repository.stream_canonical_rows = corrupted  # type: ignore[method-assign]
    service = ResearchDatasetService(repository, git_revision_provider=git_revision)
    with pytest.raises(ResearchDatasetVerificationError, match="dataset SHA-256 mismatch"):
        await service.verify(manifest.snapshot_id)


@pytest.mark.asyncio
async def test_snapshot_backtest_isolated_reproducible_and_reported(
    db_session: AsyncSession,
) -> None:
    repository, candle_repository, companies = await seeded_repository(db_session)
    snapshots = ResearchDatasetService(repository, git_revision_provider=git_revision)
    first = await snapshots.create_snapshot(
        start=date(2025, 1, 2),
        end=date(2025, 1, 6),
        universe_mode=ResearchDatasetService.EXPLICIT_TICKERS,
        tickers=["AAPL"],
        label="backtest-S1",
    )

    async def run(snapshot_id: UUID):
        source = FrozenDatasetMarketDataSource(repository, snapshot_id)
        return await MultiPortfolioBacktestService(
            source,
            source,
            source,
            BuyFirstDayStrategy(),
            stock_warmup_days=1,
            research_data_source=source,
        ).run(
            start=date(2025, 1, 2),
            end=date(2025, 1, 6),
            config=MultiPortfolioConfig(max_positions=1),
        )

    before = await run(first.snapshot_id)
    batch_service = MarketDataIngestionBatchService(MarketDataIngestionBatchRepository(db_session))
    batch = await batch_service.start(
        provider="fixture",
        feed="test",
        timeframe="1Day",
        adjustment="split",
        requested_start=date(2025, 1, 3),
        requested_end=date(2025, 1, 3),
        symbols_requested=1,
    )
    await candle_repository.upsert_many(
        [candle(companies["AAPL"].id, date(2025, 1, 3), "999")],
        provenance=CandleVersionProvenance(
            provider="fixture",
            feed="test",
            ingestion_batch_id=batch.id,
            observed_at=datetime.now(UTC),
            status=CandleProvenanceStatus.COMPLETE,
        ),
    )
    await batch_service.complete(batch, succeeded=1, failed=0)
    repeated = await run(first.snapshot_id)
    verified = await snapshots.verify(first.snapshot_id)

    assert before.portfolio == repeated.portfolio
    assert before.metrics == repeated.metrics
    assert before.successful_tickers == repeated.successful_tickers == ("AAPL",)
    assert verified.dataset_sha256 == first.dataset_sha256
    assert before.research_data is not None
    assert before.research_data.data_mode == "FROZEN_SNAPSHOT"
    assert before.research_data.dataset_snapshot_id == first.snapshot_id
    assert before.research_data.dataset_sha256 == first.dataset_sha256

    second = await snapshots.create_snapshot(
        start=date(2025, 1, 2),
        end=date(2025, 1, 6),
        universe_mode=ResearchDatasetService.EXPLICIT_TICKERS,
        tickers=["AAPL"],
        label="backtest-S2",
    )
    changed = await run(second.snapshot_id)
    assert second.dataset_sha256 != first.dataset_sha256
    assert changed.portfolio.final_equity != before.portfolio.final_equity

    report_metadata = build_metadata(
        result=before,
        strategy=StrategyName.EMA20_PULLBACK,
        entry_configuration="controlled fixture",
        config=MultiPortfolioConfig(max_positions=1),
        exit_configuration=Sprint12ExitConfiguration.parse("control"),
        stage=Sprint12ResearchStage.BASELINE,
        fold_label="snapshot-reproducibility",
        start=date(2025, 1, 2),
        end=date(2025, 1, 6),
    )
    assert report_metadata.data_mode == "FROZEN_SNAPSHOT"
    assert report_metadata.dataset_snapshot_id == str(first.snapshot_id)
    assert report_metadata.dataset_sha256 == first.dataset_sha256
