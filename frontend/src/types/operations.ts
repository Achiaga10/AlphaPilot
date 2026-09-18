export type OperationalHealth = 'HEALTHY' | 'ATTENTION' | 'DEGRADED'
export type OperationalSeverity = 'INFO' | 'WARNING' | 'CRITICAL'
export type OperationalIncidentStatus = 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED'

export interface OperationalIncidentEvent {
  id: string
  event_type: 'OPENED' | 'UPDATED' | 'ACKNOWLEDGED' | 'RESOLVED'
  from_status: OperationalIncidentStatus | null
  to_status: OperationalIncidentStatus
  source: string
  reason: string
  evidence: Record<string, unknown>
  created_at: string
}

export interface OperationalIncident {
  id: string
  incident_type: string
  severity: OperationalSeverity
  status: OperationalIncidentStatus
  source_domain: string
  source_identity: string
  deduplication_key: string
  occurrence: number
  opened_at: string
  last_observed_at: string
  acknowledged_at: string | null
  resolved_at: string | null
  summary: string
  evidence: Record<string, unknown>
  notification_state: 'NOT_ELIGIBLE' | 'SUPPRESSED_BY_PREFERENCE' | 'PENDING' | 'DELIVERED' | 'FAILED'
  events: OperationalIncidentEvent[]
}

export interface ForwardOperations {
  status: string
  scheduler_status: string
  scheduler_running: boolean
  cash: string | null
  equity: string | null
  open_positions: number
  pending_sessions: number
  latest_processed_session: string | null
  latest_completed_market_session: string | null
}

export interface BrokerOperations {
  enabled: boolean
  configured: boolean
  environment: string
  status: string
  last_success_at: string | null
  data_age_seconds: number | null
  snapshot_authoritative: boolean
}

export interface PositionDrift {
  ticker: string
  forward_quantity: string
  broker_quantity: string
  difference: string
  evaluated_at: string
}

export interface OperationsHealthResponse {
  overall_health: OperationalHealth
  critical_count: number
  warning_count: number
  info_count: number
  evaluated_at: string
  monitor_running: boolean
  monitor_status: string
  active_incidents: OperationalIncident[]
  forward: ForwardOperations
  broker: BrokerOperations
  position_drifts: PositionDrift[]
  startup: {
    database_reachable: boolean
    schema_compatible: boolean
    expected_schema_revision: string
    observed_schema_revision: string | null
    forward_scheduler_initialized: boolean
    broker_configuration_state: string
    operations_monitor_initialized: boolean
  }
}

export interface OperationsEvaluation {
  evaluated_at: string
  opened: number
  updated: number
  resolved: number
  overall_health: OperationalHealth
}

export type NotificationStatus = 'PENDING' | 'DELIVERING' | 'DELIVERED' | 'RETRY_PENDING' | 'FAILED' | 'CANCELLED'

export interface OperationalNotification {
  id: string
  incident_id: string | null
  channel: 'EMAIL'
  status: NotificationStatus
  kind: 'INCIDENT' | 'REMINDER' | 'RECOVERY' | 'DAILY_SUMMARY' | 'TEST'
  priority: 'INFO' | 'WARNING' | 'CRITICAL' | 'RECOVERED' | 'SUMMARY' | 'TEST'
  transition: string
  generation: number
  recipient: string
  subject: string
  deduplication_key: string
  trading_session: string | null
  scheduled_at: string
  next_attempt_at: string
  sent_at: string | null
  last_attempt_at: string | null
  attempt_count: number
  failure_category: string | null
  provider_message_reference: string | null
  created_at: string
  updated_at: string
  attempts: Array<{
    id: string
    attempt_number: number
    started_at: string
    completed_at: string
    result: 'DELIVERED' | 'TRANSIENT_FAILURE' | 'PERMANENT_FAILURE'
    failure_category: string | null
    provider_message_reference: string | null
    duration_ms: number
  }>
}

export interface NotificationDeliveryStatus {
  enabled: boolean
  email_enabled: boolean
  configured: boolean
  worker_running: boolean
  queue_depth: number
  pending_count: number
  failed_count: number
  last_delivery_at: string | null
  last_error: string | null
}

export interface NotificationPreferences {
  notifications_enabled: boolean
  email_enabled: boolean
  recipient: string | null
  warning_enabled: boolean
  critical_enabled: boolean
  recovery_enabled: boolean
  daily_summary_enabled: boolean
}
