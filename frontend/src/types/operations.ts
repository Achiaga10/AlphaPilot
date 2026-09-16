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
