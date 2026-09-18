import { requestJson } from './client'
import type {
  OperationalIncident,
  OperationalNotification,
  NotificationDeliveryStatus,
  NotificationPreferences,
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

const isNotification = (value: unknown): value is OperationalNotification =>
  isObject(value) && typeof value.id === 'string' && value.channel === 'EMAIL' &&
  typeof value.subject === 'string' && typeof value.status === 'string'

const isNotifications = (value: unknown): value is OperationalNotification[] =>
  Array.isArray(value) && value.every(isNotification)

const isNotificationStatus = (value: unknown): value is NotificationDeliveryStatus =>
  isObject(value) && typeof value.enabled === 'boolean' &&
  typeof value.configured === 'boolean' && typeof value.queue_depth === 'number' &&
  typeof value.failed_count === 'number'

const isPreferences = (value: unknown): value is NotificationPreferences =>
  isObject(value) && typeof value.notifications_enabled === 'boolean' &&
  typeof value.email_enabled === 'boolean' && typeof value.warning_enabled === 'boolean' &&
  typeof value.critical_enabled === 'boolean' && typeof value.recovery_enabled === 'boolean'

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

export function getNotificationStatus(signal?: AbortSignal): Promise<NotificationDeliveryStatus> {
  return requestJson('/api/v1/notifications/status', { signal }, isNotificationStatus)
}

export function getNotifications(signal?: AbortSignal): Promise<OperationalNotification[]> {
  return requestJson('/api/v1/notifications?limit=50', { signal }, isNotifications)
}

export function getNotificationPreferences(signal?: AbortSignal): Promise<NotificationPreferences> {
  return requestJson('/api/v1/notifications/preferences', { signal }, isPreferences)
}

export function updateNotificationPreferences(preferences: NotificationPreferences): Promise<NotificationPreferences> {
  return requestJson('/api/v1/notifications/preferences', {
    method: 'PUT', body: JSON.stringify(preferences),
  }, isPreferences)
}

export function sendTestNotification(): Promise<OperationalNotification> {
  return requestJson('/api/v1/notifications/test', {
    method: 'POST', body: JSON.stringify({}),
  }, isNotification)
}

export function retryNotification(id: string): Promise<OperationalNotification> {
  return requestJson(`/api/v1/notifications/${id}/retry`, { method: 'POST' }, isNotification)
}
