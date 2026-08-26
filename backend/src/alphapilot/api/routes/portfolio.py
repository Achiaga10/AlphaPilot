import hashlib
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.session import get_db
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
from alphapilot.portfolio.orchestration import PortfolioDecisionOrchestrator
from alphapilot.portfolio.risk import PortfolioRiskConfig
from alphapilot.repositories.company import CompanyRepository
from alphapilot.repositories.daily_candle import DailyCandleRepository
from alphapilot.repositories.index_constituent import IndexConstituentRepository
from alphapilot.schemas.portfolio import (
    CandidateOrchestrationStatusSchema,
    CurrentPortfolioSchema,
    LatestStoredPriceSchema,
    ManualSellRequestSchema,
    ManualSellResultSchema,
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
)
from alphapilot.services.company import CompanyService
from alphapilot.services.daily_candle import DailyCandleService, LatestStoredPriceService

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


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
    )


def get_manual_sell_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ManualPortfolioSellService:
    companies = CompanyService(CompanyRepository(session))
    prices = LatestStoredPriceService(companies, DailyCandleRepository(session))
    return ManualPortfolioSellService(prices)


@router.get("/risk-config", response_model=PortfolioRiskConfigSchema)
async def get_risk_config() -> PortfolioRiskConfigSchema:
    return PortfolioRiskConfigSchema()


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
) -> PortfolioPlanSchema:
    config = PortfolioRiskConfig(**request.risk_config.model_dump())
    state = _state(request.portfolio)
    try:
        result = await orchestrator.build_plan(
            state=state,
            strategy_name=request.strategy,
            selection_policy=request.selection_policy,
            sizing_policy=request.sizing_policy,
            risk_config=config,
            requested_as_of_date=request.as_of_date,
            tickers=tuple(request.tickers) if request.tickers is not None else None,
            exit_mode=request.exit_mode,
            hybrid_trend_threshold_pct=request.hybrid_trend_threshold_pct,
            micho_entry_mode=request.micho_entry_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    plan = result.plan
    return PortfolioPlanSchema(
        plan_id=hashlib.sha256(request.model_dump_json().encode()).hexdigest()[:24],
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
        sizing_policy=request.sizing_policy,
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
    )


def _plan_action_result(
    request: PortfolioPlanActionRequest,
    *,
    apply: bool,
) -> PortfolioPlanActionResultSchema:
    decision_data = request.decision.model_dump()
    decision_data["depends_on_action_ids"] = tuple(decision_data["depends_on_action_ids"])
    exit_context = decision_data.get("exit_context")
    if exit_context is not None:
        from alphapilot.portfolio.exit_guidance import StrategyExitContext

        decision_data["exit_context"] = StrategyExitContext(**exit_context)
    result = PortfolioPlanActionService().apply(
        state=_state(request.portfolio),
        decision=PortfolioDecision(**decision_data),
        applied_action_ids=frozenset(request.applied_action_ids),
        requested_shares=request.requested_shares,
        config=PortfolioRiskConfig(**request.risk_config.model_dump()),
        sizing_policy=request.sizing_policy,
        apply=apply,
    )
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
        portfolio=_state_schema(result.portfolio),
        summary=build_draft_summary(result.portfolio),
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
    )


@router.post("/preview-action", response_model=PortfolioPlanActionResultSchema)
async def preview_portfolio_plan_action(
    request: PortfolioPlanActionRequest,
) -> PortfolioPlanActionResultSchema:
    return _plan_action_result(request, apply=False)


@router.post("/apply-action", response_model=PortfolioPlanActionResultSchema)
async def apply_portfolio_plan_action(
    request: PortfolioPlanActionRequest,
) -> PortfolioPlanActionResultSchema:
    return _plan_action_result(request, apply=True)


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
    *,
    apply: bool,
) -> ManualSellResultSchema:
    result = await service.sell(
        state=_state(request.portfolio),
        ticker=request.ticker,
        shares_to_sell=request.shares_to_sell,
        execution_price=request.execution_price,
        apply=apply,
    )
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
        portfolio=_state_schema(result.portfolio),
        summary=build_draft_summary(result.portfolio),
    )


@router.post("/manual-sell/preview", response_model=ManualSellResultSchema)
async def preview_manual_sell(
    request: ManualSellRequestSchema,
    service: Annotated[ManualPortfolioSellService, Depends(get_manual_sell_service)],
) -> ManualSellResultSchema:
    return await _manual_sell(request, service, apply=False)


@router.post("/manual-sell", response_model=ManualSellResultSchema)
async def apply_manual_sell(
    request: ManualSellRequestSchema,
    service: Annotated[ManualPortfolioSellService, Depends(get_manual_sell_service)],
) -> ManualSellResultSchema:
    return await _manual_sell(request, service, apply=True)
