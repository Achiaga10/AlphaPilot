import { requestJson } from './client'
import type {
  HealthResponse,
  CurrentPortfolioInput,
  LatestStoredPrice,
  ManualSellRequest,
  ManualSellResult,
  PortfolioDraftSummary,
  PortfolioPlanActionRequest,
  PortfolioPlanActionResult,
  PortfolioPlan,
  PortfolioPlanRequest,
  PortfolioRiskConfig,
  ResearchPortfolio,
  ResearchPortfolioInitialize,
  PositionMonitoring,
  CashAdjustmentRequest,
  ExternalPositionRequest,
  PositionReconciliationRequest,
  PositionIntelligence,
  PaperValidation,
  PaperValidationEntryRequest,
  PaperValidationExitRequest,
  StrategyProfile,
  CopilotAnswer,
  UnifiedCopilotQuestion,
  DailyPortfolioBrief,
  DailyBriefOpportunities,
  PortfolioLiveBrief,
} from '../types/portfolio'

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isRiskConfig(value: unknown): value is PortfolioRiskConfig {
  return (
    isObject(value) &&
    typeof value.atr_period === 'number' &&
    typeof value.risk_per_position_pct === 'string' &&
    typeof value.max_positions === 'number'
  )
}

function isHealth(value: unknown): value is HealthResponse {
  return isObject(value) && typeof value.status === 'string' && typeof value.application === 'string'
}

function isPortfolioPlan(value: unknown): value is PortfolioPlan {
  if (!isObject(value) || !isStrategyProfile(value.strategy_profile)) return false
  return (
    isObject(value.portfolio) &&
    Array.isArray(value.decisions) &&
    Array.isArray(value.candidate_statuses) &&
    (typeof value.evaluation_target_ticker === 'string' || value.evaluation_target_ticker === null) &&
    isObject(value.readiness) &&
    typeof value.plan_id === 'string' &&
    typeof value.portfolio_id === 'string' &&
    typeof value.portfolio_revision === 'number' &&
    typeof value.requested_as_of_date === 'string' &&
    typeof value.analysis_as_of_date === 'string' &&
    value.strategy === value.strategy_profile.strategy &&
    value.sizing_policy === value.strategy_profile.sizing_policy &&
    selectionPolicies.has(String(value.selection_policy))
  )
}

const strategyNames = new Set(['ema20-pullback', 'micho-150'])
const selectionPolicies = new Set(['relative-strength-20', 'ticker-ascending'])
const sizingPolicies = new Set(['equal-slot', 'atr-risk', 'atr-volatility-normalized'])

function isStrategyProfile(value: unknown): value is StrategyProfile {
  return (
    isObject(value) &&
    typeof value.profile_id === 'string' &&
    typeof value.version === 'number' &&
    strategyNames.has(String(value.strategy)) &&
    typeof value.display_name === 'string' &&
    (value.classification === 'PROMISING_RESEARCH_BASELINE' || value.classification === 'RESEARCH_ONLY') &&
    typeof value.entry_description === 'string' &&
    selectionPolicies.has(String(value.recommended_selection_policy)) &&
    Array.isArray(value.allowed_selection_policies) &&
    value.allowed_selection_policies.every((item) => selectionPolicies.has(String(item))) &&
    sizingPolicies.has(String(value.sizing_policy)) &&
    typeof value.strategy_exit_description === 'string' &&
    (value.ema_exit_mode === 'hybrid' || value.ema_exit_mode === null) &&
    (typeof value.hybrid_trend_threshold_pct === 'string' || value.hybrid_trend_threshold_pct === null) &&
    (value.micho_entry_mode === 'both' || value.micho_entry_mode === null) &&
    value.protective_stop_default === 'NONE' &&
    value.profit_management_default === 'NONE' &&
    typeof value.research_only_stop_candidate === 'string'
  )
}

const isStrategyProfiles = (value: unknown): value is StrategyProfile[] =>
  Array.isArray(value) && value.length > 0 && value.every(isStrategyProfile)

const isDraftSummary = (value: unknown): value is PortfolioDraftSummary =>
  isObject(value) && typeof value.equity === 'string' && Array.isArray(value.positions)

const isActionResult = (value: unknown): value is PortfolioPlanActionResult =>
  isObject(value) && typeof value.applied === 'boolean' && isObject(value.portfolio) &&
  typeof value.portfolio_id === 'string' && typeof value.portfolio_revision === 'number' &&
  isDraftSummary(value.summary)

const isLatestPrice = (value: unknown): value is LatestStoredPrice =>
  isObject(value) && typeof value.ticker === 'string' && ('price' in value)

const isManualSell = (value: unknown): value is ManualSellResult =>
  isObject(value) && typeof value.applied === 'boolean' && typeof value.reason === 'string' &&
  typeof value.portfolio_id === 'string' && typeof value.portfolio_revision === 'number' && isObject(value.portfolio)

const isResearchPortfolio = (value: unknown): value is ResearchPortfolio =>
  isObject(value) && typeof value.portfolio_id === 'string' && typeof value.revision === 'number' &&
  typeof value.cash === 'string' && typeof value.realized_pnl === 'string' &&
  typeof value.total_cost_basis === 'string' &&
  (typeof value.positions_market_value === 'string' || value.positions_market_value === null) &&
  (typeof value.total_equity === 'string' || value.total_equity === null) &&
  (typeof value.cash_pct === 'string' || value.cash_pct === null) &&
  (typeof value.invested_pct === 'string' || value.invested_pct === null) &&
  (typeof value.total_unrealized_pnl === 'string' || value.total_unrealized_pnl === null) &&
  Array.isArray(value.positions) && value.positions.every((position) =>
    isObject(position) && typeof position.position_id === 'string' &&
    typeof position.ticker === 'string' && typeof position.quantity === 'number' &&
    typeof position.average_cost === 'string' && typeof position.cost_basis === 'string' &&
    (typeof position.latest_completed_close === 'string' || position.latest_completed_close === null) &&
    (typeof position.market_value === 'string' || position.market_value === null) &&
    (typeof position.unrealized_pnl === 'string' || position.unrealized_pnl === null) &&
    (typeof position.unrealized_pnl_pct === 'string' || position.unrealized_pnl_pct === null),
  )

const isNullableResearchPortfolio = (value: unknown): value is ResearchPortfolio | null =>
  value === null || isResearchPortfolio(value)

const isDailyPortfolioBrief = (value: unknown): value is DailyPortfolioBrief =>
  isObject(value) && typeof value.portfolio_id === 'string' &&
  typeof value.portfolio_revision === 'number' && isObject(value.data_status) &&
  (value.data_status.readiness === 'READY' || value.data_status.readiness === 'DEGRADED' || value.data_status.readiness === 'BLOCKED') &&
  isObject(value.summary) && Array.isArray(value.required_actions) &&
  Array.isArray(value.attention_positions) &&
  Array.isArray(value.hold_positions) && Array.isArray(value.unavailable_positions) &&
  Array.isArray(value.blockers)

const isDailyBriefOpportunities = (value: unknown): value is DailyBriefOpportunities =>
  isObject(value) && typeof value.portfolio_id === 'string' &&
  typeof value.portfolio_revision === 'number' &&
  Array.isArray(value.actionable_opportunities) &&
  Array.isArray(value.research_only_opportunities) &&
  Array.isArray(value.deferred_opportunities) &&
  typeof value.actionable_total_count === 'number' &&
  typeof value.research_only_total_count === 'number' &&
  typeof value.deferred_total_count === 'number'

const isPortfolioLiveBrief = (value: unknown): value is PortfolioLiveBrief =>
  isObject(value) && typeof value.portfolio_id === 'string' &&
  typeof value.portfolio_revision === 'number' &&
  typeof value.live_refresh_timestamp === 'string' &&
  typeof value.provider === 'string' && typeof value.feed === 'string' &&
  typeof value.overall_readiness === 'string' && Array.isArray(value.positions) &&
  value.positions.every((item) => isObject(item) && typeof item.position_id === 'string' &&
    typeof item.ticker === 'string' && typeof item.live_status === 'string') &&
  Array.isArray(value.partial_failures)

const isMonitoring = (value: unknown): value is PositionMonitoring[] =>
  Array.isArray(value) && value.every((item) => isObject(item) &&
    typeof item.position_id === 'string' && typeof item.ticker === 'string' &&
    (item.readiness === 'READY' || item.readiness === 'UNAVAILABLE') &&
    (item.status === 'HOLD' || item.status === 'ATTENTION' || item.status === 'SELL' || item.status === null) &&
    typeof item.reason === 'string' && isObject(item.indicator_facts))

const isPositionIntelligence = (value: unknown): value is PositionIntelligence =>
  isObject(value) && typeof value.portfolio_id === 'string' &&
  typeof value.position_id === 'string' && typeof value.ticker === 'string' &&
  typeof value.strategy_guidance_available === 'boolean' &&
  typeof value.average_cost === 'string' && typeof value.cost_basis === 'string' &&
  typeof value.monitoring_readiness === 'string' &&
  (value.monitoring_status === 'HOLD' || value.monitoring_status === 'ATTENTION' ||
    value.monitoring_status === 'SELL' || value.monitoring_status === null) &&
  isObject(value.indicator_facts) && typeof value.explanation === 'string' &&
  typeof value.protective_stop_policy === 'string' &&
  typeof value.trailing_stop_policy === 'string' && typeof value.profit_target_policy === 'string'

const isPaperValidation = (value: unknown): value is PaperValidation =>
  isObject(value) && typeof value.id === 'string' && typeof value.position_id === 'string' &&
  typeof value.ticker === 'string' && (value.status === 'OPEN' || value.status === 'CLOSED') &&
  value.execution_source === 'ALPACA_PAPER_MANUAL' && typeof value.actual_quantity === 'number' &&
  typeof value.actual_entry_price === 'string' && typeof value.actual_entry_at === 'string' &&
  (typeof value.entry_fill_difference_bps === 'string' || value.entry_fill_difference_bps === null)

const isPaperValidations = (value: unknown): value is PaperValidation[] =>
  Array.isArray(value) && value.every(isPaperValidation)

const isCopilotAnswer = (value: unknown): value is CopilotAnswer =>
  isObject(value) && typeof value.answer === 'string' && value.answer.length > 0 &&
  (value.scope === 'GENERAL' || value.scope === 'POSITION' || value.scope === 'PORTFOLIO') &&
  (typeof value.portfolio_id === 'string' || value.portfolio_id === null) &&
  (typeof value.position_id === 'string' || value.position_id === null) &&
  (typeof value.ticker === 'string' || value.ticker === null) &&
  (value.grounding_status === 'GROUNDED' || value.grounding_status === 'LIMITED') &&
  Array.isArray(value.fact_refs) &&
  value.fact_refs.every((fact) => isObject(fact) && typeof fact.fact_id === 'string' &&
    typeof fact.source === 'string' && typeof fact.field === 'string' &&
    typeof fact.label === 'string' && 'value' in fact) &&
  Array.isArray(value.limitations) && value.limitations.every((item) => typeof item === 'string') &&
  typeof value.provider === 'string' && typeof value.model === 'string'

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return requestJson('/api/v1/health/', { signal }, isHealth)
}

export function getRiskConfig(signal?: AbortSignal): Promise<PortfolioRiskConfig> {
  return requestJson('/api/v1/portfolio/risk-config', { signal }, isRiskConfig)
}

export function getStrategyProfiles(signal?: AbortSignal): Promise<StrategyProfile[]> {
  return requestJson('/api/v1/portfolio/strategy-profiles', { signal }, isStrategyProfiles)
}

export function getCurrentResearchPortfolio(signal?: AbortSignal): Promise<ResearchPortfolio | null> {
  return requestJson('/api/v1/portfolio/current', { signal }, isNullableResearchPortfolio)
}

export function getDailyPortfolioBrief(
  portfolioId: string,
  signal?: AbortSignal,
): Promise<DailyPortfolioBrief> {
  return requestJson(
    `/api/v1/portfolio/${portfolioId}/daily-brief`,
    { signal },
    isDailyPortfolioBrief,
  )
}

export function getDailyBriefOpportunities(
  portfolioId: string,
  researchOnlyLimit = 10,
  signal?: AbortSignal,
): Promise<DailyBriefOpportunities> {
  return requestJson(
    `/api/v1/portfolio/${portfolioId}/daily-brief/opportunities?research_only_limit=${researchOnlyLimit}`,
    { signal },
    isDailyBriefOpportunities,
  )
}

export function refreshLivePortfolio(portfolioId: string): Promise<PortfolioLiveBrief> {
  return requestJson(
    `/api/v1/portfolio/${portfolioId}/live-refresh`,
    { method: 'POST' },
    isPortfolioLiveBrief,
  )
}

export function initializeResearchPortfolio(
  request: ResearchPortfolioInitialize,
): Promise<ResearchPortfolio> {
  return requestJson(
    '/api/v1/portfolio/initialize',
    { method: 'POST', body: JSON.stringify(request) },
    isResearchPortfolio,
  )
}

export function getPositionMonitoring(portfolioId: string, signal?: AbortSignal): Promise<PositionMonitoring[]> {
  return requestJson(`/api/v1/portfolio/${portfolioId}/monitoring`, { signal }, isMonitoring)
}

export function adjustResearchCash(portfolioId: string, request: CashAdjustmentRequest): Promise<ResearchPortfolio> {
  return requestJson(`/api/v1/portfolio/${portfolioId}/cash-adjustments`, { method: 'POST', body: JSON.stringify(request) }, isResearchPortfolio)
}

export function addExternalPosition(portfolioId: string, request: ExternalPositionRequest): Promise<ResearchPortfolio> {
  return requestJson(`/api/v1/portfolio/${portfolioId}/external-positions`, { method: 'POST', body: JSON.stringify(request) }, isResearchPortfolio)
}

export function reconcileResearchPosition(portfolioId: string, positionId: string, request: PositionReconciliationRequest): Promise<ResearchPortfolio> {
  return requestJson(`/api/v1/portfolio/${portfolioId}/positions/${positionId}/reconcile`, { method: 'POST', body: JSON.stringify(request) }, isResearchPortfolio)
}

export function getPositionIntelligence(portfolioId: string, positionId: string, signal?: AbortSignal): Promise<PositionIntelligence> {
  return requestJson(`/api/v1/portfolio/${portfolioId}/positions/${positionId}/intelligence`, { signal }, isPositionIntelligence)
}

export function getPositionPaperValidations(portfolioId: string, positionId: string, signal?: AbortSignal): Promise<PaperValidation[]> {
  return requestJson(`/api/v1/portfolio/${portfolioId}/positions/${positionId}/paper-validations`, { signal }, isPaperValidations)
}

export function recordPaperValidationEntry(portfolioId: string, positionId: string, request: PaperValidationEntryRequest): Promise<PaperValidation> {
  return requestJson(`/api/v1/portfolio/${portfolioId}/positions/${positionId}/paper-validations`, { method: 'POST', body: JSON.stringify(request) }, isPaperValidation)
}

export function recordPaperValidationExit(portfolioId: string, validationId: string, request: PaperValidationExitRequest): Promise<PaperValidation> {
  return requestJson(`/api/v1/portfolio/${portfolioId}/paper-validations/${validationId}/exit`, { method: 'POST', body: JSON.stringify(request) }, isPaperValidation)
}

export function askPositionCopilot(portfolioId: string, positionId: string, question: string): Promise<CopilotAnswer> {
  return requestJson(
    `/api/v1/ai/copilot/portfolio/${portfolioId}/positions/${positionId}/ask`,
    { method: 'POST', body: JSON.stringify({ question }) },
    isCopilotAnswer,
  )
}

export function askPortfolioCopilot(portfolioId: string, question: string): Promise<CopilotAnswer> {
  return requestJson(`/api/v1/ai/copilot/portfolio/${portfolioId}/ask`, { method: 'POST', body: JSON.stringify({ question }) }, isCopilotAnswer)
}

export function askGeneralCopilot(question: string): Promise<CopilotAnswer> {
  return requestJson('/api/v1/ai/copilot/general/ask', { method: 'POST', body: JSON.stringify({ question }) }, isCopilotAnswer)
}

export function askUnifiedCopilot(
  portfolioId: string,
  request: UnifiedCopilotQuestion,
): Promise<CopilotAnswer> {
  return requestJson(
    `/api/v1/ai/copilot/portfolio/${portfolioId}/query`,
    { method: 'POST', body: JSON.stringify(request) },
    isCopilotAnswer,
  )
}

export function createPortfolioPlan(
  request: PortfolioPlanRequest,
  signal?: AbortSignal,
): Promise<PortfolioPlan> {
  return requestJson(
    '/api/v1/portfolio/plan',
    { method: 'POST', body: JSON.stringify(request), signal },
    isPortfolioPlan,
  )
}

export function summarizePortfolioState(portfolio: CurrentPortfolioInput): Promise<PortfolioDraftSummary> {
  return requestJson(
    '/api/v1/portfolio/state-summary',
    { method: 'POST', body: JSON.stringify(portfolio) },
    isDraftSummary,
  )
}

export function applyPortfolioPlanAction(request: PortfolioPlanActionRequest): Promise<PortfolioPlanActionResult> {
  return requestJson(
    '/api/v1/portfolio/apply-action',
    { method: 'POST', body: JSON.stringify(request) },
    isActionResult,
  )
}

export function previewPortfolioPlanAction(request: PortfolioPlanActionRequest): Promise<PortfolioPlanActionResult> {
  return requestJson(
    '/api/v1/portfolio/preview-action',
    { method: 'POST', body: JSON.stringify(request) },
    isActionResult,
  )
}

export function getLatestStoredPrice(ticker: string): Promise<LatestStoredPrice> {
  return requestJson(`/api/v1/portfolio/latest-price/${encodeURIComponent(ticker)}`, {}, isLatestPrice)
}

export function previewManualSell(request: ManualSellRequest): Promise<ManualSellResult> {
  return requestJson(
    '/api/v1/portfolio/manual-sell/preview',
    { method: 'POST', body: JSON.stringify(request) },
    isManualSell,
  )
}

export function applyManualSell(request: ManualSellRequest): Promise<ManualSellResult> {
  return requestJson(
    '/api/v1/portfolio/manual-sell',
    { method: 'POST', body: JSON.stringify(request) },
    isManualSell,
  )
}
