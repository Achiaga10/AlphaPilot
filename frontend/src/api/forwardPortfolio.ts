import { requestJson } from './client'
import type {
  ForwardAnalytics,
  ForwardCycleResult,
  ForwardEvent,
  ForwardHealth,
  ForwardOrder,
  ForwardPortfolio,
  ForwardPosition,
  ForwardTrade,
  ExternalAction,
  ExternalExecutionAnalytics,
  ExternalFillInput,
  ExternalTradeComparison,
} from '../types/forwardPortfolio'

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null

const isForwardPortfolio = (value: unknown): value is ForwardPortfolio =>
  isObject(value) && typeof value.id === 'string' && value.strategy_id === 'micho-150-v1' &&
  value.strategy_version === 1 && value.execution_mode === 'VIRTUAL' &&
  value.broker_execution_mode === 'MANUAL_EXTERNAL' &&
  (value.status === 'ACTIVE' || value.status === 'PAUSED' || value.status === 'ARCHIVED') &&
  typeof value.cash_balance === 'string' && typeof value.equity === 'string' &&
  typeof value.revision === 'number'

const isNullableForwardPortfolio = (value: unknown): value is ForwardPortfolio | null =>
  value === null || isForwardPortfolio(value)

const isForwardPositions = (value: unknown): value is ForwardPosition[] =>
  Array.isArray(value) && value.every((item) => isObject(item) &&
    typeof item.id === 'string' && typeof item.ticker === 'string' &&
    typeof item.shares === 'number' && typeof item.market_value === 'string' &&
    typeof item.unrealized_return_pct === 'string' &&
    (item.status === 'OPEN' || item.status === 'CLOSED'))

const isForwardOrders = (value: unknown): value is ForwardOrder[] =>
  Array.isArray(value) && value.every((item) => isObject(item) &&
    typeof item.id === 'string' && typeof item.ticker === 'string' &&
    (item.side === 'ENTRY' || item.side === 'EXIT') &&
    (item.status === 'PENDING' || item.status === 'FILLED' || item.status === 'CANCELLED') &&
    typeof item.planned_shares === 'number')

const isForwardTrades = (value: unknown): value is ForwardTrade[] =>
  Array.isArray(value) && value.every((item) => isObject(item) &&
    typeof item.id === 'string' && typeof item.ticker === 'string' &&
    typeof item.net_pnl === 'string' && typeof item.exit_session === 'string')

const isForwardEvents = (value: unknown): value is ForwardEvent[] =>
  Array.isArray(value) && value.every((item) => isObject(item) &&
    typeof item.id === 'string' && typeof item.event_type === 'string' &&
    typeof item.reason_code === 'string' && typeof item.created_at === 'string')

const isForwardAnalytics = (value: unknown): value is ForwardAnalytics =>
  isObject(value) && typeof value.current_equity === 'string' &&
  typeof value.net_return_pct === 'string' && typeof value.completed_trades === 'number' &&
  typeof value.friction_dollars === 'string' && typeof value.current_exposure_pct === 'string'

const isForwardHealth = (value: unknown): value is ForwardHealth =>
  isObject(value) && typeof value.scheduler_running === 'boolean' &&
  typeof value.scheduler_status === 'string' && typeof value.pending_sessions === 'number' &&
  typeof value.data_ready === 'boolean'

const isCycleResult = (value: unknown): value is ForwardCycleResult =>
  isObject(value) && Array.isArray(value.processed_sessions) &&
  Array.isArray(value.skipped_sessions)

export function getCurrentForwardPortfolio(signal?: AbortSignal): Promise<ForwardPortfolio | null> {
  return requestJson('/api/v1/forward-portfolio/current', { signal }, isNullableForwardPortfolio)
}

export function initializeForwardPortfolio(request: {
  initial_cash: string
  forward_start_session: string
}): Promise<ForwardPortfolio> {
  return requestJson('/api/v1/forward-portfolio/initialize', {
    method: 'POST', body: JSON.stringify(request),
  }, isForwardPortfolio)
}

export function pauseForwardPortfolio(portfolio: ForwardPortfolio): Promise<ForwardPortfolio> {
  return requestJson(`/api/v1/forward-portfolio/${portfolio.id}/pause`, {
    method: 'POST', body: JSON.stringify({ expected_revision: portfolio.revision, confirmed: true }),
  }, isForwardPortfolio)
}

export function resumeForwardPortfolio(portfolio: ForwardPortfolio): Promise<ForwardPortfolio> {
  return requestJson(`/api/v1/forward-portfolio/${portfolio.id}/resume`, {
    method: 'POST', body: JSON.stringify({ expected_revision: portfolio.revision, confirmed: true }),
  }, isForwardPortfolio)
}

export function runForwardCycles(portfolioId: string): Promise<ForwardCycleResult> {
  return requestJson(`/api/v1/forward-portfolio/${portfolioId}/cycles/run`, {
    method: 'POST',
  }, isCycleResult)
}

export function getForwardPositions(portfolioId: string, signal?: AbortSignal): Promise<ForwardPosition[]> {
  return requestJson(`/api/v1/forward-portfolio/${portfolioId}/positions`, { signal }, isForwardPositions)
}

export function getForwardOrders(portfolioId: string, signal?: AbortSignal): Promise<ForwardOrder[]> {
  return requestJson(`/api/v1/forward-portfolio/${portfolioId}/orders`, { signal }, isForwardOrders)
}

export function getForwardTrades(portfolioId: string, signal?: AbortSignal): Promise<ForwardTrade[]> {
  return requestJson(`/api/v1/forward-portfolio/${portfolioId}/trades`, { signal }, isForwardTrades)
}

export function getForwardEvents(portfolioId: string, signal?: AbortSignal): Promise<ForwardEvent[]> {
  return requestJson(`/api/v1/forward-portfolio/${portfolioId}/events`, { signal }, isForwardEvents)
}

export function getForwardAnalytics(portfolioId: string, signal?: AbortSignal): Promise<ForwardAnalytics> {
  return requestJson(`/api/v1/forward-portfolio/${portfolioId}/analytics`, { signal }, isForwardAnalytics)
}

export function getForwardHealth(portfolioId: string, signal?: AbortSignal): Promise<ForwardHealth> {
  return requestJson(`/api/v1/forward-portfolio/${portfolioId}/health`, { signal }, isForwardHealth)
}

const isExternalAction = (value: unknown): value is ExternalAction =>
  isObject(value) && typeof value.id === 'string' && typeof value.forward_order_id === 'string' &&
  typeof value.ticker === 'string' && (value.side === 'BUY' || value.side === 'SELL') &&
  typeof value.status === 'string' && typeof value.reconciliation_status === 'string' &&
  typeof value.planned_shares === 'number' && typeof value.recorded_shares === 'number' &&
  Array.isArray(value.fills) && Array.isArray(value.events)

const isExternalActions = (value: unknown): value is ExternalAction[] =>
  Array.isArray(value) && value.every(isExternalAction)

const isExternalComparisons = (value: unknown): value is ExternalTradeComparison[] =>
  Array.isArray(value) && value.every((item) => isObject(item) &&
    typeof item.forward_trade_id === 'string' && typeof item.virtual_net_pnl === 'string' &&
    typeof item.completeness === 'string')

const isExternalAnalytics = (value: unknown): value is ExternalExecutionAnalytics =>
  isObject(value) && typeof value.expected_actions === 'number' &&
  typeof value.recorded_actions === 'number' && typeof value.skipped_actions === 'number'

export function getExternalActions(portfolioId: string, signal?: AbortSignal): Promise<ExternalAction[]> {
  return requestJson(`/api/v1/forward-portfolio/${portfolioId}/external-actions`, { signal }, isExternalActions)
}

export function recordExternalFill(portfolioId: string, caseId: string, fill: ExternalFillInput): Promise<ExternalAction> {
  return requestJson(`/api/v1/forward-portfolio/${portfolioId}/external-actions/${caseId}/fills`, {
    method: 'POST', body: JSON.stringify(fill),
  }, isExternalAction)
}

export function skipExternalAction(portfolioId: string, caseId: string, reason: string): Promise<ExternalAction> {
  return requestJson(`/api/v1/forward-portfolio/${portfolioId}/external-actions/${caseId}/skip`, {
    method: 'POST', body: JSON.stringify({ confirmed: true, reason }),
  }, isExternalAction)
}

export function voidExternalFill(portfolioId: string, fillId: string, reason: string, requestKey: string): Promise<ExternalAction> {
  return requestJson(`/api/v1/forward-portfolio/${portfolioId}/external-fills/${fillId}/void`, {
    method: 'POST', body: JSON.stringify({ confirmed: true, request_key: requestKey, reason }),
  }, isExternalAction)
}

export function getExternalReconciliation(portfolioId: string, signal?: AbortSignal): Promise<ExternalTradeComparison[]> {
  return requestJson(`/api/v1/forward-portfolio/${portfolioId}/reconciliation`, { signal }, isExternalComparisons)
}

export function getExternalExecutionAnalytics(portfolioId: string, signal?: AbortSignal): Promise<ExternalExecutionAnalytics> {
  return requestJson(`/api/v1/forward-portfolio/${portfolioId}/execution-analytics`, { signal }, isExternalAnalytics)
}
