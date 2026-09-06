import { useForwardPaperAnalyticsQuery } from '../../hooks/usePortfolioApi'
import { formatMoney, formatPercent } from '../../utils/format'
import type { PaperTradeAnalytics } from '../../types/portfolio'

const available = (value: unknown) =>
  typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean'
    ? String(value) : 'Unavailable'

function TradeDetail({ trade }: { trade: PaperTradeAnalytics }) {
  const entry = trade.record.entry_evidence
  const decision = entry?.decision as Record<string, unknown> | undefined
  const loss = entry?.loss_control as Record<string, unknown> | undefined
  const completed = entry?.completed_state as Record<string, unknown> | undefined
  return <details className="inline-note">
    <summary><strong>{trade.record.ticker} · {trade.record.status}</strong> · cycle {trade.record.id} · entered {trade.record.actual_entry_at}{trade.record.actual_exit_at ? ` · exited ${trade.record.actual_exit_at}` : ''}</summary>
    <p>Paper record {trade.record.id} · {trade.record.strategy_profile_id ?? 'Unknown profile'} v{trade.record.strategy_profile_version ?? '—'}</p>
    <h3>AlphaPilot plan</h3><p>Source action: {available(decision?.source_action_id)} · Planned price: {formatMoney(trade.record.reference_entry_price)} · Planned quantity: {available(trade.record.planned_quantity)} · Loss control: {available(loss?.policy)} / {available(loss?.boundary)}</p>
    <h3>Actual Paper entry</h3><p>{trade.record.actual_quantity} shares at {formatMoney(trade.record.actual_entry_price)} · {trade.record.actual_entry_at}</p>
    <h3>Entry comparison</h3><p>Adverse slippage: {formatMoney(trade.record.entry_adverse_slippage_dollars_per_share)} per share ({formatPercent(trade.record.entry_slippage_percent)}) · Quantity adherence: {formatPercent(trade.record.quantity_adherence_percent)}</p>
    <h3>At-entry strategy state</h3><p>Completed session: {available(completed?.session)} · EMA20: {available(completed?.ema20)} · EMA50: {available(completed?.ema50)} · SMA150: {available(completed?.sma150)} · Evidence: {trade.record.evidence_completeness}</p>
    {trade.record.status === 'CLOSED' ? <><h3>Outcome</h3><p>Exit: {formatMoney(trade.record.actual_exit_price)} · Gross P&amp;L: {formatMoney(trade.record.paper_gross_pnl)} · Return: {formatPercent(trade.record.paper_gross_return_pct)} · {trade.calendar_days_held} calendar days</p><h3>Post-trade observations</h3><p>MFE: {formatPercent(trade.mfe_percent)} · MAE: {formatPercent(trade.mae_percent)} · 5/10/20 sessions: {[5, 10, 20].map((horizon) => `${horizon} ${available(trade.post_exit_observations[String(horizon)]?.status)}`).join(' · ')}</p></> : <><h3>Current observation</h3><p>Completed close: {formatMoney(trade.current_completed_close)} · Unrealized Paper P&amp;L: {formatMoney(trade.current_unrealized_pnl)}</p></>}
  </details>
}

export function ForwardPaperAnalyticsPanel({ portfolioId }: { portfolioId: string }) {
  const query = useForwardPaperAnalyticsQuery(portfolioId)
  if (query.isPending) return <section className="panel"><p className="muted">Loading Forward Paper Evidence…</p></section>
  if (query.isError) return <section className="panel"><p className="inline-note inline-note--warning">Forward Paper Analytics is unavailable.</p></section>
  const data = query.data
  return <details className="panel" aria-labelledby="forward-paper-title">
    <summary><strong id="forward-paper-title">Forward Paper Evidence</strong> · {data.evidence_maturity.replaceAll('_', ' ')} · {data.open_trade_count} open / {data.closed_trade_count} closed · View analytics</summary>
    <p className="muted">Secondary research evidence from manually recorded Alpaca Paper fills. It is separate from current ResearchPortfolio holdings and cannot promote or retune a strategy. OPEN means no manual Paper exit is recorded; it does not assert current portfolio ownership.</p>
    {data.evidence_maturity !== 'MEANINGFUL_SAMPLE' ? <p className="inline-note inline-note--warning">Tiny forward sample: treat these execution outcomes as descriptive evidence only.</p> : null}
    <dl className="config-grid">
      <div><dt>Open / closed</dt><dd>{data.open_trade_count} / {data.closed_trade_count}</dd></div>
      <div><dt>Gross realized P&amp;L</dt><dd>{formatMoney(data.gross_realized_pnl)}</dd></div>
      <div><dt>Closed-trade win rate</dt><dd>{formatPercent(data.win_rate_percent)}</dd></div>
      <div><dt>Evidence quality</dt><dd>{data.complete_evidence_count} full · {data.partial_evidence_count} partial · {data.legacy_evidence_count} legacy</dd></div>
    </dl>
    {data.strategy_breakdown.map((group) => <article className="inline-note" key={`${group.strategy_profile_id}-${group.strategy_profile_version}`}><strong>{group.strategy_profile_id ?? 'Unknown profile'} v{group.strategy_profile_version ?? '—'}</strong><br />{group.closed_trade_count} closed · {formatMoney(group.gross_total_pnl)} gross P&amp;L · {formatPercent(group.win_rate_percent)} win rate · {group.evidence_maturity.replaceAll('_', ' ')}</article>)}
    {data.open_trades.length ? <><h3>Current Open Paper Validation Trades</h3><p className="muted">These are open manual Paper-validation cycles, not the authoritative current holdings list.</p>{data.open_trades.map((trade) => <TradeDetail key={trade.record.id} trade={trade} />)}</> : null}
    {data.closed_trades.length ? <><h3>Historical Closed Paper Trades</h3><p className="muted">A ticker may also appear above when it has a separate, newer Paper cycle.</p>{data.closed_trades.map((trade) => <TradeDetail key={trade.record.id} trade={trade} />)}</> : null}
    {data.total_trade_count === 0 ? <p className="muted">No forward Paper evidence has been recorded yet.</p> : null}
  </details>
}
