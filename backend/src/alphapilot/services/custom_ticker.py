from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Protocol
from uuid import UUID

import httpx

from alphapilot.database.models.company import Company
from alphapilot.market.dto import CompanyMetadata
from alphapilot.schemas.company import CompanyUpdate
from alphapilot.services.market_batch_sync import MarketTickerSyncResult

TICKER_PATTERN = re.compile(r"^[A-Z0-9.-]{1,10}$")


class CustomTickerState(StrEnum):
    TRACKED_AND_SYNCED = "TRACKED_AND_SYNCED"
    REACTIVATED_AND_SYNCED = "REACTIVATED_AND_SYNCED"
    TRACKED_NO_DATA = "TRACKED_NO_DATA"
    TRACKED_CANDLE_SYNC_FAILED = "TRACKED_CANDLE_SYNC_FAILED"
    ALREADY_SP500 = "ALREADY_SP500"
    SYMBOL_NOT_FOUND = "SYMBOL_NOT_FOUND"
    METADATA_PROVIDER_FAILED = "METADATA_PROVIDER_FAILED"
    DEACTIVATED = "DEACTIVATED"
    NOT_CUSTOM_TRACKED = "NOT_CUSTOM_TRACKED"


class CompanyMetadataLookup(Protocol):
    async def get_company_metadata(self, ticker: str) -> CompanyMetadata | None: ...


class CustomCompanyService(Protocol):
    async def get_company(self, ticker: str) -> Company | None: ...
    async def create(self, company: Company) -> Company: ...
    async def update_company(self, company_id: UUID, data: CompanyUpdate) -> Company | None: ...


class MembershipLookup(Protocol):
    async def is_active_member(self, index_symbol: str, ticker: str) -> bool: ...


class TickerSync(Protocol):
    async def sync_ticker(self, ticker: str, start: date, end: date) -> MarketTickerSyncResult: ...


class CandleSummaryLookup(Protocol):
    async def company_candle_summary(self, ticker: str) -> tuple[int, date | None, date | None]: ...


@dataclass(slots=True, frozen=True)
class CustomTickerOutcome:
    ticker: str
    state: CustomTickerState
    company_name: str | None
    exchange: str | None
    sector: str | None
    is_custom_tracked: bool
    is_sp500_member: bool
    stored_candle_count: int
    first_candle_date: date | None
    latest_candle_date: date | None
    message: str


class CustomTickerService:
    SP500_INDEX_SYMBOL = "^GSPC"

    def __init__(
        self,
        company_service: CustomCompanyService,
        membership_repository: MembershipLookup,
        metadata_provider: CompanyMetadataLookup,
        market_sync_service: TickerSync,
        candle_summary_repository: CandleSummaryLookup,
    ) -> None:
        self.company_service = company_service
        self.membership_repository = membership_repository
        self.metadata_provider = metadata_provider
        self.market_sync_service = market_sync_service
        self.candle_summary_repository = candle_summary_repository

    async def add_and_sync(self, ticker: str, start: date, end: date) -> CustomTickerOutcome:
        normalized = self.normalize(ticker)
        existing = await self.company_service.get_company(normalized)
        is_member = await self.membership_repository.is_active_member(
            self.SP500_INDEX_SYMBOL, normalized
        )
        if is_member:
            return await self._outcome(
                existing,
                normalized,
                CustomTickerState.ALREADY_SP500,
                True,
                "Ticker already exists as a current S&P 500 constituent.",
            )
        was_reactivation = existing is not None and not existing.is_custom_tracked
        if existing is None:
            try:
                metadata = await self.metadata_provider.get_company_metadata(normalized)
            except httpx.HTTPError:
                return await self._outcome(
                    None,
                    normalized,
                    CustomTickerState.METADATA_PROVIDER_FAILED,
                    False,
                    "Company metadata provider request failed safely.",
                )
            if metadata is None:
                return await self._outcome(
                    None,
                    normalized,
                    CustomTickerState.SYMBOL_NOT_FOUND,
                    False,
                    "The configured metadata provider did not recognize this symbol.",
                )
            existing = await self.company_service.create(self._company(metadata))
        elif not existing.is_custom_tracked:
            updated = await self.company_service.update_company(
                existing.id,
                CompanyUpdate(is_custom_tracked=True, is_active=True),
            )
            if updated is not None:
                existing = updated
        result = await self.market_sync_service.sync_ticker(normalized, start, end)
        if result.failure is not None:
            return await self._outcome(
                existing,
                normalized,
                CustomTickerState.TRACKED_CANDLE_SYNC_FAILED,
                False,
                result.failure.error,
            )
        if result.skipped:
            return await self._outcome(
                existing,
                normalized,
                CustomTickerState.TRACKED_NO_DATA,
                False,
                "Company is tracked, but no candles were returned for the requested range.",
            )
        state = (
            CustomTickerState.REACTIVATED_AND_SYNCED
            if was_reactivation
            else CustomTickerState.TRACKED_AND_SYNCED
        )
        return await self._outcome(
            existing,
            normalized,
            state,
            False,
            "Custom ticker is tracked and stored candles were synchronized.",
        )

    async def deactivate(self, ticker: str) -> CustomTickerOutcome:
        normalized = self.normalize(ticker)
        company = await self.company_service.get_company(normalized)
        is_member = await self.membership_repository.is_active_member(
            self.SP500_INDEX_SYMBOL, normalized
        )
        if is_member:
            return await self._outcome(
                company,
                normalized,
                CustomTickerState.ALREADY_SP500,
                True,
                "Current S&P 500 membership is managed by universe synchronization.",
            )
        if company is None or not company.is_custom_tracked:
            return await self._outcome(
                company,
                normalized,
                CustomTickerState.NOT_CUSTOM_TRACKED,
                False,
                "Ticker is not actively custom tracked.",
            )
        updated = await self.company_service.update_company(
            company.id, CompanyUpdate(is_custom_tracked=False)
        )
        return await self._outcome(
            updated or company,
            normalized,
            CustomTickerState.DEACTIVATED,
            False,
            "Custom tracking was deactivated; company and candle history were preserved.",
        )

    @staticmethod
    def normalize(ticker: str) -> str:
        normalized = ticker.strip().upper()
        if not TICKER_PATTERN.fullmatch(normalized):
            raise ValueError("ticker must contain 1-10 letters, digits, dots, or hyphens")
        return normalized

    @staticmethod
    def _company(metadata: CompanyMetadata) -> Company:
        return Company(
            ticker=metadata.ticker,
            name=metadata.name,
            exchange=metadata.exchange,
            sector=metadata.sector,
            industry=metadata.industry,
            market_cap=metadata.market_cap,
            is_active=True,
            is_custom_tracked=True,
        )

    async def _outcome(
        self,
        company: Company | None,
        ticker: str,
        state: CustomTickerState,
        is_member: bool,
        message: str,
    ) -> CustomTickerOutcome:
        count, first, latest = await self.candle_summary_repository.company_candle_summary(ticker)
        return CustomTickerOutcome(
            ticker=ticker,
            state=state,
            company_name=company.name if company else None,
            exchange=company.exchange if company else None,
            sector=company.sector if company else None,
            is_custom_tracked=bool(company and company.is_custom_tracked),
            is_sp500_member=is_member,
            stored_candle_count=count,
            first_candle_date=first,
            latest_candle_date=latest,
            message=message,
        )
