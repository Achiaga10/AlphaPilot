import { requestJson } from './client'
import type {
  AdminDataSummary,
  AdminCustomTicker,
  AdminCustomTickerListItem,
  AdminFullSyncRequest,
  AdminFullSyncStart,
  AdminSyncJob,
  AdminTickerSyncRequest,
  AdminTickerSyncResponse,
  AdminToolsCapability,
  DailySchedulerStatus,
} from '../types/portfolio'

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

const isCapability = (value: unknown): value is AdminToolsCapability =>
  isObject(value) && typeof value.enabled === 'boolean' && typeof value.warning === 'string'

const isJob = (value: unknown): value is AdminSyncJob =>
  isObject(value) && typeof value.job_id === 'string' && typeof value.state === 'string' && isObject(value.progress)

const isSummary = (value: unknown): value is AdminDataSummary =>
  isObject(value) && typeof value.active_company_count === 'number' && typeof value.active_sp500_count === 'number'

const isTickerSync = (value: unknown): value is AdminTickerSyncResponse =>
  isObject(value) && typeof value.ticker === 'string' && typeof value.state === 'string' && typeof value.message === 'string'

const isFullStart = (value: unknown): value is AdminFullSyncStart =>
  isObject(value) && typeof value.started === 'boolean' && isJob(value.job)

const isCustomTicker = (value: unknown): value is AdminCustomTicker =>
  isObject(value) && typeof value.ticker === 'string' && typeof value.state === 'string'

const isCustomTickerList = (value: unknown): value is AdminCustomTickerListItem[] =>
  Array.isArray(value) && value.every((item) => isObject(item) && typeof item.ticker === 'string')

const isScheduler = (value: unknown): value is DailySchedulerStatus =>
  isObject(value) && typeof value.enabled === 'boolean' &&
  value.timezone === 'America/New_York' && value.scheduled_local_time === '16:30' &&
  typeof value.last_status === 'string'

export function getAdminCapability(signal?: AbortSignal): Promise<AdminToolsCapability> {
  return requestJson('/api/v1/admin/data/capability', { signal }, isCapability)
}

export function getAdminDataSummary(signal?: AbortSignal): Promise<AdminDataSummary> {
  return requestJson('/api/v1/admin/data/summary', { signal }, isSummary)
}

export function getDailySchedulerStatus(signal?: AbortSignal): Promise<DailySchedulerStatus> {
  return requestJson('/api/v1/admin/data/scheduler', { signal }, isScheduler)
}

export function syncAdminTicker(request: AdminTickerSyncRequest): Promise<AdminTickerSyncResponse> {
  return requestJson(
    '/api/v1/admin/data/sync/ticker',
    { method: 'POST', body: JSON.stringify(request) },
    isTickerSync,
  )
}

export function startAdminFullSync(request: AdminFullSyncRequest): Promise<AdminFullSyncStart> {
  return requestJson(
    '/api/v1/admin/data/sync/all',
    { method: 'POST', body: JSON.stringify(request) },
    isFullStart,
  )
}

export function startAdminUniverseSync(request: AdminFullSyncRequest): Promise<AdminFullSyncStart> {
  return requestJson('/api/v1/admin/data/sync/universe', { method: 'POST', body: JSON.stringify(request) }, isFullStart)
}

export function startAdminCandleSync(request: AdminFullSyncRequest): Promise<AdminFullSyncStart> {
  return requestJson('/api/v1/admin/data/sync/candles', { method: 'POST', body: JSON.stringify(request) }, isFullStart)
}

export function getCustomTickers(signal?: AbortSignal): Promise<AdminCustomTickerListItem[]> {
  return requestJson('/api/v1/admin/data/custom-tickers', { signal }, isCustomTickerList)
}

export function addCustomTicker(request: AdminTickerSyncRequest): Promise<AdminCustomTicker> {
  return requestJson('/api/v1/admin/data/custom-tickers', { method: 'POST', body: JSON.stringify(request) }, isCustomTicker)
}

export function deactivateCustomTicker(ticker: string): Promise<AdminCustomTicker> {
  return requestJson(`/api/v1/admin/data/custom-tickers/${encodeURIComponent(ticker)}/deactivate`, { method: 'POST' }, isCustomTicker)
}

export function getAdminSyncJob(jobId: string, signal?: AbortSignal): Promise<AdminSyncJob> {
  return requestJson(`/api/v1/admin/data/sync/jobs/${jobId}`, { signal }, isJob)
}
