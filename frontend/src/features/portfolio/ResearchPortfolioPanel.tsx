import { useState } from 'react'
import { PortfolioAllocationDonut } from './PortfolioAllocationDonut'
import { ManualSellDialog } from './ManualSellDialog'
import type { PortfolioPositionSummary } from '../../types/portfolio'
import { usePortfolioWorkspace } from './PortfolioWorkspace'
import { formatDate, formatMoney, formatPercent } from '../../utils/format'
import { usePositionMonitoringQuery } from '../../hooks/usePortfolioApi'
import { ManageResearchPortfolio } from './ManageResearchPortfolio'
import { PositionIntelligencePanel } from './PositionIntelligencePanel'

export function ResearchPortfolioPanel() {
  const { draftSummary, portfolio, portfolioPending, portfolioError, refreshPortfolio } = usePortfolioWorkspace()
  const [selling, setSelling] = useState<PortfolioPositionSummary | null>(null)
  const [intelligencePositionId, setIntelligencePositionId] = useState<string | null>(null)
  const monitoring = usePositionMonitoringQuery(portfolio?.portfolio_id ?? null)
  if (portfolioPending) return <section className="panel"><p className="muted">Loading persistent research portfolio…</p></section>
  if (portfolioError) return <section className="panel"><p className="inline-note inline-note--warning">Persistent research portfolio is unavailable.</p><button className="button button--secondary button--small" type="button" onClick={() => void refreshPortfolio()}>Retry</button></section>
  if (!portfolio) return <section className="panel"><p className="muted">Initializing persistent research portfolio…</p></section>
  if (!draftSummary) return <section className="panel"><h2>{portfolio.name}</h2><p className="inline-note inline-note--warning">Valuation is {portfolio.valuation_status.toLowerCase()} because at least one holding has no stored completed close. Cash is {formatMoney(portfolio.cash)}; aggregate equity is not fabricated.</p>{portfolio.positions.map((position) => <p key={position.position_id}>{position.ticker}: {position.valuation_status === 'VALUED' ? formatMoney(position.market_value) : 'Price unavailable'}</p>)}</section>
  return (
    <div className="page-stack research-portfolio-panel">
      <section className="panel"><div className="section-heading"><div><p className="eyebrow">Persistent research portfolio · revision {portfolio.revision}</p><h2>{portfolio.name}</h2></div><span className="badge badge--positive">{portfolio.valuation_status}</span></div><dl className="config-grid"><div><dt>Realized P&amp;L</dt><dd>{formatMoney(portfolio.realized_pnl)}</dd></div><div><dt>Unrealized P&amp;L</dt><dd>{formatMoney(portfolio.total_unrealized_pnl)}</dd></div><div><dt>Valued through</dt><dd>{formatDate(portfolio.latest_completed_trading_day)}</dd></div><div><dt>Portfolio revision</dt><dd>{portfolio.revision}</dd></div></dl></section>
      <PortfolioAllocationDonut summary={draftSummary} />
      <ManageResearchPortfolio portfolio={portfolio} onChanged={() => { void refreshPortfolio(); void monitoring.refetch() }} />
      {intelligencePositionId ? <PositionIntelligencePanel portfolioId={portfolio.portfolio_id} positionId={intelligencePositionId} onClose={() => setIntelligencePositionId(null)} /> : null}
      <section className="panel" aria-labelledby="monitoring-title">
        <div className="section-heading"><div><p className="eyebrow">Backend exit guidance</p><h2 id="monitoring-title">Position Monitoring</h2></div><span className="muted">Completed sessions only</span></div>
        {monitoring.isPending ? <p className="muted">Loading monitoring…</p> : null}
        {monitoring.isError ? <p className="inline-note inline-note--warning">Monitoring is unavailable.</p> : null}
        {monitoring.data?.map((item) => <article className="inline-note" key={item.position_id}><strong>{item.ticker} · {item.status ?? 'UNAVAILABLE'}</strong><br />{item.reason}{item.exit_triggered ? ` · SELL triggered ${formatDate(item.exit_triggered_on)} and remains latched until full exit.` : ''}<br /><small>Profile: {item.strategy_profile_id ? `${item.strategy_profile_id} v${item.strategy_profile_version}` : 'unknown'} · Stop: {item.protective_stop_policy} · Trailing: {item.trailing_stop_policy} · Profit target: {item.profit_target_policy}</small></article>)}
      </section>
      <section aria-labelledby="persistent-positions-title"><div className="section-heading"><div><p className="eyebrow">Backend-valued holdings</p><h2 id="persistent-positions-title">Current positions</h2></div><span className="muted">{portfolio.positions.length} positions</span></div><div className="table-scroll"><table><thead><tr><th>Ticker</th><th>Shares</th><th>Average cost</th><th>Cost basis</th><th>Completed close</th><th>Market value</th><th>Unrealized P&amp;L</th><th>Entry provenance</th><th>Actions</th></tr></thead><tbody>{portfolio.positions.map((position) => <tr key={position.position_id}><th>{position.ticker}</th><td>{position.quantity}</td><td>{formatMoney(position.average_cost)}</td><td>{formatMoney(position.cost_basis)}</td><td>{formatMoney(position.latest_completed_close)}</td><td>{formatMoney(position.market_value)}</td><td>{formatMoney(position.unrealized_pnl)} / {formatPercent(position.unrealized_pnl_pct)}</td><td>{position.provenance_status === 'PLAN_PROFILE' ? `${position.strategy_profile_id} v${position.strategy_profile_version}` : 'Legacy imported · strategy unknown'}</td><td><button className="table-action table-action--button" type="button" onClick={() => setIntelligencePositionId(position.position_id)}>Why this position?</button>{position.latest_completed_close === null ? ' Price unavailable' : <button className="table-action table-action--button" type="button" onClick={() => setSelling(draftSummary.positions.find((item) => item.ticker === position.ticker) ?? null)}>Sell Position</button>}</td></tr>)}</tbody></table></div></section>
      {selling ? <ManualSellDialog position={selling} onClose={() => setSelling(null)} /> : null}
    </div>
  )
}
