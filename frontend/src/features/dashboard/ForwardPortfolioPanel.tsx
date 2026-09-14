import { useState } from 'react'
import { formatMoney, formatPercent } from '../../utils/format'
import {
  useCurrentForwardPortfolioQuery,
  useForwardPortfolioDetails,
  useForwardPortfolioMutations,
} from '../../hooks/usePortfolioApi'

const dateLabel = (value: string | null) => value ?? 'Not yet processed'
const metric = (value: string | null, formatter = formatMoney) =>
  value === null ? 'N/A' : formatter(value)

export function ForwardPortfolioPanel() {
  const current = useCurrentForwardPortfolioQuery()
  const portfolio = current.data ?? null
  const details = useForwardPortfolioDetails(portfolio?.id ?? null)
  const actions = useForwardPortfolioMutations()
  const [initialCash, setInitialCash] = useState('')
  const [startSession, setStartSession] = useState('')
  const [confirming, setConfirming] = useState<'pause' | 'resume' | null>(null)

  if (current.isPending) {
    return <section className="panel"><p>Loading Micho Forward Portfolio…</p></section>
  }
  if (current.isError) {
    return <section className="panel data-health--warning" role="alert"><h2>Micho Forward Portfolio unavailable</h2><p>The backend Forward endpoint could not be loaded.</p></section>
  }
  if (!portfolio) {
    return <section className="panel forward-portfolio" aria-labelledby="forward-title">
      <p className="eyebrow">Sprint 25 · Micho only</p>
      <h2 id="forward-title">Micho Forward Portfolio</h2>
      <p className="forward-boundary"><strong>VIRTUAL FORWARD PORTFOLIO.</strong> AlphaPilot will model Micho trades automatically. Broker execution remains manual and external.</p>
      <p>This does not connect to or read your Alpaca balance. It creates a separate, persistent AlphaPilot Forward Portfolio and never backfills trades before its explicit start session.</p>
      <form className="forward-initialize" onSubmit={(event) => {
        event.preventDefault()
        actions.initialize.mutate({ initial_cash: initialCash, forward_start_session: startSession })
      }}>
        <label>Initial virtual cash<input aria-label="Initial virtual cash" type="number" min="0.01" step="0.01" required value={initialCash} onChange={(event) => setInitialCash(event.target.value)} /></label>
        <label>Forward start session<input aria-label="Forward start session" type="date" required value={startSession} onChange={(event) => setStartSession(event.target.value)} /></label>
        <button className="button button--primary" disabled={actions.initialize.isPending}>Initialize virtual portfolio</button>
      </form>
      {actions.initialize.isError ? <p className="inline-note inline-note--warning" role="alert">{actions.initialize.error.message}</p> : null}
      <p className="inline-note">EMA20 approved BUY recommendations remain visible in Portfolio Plan, but Forward automation is not enabled for EMA20 in Sprint 25.</p>
    </section>
  }

  const positions = details.positions.data ?? []
  const orders = details.orders.data ?? []
  const trades = details.trades.data ?? []
  const events = details.events.data ?? []
  const analytics = details.analytics.data
  const health = details.health.data
  const openPositions = positions.filter((item) => item.status === 'OPEN')
  const pendingEntries = orders.filter((item) => item.side === 'ENTRY' && item.status === 'PENDING')
  const pendingExits = orders.filter((item) => item.side === 'EXIT' && item.status === 'PENDING')
  const busy = actions.pause.isPending || actions.resume.isPending || actions.run.isPending

  return <section className="panel forward-portfolio" aria-labelledby="forward-title">
    <div className="section-heading"><div><p className="eyebrow">VIRTUAL FORWARD PORTFOLIO</p><h2 id="forward-title">Micho Forward Portfolio</h2></div><span className={`badge ${portfolio.status === 'PAUSED' ? 'badge--warning' : 'badge--neutral'}`}>{portfolio.status}</span></div>
    <p className="forward-boundary"><strong>Automatic virtual execution · manual external broker.</strong> A virtual fill is AlphaPilot’s modeled execution only; it is not an Alpaca order or broker-confirmed fill.</p>
    <dl className="config-grid">
      <div><dt>Strategy</dt><dd>Micho · {portfolio.strategy_id} v{portfolio.strategy_version}</dd></div>
      <div><dt>Execution</dt><dd>{portfolio.execution_mode}</dd></div>
      <div><dt>Broker boundary</dt><dd>{portfolio.broker_execution_mode}</dd></div>
      <div><dt>Forward start</dt><dd>{portfolio.forward_start_session}</dd></div>
      <div><dt>Last processed</dt><dd>{dateLabel(portfolio.last_processed_session)}</dd></div>
      <div><dt>Revision</dt><dd>{portfolio.revision}</dd></div>
    </dl>
    <div className="table-actions">
      {portfolio.status === 'ACTIVE' ? <button className="button button--secondary" disabled={busy} onClick={() => setConfirming('pause')}>Pause new entries</button> : null}
      {portfolio.status === 'PAUSED' ? <button className="button button--secondary" disabled={busy} onClick={() => setConfirming('resume')}>Resume new entries</button> : null}
      <button className="button button--secondary" disabled={busy} onClick={() => actions.run.mutate(portfolio.id)}>Run pending cycles</button>
    </div>
    {confirming ? <div className="inline-note inline-note--warning" role="alertdialog" aria-label={`Confirm ${confirming}`}><p>{confirming === 'pause' ? 'Pause blocks and cancels new virtual entries. Existing positions continue automatic Micho exit management.' : 'Resume allows new final actionable Micho BUYs to create virtual pending entries.'}</p><div className="table-actions"><button className="button button--primary" onClick={() => { const action = confirming; setConfirming(null); if (action === 'pause') actions.pause.mutate(portfolio); else actions.resume.mutate(portfolio) }}>Confirm {confirming}</button><button className="button button--secondary" onClick={() => setConfirming(null)}>Cancel</button></div></div> : null}
    {actions.run.data ? <p className="inline-note" role="status">Processed {actions.run.data.processed_sessions.length} session(s); latest completed market session {dateLabel(actions.run.data.latest_completed_market_session)}.</p> : null}
    {actions.pause.isError || actions.resume.isError || actions.run.isError ? <p className="inline-note inline-note--warning" role="alert">Forward action failed. Refresh the portfolio and retry.</p> : null}

    <div className="summary-grid forward-summary" aria-label="Forward portfolio summary">
      <article><span>Equity</span><strong>{formatMoney(portfolio.equity)}</strong></article>
      <article><span>Cash</span><strong>{formatMoney(portfolio.cash_balance)}</strong></article>
      <article><span>Market value</span><strong>{analytics ? formatMoney(analytics.market_value) : 'N/A'}</strong></article>
      <article><span>Realized P&amp;L</span><strong>{formatMoney(portfolio.realized_pnl)}</strong></article>
      <article><span>Unrealized P&amp;L</span><strong>{analytics ? formatMoney(analytics.unrealized_pnl) : 'N/A'}</strong></article>
      <article><span>Exposure</span><strong>{analytics ? formatPercent(analytics.current_exposure_pct) : 'N/A'}</strong></article>
      <article><span>Open positions</span><strong>{openPositions.length}</strong></article>
      <article><span>Pending entries / exits</span><strong>{pendingEntries.length} / {pendingExits.length}</strong></article>
    </div>

    <details open><summary>Open virtual positions ({openPositions.length})</summary>{openPositions.length ? <div className="table-shell"><table><thead><tr><th>Ticker</th><th>Strategy</th><th>Shares</th><th>Modeled entry</th><th>Last close</th><th>Value</th><th>Unrealized</th><th>Loss control</th><th>Holding</th><th>Status</th></tr></thead><tbody>{openPositions.map((item) => <tr key={item.id}><td>{item.ticker}</td><td>{portfolio.strategy_id}</td><td>{item.shares}</td><td>{formatMoney(item.modeled_entry_price)}</td><td>{formatMoney(item.last_close)}</td><td>{formatMoney(item.market_value)}</td><td>{formatMoney(item.unrealized_pnl)} · {formatPercent(item.unrealized_return_pct)}</td><td>{formatMoney(item.loss_control_boundary)} · {item.loss_control_policy}</td><td>{item.holding_sessions} sessions / {item.holding_calendar_days} days</td><td>{item.management_status}</td></tr>)}</tbody></table></div> : <p className="empty-inline">No open virtual Micho positions.</p>}</details>

    <details><summary>Pending virtual entries ({pendingEntries.length})</summary>{pendingEntries.length ? <div className="daily-grid">{pendingEntries.map((item) => <article className="daily-card" key={item.id}><strong>{item.ticker} · PENDING VIRTUAL ENTRY</strong><dl className="daily-card__facts"><div><dt>Strategy</dt><dd>{item.strategy_id} v{item.strategy_version}</dd></div><div><dt>Signal session</dt><dd>{item.source_signal_session}</dd></div><div><dt>Planned execution</dt><dd>{item.planned_execution_session ?? 'Next eligible stored session'}</dd></div><div><dt>Allocation</dt><dd>{formatMoney(item.approved_allocation)}</dd></div><div><dt>Shares</dt><dd>{item.planned_shares}</dd></div><div><dt>Loss control</dt><dd>{item.loss_control_policy} · {formatMoney(item.loss_control_boundary)}</dd></div></dl></article>)}</div> : <p className="empty-inline">No pending virtual entries.</p>}</details>

    <details><summary>Forward analytics</summary>{analytics ? <dl className="config-grid"><div><dt>Forward return</dt><dd>{formatPercent(analytics.net_return_pct)}</dd></div><div><dt>Maximum drawdown</dt><dd>{formatPercent(analytics.max_drawdown_pct)}</dd></div><div><dt>Completed trades</dt><dd>{analytics.completed_trades}</dd></div><div><dt>Win rate</dt><dd>{metric(analytics.win_rate_pct, formatPercent)}</dd></div><div><dt>Profit factor</dt><dd>{analytics.profit_factor ?? 'N/A'}</dd></div><div><dt>Expectancy</dt><dd>{metric(analytics.expectancy)}</dd></div><div><dt>Worst trade</dt><dd>{metric(analytics.worst_trade)}</dd></div><div><dt>Friction</dt><dd>{formatMoney(analytics.friction_dollars)}</dd></div><div><dt>Turnover</dt><dd>{formatPercent(analytics.turnover_pct)}</dd></div><div><dt>Max concurrent</dt><dd>{analytics.max_concurrent_positions}</dd></div></dl> : <p>N/A</p>}</details>

    <details><summary>Closed virtual trades ({trades.length})</summary>{trades.length ? <div className="table-shell"><table><thead><tr><th>Ticker</th><th>Entry</th><th>Exit</th><th>Shares</th><th>Net P&amp;L</th><th>Return</th><th>Reason</th></tr></thead><tbody>{trades.map((item) => <tr key={item.id}><td>{item.ticker}</td><td>{item.entry_session} · {formatMoney(item.modeled_entry_price)}</td><td>{item.exit_session} · {formatMoney(item.modeled_exit_price)}</td><td>{item.shares}</td><td>{formatMoney(item.net_pnl)}</td><td>{formatPercent(item.return_pct)}</td><td>{item.exit_reason}</td></tr>)}</tbody></table></div> : <p className="empty-inline">No completed Forward trades.</p>}</details>

    <details><summary>Recent Forward activity</summary>{events.length ? <ol className="forward-activity">{events.slice(0, 20).map((item) => <li key={item.id}><strong>{item.event_type.replaceAll('_', ' ')}</strong><span>{item.ticker ? `${item.ticker} · ` : ''}{item.trading_session ?? new Date(item.created_at).toLocaleString()} · {item.reason_code}</span></li>)}</ol> : <p className="empty-inline">No Forward activity yet.</p>}</details>

    <div className="inline-note"><strong>Forward Engine Health:</strong> {health?.scheduler_running ? 'Scheduler running' : 'Scheduler not running'} · {health?.scheduler_status ?? 'N/A'} · pending sessions {health?.pending_sessions ?? 'N/A'} · data {health?.data_ready ? 'ready' : 'not ready'}{health?.last_error ? ` · ${health.last_error}` : ''}</div>
    <p className="inline-note">EMA20 remains recommendation-only: approved EMA20 BUYs and MANUAL STOP REQUIRED behavior are preserved, but <strong>Forward automation is not enabled for EMA20.</strong></p>
  </section>
}
