import { useState } from 'react'
import { ErrorState, LoadingState } from '../../components/AsyncState'
import { useOperationsCenter } from '../../hooks/useOperationsApi'
import type { OperationalIncident } from '../../types/operations'
import { formatMoney } from '../../utils/format'

const label = (value: string) => value.replaceAll('_', ' ')

function IncidentCard({ incident, busy, onAcknowledge }: {
  incident: OperationalIncident
  busy: boolean
  onAcknowledge: (id: string, reason: string) => void
}) {
  const [acknowledging, setAcknowledging] = useState(false)
  const [reason, setReason] = useState('Operator reviewed this incident')
  return <li className={`operations-incident operations-incident--${incident.severity.toLowerCase()}`}>
    <div className="section-heading"><div><strong>{label(incident.incident_type)}</strong><p>{incident.summary}</p></div><span className={`badge ${incident.severity === 'CRITICAL' ? 'badge--danger' : incident.severity === 'WARNING' ? 'badge--warning' : 'badge--neutral'}`}>{incident.severity} · {incident.status}</span></div>
    <p className="muted">{label(incident.source_domain)} · last observed {new Date(incident.last_observed_at).toLocaleString()} · occurrence {incident.occurrence}</p>
    <details><summary>Evidence</summary><pre className="operations-evidence">{JSON.stringify(incident.evidence, null, 2)}</pre></details>
    {incident.status === 'OPEN' ? <button className="button button--secondary" disabled={busy} onClick={() => setAcknowledging(true)}>Acknowledge</button> : null}
    {acknowledging ? <div className="inline-note inline-note--warning" role="dialog" aria-label={`Acknowledge ${label(incident.incident_type)}`}><label>Audit reason<input value={reason} minLength={3} onChange={(event) => setReason(event.target.value)} /></label><div className="table-actions"><button className="button button--primary" disabled={busy || reason.trim().length < 3} onClick={() => { onAcknowledge(incident.id, reason.trim()); setAcknowledging(false) }}>Confirm acknowledgement</button><button className="button button--secondary" onClick={() => setAcknowledging(false)}>Cancel</button></div></div> : null}
  </li>
}

export function OperationsCenter() {
  const operations = useOperationsCenter()
  const health = operations.health.data
  if (operations.health.isPending) return <section aria-labelledby="operations-title"><h2 id="operations-title">Operations Center</h2><LoadingState label="Loading operational health…" /></section>
  if (operations.health.isError || !health) return <section aria-labelledby="operations-title"><h2 id="operations-title">Operations Center</h2><ErrorState error={operations.health.error} onRetry={() => void operations.health.refetch()} /></section>
  const busy = operations.acknowledge.isPending || operations.evaluate.isPending
  return <section className="operations-center" aria-labelledby="operations-title">
    <div className="section-heading"><div><p className="eyebrow">DETERMINISTIC IN-APP MONITORING</p><h2 id="operations-title">Operations Center</h2></div><span className={`badge ${health.overall_health === 'DEGRADED' ? 'badge--danger' : health.overall_health === 'ATTENTION' ? 'badge--warning' : 'badge--neutral'}`}>{health.overall_health}</span></div>
    <p className="forward-boundary"><strong>Observational only.</strong> Health incidents cannot trade, change Micho decisions, alter Forward economics, or make News authoritative.</p>
    <div className="operations-counts"><strong>{health.critical_count} critical</strong><span>{health.warning_count} warning</span><span>{health.info_count} info</span><button className="button button--secondary" disabled={busy} onClick={() => operations.evaluate.mutate()}>Evaluate now</button></div>
    <div className="operations-health-grid">
      <article><h3>Forward health</h3><dl className="config-grid"><div><dt>Portfolio</dt><dd>{health.forward.status}</dd></div><div><dt>Scheduler</dt><dd>{health.forward.scheduler_status}</dd></div><div><dt>Equity / cash</dt><dd>{health.forward.equity ? formatMoney(health.forward.equity) : 'Unavailable'} / {health.forward.cash ? formatMoney(health.forward.cash) : 'Unavailable'}</dd></div><div><dt>Open / pending sessions</dt><dd>{health.forward.open_positions} / {health.forward.pending_sessions}</dd></div></dl></article>
      <article><h3>Alpaca read-only health</h3><dl className="config-grid"><div><dt>State</dt><dd>{health.broker.environment} · {health.broker.status}</dd></div><div><dt>Enabled / configured</dt><dd>{health.broker.enabled ? 'YES' : 'NO'} / {health.broker.configured ? 'YES' : 'NO'}</dd></div><div><dt>Authoritative snapshot</dt><dd>{health.broker.snapshot_authoritative ? 'FRESH' : 'UNKNOWN / NOT EVALUATED'}</dd></div><div><dt>Last success</dt><dd>{health.broker.last_success_at ? new Date(health.broker.last_success_at).toLocaleString() : 'Never'}</dd></div></dl></article>
    </div>
    <div className="operations-priority"><h3>Needs attention</h3>{health.active_incidents.length ? <ol>{health.active_incidents.map((incident) => <IncidentCard key={incident.id} incident={incident} busy={busy} onAcknowledge={(id, reason) => operations.acknowledge.mutate({ id, reason })} />)}</ol> : <p className="empty-inline">No active operational incidents.</p>}</div>
    <details open={health.position_drifts.length > 0}><summary>Forward / broker position drift ({health.position_drifts.length})</summary>{health.broker.snapshot_authoritative ? health.position_drifts.length ? <div className="table-shell"><table><thead><tr><th>Ticker</th><th>Forward</th><th>Alpaca</th><th>Difference</th></tr></thead><tbody>{health.position_drifts.map((drift) => <tr key={drift.ticker}><td>{drift.ticker}</td><td>{drift.forward_quantity}</td><td>{drift.broker_quantity}</td><td>{drift.difference}</td></tr>)}</tbody></table></div> : <p className="empty-inline">Fresh Alpaca snapshot is aligned for relevant Micho Forward symbols.</p> : <p className="empty-inline">Drift is unknown and not evaluated until a fresh successful Alpaca snapshot exists.</p>}</details>
    <details><summary>Resolved incident history ({operations.resolved.data?.length ?? 0})</summary>{operations.resolved.data?.length ? <ol className="forward-activity">{operations.resolved.data.map((incident) => <li key={incident.id}><strong>{label(incident.incident_type)}</strong><span>{incident.resolved_at ? new Date(incident.resolved_at).toLocaleString() : 'Resolution time unavailable'} · occurrence {incident.occurrence}</span></li>)}</ol> : <p className="empty-inline">No resolved incidents recorded.</p>}</details>
  </section>
}
