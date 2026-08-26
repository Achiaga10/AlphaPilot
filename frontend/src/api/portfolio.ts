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
  return (
    isObject(value) &&
    isObject(value.portfolio) &&
    Array.isArray(value.decisions) &&
    Array.isArray(value.candidate_statuses) &&
    (typeof value.evaluation_target_ticker === 'string' || value.evaluation_target_ticker === null) &&
    isObject(value.readiness) &&
    typeof value.plan_id === 'string' &&
    typeof value.requested_as_of_date === 'string' &&
    typeof value.analysis_as_of_date === 'string'
  )
}

const isDraftSummary = (value: unknown): value is PortfolioDraftSummary =>
  isObject(value) && typeof value.equity === 'string' && Array.isArray(value.positions)

const isActionResult = (value: unknown): value is PortfolioPlanActionResult =>
  isObject(value) && typeof value.applied === 'boolean' && isObject(value.portfolio) && isDraftSummary(value.summary)

const isLatestPrice = (value: unknown): value is LatestStoredPrice =>
  isObject(value) && typeof value.ticker === 'string' && ('price' in value)

const isManualSell = (value: unknown): value is ManualSellResult =>
  isObject(value) && typeof value.applied === 'boolean' && typeof value.reason === 'string' && isObject(value.portfolio)

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return requestJson('/api/v1/health/', { signal }, isHealth)
}

export function getRiskConfig(signal?: AbortSignal): Promise<PortfolioRiskConfig> {
  return requestJson('/api/v1/portfolio/risk-config', { signal }, isRiskConfig)
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
