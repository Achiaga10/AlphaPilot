from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from alphapilot.database.session import get_db
from alphapilot.portfolio.decisions import (
    CurrentPortfolioState,
    PortfolioCandidate,
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
    PortfolioDecisionPlanSchema,
    PortfolioDecisionRequest,
    PortfolioDecisionSchema,
    PortfolioPlanRequest,
    PortfolioPlanSchema,
    PortfolioRiskConfigSchema,
    PortfolioSummarySchema,
)
from alphapilot.services.company import CompanyService
from alphapilot.services.daily_candle import DailyCandleService

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def get_portfolio_decision_orchestrator(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PortfolioDecisionOrchestrator:
    return PortfolioDecisionOrchestrator(
        CompanyService(CompanyRepository(session)),
        DailyCandleService(DailyCandleRepository(session)),
        IndexConstituentRepository(session),
    )


@router.get("/risk-config", response_model=PortfolioRiskConfigSchema)
async def get_risk_config() -> PortfolioRiskConfigSchema:
    return PortfolioRiskConfigSchema()


@router.post("/decisions", response_model=PortfolioDecisionPlanSchema)
async def build_portfolio_decisions(
    request: PortfolioDecisionRequest,
) -> PortfolioDecisionPlanSchema:
    config = PortfolioRiskConfig(**request.risk_config.model_dump())
    state = CurrentPortfolioState(
        cash=request.portfolio.cash,
        positions=tuple(
            PortfolioStatePosition(**position.model_dump())
            for position in request.portfolio.positions
        ),
    )
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
        portfolio=PortfolioSummarySchema(
            equity=plan.equity,
            cash=plan.cash,
            cash_reserve_requirement=plan.cash_reserve_requirement,
            current_portfolio_risk=plan.current_portfolio_risk,
            available_portfolio_risk=plan.available_portfolio_risk,
            open_positions=plan.open_positions,
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
    state = CurrentPortfolioState(
        cash=request.portfolio.cash,
        positions=tuple(
            PortfolioStatePosition(**position.model_dump())
            for position in request.portfolio.positions
        ),
    )
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
        portfolio=PortfolioSummarySchema(
            equity=plan.equity,
            cash=plan.cash,
            cash_reserve_requirement=plan.cash_reserve_requirement,
            current_portfolio_risk=plan.current_portfolio_risk,
            available_portfolio_risk=plan.available_portfolio_risk,
            open_positions=plan.open_positions,
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
    )
