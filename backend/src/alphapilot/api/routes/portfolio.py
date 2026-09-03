import hashlib
import json
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.api.routes.news import get_news_service
from alphapilot.core.lifespan import daily_market_scheduler
from alphapilot.database.session import get_db
from alphapilot.market.providers.alpaca import AlpacaProvider
from alphapilot.news.policy import NewsEffect
from alphapilot.news.service import NewsService
from alphapilot.portfolio.actions import (
    ManualPortfolioSellService,
    PortfolioPlanActionService,
)
from alphapilot.portfolio.decisions import (
    CurrentPortfolioState,
    PortfolioCandidate,
    PortfolioDecision,
    PortfolioDecisionEngine,
    PortfolioStatePosition,
)
from alphapilot.portfolio.entry_safety import Ema20EntrySafety
from alphapilot.portfolio.execution_readiness import (
    ExecutionReadiness,
    ExecutionReadinessReason,
)
from alphapilot.portfolio.orchestration import PortfolioDecisionOrchestrator
from alphapilot.portfolio.risk import PortfolioRiskConfig
from alphapilot.portfolio.sizing import PortfolioDecisionReason, PortfolioDecisionType
from alphapilot.repositories.company import CompanyRepository
from alphapilot.repositories.daily_candle import DailyCandleRepository
from alphapilot.repositories.index_constituent import IndexConstituentRepository
from alphapilot.repositories.research_data import ResearchDataRepository
from alphapilot.schemas.daily_brief import (
    DailyBriefOpportunitiesSchema,
    DailyPortfolioBriefCoreSchema,
)
from alphapilot.schemas.live_portfolio import PortfolioLiveBriefSchema
from alphapilot.schemas.paper_analytics import (
    ForwardPaperAnalyticsSchema,
    PaperTradeAnalyticsSchema,
)
from alphapilot.schemas.portfolio import (
    CandidateOrchestrationStatusSchema,
    CashAdjustmentRequestSchema,
    CurrentPortfolioSchema,
    ExternalPositionRequestSchema,
    LatestStoredPriceSchema,
    ManualSellRequestSchema,
    ManualSellResultSchema,
    PaperValidationEntryRequestSchema,
    PaperValidationExitRequestSchema,
    PaperValidationSchema,
    PortfolioDecisionPlanSchema,
    PortfolioDecisionRequest,
    PortfolioDecisionSchema,
    PortfolioDraftSummarySchema,
    PortfolioPlanActionRequest,
    PortfolioPlanActionResultSchema,
    PortfolioPlanReadinessSchema,
    PortfolioPlanRequest,
    PortfolioPlanSchema,
    PortfolioPositionSchema,
    PortfolioPositionSummarySchema,
    PortfolioRiskConfigSchema,
    PortfolioSummarySchema,
    PositionIntelligenceSchema,
    PositionMonitoringSchema,
    PositionReconciliationRequestSchema,
    ResearchPortfolioInitializeSchema,
    ResearchPortfolioSchema,
    ResearchReconciliationEventSchema,
    ResearchTradeEventSchema,
    StrategyProfileSchema,
)
from alphapilot.services.admin_data import ResearchDataSummaryService
from alphapilot.services.company import CompanyService
from alphapilot.services.daily_candle import DailyCandleService, LatestStoredPriceService
from alphapilot.services.daily_portfolio_brief import DailyPortfolioBriefService
from alphapilot.services.live_portfolio import LivePortfolioService
from alphapilot.services.paper_analytics import ForwardPaperAnalyticsService
from alphapilot.services.paper_validation import PaperValidationService
from alphapilot.services.position_intelligence import PositionIntelligenceService
from alphapilot.services.position_monitoring import PositionMonitoringService
from alphapilot.services.research_portfolio import (
    ImportedPosition,
    ResearchPortfolioService,
    StalePortfolioRevisionError,
)
from alphapilot.strategy.exit_mode import TrendExitMode
from alphapilot.strategy.micho_entry_mode import MichoEntryMode
from alphapilot.strategy.profile import (
    StrategyProfile,
    list_strategy_profiles,
    resolve_strategy_profile,
    resolve_strategy_profile_identity,
)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def strategy_profile_plan_id(
    request: PortfolioPlanRequest,
    profile: StrategyProfile,
    portfolio_revision: int | None = None,
) -> str:
    payload = {
        "request": request.model_dump(mode="json"),
        "strategy_profile": StrategyProfileSchema.model_validate(
            profile, from_attributes=True
        ).model_dump(mode="json"),
        "portfolio_revision": portfolio_revision,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:24]


def build_portfolio_summary(
    state: CurrentPortfolioState,
    plan_equity: Decimal,
    cash_reserve_requirement: Decimal,
    current_portfolio_risk: Decimal,
    available_portfolio_risk: Decimal,
) -> PortfolioSummarySchema:
    invested_value = sum((position.market_value for position in state.positions), Decimal("0"))

    def pct(value: Decimal) -> Decimal:
        return value / plan_equity * Decimal("100") if plan_equity > 0 else Decimal("0")

    return PortfolioSummarySchema(
        equity=plan_equity,
        cash=state.cash,
        cash_pct=pct(state.cash),
        invested_value=invested_value,
        invested_pct=pct(invested_value),
        cash_reserve_requirement=cash_reserve_requirement,
        current_portfolio_risk=current_portfolio_risk,
        current_portfolio_risk_pct=pct(current_portfolio_risk),
        available_portfolio_risk=available_portfolio_risk,
        available_portfolio_risk_pct=pct(available_portfolio_risk),
        modeled_risk_complete=all(
            position.modeled_risk_dollars > 0 for position in state.positions
        ),
        open_positions=len(state.positions),
        positions=[
            PortfolioPositionSummarySchema(
                ticker=position.ticker.upper(),
                shares=position.shares,
                reference_price=position.reference_price,
                market_value=position.market_value,
                portfolio_weight_pct=pct(position.market_value),
                cost_basis=position.cost_basis,
                sector=position.sector or "Unclassified",
                modeled_risk_dollars=position.modeled_risk_dollars,
            )
            for position in state.positions
        ],
    )


def _state(value: CurrentPortfolioSchema) -> CurrentPortfolioState:
    return CurrentPortfolioState(
        cash=value.cash,
        positions=tuple(
            PortfolioStatePosition(**position.model_dump()) for position in value.positions
        ),
    )


def _state_schema(value: CurrentPortfolioState) -> CurrentPortfolioSchema:
    return CurrentPortfolioSchema.model_validate(value, from_attributes=True)


def build_draft_summary(state: CurrentPortfolioState) -> PortfolioDraftSummarySchema:
    equity = state.equity
    invested = equity - state.cash

    def pct(value: Decimal) -> Decimal:
        return value / equity * Decimal("100") if equity > 0 else Decimal("0")

    return PortfolioDraftSummarySchema(
        equity=equity,
        cash=state.cash,
        cash_pct=pct(state.cash),
        invested_value=invested,
        invested_pct=pct(invested),
        open_positions=len(state.positions),
        positions=[
            PortfolioPositionSummarySchema(
                ticker=position.ticker.upper(),
                shares=position.shares,
                reference_price=position.reference_price,
                market_value=position.market_value,
                portfolio_weight_pct=pct(position.market_value),
                cost_basis=position.cost_basis,
                sector=position.sector or "Unclassified",
                modeled_risk_dollars=position.modeled_risk_dollars,
            )
            for position in state.positions
        ],
    )


def get_portfolio_decision_orchestrator(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PortfolioDecisionOrchestrator:
    return PortfolioDecisionOrchestrator(
        CompanyService(CompanyRepository(session)),
        DailyCandleService(DailyCandleRepository(session)),
        IndexConstituentRepository(session),
        live_quote_provider=AlpacaProvider(),
    )


def get_manual_sell_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ManualPortfolioSellService:
    companies = CompanyService(CompanyRepository(session))
    prices = LatestStoredPriceService(companies, DailyCandleRepository(session))
    return ManualPortfolioSellService(prices)


def get_research_portfolio_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResearchPortfolioService:
    return ResearchPortfolioService(session)


def get_position_monitoring_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PositionMonitoringService:
    return PositionMonitoringService(session)


def get_position_intelligence_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PositionIntelligenceService:
    return PositionIntelligenceService(session)


def get_daily_portfolio_brief_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DailyPortfolioBriefService:
    return DailyPortfolioBriefService(
        ResearchPortfolioService(session),
        PositionIntelligenceService(session),
        get_portfolio_decision_orchestrator(session),
        ResearchDataSummaryService(ResearchDataRepository(session)),
        daily_market_scheduler.status,
        get_news_service(session),
    )


def get_paper_validation_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PaperValidationService:
    return PaperValidationService(session)


def get_forward_paper_analytics_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ForwardPaperAnalyticsService:
    return ForwardPaperAnalyticsService(session)


def get_live_portfolio_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LivePortfolioService:
    return LivePortfolioService(session, AlpacaProvider())


async def _persistent_state(
    service: ResearchPortfolioService, portfolio_id: UUID
) -> tuple[CurrentPortfolioState, ResearchPortfolioSchema]:
    valuation = await service.value(portfolio_id)
    if any(item.latest_completed_close is None for item in valuation.positions):
        raise HTTPException(
            status_code=422,
            detail="Persistent portfolio contains a position without a completed valuation price",
        )
    state = CurrentPortfolioState(
        cash=valuation.cash,
        positions=tuple(
            PortfolioStatePosition(
                ticker=item.ticker,
                shares=item.quantity,
                reference_price=item.latest_completed_close,
                cost_basis=item.cost_basis,
                sector=item.sector,
                modeled_risk_dollars=item.modeled_risk_dollars,
            )
            for item in valuation.positions
            if item.latest_completed_close is not None
        ),
    )
    return state, ResearchPortfolioSchema.model_validate(valuation, from_attributes=True)


@router.get("/current", response_model=ResearchPortfolioSchema | None)
async def get_current_research_portfolio(
    service: Annotated[ResearchPortfolioService, Depends(get_research_portfolio_service)],
) -> ResearchPortfolioSchema | None:
    portfolio = await service.current()
    if portfolio is None:
        return None
    return ResearchPortfolioSchema.model_validate(
        await service.value(portfolio.id), from_attributes=True
    )


@router.get("/{portfolio_id}/daily-brief", response_model=DailyPortfolioBriefCoreSchema)
async def get_daily_portfolio_brief(
    portfolio_id: UUID,
    service: Annotated[DailyPortfolioBriefService, Depends(get_daily_portfolio_brief_service)],
    as_of_date: date | None = None,
) -> DailyPortfolioBriefCoreSchema:
    try:
        brief = await service.build_core(portfolio_id, requested_as_of_date=as_of_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return DailyPortfolioBriefCoreSchema.model_validate(brief, from_attributes=True)


@router.get(
    "/{portfolio_id}/daily-brief/opportunities",
    response_model=DailyBriefOpportunitiesSchema,
)
async def get_daily_brief_opportunities(
    portfolio_id: UUID,
    service: Annotated[DailyPortfolioBriefService, Depends(get_daily_portfolio_brief_service)],
    as_of_date: date | None = None,
    research_only_limit: int = 10,
) -> DailyBriefOpportunitiesSchema:
    if not 1 <= research_only_limit <= 100:
        raise HTTPException(status_code=422, detail="research_only_limit must be 1 through 100")
    try:
        opportunities = await service.build_opportunities(
            portfolio_id,
            requested_as_of_date=as_of_date,
            research_only_limit=research_only_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return DailyBriefOpportunitiesSchema.model_validate(opportunities, from_attributes=True)


@router.post("/{portfolio_id}/live-refresh", response_model=PortfolioLiveBriefSchema)
async def refresh_live_portfolio(
    portfolio_id: UUID,
    service: Annotated[LivePortfolioService, Depends(get_live_portfolio_service)],
) -> PortfolioLiveBriefSchema:
    try:
        return PortfolioLiveBriefSchema.model_validate(
            await service.refresh(portfolio_id), from_attributes=True
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/initialize", response_model=ResearchPortfolioSchema)
async def initialize_research_portfolio(
    request: ResearchPortfolioInitializeSchema,
    service: Annotated[ResearchPortfolioService, Depends(get_research_portfolio_service)],
) -> ResearchPortfolioSchema:
    try:
        portfolio = await service.initialize(
            starting_cash=request.starting_cash,
            name=request.name,
            imported_positions=tuple(
                ImportedPosition(
                    ticker=item.ticker,
                    quantity=item.quantity,
                    average_cost=item.average_cost,
                    cost_basis=item.cost_basis,
                )
                for item in request.imported_positions
            ),
        )
        return ResearchPortfolioSchema.model_validate(
            await service.value(portfolio.id), from_attributes=True
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{portfolio_id}/events", response_model=list[ResearchTradeEventSchema])
async def get_research_portfolio_events(
    portfolio_id: UUID,
    service: Annotated[ResearchPortfolioService, Depends(get_research_portfolio_service)],
) -> list[ResearchTradeEventSchema]:
    return [
        ResearchTradeEventSchema.model_validate(item, from_attributes=True)
        for item in await service.events(portfolio_id)
    ]


@router.get(
    "/{portfolio_id}/reconciliation-events",
    response_model=list[ResearchReconciliationEventSchema],
)
async def get_reconciliation_events(
    portfolio_id: UUID,
    service: Annotated[ResearchPortfolioService, Depends(get_research_portfolio_service)],
) -> list[ResearchReconciliationEventSchema]:
    return [
        ResearchReconciliationEventSchema.model_validate(item, from_attributes=True)
        for item in await service.reconciliation_events(portfolio_id)
    ]


@router.get("/{portfolio_id}/monitoring", response_model=list[PositionMonitoringSchema])
async def get_position_monitoring(
    portfolio_id: UUID,
    service: Annotated[PositionMonitoringService, Depends(get_position_monitoring_service)],
) -> list[PositionMonitoringSchema]:
    positions = await service.portfolios.list_open_positions(portfolio_id)
    output: list[PositionMonitoringSchema] = []
    for position in positions:
        item = await service.monitor_position(position)
        output.append(
            PositionMonitoringSchema(
                position_id=position.id,
                ticker=position.ticker_at_entry,
                strategy_profile_id=position.strategy_profile_id,
                strategy_profile_version=position.strategy_profile_version,
                readiness=item.readiness.value,
                status=item.status.value if item.status else None,
                reason=item.reason.value,
                completed_trading_day=item.completed_trading_day,
                latest_close=item.latest_close,
                indicator_facts=item.indicator_facts,
                exit_triggered=item.exit_triggered,
                exit_triggered_on=item.exit_triggered_on,
                exit_trigger_reason=item.exit_trigger_reason,
                protective_stop_policy=item.protective_stop_policy,
                trailing_stop_policy=item.trailing_stop_policy,
                profit_target_policy=item.profit_target_policy,
            )
        )
    await service.session.commit()
    return output


@router.get(
    "/{portfolio_id}/positions/{position_id}/intelligence",
    response_model=PositionIntelligenceSchema,
)
async def get_position_intelligence(
    portfolio_id: UUID,
    position_id: UUID,
    service: Annotated[PositionIntelligenceService, Depends(get_position_intelligence_service)],
) -> PositionIntelligenceSchema:
    try:
        return PositionIntelligenceSchema.model_validate(
            await service.get_position_intelligence(portfolio_id, position_id),
            from_attributes=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/{portfolio_id}/positions/{position_id}/paper-validations",
    response_model=PaperValidationSchema,
)
async def record_paper_validation_entry(
    portfolio_id: UUID,
    position_id: UUID,
    request: PaperValidationEntryRequestSchema,
    service: Annotated[PaperValidationService, Depends(get_paper_validation_service)],
) -> PaperValidationSchema:
    try:
        return PaperValidationSchema.model_validate(
            await service.record_entry(
                portfolio_id=portfolio_id,
                position_id=position_id,
                actual_quantity=request.actual_quantity,
                actual_entry_price=request.actual_average_fill_price,
                actual_entry_at=request.actual_execution_at,
                note=request.note,
            ),
            from_attributes=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{portfolio_id}/paper-validations", response_model=list[PaperValidationSchema])
async def list_paper_validations(
    portfolio_id: UUID,
    service: Annotated[PaperValidationService, Depends(get_paper_validation_service)],
) -> list[PaperValidationSchema]:
    return [
        PaperValidationSchema.model_validate(item, from_attributes=True)
        for item in await service.list(portfolio_id)
    ]


@router.get(
    "/{portfolio_id}/paper-analytics",
    response_model=ForwardPaperAnalyticsSchema,
)
async def get_forward_paper_analytics(
    portfolio_id: UUID,
    service: Annotated[ForwardPaperAnalyticsService, Depends(get_forward_paper_analytics_service)],
    strategy_profile_id: str | None = None,
    ticker: str | None = None,
    status: str | None = None,
) -> ForwardPaperAnalyticsSchema:
    if status is not None and status not in {"OPEN", "CLOSED"}:
        raise HTTPException(status_code=422, detail="status must be OPEN or CLOSED")
    return ForwardPaperAnalyticsSchema.model_validate(
        await service.summary(
            portfolio_id,
            strategy_profile_id=strategy_profile_id,
            ticker=ticker,
            status=status,
        ),
        from_attributes=True,
    )


@router.get(
    "/{portfolio_id}/paper-analytics/{validation_id}",
    response_model=PaperTradeAnalyticsSchema,
)
async def get_forward_paper_trade_analytics(
    portfolio_id: UUID,
    validation_id: UUID,
    service: Annotated[ForwardPaperAnalyticsService, Depends(get_forward_paper_analytics_service)],
) -> PaperTradeAnalyticsSchema:
    try:
        return PaperTradeAnalyticsSchema.model_validate(
            await service.detail(portfolio_id, validation_id), from_attributes=True
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/{portfolio_id}/positions/{position_id}/paper-validations",
    response_model=list[PaperValidationSchema],
)
async def list_position_paper_validations(
    portfolio_id: UUID,
    position_id: UUID,
    service: Annotated[PaperValidationService, Depends(get_paper_validation_service)],
) -> list[PaperValidationSchema]:
    return [
        PaperValidationSchema.model_validate(item, from_attributes=True)
        for item in await service.list(portfolio_id, position_id=position_id)
    ]


@router.post(
    "/{portfolio_id}/paper-validations/{validation_id}/exit",
    response_model=PaperValidationSchema,
)
async def record_paper_validation_exit(
    portfolio_id: UUID,
    validation_id: UUID,
    request: PaperValidationExitRequestSchema,
    service: Annotated[PaperValidationService, Depends(get_paper_validation_service)],
) -> PaperValidationSchema:
    try:
        return PaperValidationSchema.model_validate(
            await service.record_exit(
                portfolio_id=portfolio_id,
                validation_id=validation_id,
                actual_exit_quantity=request.actual_exit_quantity,
                actual_exit_price=request.actual_average_exit_fill,
                actual_exit_at=request.actual_execution_at,
                note=request.note,
            ),
            from_attributes=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


async def _valued(service: ResearchPortfolioService, portfolio_id: UUID) -> ResearchPortfolioSchema:
    return ResearchPortfolioSchema.model_validate(
        await service.value(portfolio_id), from_attributes=True
    )


@router.post("/{portfolio_id}/cash-adjustments", response_model=ResearchPortfolioSchema)
async def adjust_research_cash(
    portfolio_id: UUID,
    request: CashAdjustmentRequestSchema,
    service: Annotated[ResearchPortfolioService, Depends(get_research_portfolio_service)],
) -> ResearchPortfolioSchema:
    try:
        await service.adjust_cash(
            portfolio_id=portfolio_id,
            expected_revision=request.expected_revision,
            delta=request.delta,
            reason_code=request.reason_code,
            note=request.note,
        )
        return await _valued(service, portfolio_id)
    except StalePortfolioRevisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{portfolio_id}/external-positions", response_model=ResearchPortfolioSchema)
async def add_external_position(
    portfolio_id: UUID,
    request: ExternalPositionRequestSchema,
    service: Annotated[ResearchPortfolioService, Depends(get_research_portfolio_service)],
) -> ResearchPortfolioSchema:
    try:
        await service.import_external_position(
            portfolio_id=portfolio_id,
            expected_revision=request.expected_revision,
            ticker=request.ticker,
            quantity=request.quantity,
            average_cost=request.average_cost,
            entry_trading_day=request.entry_trading_day,
            reason_code=request.reason_code,
            note=request.note,
        )
        return await _valued(service, portfolio_id)
    except StalePortfolioRevisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/{portfolio_id}/positions/{position_id}/reconcile",
    response_model=ResearchPortfolioSchema,
)
async def reconcile_research_position(
    portfolio_id: UUID,
    position_id: UUID,
    request: PositionReconciliationRequestSchema,
    service: Annotated[ResearchPortfolioService, Depends(get_research_portfolio_service)],
) -> ResearchPortfolioSchema:
    try:
        await service.reconcile_position(
            portfolio_id=portfolio_id,
            position_id=position_id,
            expected_revision=request.expected_revision,
            quantity=request.quantity,
            average_cost=request.average_cost,
            entry_trading_day=request.entry_trading_day,
            reason_code=request.reason_code,
            note=request.note,
        )
        return await _valued(service, portfolio_id)
    except StalePortfolioRevisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/risk-config", response_model=PortfolioRiskConfigSchema)
async def get_risk_config() -> PortfolioRiskConfigSchema:
    return PortfolioRiskConfigSchema()


@router.get("/strategy-profiles", response_model=list[StrategyProfileSchema])
async def get_strategy_profiles() -> list[StrategyProfileSchema]:
    return [
        StrategyProfileSchema.model_validate(profile, from_attributes=True)
        for profile in list_strategy_profiles()
    ]


@router.post("/state-summary", response_model=PortfolioDraftSummarySchema)
async def summarize_portfolio_state(
    portfolio: CurrentPortfolioSchema,
) -> PortfolioDraftSummarySchema:
    return build_draft_summary(_state(portfolio))


@router.post("/decisions", response_model=PortfolioDecisionPlanSchema)
async def build_portfolio_decisions(
    request: PortfolioDecisionRequest,
) -> PortfolioDecisionPlanSchema:
    config = PortfolioRiskConfig(**request.risk_config.model_dump())
    state = _state(request.portfolio)
    candidates = tuple(
        PortfolioCandidate(**candidate.model_dump()) for candidate in request.candidates
    )
    plan = PortfolioDecisionEngine().build_plan(
        state,
        candidates,
        config,
        sizing_policy=request.sizing_policy,
    )
    return PortfolioDecisionPlanSchema(
        portfolio=build_portfolio_summary(
            state,
            plan.equity,
            plan.cash_reserve_requirement,
            plan.current_portfolio_risk,
            plan.available_portfolio_risk,
        ),
        config=request.risk_config,
        strategy=request.strategy,
        selection_policy=request.selection_policy,
        sizing_policy=request.sizing_policy,
        decisions=[PortfolioDecisionSchema.model_validate(item) for item in plan.decisions],
    )


@router.post("/plan", response_model=PortfolioPlanSchema)
async def build_portfolio_plan(
    request: PortfolioPlanRequest,
    orchestrator: Annotated[
        PortfolioDecisionOrchestrator,
        Depends(get_portfolio_decision_orchestrator),
    ],
    persistent: Annotated[
        ResearchPortfolioService,
        Depends(get_research_portfolio_service),
    ],
    news: Annotated[NewsService, Depends(get_news_service)],
) -> PortfolioPlanSchema:
    profile = resolve_strategy_profile(request.strategy)
    if request.selection_policy not in profile.allowed_selection_policies:
        raise HTTPException(status_code=422, detail="Selection policy is not allowed")
    config = PortfolioRiskConfig(**request.risk_config.model_dump())
    portfolio_revision: int | None = None
    persistent_schema: ResearchPortfolioSchema | None = None
    if request.portfolio_id is not None:
        state, persistent_schema = await _persistent_state(persistent, request.portfolio_id)
        portfolio_revision = persistent_schema.revision
    elif request.portfolio is not None:
        state = _state(request.portfolio)
    else:
        raise HTTPException(status_code=422, detail="portfolio_id is required for normal plans")
    try:
        result = await orchestrator.build_plan(
            state=state,
            strategy_name=request.strategy,
            selection_policy=request.selection_policy,
            sizing_policy=profile.sizing_policy,
            risk_config=config,
            requested_as_of_date=request.as_of_date,
            tickers=tuple(request.tickers) if request.tickers is not None else None,
            exit_mode=profile.ema_exit_mode or TrendExitMode.HYBRID,
            hybrid_trend_threshold_pct=(profile.hybrid_trend_threshold_pct or Decimal("2")),
            micho_entry_mode=profile.micho_entry_mode or MichoEntryMode.BOTH,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    plan = result.plan
    if request.portfolio_id is not None:
        # Technical facts remain frozen through the completed analysis session, while
        # News evidence is evaluated at the current plan-decision instant.
        as_of = datetime.now(UTC)
        news_decisions = []
        held = {item.ticker.upper(): item for item in state.positions}
        for decision in plan.decisions:
            if decision.reason in {
                PortfolioDecisionReason.ENTRY_TOO_EXTENDED_ABOVE_EMA20,
                PortfolioDecisionReason.EMA20_ENTRY_REVALIDATION_UNAVAILABLE,
            }:
                news_decisions.append(
                    replace(
                        decision,
                        base_decision=decision.decision,
                        final_action="DO_NOT_BUY",
                        news_reason="News was not evaluated because EMA20 entry safety failed.",
                    )
                )
                continue
            assessment = await news.assess(request.portfolio_id, decision.ticker, as_of=as_of)
            original = decision.decision
            updated = decision
            final_action = original.value
            reason = decision.reason
            if original is PortfolioDecisionType.BUY and assessment.effect in {
                NewsEffect.BUY_BLOCKED,
                NewsEffect.EXIT_REQUIRED,
            }:
                updated = replace(
                    updated,
                    decision=PortfolioDecisionType.SKIP,
                    execution_readiness=ExecutionReadiness.RESEARCH_ONLY,
                    execution_readiness_reason=ExecutionReadinessReason.NEWS_RISK_BLOCK,
                )
                final_action = "DO_NOT_BUY"
                reason = PortfolioDecisionReason.NEWS_RISK_BLOCK
            elif original is PortfolioDecisionType.BUY and assessment.effect in {
                NewsEffect.NEWS_ASSESSMENT_UNAVAILABLE,
                NewsEffect.NEWS_ASSESSMENT_PARTIAL,
            }:
                updated = replace(
                    updated,
                    decision=PortfolioDecisionType.SKIP,
                    execution_readiness=ExecutionReadiness.UNAVAILABLE,
                    execution_readiness_reason=(
                        ExecutionReadinessReason.NEWS_ASSESSMENT_UNAVAILABLE
                    ),
                )
                final_action = "DO_NOT_BUY"
                reason = PortfolioDecisionReason.NEWS_ASSESSMENT_UNAVAILABLE
            elif assessment.effect is NewsEffect.EXIT_REQUIRED and decision.ticker.upper() in held:
                position = held[decision.ticker.upper()]
                updated = replace(
                    updated,
                    decision=PortfolioDecisionType.SELL,
                    current_shares=position.shares,
                    estimated_proceeds=position.market_value,
                )
                final_action = "EXIT_REQUIRED"
                reason = PortfolioDecisionReason.NEWS_RISK_EXIT
            updated = replace(
                updated,
                reason=reason,
                base_decision=original,
                news_effect=assessment.effect.value,
                news_coverage=assessment.coverage.value,
                final_action=final_action,
                news_reason=assessment.reason,
                news_policy_version=assessment.policy_version,
                supporting_news_article_ids=assessment.supporting_article_ids,
            )
            news_decisions.append(updated)
        plan = replace(plan, decisions=tuple(news_decisions))
    return PortfolioPlanSchema(
        plan_id=strategy_profile_plan_id(request, profile, portfolio_revision),
        strategy_profile=StrategyProfileSchema.model_validate(profile, from_attributes=True),
        portfolio=build_portfolio_summary(
            state,
            plan.equity,
            plan.cash_reserve_requirement,
            plan.current_portfolio_risk,
            plan.available_portfolio_risk,
        ),
        config=request.risk_config,
        strategy=request.strategy.value,
        selection_policy=request.selection_policy.value,
        sizing_policy=profile.sizing_policy,
        decisions=[PortfolioDecisionSchema.model_validate(item) for item in plan.decisions],
        requested_as_of_date=result.requested_as_of_date,
        analysis_as_of_date=result.analysis_as_of_date,
        candidate_statuses=[
            CandidateOrchestrationStatusSchema.model_validate(item, from_attributes=True)
            for item in result.statuses
        ],
        readiness=PortfolioPlanReadinessSchema.model_validate(
            result.readiness, from_attributes=True
        ),
        evaluation_target_ticker=result.evaluation_target_ticker,
        portfolio_id=request.portfolio_id,
        portfolio_revision=portfolio_revision,
    )


async def _plan_action_result(
    request: PortfolioPlanActionRequest,
    persistent: ResearchPortfolioService,
    *,
    apply: bool,
) -> PortfolioPlanActionResultSchema:
    try:
        profile = resolve_strategy_profile_identity(
            request.strategy_profile_id,
            request.strategy_profile_version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if request.sizing_policy != profile.sizing_policy:
        raise HTTPException(
            status_code=422,
            detail="Sizing policy does not match the authoritative strategy profile",
        )
    exit_context = request.decision.exit_context
    if exit_context is not None and exit_context.strategy != profile.strategy:
        raise HTTPException(
            status_code=422,
            detail="Decision strategy does not match the authoritative strategy profile",
        )
    decision_data = request.decision.model_dump()
    decision_data["depends_on_action_ids"] = tuple(decision_data["depends_on_action_ids"])
    exit_context = decision_data.get("exit_context")
    if exit_context is not None:
        from alphapilot.portfolio.exit_guidance import StrategyExitContext

        decision_data["exit_context"] = StrategyExitContext(**exit_context)
    entry_safety = decision_data.get("entry_safety")
    if entry_safety is not None:
        decision_data["entry_safety"] = Ema20EntrySafety(**entry_safety)
    persistent_mode = request.portfolio_id is not None
    if persistent_mode:
        if request.portfolio_revision is None:
            raise HTTPException(status_code=422, detail="portfolio_revision is required")
        assert request.portfolio_id is not None
        state, current_portfolio = await _persistent_state(persistent, request.portfolio_id)
        if current_portfolio.revision != request.portfolio_revision:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Stale portfolio revision {request.portfolio_revision}; "
                    f"current revision is {current_portfolio.revision}"
                ),
            )
    elif request.portfolio is not None:
        state = _state(request.portfolio)
    else:
        raise HTTPException(status_code=422, detail="portfolio_id is required")
    decision = PortfolioDecision(**decision_data)
    result = PortfolioPlanActionService().apply(
        state=state,
        decision=decision,
        applied_action_ids=frozenset(request.applied_action_ids),
        requested_shares=request.requested_shares,
        config=PortfolioRiskConfig(**request.risk_config.model_dump()),
        sizing_policy=request.sizing_policy,
        apply=apply,
        require_ema20_entry_safety=profile.strategy.value == "ema20-pullback",
    )
    resulting_portfolio_id = request.portfolio_id
    resulting_revision = request.portfolio_revision
    result_state = result.portfolio
    if apply and result.applied and persistent_mode:
        assert request.portfolio_id is not None
        assert request.portfolio_revision is not None
        try:
            if decision.decision.value == "BUY":
                await persistent.buy(
                    portfolio_id=request.portfolio_id,
                    expected_revision=request.portfolio_revision,
                    ticker=decision.ticker,
                    quantity=result.requested_shares,
                    execution_price=decision.reference_price,
                    trading_day=request.analysis_as_of_date,
                    strategy=profile.strategy.value,
                    profile_id=profile.profile_id,
                    profile_version=profile.version,
                    profile_snapshot=StrategyProfileSchema.model_validate(
                        profile, from_attributes=True
                    ).model_dump(mode="json"),
                    selection_policy=request.selection_policy.value,
                    decision=decision.decision.value,
                    reason=decision.reason.value,
                    modeled_risk_dollars=result.modeled_position_risk_dollars or Decimal("0"),
                    action_id=result.action_id or request.plan_id,
                    decision_evidence={
                        "schema_version": 2,
                        "base_decision": decision.base_decision.value
                        if decision.base_decision
                        else decision.decision.value,
                        "news_effect": decision.news_effect,
                        "news_coverage": decision.news_coverage,
                        "final_action": decision.final_action or decision.decision.value,
                        "news_reason": decision.news_reason,
                        "news_policy_version": decision.news_policy_version,
                        "supporting_news_article_ids": [
                            str(item) for item in decision.supporting_news_article_ids
                        ],
                        "entry_safety": (
                            {
                                "policy_version": decision.entry_safety.policy_version,
                                "entry_price": str(decision.entry_safety.entry_price),
                                "entry_price_source": (
                                    decision.entry_safety.entry_price_source.value
                                    if decision.entry_safety.entry_price_source
                                    else None
                                ),
                                "entry_price_timestamp": (
                                    decision.entry_safety.entry_price_timestamp.isoformat()
                                    if decision.entry_safety.entry_price_timestamp
                                    else None
                                ),
                                "ema20": str(decision.entry_safety.ema20),
                                "ema20_as_of": (
                                    decision.entry_safety.ema20_as_of.isoformat()
                                    if decision.entry_safety.ema20_as_of
                                    else None
                                ),
                                "distance_to_ema20_pct": str(
                                    decision.entry_safety.distance_to_ema20_pct
                                ),
                                "entry_relation": decision.entry_safety.relation.value,
                                "entry_safety_result": decision.entry_safety.status.value,
                                "reason": decision.entry_safety.reason.value,
                            }
                            if decision.entry_safety is not None
                            else None
                        ),
                    },
                )
            else:
                await persistent.sell(
                    portfolio_id=request.portfolio_id,
                    expected_revision=request.portfolio_revision,
                    ticker=decision.ticker,
                    quantity=result.requested_shares,
                    execution_price=decision.reference_price,
                    trading_day=request.analysis_as_of_date,
                    source="PORTFOLIO_PLAN",
                    reason=decision.reason.value,
                    action_id=result.action_id,
                )
        except StalePortfolioRevisionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        result_state, persisted = await _persistent_state(persistent, request.portfolio_id)
        resulting_revision = persisted.revision
    return PortfolioPlanActionResultSchema(
        plan_id=request.plan_id,
        applied=result.applied,
        reason=result.reason,
        action_id=result.action_id,
        action_type=result.action_type,
        cash_before=result.cash_before,
        cash_impact=result.cash_impact,
        cash_after=result.cash_after,
        position_before=(
            PortfolioPositionSchema.model_validate(result.position_before, from_attributes=True)
            if result.position_before
            else None
        ),
        position_after=(
            PortfolioPositionSchema.model_validate(result.position_after, from_attributes=True)
            if result.position_after
            else None
        ),
        portfolio=_state_schema(result_state),
        summary=build_draft_summary(result_state),
        validation_status=result.validation_status,
        quantity_semantics=result.quantity_semantics,
        recommended_shares=result.recommended_shares,
        requested_shares=result.requested_shares,
        recommended_allocation_dollars=result.recommended_allocation_dollars,
        requested_allocation_dollars=result.requested_allocation_dollars,
        resulting_position_weight_pct=result.resulting_position_weight_pct,
        sector_weight_before_pct=result.sector_weight_before_pct,
        sector_weight_after_pct=result.sector_weight_after_pct,
        modeled_position_risk_dollars=result.modeled_position_risk_dollars,
        portfolio_risk_after_dollars=result.portfolio_risk_after_dollars,
        cash_reserve_requirement=result.cash_reserve_requirement,
        portfolio_id=resulting_portfolio_id,
        portfolio_revision=resulting_revision,
    )


@router.post("/preview-action", response_model=PortfolioPlanActionResultSchema)
async def preview_portfolio_plan_action(
    request: PortfolioPlanActionRequest,
    persistent: Annotated[ResearchPortfolioService, Depends(get_research_portfolio_service)],
) -> PortfolioPlanActionResultSchema:
    return await _plan_action_result(request, persistent, apply=False)


@router.post("/apply-action", response_model=PortfolioPlanActionResultSchema)
async def apply_portfolio_plan_action(
    request: PortfolioPlanActionRequest,
    persistent: Annotated[ResearchPortfolioService, Depends(get_research_portfolio_service)],
) -> PortfolioPlanActionResultSchema:
    return await _plan_action_result(request, persistent, apply=True)


@router.get("/latest-price/{ticker}", response_model=LatestStoredPriceSchema)
async def get_latest_stored_price(
    ticker: str,
    service: Annotated[ManualPortfolioSellService, Depends(get_manual_sell_service)],
) -> LatestStoredPriceSchema:
    normalized = ticker.strip().upper()
    stored = await service.prices.get_latest_stored_price(normalized)
    return LatestStoredPriceSchema(
        ticker=normalized,
        price=stored[0] if stored else None,
        price_date=stored[1] if stored else None,
    )


async def _manual_sell(
    request: ManualSellRequestSchema,
    service: ManualPortfolioSellService,
    persistent: ResearchPortfolioService,
    *,
    apply: bool,
) -> ManualSellResultSchema:
    persistent_mode = request.portfolio_id is not None
    if persistent_mode:
        if request.portfolio_revision is None:
            raise HTTPException(status_code=422, detail="portfolio_revision is required")
        assert request.portfolio_id is not None
        state, current_portfolio = await _persistent_state(persistent, request.portfolio_id)
        if current_portfolio.revision != request.portfolio_revision:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Stale portfolio revision {request.portfolio_revision}; "
                    f"current revision is {current_portfolio.revision}"
                ),
            )
    elif request.portfolio is not None:
        state = _state(request.portfolio)
    else:
        raise HTTPException(status_code=422, detail="portfolio_id is required")
    result = await service.sell(
        state=state,
        ticker=request.ticker,
        shares_to_sell=request.shares_to_sell,
        execution_price=request.execution_price,
        apply=apply,
    )
    result_state = result.portfolio
    resulting_revision = request.portfolio_revision
    if apply and result.applied and persistent_mode:
        assert request.portfolio_id is not None
        assert request.portfolio_revision is not None
        assert result.execution_price is not None
        try:
            await persistent.sell(
                portfolio_id=request.portfolio_id,
                expected_revision=request.portfolio_revision,
                ticker=result.ticker,
                quantity=result.shares_sold,
                execution_price=result.execution_price,
                trading_day=result.price_date,
                source=result.price_source.value if result.price_source else "MANUAL_RESEARCH",
                reason="MANUAL_RESEARCH_SELL",
                action_id=None,
            )
        except StalePortfolioRevisionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        result_state, persisted = await _persistent_state(persistent, request.portfolio_id)
        resulting_revision = persisted.revision
    return ManualSellResultSchema(
        applied=result.applied,
        reason=result.reason,
        ticker=result.ticker,
        shares_sold=result.shares_sold,
        shares_remaining=result.shares_remaining,
        execution_price=result.execution_price,
        price_source=result.price_source,
        price_date=result.price_date,
        gross_proceeds=result.gross_proceeds,
        cash_before=result.cash_before,
        cash_after=result.cash_after,
        position_removed=result.position_removed,
        portfolio=_state_schema(result_state),
        summary=build_draft_summary(result_state),
        portfolio_id=request.portfolio_id,
        portfolio_revision=resulting_revision,
    )


@router.post("/manual-sell/preview", response_model=ManualSellResultSchema)
async def preview_manual_sell(
    request: ManualSellRequestSchema,
    service: Annotated[ManualPortfolioSellService, Depends(get_manual_sell_service)],
    persistent: Annotated[ResearchPortfolioService, Depends(get_research_portfolio_service)],
) -> ManualSellResultSchema:
    return await _manual_sell(request, service, persistent, apply=False)


@router.post("/manual-sell", response_model=ManualSellResultSchema)
async def apply_manual_sell(
    request: ManualSellRequestSchema,
    service: Annotated[ManualPortfolioSellService, Depends(get_manual_sell_service)],
    persistent: Annotated[ResearchPortfolioService, Depends(get_research_portfolio_service)],
) -> ManualSellResultSchema:
    return await _manual_sell(request, service, persistent, apply=True)
