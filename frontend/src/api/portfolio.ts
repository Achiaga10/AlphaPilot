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
  StrategyProfile,
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

export function initializeResearchPortfolio(
  request: ResearchPortfolioInitialize,
): Promise<ResearchPortfolio> {
  return requestJson(
    '/api/v1/portfolio/initialize',
    { method: 'POST', body: JSON.stringify(request) },
    isResearchPortfolio,
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
