from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.models.research_portfolio import (
    ResearchPortfolio,
    ResearchPosition,
    ResearchPositionProvenance,
    ResearchPositionStatus,
    ResearchTradeEvent,
    ResearchTradeEventType,
)
from alphapilot.repositories.company import CompanyRepository
from alphapilot.repositories.daily_candle import DailyCandleRepository
from alphapilot.repositories.research_portfolio import ResearchPortfolioRepository


class PortfolioValuationStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"


class StalePortfolioRevisionError(ValueError):
    pass


@dataclass(slots=True, frozen=True)
class ImportedPosition:
    ticker: str
    quantity: int
    average_cost: Decimal
    cost_basis: Decimal | None = None


@dataclass(slots=True, frozen=True)
class PositionValuation:
    position_id: UUID
    company_id: UUID
    ticker: str
    sector: str | None
    status: str
    quantity: int
    average_cost: Decimal
    cost_basis: Decimal
    entry_trading_day: date | None
    entry_price: Decimal | None
    strategy: str | None
    strategy_profile_id: str | None
    strategy_profile_version: int | None
    selection_policy: str | None
    provenance_status: str
    modeled_risk_dollars: Decimal
    latest_completed_trading_day: date | None
    latest_completed_close: Decimal | None
    market_value: Decimal | None
    portfolio_weight_pct: Decimal | None
    unrealized_pnl: Decimal | None
    unrealized_pnl_pct: Decimal | None
    valuation_status: str


@dataclass(slots=True, frozen=True)
class ResearchPortfolioValuation:
    portfolio_id: UUID
    stable_key: str
    name: str
    revision: int
    cash: Decimal
    realized_pnl: Decimal
    total_cost_basis: Decimal
    positions_market_value: Decimal | None
    total_equity: Decimal | None
    cash_pct: Decimal | None
    invested_pct: Decimal | None
    total_unrealized_pnl: Decimal | None
    latest_completed_trading_day: date | None
    valuation_status: PortfolioValuationStatus
    positions: tuple[PositionValuation, ...]


class ResearchPortfolioService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        candle_repository: DailyCandleRepository | None = None,
    ) -> None:
        self.session = session
        self.portfolios = ResearchPortfolioRepository(session)
        self.companies = CompanyRepository(session)
        self.candles = candle_repository or DailyCandleRepository(session)

    async def initialize(
        self,
        *,
        starting_cash: Decimal,
        name: str = "AlphaPilot Research Portfolio",
        stable_key: str = "default",
        imported_positions: tuple[ImportedPosition, ...] = (),
    ) -> ResearchPortfolio:
        if starting_cash < 0:
            raise ValueError("starting cash must not be negative")
        existing = await self.portfolios.get_current(stable_key)
        if existing is not None:
            return existing
        portfolio = ResearchPortfolio(
            stable_key=stable_key,
            name=name,
            cash_balance=starting_cash,
            realized_pnl=Decimal("0"),
            revision=0,
        )
        self.portfolios.add(portfolio)
        await self.portfolios.flush()
        seen: set[UUID] = set()
        for imported in imported_positions:
            if imported.quantity <= 0 or imported.average_cost <= 0:
                raise ValueError("imported positions require positive whole shares and cost")
            company = await self.companies.get_by_ticker(imported.ticker.strip().upper())
            if company is None:
                raise ValueError(f"Company {imported.ticker.strip().upper()} not found")
            if company.id in seen:
                raise ValueError("duplicate imported company position")
            seen.add(company.id)
            basis = imported.cost_basis or Decimal(imported.quantity) * imported.average_cost
            position = ResearchPosition(
                portfolio_id=portfolio.id,
                company_id=company.id,
                ticker_at_entry=company.ticker,
                status=ResearchPositionStatus.OPEN.value,
                quantity=imported.quantity,
                average_entry_cost=imported.average_cost,
                cost_basis=basis,
                entry_trading_day=None,
                entry_price=None,
                strategy=None,
                strategy_profile_id=None,
                strategy_profile_version=None,
                strategy_profile_snapshot=None,
                selection_policy=None,
                entry_decision=None,
                entry_reason=None,
                provenance_status=ResearchPositionProvenance.LEGACY_IMPORTED.value,
                modeled_risk_dollars=Decimal("0"),
            )
            self.portfolios.add(position)
            await self.portfolios.flush()
        if imported_positions:
            portfolio.revision = 1
        await self.session.commit()
        await self.session.refresh(portfolio)
        return portfolio

    async def current(self) -> ResearchPortfolio | None:
        return await self.portfolios.get_current()

    async def value(self, portfolio_id: UUID) -> ResearchPortfolioValuation:
        portfolio = await self.portfolios.get(portfolio_id)
        if portfolio is None:
            raise ValueError("Research portfolio not found")
        positions = await self.portfolios.list_open_positions(portfolio_id)
        valued: list[PositionValuation] = []
        for position in positions:
            candle = await self.candles.get_latest(position.company_id)
            company = await self.companies.get(position.company_id)
            close = Decimal(candle.close) if candle is not None else None
            market_value = Decimal(position.quantity) * close if close is not None else None
            unrealized = (
                market_value - Decimal(position.cost_basis) if market_value is not None else None
            )
            unrealized_pct = (
                unrealized / Decimal(position.cost_basis) * Decimal("100")
                if unrealized is not None and position.cost_basis > 0
                else None
            )
            valued.append(
                PositionValuation(
                    position_id=position.id,
                    company_id=position.company_id,
                    ticker=position.ticker_at_entry,
                    sector=company.sector if company else None,
                    status=position.status,
                    quantity=position.quantity,
                    average_cost=Decimal(position.average_entry_cost),
                    cost_basis=Decimal(position.cost_basis),
                    entry_trading_day=position.entry_trading_day,
                    entry_price=(Decimal(position.entry_price) if position.entry_price else None),
                    strategy=position.strategy,
                    strategy_profile_id=position.strategy_profile_id,
                    strategy_profile_version=position.strategy_profile_version,
                    selection_policy=position.selection_policy,
                    provenance_status=position.provenance_status,
                    modeled_risk_dollars=Decimal(position.modeled_risk_dollars),
                    latest_completed_trading_day=(candle.trading_day if candle else None),
                    latest_completed_close=close,
                    market_value=market_value,
                    portfolio_weight_pct=None,
                    unrealized_pnl=unrealized,
                    unrealized_pnl_pct=unrealized_pct,
                    valuation_status=("VALUED" if candle else "PRICE_UNAVAILABLE"),
                )
            )
        missing = sum(item.market_value is None for item in valued)
        status = (
            PortfolioValuationStatus.COMPLETE
            if missing == 0
            else PortfolioValuationStatus.UNAVAILABLE
            if missing == len(valued)
            else PortfolioValuationStatus.PARTIAL
        )
        market_value_total = (
            sum((item.market_value or Decimal("0") for item in valued), Decimal("0"))
            if missing == 0
            else None
        )
        unrealized_total = (
            sum((item.unrealized_pnl or Decimal("0") for item in valued), Decimal("0"))
            if missing == 0
            else None
        )
        total_equity = (
            Decimal(portfolio.cash_balance) + market_value_total
            if market_value_total is not None
            else None
        )
        if total_equity is not None and total_equity > 0:
            valued = [
                replace(
                    item,
                    portfolio_weight_pct=(
                        item.market_value / total_equity * Decimal("100")
                        if item.market_value is not None
                        else None
                    ),
                )
                for item in valued
            ]
        return ResearchPortfolioValuation(
            portfolio_id=portfolio.id,
            stable_key=portfolio.stable_key,
            name=portfolio.name,
            revision=portfolio.revision,
            cash=Decimal(portfolio.cash_balance),
            realized_pnl=Decimal(portfolio.realized_pnl),
            total_cost_basis=sum((item.cost_basis for item in valued), Decimal("0")),
            positions_market_value=market_value_total,
            total_equity=total_equity,
            cash_pct=(
                Decimal(portfolio.cash_balance) / total_equity * Decimal("100")
                if total_equity is not None and total_equity > 0
                else None
            ),
            invested_pct=(
                market_value_total / total_equity * Decimal("100")
                if total_equity is not None and total_equity > 0 and market_value_total is not None
                else None
            ),
            total_unrealized_pnl=unrealized_total,
            latest_completed_trading_day=max(
                (
                    item.latest_completed_trading_day
                    for item in valued
                    if item.latest_completed_trading_day
                ),
                default=None,
            ),
            valuation_status=status,
            positions=tuple(valued),
        )

    async def buy(
        self,
        *,
        portfolio_id: UUID,
        expected_revision: int,
        ticker: str,
        quantity: int,
        execution_price: Decimal,
        trading_day: date | None,
        strategy: str,
        profile_id: str,
        profile_version: int,
        profile_snapshot: dict[str, Any],
        selection_policy: str,
        decision: str,
        reason: str,
        modeled_risk_dollars: Decimal,
        action_id: str,
    ) -> ResearchPortfolio:
        portfolio = await self._locked(portfolio_id, expected_revision)
        if quantity <= 0 or execution_price <= 0:
            raise ValueError("BUY requires positive whole shares and price")
        company = await self.companies.get_by_ticker(ticker.strip().upper())
        if company is None:
            raise ValueError("Company not found")
        if await self.portfolios.get_open_position(portfolio.id, company.id):
            raise ValueError("Position already held")
        outlay = Decimal(quantity) * execution_price
        if outlay > portfolio.cash_balance:
            raise ValueError("Insufficient cash")
        position = ResearchPosition(
            portfolio_id=portfolio.id,
            company_id=company.id,
            ticker_at_entry=company.ticker,
            status=ResearchPositionStatus.OPEN.value,
            quantity=quantity,
            average_entry_cost=execution_price,
            cost_basis=outlay,
            entry_trading_day=trading_day,
            entry_price=execution_price,
            strategy=strategy,
            strategy_profile_id=profile_id,
            strategy_profile_version=profile_version,
            strategy_profile_snapshot=profile_snapshot,
            selection_policy=selection_policy,
            entry_decision=decision,
            entry_reason=reason,
            provenance_status=ResearchPositionProvenance.PLAN_PROFILE.value,
            modeled_risk_dollars=modeled_risk_dollars,
        )
        self.portfolios.add(position)
        await self.portfolios.flush()
        portfolio.cash_balance -= outlay
        portfolio.revision += 1
        self.portfolios.add(
            ResearchTradeEvent(
                portfolio_id=portfolio.id,
                position_id=position.id,
                company_id=company.id,
                event_type=ResearchTradeEventType.OPEN.value,
                quantity=quantity,
                execution_price=execution_price,
                trading_day=trading_day,
                cash_effect=-outlay,
                realized_pnl=Decimal("0"),
                source="PORTFOLIO_PLAN",
                reason=reason,
                action_id=action_id,
                strategy=strategy,
                strategy_profile_id=profile_id,
                strategy_profile_version=profile_version,
                provenance_status=ResearchPositionProvenance.PLAN_PROFILE.value,
            )
        )
        await self.session.commit()
        return portfolio

    async def sell(
        self,
        *,
        portfolio_id: UUID,
        expected_revision: int,
        ticker: str,
        quantity: int,
        execution_price: Decimal,
        trading_day: date | None,
        source: str,
        reason: str,
        action_id: str | None,
    ) -> ResearchPortfolio:
        portfolio = await self._locked(portfolio_id, expected_revision)
        company = await self.companies.get_by_ticker(ticker.strip().upper())
        if company is None:
            raise ValueError("Company not found")
        position = await self.portfolios.get_open_position(portfolio.id, company.id)
        if position is None:
            raise ValueError("Position not held")
        if quantity <= 0 or quantity > position.quantity or execution_price <= 0:
            raise ValueError("Invalid sell quantity or price")
        proceeds = Decimal(quantity) * execution_price
        realized = Decimal(quantity) * (execution_price - Decimal(position.average_entry_cost))
        remaining = position.quantity - quantity
        position.quantity = remaining
        position.cost_basis = Decimal(remaining) * Decimal(position.average_entry_cost)
        position.modeled_risk_dollars = (
            Decimal(position.modeled_risk_dollars)
            * Decimal(remaining)
            / Decimal(quantity + remaining)
        )
        event_type = ResearchTradeEventType.PARTIAL_EXIT
        if remaining == 0:
            position.status = ResearchPositionStatus.CLOSED.value
            position.closed_at_trading_day = trading_day
            event_type = ResearchTradeEventType.FULL_EXIT
        portfolio.cash_balance += proceeds
        portfolio.realized_pnl += realized
        portfolio.revision += 1
        self.portfolios.add(
            ResearchTradeEvent(
                portfolio_id=portfolio.id,
                position_id=position.id,
                company_id=company.id,
                event_type=event_type.value,
                quantity=quantity,
                execution_price=execution_price,
                trading_day=trading_day,
                cash_effect=proceeds,
                realized_pnl=realized,
                source=source,
                reason=reason,
                action_id=action_id,
                strategy=position.strategy,
                strategy_profile_id=position.strategy_profile_id,
                strategy_profile_version=position.strategy_profile_version,
                provenance_status=position.provenance_status,
            )
        )
        await self.session.commit()
        return portfolio

    async def events(self, portfolio_id: UUID) -> list[ResearchTradeEvent]:
        return await self.portfolios.list_events(portfolio_id)

    async def _locked(self, portfolio_id: UUID, revision: int) -> ResearchPortfolio:
        portfolio = await self.portfolios.get(portfolio_id, for_update=True)
        if portfolio is None:
            raise ValueError("Research portfolio not found")
        if portfolio.revision != revision:
            raise StalePortfolioRevisionError(
                f"Portfolio revision is stale: expected {portfolio.revision}, received {revision}"
            )
        return portfolio
