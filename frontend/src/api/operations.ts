import { requestJson } from './client'
import type {
  OperationalIncident,
  OperationsEvaluation,
  OperationsHealthResponse,
} from '../types/operations'

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null

const isIncident = (value: unknown): value is OperationalIncident =>
  isObject(value) && typeof value.id === 'string' &&
  typeof value.incident_type === 'string' && typeof value.summary === 'string' &&
  (value.severity === 'INFO' || value.severity === 'WARNING' || value.severity === 'CRITICAL') &&
  (value.status === 'OPEN' || value.status === 'ACKNOWLEDGED' || value.status === 'RESOLVED')

const isHealth = (value: unknown): value is OperationsHealthResponse =>
  isObject(value) &&
  (value.overall_health === 'HEALTHY' || value.overall_health === 'ATTENTION' || value.overall_health === 'DEGRADED') &&
  typeof value.critical_count === 'number' && typeof value.warning_count === 'number' &&
  Array.isArray(value.active_incidents) && value.active_incidents.every(isIncident) &&
  isObject(value.forward) && isObject(value.broker) && Array.isArray(value.position_drifts)

const isIncidents = (value: unknown): value is OperationalIncident[] =>
  Array.isArray(value) && value.every(isIncident)

const isEvaluation = (value: unknown): value is OperationsEvaluation =>
  isObject(value) && typeof value.opened === 'number' && typeof value.updated === 'number' &&
  typeof value.resolved === 'number' && typeof value.overall_health === 'string'

export function getOperationsHealth(signal?: AbortSignal): Promise<OperationsHealthResponse> {
  return requestJson('/api/v1/operations/health', { signal }, isHealth)
}

export function getResolvedIncidents(signal?: AbortSignal): Promise<OperationalIncident[]> {
  return requestJson('/api/v1/operations/incidents?status=RESOLVED', { signal }, isIncidents)
}

export function acknowledgeIncident(id: string, reason: string): Promise<OperationalIncident> {
  return requestJson(`/api/v1/operations/incidents/${id}/acknowledge`, {
    method: 'POST', body: JSON.stringify({ reason }),
  }, isIncident)
}

export function evaluateOperations(): Promise<OperationsEvaluation> {
  return requestJson('/api/v1/operations/evaluate', { method: 'POST' }, isEvaluation)
}
