import { useState } from 'react'
import { useAlpacaReadOnly, useExternalExecution } from '../../hooks/usePortfolioApi'
import type { BrokerExecution, ExternalAction, ForwardPosition } from '../../types/forwardPortfolio'
import { formatMoney } from '../../utils/format'

const label = (value: string) => value.replaceAll('_', ' ')
const money = (value: string | null) => value === null ? 'Unavailable' : formatMoney(value)

function UnmatchedActivity({ execution, actions, busy, onMatch, onIgnore }: {
  execution: BrokerExecution
  actions: ExternalAction[]
  busy: boolean
  onMatch: (caseId: string, reason: string) => void
  onIgnore: (reason: string) => void
}) {
  const compatible = actions.filter((action) => action.ticker === execution.symbol && action.side === execution.side)
  const [caseId, setCaseId] = useState(compatible[0]?.id ?? '')
  const [reason, setReason] = useState('User verified broker activity')
  const [mode, setMode] = useState<'match' | 'ignore' | null>(null)
  return <li>
    <strong>{execution.symbol} · {execution.side} {execution.quantity} @ {formatMoney(execution.price)}</strong>
    <span>{new Date(execution.executed_at).toLocaleString()} · {label(execution.match_state)} · {label(execution.match_reason)}</span>
    <div className="table-actions">
      <button className="button button--secondary" onClick={() => setMode('match')}>Link to Forward action</button>
      <button className="button button--secondary" onClick={() => setMode('ignore')}>Ignore external activity</button>
    </div>
    {mode ? <div className="inline-note inline-note--warning" role="alertdialog" aria-label={`Confirm ${mode} ${execution.symbol}`}>
      {mode === 'match' ? <label>Compatible Forward action<select aria-label={`${execution.symbol} Forward action`} value={caseId} onChange={(event) => setCaseId(event.target.value)}><option value="">Select action</option>{compatible.map((action) => <option key={action.id} value={action.id}>{action.side} · {action.source_signal_session} · {action.status}</option>)}</select></label> : null}
      <label>Audit reason<input aria-label={`${execution.symbol} broker audit reason`} minLength={3} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
      <div className="table-actions"><button className="button button--primary" disabled={busy || reason.trim().length < 3 || (mode === 'match' && !caseId)} onClick={() => { if (mode === 'match') onMatch(caseId, reason.trim()); else onIgnore(reason.trim()); setMode(null) }}>Confirm {mode}</button><button className="button button--secondary" onClick={() => setMode(null)}>Cancel</button></div>
    </div> : null}
  </li>
}

function LinkedActivity({ execution, busy, onUnlink }: {
  execution: BrokerExecution
  busy: boolean
  onUnlink: (reason: string) => void
}) {
  const [confirming, setConfirming] = useState(false)
  const [reason, setReason] = useState('User requested audited unlink')
  return <li>
    <strong>{execution.symbol} · {execution.side} {execution.quantity} @ {formatMoney(execution.price)}</strong>
    <span>{label(execution.match_state)} · {execution.provenance}{execution.fee === null ? ' · fee unavailable' : ` · fee ${formatMoney(execution.fee)}`}</span>
    {execution.external_case_id ? <button className="button button--secondary" disabled={busy} onClick={() => setConfirming(true)}>Unlink / rematch</button> : null}
    {confirming ? <div className="inline-note inline-note--warning" role="alertdialog" aria-label={`Confirm unlink ${execution.symbol}`}><label>Audit reason<input aria-label={`${execution.symbol} unlink reason`} minLength={3} value={reason} onChange={(event) => setReason(event.target.value)} /></label><div className="table-actions"><button className="button button--primary" disabled={busy || reason.trim().length < 3} onClick={() => { onUnlink(reason.trim()); setConfirming(false) }}>Confirm unlink</button><button className="button button--secondary" onClick={() => setConfirming(false)}>Cancel</button></div></div> : null}
  </li>
}

export function AlpacaReadOnlyPanel({ portfolioId, forwardPositions }: {
  portfolioId: string
  forwardPositions: ForwardPosition[]
}) {
  const broker = useAlpacaReadOnly()
  const journal = useExternalExecution(portfolioId)
  const status = broker.status.data
  const account = broker.account.data
  const positions = broker.positions.data ?? []
  const activity = broker.activity.data ?? []
  const unmatched = broker.unmatched.data ?? []
  const actions = journal.actions.data ?? []
  const forwardByTicker = new Map(forwardPositions.filter((item) => item.status === 'OPEN').map((item) => [item.ticker, item]))
  const busy = broker.sync.isPending || broker.match.isPending || broker.unlink.isPending || broker.ignore.isPending

  return <section className="forward-external" aria-labelledby="alpaca-read-only-title">
    <div className="section-heading"><div><p className="eyebrow">OBSERVATIONAL BROKER EVIDENCE</p><h3 id="alpaca-read-only-title">ALPACA — READ ONLY</h3></div><span className={`badge ${status?.status === 'SUCCEEDED' ? 'badge--neutral' : 'badge--warning'}`}>{status?.environment ?? 'PAPER'} · {status?.status ?? 'UNAVAILABLE'}</span></div>
    <p className="forward-boundary"><strong>No trading authority.</strong> AlphaPilot can only read account, position, order, and fill evidence. It cannot submit, replace, cancel, or close an Alpaca order or position.</p>
    {broker.status.isError ? <p role="alert">Alpaca read-only status unavailable.</p> : null}
    {status ? <dl className="config-grid"><div><dt>Enabled / configured</dt><dd>{status.enabled ? 'YES' : 'NO'} / {status.configured ? 'YES' : 'NO'}</dd></div><div><dt>Last attempt</dt><dd>{status.last_attempt_at ? new Date(status.last_attempt_at).toLocaleString() : 'Never'}</dd></div><div><dt>Last successful snapshot</dt><dd>{status.last_success_at ? new Date(status.last_success_at).toLocaleString() : 'Never'}</dd></div><div><dt>Data age</dt><dd>{status.data_age_seconds === null ? 'Unavailable' : `${status.data_age_seconds} seconds`}</dd></div><div><dt>Observed positions / orders</dt><dd>{status.positions} / {status.orders}</dd></div><div><dt>Executions / unmatched</dt><dd>{status.executions} / {status.unmatched_executions}</dd></div><div><dt>Refresh interval</dt><dd>{status.interval_seconds} seconds</dd></div><div><dt>Provenance</dt><dd>{status.provenance}</dd></div>{status.last_error ? <div><dt>Last sync error</dt><dd>{status.last_error}</dd></div> : null}</dl> : null}
    <div className="table-actions"><button className="button button--secondary" disabled={busy || !status?.enabled || !status.configured} onClick={() => broker.sync.mutate()}>Refresh read-only evidence</button></div>
    {broker.sync.isSuccess ? <p role="status">Alpaca read-only evidence refreshed.</p> : null}
    {broker.sync.isError ? <p role="alert">Read-only refresh failed. Existing broker snapshot remains available.</p> : null}
    {account ? <dl className="config-grid"><div><dt>Alpaca equity</dt><dd>{formatMoney(account.equity)}</dd></div><div><dt>Alpaca cash</dt><dd>{formatMoney(account.cash)}</dd></div><div><dt>Buying power</dt><dd>{formatMoney(account.buying_power)}</dd></div><div><dt>Snapshot time</dt><dd>{new Date(account.observed_at).toLocaleString()}</dd></div></dl> : <p className="empty-inline">No Alpaca account snapshot stored.</p>}

    <details open><summary>Forward vs Alpaca positions ({positions.length})</summary>{positions.length ? <div className="table-shell"><table><thead><tr><th>Ticker</th><th>Alpaca shares</th><th>Forward shares</th><th>Alpaca average</th><th>Forward modeled entry</th><th>Difference</th></tr></thead><tbody>{positions.map((item) => { const forward = forwardByTicker.get(item.symbol); return <tr key={item.symbol}><td>{item.symbol}</td><td>{item.quantity}</td><td>{forward?.shares ?? 'No Forward position'}</td><td>{money(item.average_entry_price)}</td><td>{forward ? formatMoney(forward.modeled_entry_price) : 'Unavailable'}</td><td>{forward ? Number(item.quantity) - forward.shares : 'Outside Forward'}</td></tr> })}</tbody></table></div> : <p className="empty-inline">No observed Alpaca positions.</p>}</details>

    <details open><summary>Unmatched or ambiguous activity ({unmatched.length})</summary>{unmatched.length ? <ol className="forward-activity">{unmatched.map((execution) => <UnmatchedActivity key={execution.id} execution={execution} actions={actions} busy={busy} onMatch={(caseId, reason) => broker.match.mutate({ executionId: execution.id, caseId, reason, requestKey: crypto.randomUUID() })} onIgnore={(reason) => broker.ignore.mutate({ executionId: execution.id, reason, requestKey: crypto.randomUUID() })} />)}</ol> : <p className="empty-inline">No unmatched Alpaca fill activity.</p>}</details>

    <details><summary>Observed Alpaca execution provenance ({activity.length})</summary>{activity.length ? <ol className="forward-activity">{activity.map((execution) => <LinkedActivity key={execution.id} execution={execution} busy={busy} onUnlink={(reason) => broker.unlink.mutate({ executionId: execution.id, reason, requestKey: crypto.randomUUID() })} />)}</ol> : <p className="empty-inline">No broker executions observed.</p>}</details>
  </section>
}
