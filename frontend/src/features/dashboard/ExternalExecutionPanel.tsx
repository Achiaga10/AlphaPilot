import { useState } from 'react'
import { useExternalExecution } from '../../hooks/usePortfolioApi'
import type { ExternalAction } from '../../types/forwardPortfolio'
import { formatMoney } from '../../utils/format'

const money = (value: string | null) => value === null ? 'Unavailable' : formatMoney(value)
const label = (value: string) => value.replaceAll('_', ' ')
const exchangeTime = (value: string) => new Date(value).toLocaleString('en-US', {
  timeZone: 'America/New_York', dateStyle: 'medium', timeStyle: 'short',
})

function ActionCard({
  action, onRecord, onSkip, onVoid, busy,
}: {
  action: ExternalAction
  onRecord: (action: ExternalAction, quantity: number, price: string, executedAt: string, fee: string | null, complete: boolean, requestKey: string) => Promise<void>
  onSkip: (action: ExternalAction, reason: string) => void
  onVoid: (fillId: string, reason: string, requestKey: string) => Promise<void>
  busy: boolean
}) {
  const [quantity, setQuantity] = useState('')
  const [price, setPrice] = useState('')
  const [executedAt, setExecutedAt] = useState('')
  const [fee, setFee] = useState('')
  const [complete, setComplete] = useState(true)
  const [fillRequestKey, setFillRequestKey] = useState(() => crypto.randomUUID())
  const [skipReason, setSkipReason] = useState('USER_SKIPPED')
  const [confirmSkip, setConfirmSkip] = useState(false)
  const [voidingFill, setVoidingFill] = useState<string | null>(null)
  const [voidReason, setVoidReason] = useState('')
  const [voidRequestKey, setVoidRequestKey] = useState(() => crypto.randomUUID())
  const canRecord = action.status !== 'SKIPPED'
  const changeFill = () => setFillRequestKey(crypto.randomUUID())

  return <article className="daily-card" aria-label={`${action.ticker} external ${action.side} action`}>
    <div className="section-heading"><div><strong>{action.ticker} · EXTERNAL {action.side} EXPECTED</strong><p>{action.strategy_id} v{action.strategy_version} · {action.broker} · {action.provenance}</p></div><span className="badge badge--neutral">{label(action.status)}</span></div>
    <p className="inline-note">This is an informational external action. AlphaPilot never submits an Alpaca order; execution evidence may be user-recorded or read-only broker-synced.</p>
    <dl className="daily-card__facts">
      <div><dt>Signal session</dt><dd>{action.source_signal_session}</dd></div>
      <div><dt>Expected timing</dt><dd>{action.planned_execution_session ?? 'Next eligible stored session'} open</dd></div>
      <div><dt>Planned shares</dt><dd>{action.planned_shares}</dd></div>
      <div><dt>Virtual order</dt><dd>{action.virtual_order_status} · {action.virtual_filled_shares ?? 'Not filled'} shares</dd></div>
      <div><dt>Decision reason</dt><dd>{action.decision_reason}</dd></div>
      <div><dt>Loss control</dt><dd>{action.loss_control_policy} · {money(action.loss_control_boundary)}</dd></div>
      <div><dt>Due</dt><dd>{label(action.due_status)}</dd></div>
      <div><dt>Reconciliation</dt><dd>{label(action.reconciliation_status)}</dd></div>
      <div><dt>Canonical execution source</dt><dd>{label(action.canonical_execution_source ?? action.provenance)}</dd></div>
      <div><dt>Match state</dt><dd>{action.broker_match_state ? label(action.broker_match_state) : 'Manual / unavailable'}</dd></div>
      <div><dt>Recorded shares</dt><dd>{action.recorded_shares}</dd></div>
      <div><dt>Recorded weighted price</dt><dd>{money(action.weighted_fill_price)}</dd></div>
      <div><dt>Virtual modeled price</dt><dd>{money(action.virtual_modeled_fill_price)}</dd></div>
      <div><dt>Price difference / share</dt><dd>{money(action.price_difference_per_share)} · {action.price_difference_bps ?? 'Unavailable'} bps</dd></div>
      <div><dt>Share variance vs virtual</dt><dd>{action.share_variance_vs_virtual ?? 'Unavailable'}</dd></div>
      <div><dt>Recorded fees</dt><dd>{money(action.recorded_fees)}{action.fee_coverage_complete ? '' : ' · incomplete'}</dd></div>
    </dl>
    {action.status === 'SKIPPED' ? <p className="inline-note">User skipped: {label(action.skip_reason ?? 'UNKNOWN')}. The virtual Forward lifecycle remains independent.</p> : null}
    {action.virtual_order_status === 'CANCELLED' ? <p className="inline-note inline-note--warning">Virtual order cancelled. Do not treat this as a normal action to execute. Any separately recorded external execution remains an observation.</p> : null}
    {canRecord ? <details><summary>Record a user-observed {action.side} fill</summary>
      <form className="forward-initialize" onSubmit={(event) => {
        event.preventDefault()
        if (!executedAt) return
        void onRecord(action, Number(quantity), price, new Date(executedAt).toISOString(), fee === '' ? null : fee, complete, fillRequestKey).then(() => {
          setQuantity(''); setPrice(''); setFee(''); setFillRequestKey(crypto.randomUUID())
        }).catch(() => { /* Preserve the exact form and key for a safe retry. */ })
      }}>
        <label>Quantity<input aria-label={`${action.ticker} fill quantity`} type="number" min="1" step="1" required value={quantity} onChange={(event) => { setQuantity(event.target.value); changeFill() }} /></label>
        <label>Price per share<input aria-label={`${action.ticker} fill price`} type="number" min="0.0001" step="0.0001" required value={price} onChange={(event) => { setPrice(event.target.value); changeFill() }} /></label>
        <label>Executed at (local time)<input aria-label={`${action.ticker} executed at`} type="datetime-local" required value={executedAt} onChange={(event) => { setExecutedAt(event.target.value); changeFill() }} /></label>
        <label>Broker fee (optional)<input aria-label={`${action.ticker} broker fee`} type="number" min="0" step="0.0001" value={fee} onChange={(event) => { setFee(event.target.value); changeFill() }} /></label>
        <label><input type="checkbox" checked={complete} onChange={(event) => { setComplete(event.target.checked); changeFill() }} /> Final fill for this action</label>
        <button className="button button--primary" disabled={busy}>Record observed fill</button>
      </form>
      <p className="inline-note">For partial fills, uncheck “Final fill” until the last fill. Fees left blank remain unknown, not zero.</p>
    </details> : null}
    {action.status !== 'SKIPPED' && Number(action.recorded_shares) === 0 && action.virtual_order_status !== 'CANCELLED' ? <div className="table-actions"><button className="button button--secondary" disabled={busy} onClick={() => setConfirmSkip(true)}>Mark external action skipped</button></div> : null}
    {confirmSkip ? <div className="inline-note inline-note--warning" role="alertdialog" aria-label={`Confirm skip ${action.ticker}`}><label>Reason<select aria-label={`${action.ticker} skip reason`} value={skipReason} onChange={(event) => setSkipReason(event.target.value)}><option value="USER_SKIPPED">User skipped</option><option value="MISSED_ENTRY">Missed entry</option><option value="BROKER_UNAVAILABLE">Broker unavailable</option><option value="MANUAL_RISK_DECISION">Manual risk decision</option><option value="OTHER">Other</option></select></label><div className="table-actions"><button className="button button--primary" disabled={busy} onClick={() => { onSkip(action, skipReason); setConfirmSkip(false) }}>Confirm skip</button><button className="button button--secondary" onClick={() => setConfirmSkip(false)}>Cancel</button></div></div> : null}
    {action.fills.length ? <details><summary>User-recorded fills and correction audit ({action.fills.length})</summary><ol className="forward-activity">{action.fills.map((fill) => <li key={fill.id}><strong>{fill.voided_at ? 'VOIDED' : 'ACTIVE'} · {fill.side} {fill.quantity} @ {formatMoney(fill.price)}</strong><span>{exchangeTime(fill.executed_at)} · fee {money(fill.fee)} · {fill.source}{fill.void_reason ? ` · correction: ${fill.void_reason}` : ''}</span>{!fill.voided_at ? <button className="button button--secondary" disabled={busy} onClick={() => { setVoidingFill(fill.id); setVoidReason(''); setVoidRequestKey(crypto.randomUUID()) }}>Void / correct fill</button> : null}{voidingFill === fill.id ? <div role="alertdialog" aria-label="Confirm fill correction"><label>Correction reason<input aria-label="Correction reason" minLength={3} maxLength={200} required value={voidReason} onChange={(event) => { setVoidReason(event.target.value); setVoidRequestKey(crypto.randomUUID()) }} /></label><button className="button button--primary" disabled={busy || voidReason.trim().length < 3} onClick={() => { void onVoid(fill.id, voidReason.trim(), voidRequestKey).then(() => setVoidingFill(null)).catch(() => { /* Keep the same key for retry. */ }) }}>Confirm void</button><button className="button button--secondary" onClick={() => setVoidingFill(null)}>Cancel</button></div> : null}</li>)}</ol><ol className="forward-activity">{action.events.map((item) => <li key={item.id}>{label(item.event_type)} · {exchangeTime(item.created_at)} · {item.reason_code}</li>)}</ol></details> : null}
  </article>
}

export function ExternalExecutionPanel({ portfolioId }: { portfolioId: string }) {
  const journal = useExternalExecution(portfolioId)
  const actions = journal.actions.data ?? []
  const comparisons = journal.comparisons.data ?? []
  const analytics = journal.analytics.data
  const needed = actions.filter((item) => item.status === 'AWAITING_ACTION' || item.status === 'AWAITING_RECORD' || item.status === 'PARTIALLY_RECORDED')
  const history = actions.filter((item) => !needed.includes(item))
  const busy = journal.record.isPending || journal.skip.isPending || journal.voidFill.isPending
  const error = journal.record.error ?? journal.skip.error ?? journal.voidFill.error
  const record = async (action: ExternalAction, quantity: number, price: string, executedAt: string, fee: string | null, complete: boolean, requestKey: string) => {
    await journal.record.mutateAsync({ caseId: action.id, fill: { request_key: requestKey, side: action.side, quantity, price, executed_at: executedAt, fee, mark_complete: complete } })
  }
  const voidFill = async (fillId: string, reason: string, requestKey: string) => {
    await journal.voidFill.mutateAsync({ fillId, reason, requestKey })
  }

  return <section className="forward-external" aria-labelledby="forward-external-title">
    <h3 id="forward-external-title">External execution journal &amp; reconciliation</h3>
    <p className="forward-boundary"><strong>OBSERVATIONAL ONLY.</strong> Manual entries remain available when broker evidence is absent. Linked Alpaca fills use ALPACA_READ_ONLY_SYNC provenance; conflicts preserve both sources and never blend them. Neither source changes virtual Forward cash, positions, decisions, or P&amp;L.</p>
    {journal.actions.isError ? <p role="alert">External action queue unavailable.</p> : null}
    {error ? <p className="inline-note inline-note--warning" role="alert">Could not save journal entry: {error.message}</p> : null}
    {journal.record.isSuccess || journal.skip.isSuccess || journal.voidFill.isSuccess ? <p role="status">Manual execution journal updated.</p> : null}
    {analytics ? <dl className="config-grid"><div><dt>Expected actions</dt><dd>{analytics.expected_actions}</dd></div><div><dt>Recorded / skipped</dt><dd>{analytics.recorded_actions} / {analytics.skipped_actions}</dd></div><div><dt>Awaiting record</dt><dd>{analytics.actions_awaiting_recording}</dd></div><div><dt>Diverged actions</dt><dd>{analytics.diverged_actions}</dd></div><div><dt>Matched recorded-execution P&amp;L</dt><dd>{money(analytics.matched_recorded_execution_pnl)}</dd></div><div><dt>Matched virtual P&amp;L</dt><dd>{money(analytics.matched_virtual_pnl)}</dd></div></dl> : null}
    <details open><summary>External action needed ({needed.length})</summary>{needed.length ? <div className="daily-grid">{needed.map((action) => <ActionCard key={action.id} action={action} onRecord={record} onSkip={(item, reason) => journal.skip.mutate({ caseId: item.id, reason })} onVoid={voidFill} busy={busy} />)}</div> : <p className="empty-inline">No external action currently awaiting manual execution or recording.</p>}</details>
    <details><summary>Recorded, skipped &amp; cancelled action history ({history.length})</summary>{history.length ? <div className="daily-grid">{history.map((action) => <ActionCard key={action.id} action={action} onRecord={record} onSkip={(item, reason) => journal.skip.mutate({ caseId: item.id, reason })} onVoid={voidFill} busy={busy} />)}</div> : <p className="empty-inline">No external action history yet.</p>}</details>
    <details><summary>Closed-trade execution comparison ({comparisons.length})</summary>{comparisons.length ? <div className="table-shell"><table><thead><tr><th>Ticker</th><th>Completeness</th><th>Virtual shares</th><th>Recorded entry / exit shares</th><th>Virtual entry / exit</th><th>Recorded entry / exit</th><th>Virtual net P&amp;L</th><th>Recorded execution P&amp;L</th><th>Difference</th></tr></thead><tbody>{comparisons.map((item) => <tr key={item.forward_trade_id}><td>{item.ticker}</td><td>{label(item.completeness)}</td><td>{item.virtual_shares}</td><td>{item.recorded_entry_shares ?? 'Unavailable'} / {item.recorded_exit_shares ?? 'Unavailable'}</td><td>{formatMoney(item.virtual_entry_price)} / {formatMoney(item.virtual_exit_price)}</td><td>{money(item.recorded_entry_price)} / {money(item.recorded_exit_price)}</td><td>{formatMoney(item.virtual_net_pnl)}</td><td>{money(item.recorded_execution_pnl)}</td><td>{money(item.pnl_difference)}</td></tr>)}</tbody></table></div> : <p className="empty-inline">No closed Forward trades to compare.</p>}</details>
    <p className="inline-note">Recorded execution P&amp;L covers only complete canonical Forward-linked entry and exit fills with known fees. Missing Alpaca fees keep net P&amp;L unavailable. This remains separate from Forward strategy analytics and Alpaca account equity.</p>
  </section>
}
