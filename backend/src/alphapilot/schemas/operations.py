"""Public contracts for the deterministic Operations Center."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from alphapilot.database.models.operations import (
    OperationalEventType,
    OperationalHealth,
    OperationalIncidentStatus,
    OperationalIncidentType,
    OperationalSeverity,
    OperationalSourceDomain,
)


class OperationalIncidentEventSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_type: OperationalEventType
    from_status: OperationalIncidentStatus | None
    to_status: OperationalIncidentStatus
    source: str
    reason: str
    evidence: dict[str, Any]
    created_at: AwareDatetime


class OperationalIncidentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    incident_type: OperationalIncidentType
    severity: OperationalSeverity
    status: OperationalIncidentStatus
    source_domain: OperationalSourceDomain
    source_identity: str
    deduplication_key: str
    occurrence: int
    opened_at: AwareDatetime
    last_observed_at: AwareDatetime
    acknowledged_at: AwareDatetime | None
    resolved_at: AwareDatetime | None
    summary: str
    evidence: dict[str, Any]
    notification_state: str = "NOT_ELIGIBLE"
    events: list[OperationalIncidentEventSchema] = Field(default_factory=list)


class StartupCheckSchema(BaseModel):
    database_reachable: bool
    schema_compatible: bool
    expected_schema_revision: str
    observed_schema_revision: str | None
    forward_scheduler_initialized: bool
    broker_configuration_state: str
    operations_monitor_initialized: bool


class ForwardOperationsSchema(BaseModel):
    status: str
    scheduler_status: str
    scheduler_running: bool
    cash: Decimal | None
    equity: Decimal | None
    open_positions: int
    pending_sessions: int
    latest_processed_session: date | None
    latest_completed_market_session: date | None


class BrokerOperationsSchema(BaseModel):
    enabled: bool
    configured: bool
    environment: str
    status: str
    last_success_at: AwareDatetime | None
    data_age_seconds: int | None
    snapshot_authoritative: bool


class PositionDriftSchema(BaseModel):
    ticker: str
    forward_quantity: Decimal
    broker_quantity: Decimal
    difference: Decimal
    evaluated_at: AwareDatetime


class OperationsHealthSchema(BaseModel):
    overall_health: OperationalHealth
    critical_count: int
    warning_count: int
    info_count: int
    evaluated_at: AwareDatetime
    monitor_running: bool
    monitor_status: str
    active_incidents: list[OperationalIncidentSchema]
    forward: ForwardOperationsSchema
    broker: BrokerOperationsSchema
    position_drifts: list[PositionDriftSchema]
    startup: StartupCheckSchema


class DailyOperationsSummarySchema(BaseModel):
    generated_at: AwareDatetime
    overall_health: OperationalHealth
    critical_count: int
    warning_count: int
    forward: ForwardOperationsSchema
    expected_manual_buys: int
    expected_manual_sells: int
    overdue_actions: int
    broker: BrokerOperationsSchema
    unmatched_broker_activity: int
    ambiguous_matches: int
    execution_conflicts: int
    position_drift_count: int
    latest_completed_market_session: date | None
    latest_forward_processed_session: date | None


class OperationsEvaluationSchema(BaseModel):
    evaluated_at: AwareDatetime
    opened: int
    updated: int
    resolved: int
    overall_health: OperationalHealth


class IncidentAcknowledgeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=200)
