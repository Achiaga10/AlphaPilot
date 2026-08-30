import { type FormEvent } from 'react'
import {
  usePaperValidationEntryMutation,
  usePaperValidationExitMutation,
  usePositionIntelligenceQuery,
  usePositionPaperValidationsQuery,
  usePositionCopilotMutation,
} from '../../hooks/usePortfolioApi'
import { formatDate, formatMoney, formatPercent } from '../../utils/format'
import { OPEN_COPILOT_EVENT } from '../copilot/FloatingCopilot'

function formatFactValue(value: unknown) {
  if (value === null || value === undefined) return 'Unavailable'
  if (typeof value === 'object') return JSON.stringify(value)
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  return 'Unavailable'
}

export function PositionIntelligencePanel({ portfolioId, positionId, onClose }: {
  portfolioId: string; positionId: string; onClose: () => void
}) {
  const intelligence = usePositionIntelligenceQuery(portfolioId, positionId)
  const papers = usePositionPaperValidationsQuery(portfolioId, positionId)
  const entry = usePaperValidationEntryMutation(portfolioId, positionId)
  const exit = usePaperValidationExitMutation(portfolioId)
  const copilot = usePositionCopilotMutation(portfolioId, positionId)
  const text = (data: FormData, name: string) => {
    const value = data.get(name)
    return typeof value === 'string' ? value : ''
  }
  const iso = (value: string) => new Date(value).toISOString()
  function recordEntry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget)
    entry.mutate({ actual_quantity: Number(text(data, 'quantity')), actual_average_fill_price: text(data, 'price'), actual_execution_at: iso(text(data, 'executed_at')), note: text(data, 'note') || null }, { onSuccess: () => void papers.refetch() })
  }
  function recordExit(event: FormEvent<HTMLFormElement>, validationId: string) {
    event.preventDefault(); const data = new FormData(event.currentTarget)
    exit.mutate({ validationId, request: { actual_exit_quantity: Number(text(data, 'quantity')), actual_average_exit_fill: text(data, 'price'), actual_execution_at: iso(text(data, 'executed_at')), note: text(data, 'note') || null } }, { onSuccess: () => void papers.refetch() })
  }
  function askCopilot(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget)
    copilot.mutate(text(data, 'question'))
  }
  const facts = intelligence.data
  return <section className="panel" aria-labelledby="position-intelligence-title">
    <div className="section-heading"><div><p className="eyebrow">Backend-owned position facts</p><h2 id="position-intelligence-title">Position Intelligence</h2></div><div className="table-actions"><button className="button button--primary button--small" type="button" onClick={() => window.dispatchEvent(new CustomEvent(OPEN_COPILOT_EVENT, { detail: { positionId } }))}>Ask AI</button><button className="button button--secondary button--small" type="button" onClick={onClose}>Close</button></div></div>
    {intelligence.isPending ? <p>Loading position intelligence…</p> : null}
    {intelligence.isError ? <p role="alert" className="inline-note inline-note--warning">Position Intelligence response was unavailable or malformed.</p> : null}
    {facts ? <div className="page-stack">
      <section><h3>Entry</h3><dl className="config-grid"><div><dt>Ticker</dt><dd>{facts.ticker}</dd></div><div><dt>Quantity</dt><dd>{facts.quantity}</dd></div><div><dt>Entry price</dt><dd>{formatMoney(facts.entry_price)}</dd></div><div><dt>Strategy</dt><dd>{facts.strategy ?? 'Unavailable'}</dd></div><div><dt>Profile</dt><dd>{facts.strategy_profile_id ? `${facts.strategy_profile_id} v${facts.strategy_profile_version}` : 'Unavailable'}</dd></div></dl>{!facts.strategy_guidance_available ? <p className="inline-note inline-note--warning">Strategy guidance unavailable: profile provenance is unknown. No HOLD or SELL guidance is inferred.</p> : null}</section>
      <section><h3>Current state</h3><dl className="config-grid"><div><dt>Completed close</dt><dd>{formatMoney(facts.latest_completed_close)} · {formatDate(facts.latest_completed_trading_day)}</dd></div><div><dt>Market value</dt><dd>{formatMoney(facts.market_value)}</dd></div><div><dt>Unrealized P&amp;L</dt><dd>{formatMoney(facts.unrealized_pnl)} / {formatPercent(facts.unrealized_pnl_pct)}</dd></div><div><dt>Monitoring</dt><dd>{facts.monitoring_status ?? 'Unavailable'}</dd></div></dl><p>{facts.explanation}</p></section>
      <section><h3>Exit &amp; risk</h3><dl className="config-grid"><div><dt>Active exit</dt><dd>{facts.active_exit_policy ?? 'Unavailable'}</dd></div><div><dt>Exit triggered</dt><dd>{facts.exit_triggered ? `Yes · ${formatDate(facts.exit_triggered_on)}` : 'No'}</dd></div>{facts.loss_control_active ? <><div><dt>Loss-control boundary</dt><dd>{facts.loss_control_policy} · {formatMoney(facts.current_loss_control_boundary)}</dd></div><div><dt>Trigger</dt><dd>{facts.loss_control_trigger}</dd></div><div><dt>Status</dt><dd>ACTIVE STRATEGY LOSS CONTROL</dd></div><div><dt>Broker stop order</dt><dd>{facts.loss_control_broker_stop_order ? 'ACTIVE' : 'NONE'}</dd></div></> : null}<div><dt>Protective stop</dt><dd>{facts.protective_stop_policy}</dd></div><div><dt>Trailing stop</dt><dd>{facts.trailing_stop_policy}</dd></div><div><dt>Profit target</dt><dd>{facts.profit_target_policy}</dd></div><div><dt>Research-only stop</dt><dd>{facts.research_only_stop_candidate ? `${facts.research_only_stop_candidate} · ${facts.research_only_stop_status?.replace('_', ' ')}` : 'Unavailable'}</dd></div></dl></section>
      <section><h3>What changed</h3><p>Price change since entry: {formatMoney(facts.price_change_since_entry)}. Latest transition: {facts.latest_monitoring_transition ?? 'No stored transition'}.</p></section>
      <section aria-labelledby="copilot-title"><p className="eyebrow">Read-only · grounded in backend facts</p><h3 id="copilot-title">Ask AlphaPilot AI about {facts.ticker}</h3><p>The AI explains AlphaPilot data. It does not calculate indicators, change decisions, or place orders.</p>
        <form onSubmit={askCopilot}><label><span>Question for {facts.ticker}</span><input name="question" maxLength={1000} placeholder="What is my stop?" required /></label><button className="button button--primary button--small" disabled={copilot.isPending}>{copilot.isPending ? 'Asking…' : 'Ask AlphaPilot AI'}</button></form>
        {copilot.isError ? <p role="alert" className="inline-note inline-note--warning">AlphaPilot AI is disabled, unavailable, or returned an invalid grounded response.</p> : null}
        {copilot.data ? <article className="inline-note" aria-live="polite"><h4>AI explanation</h4><p>{copilot.data.answer}</p><h4>Based on AlphaPilot data</h4>{copilot.data.as_of_date ? <p>As of completed session: {formatDate(copilot.data.as_of_date)}</p> : null}<dl className="config-grid">{copilot.data.fact_refs.map((fact) => <div key={fact.fact_id}><dt>{fact.label}</dt><dd>{formatFactValue(fact.value)}</dd></div>)}</dl>{copilot.data.limitations.map((item) => <p className="helper-text" key={item}>{item}</p>)}</article> : null}
      </section>
      <section><p className="eyebrow">Forward paper validation · manually recorded, not broker-connected</p><h3>Alpaca Paper</h3>
        {papers.data?.map((paper) => <article className="inline-note" key={paper.id}><strong>{paper.execution_source} · {paper.status}</strong><br />Actual entry: {paper.actual_quantity} @ {formatMoney(paper.actual_entry_price)}. AlphaPilot reference: {paper.planned_quantity ?? 'Unavailable'} @ {formatMoney(paper.reference_entry_price)}.<br />Fill difference: {formatMoney(paper.entry_fill_difference)} / {paper.entry_fill_difference_bps === null ? 'Unavailable' : `${paper.entry_fill_difference_bps} bps`}.{paper.status === 'CLOSED' ? <> Gross paper P&amp;L: {formatMoney(paper.paper_gross_pnl)} / {formatPercent(paper.paper_gross_return_pct)}.</> : <form onSubmit={(event) => recordExit(event, paper.id)}><label><span>Full exit quantity</span><input name="quantity" type="number" min="1" defaultValue={paper.actual_quantity} required /></label><label><span>Average exit fill</span><input name="price" type="number" min="0.0001" step="0.0001" required /></label><label><span>Execution date/time</span><input name="executed_at" type="datetime-local" required /></label><label><span>Note (optional)</span><input name="note" maxLength={500} /></label><button className="button button--primary button--small">Record Paper Exit</button></form>}</article>)}
        {!papers.data?.some((paper) => paper.status === 'OPEN') ? <form onSubmit={recordEntry}><h4>Record Alpaca Paper Entry</h4><p>AlphaPilot reference values are read-only. Enter only the manual paper execution.</p><label><span>Actual quantity</span><input name="quantity" type="number" min="1" required /></label><label><span>Average fill price</span><input name="price" type="number" min="0.0001" step="0.0001" required /></label><label><span>Execution date/time</span><input name="executed_at" type="datetime-local" required /></label><label><span>Note (optional)</span><input name="note" maxLength={500} /></label><button className="button button--primary button--small">Record Alpaca Paper Entry</button></form> : null}
        {entry.isError || exit.isError ? <p role="alert" className="inline-note inline-note--warning">The manual paper record was rejected.</p> : null}
      </section>
    </div> : null}
  </section>
}
