import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { DailyBriefOpportunities, DailyBriefOpportunity, DailyBriefPosition, DailyPortfolioBrief } from '../../types/portfolio'
import { formatDate, formatMoney, formatPercent, sizingLabel, strategyLabel } from '../../utils/format'
import { OPEN_COPILOT_EVENT } from '../copilot/FloatingCopilot'
import { PositionIntelligencePanel } from '../portfolio/PositionIntelligencePanel'

function PositionCard({ item, priority, onInspect }: { item: DailyBriefPosition; priority: 'sell' | 'attention' | 'hold' | 'unavailable'; onInspect: () => void }) {
  return <article className={`daily-card daily-card--${priority}`}>
    <div className="daily-card__heading"><div><strong>{item.ticker}</strong><span className={`badge badge--${priority === 'sell' ? 'negative' : priority === 'attention' ? 'warning' : 'neutral'}`}>{item.status}</span></div><small>As of {formatDate(item.as_of_session)}</small></div>
    <p>{item.explanation}</p>
    <dl className="daily-card__facts"><div><dt>Reason</dt><dd>{item.reason}</dd></div><div><dt>Quantity</dt><dd>{item.quantity}</dd></div><div><dt>Completed close</dt><dd>{formatMoney(item.latest_completed_close)}</dd></div><div><dt>Unrealized P&amp;L</dt><dd>{formatMoney(item.unrealized_pnl)} / {formatPercent(item.unrealized_pnl_pct)}</dd></div>{item.loss_control_boundary !== null ? <div><dt>Loss-control boundary</dt><dd>{formatMoney(item.loss_control_boundary)}</dd></div> : null}</dl>
    {item.sticky_sell ? <p className="inline-note inline-note--warning">Strategy SELL required. No broker order has been sent. The SELL remains latched until the research position is fully exited.</p> : null}
    <div className="table-actions"><button className="button button--secondary button--small" type="button" onClick={onInspect}>Why this position?</button><button className="button button--secondary button--small" type="button" onClick={() => window.dispatchEvent(new CustomEvent(OPEN_COPILOT_EVENT, { detail: { positionId: item.position_id } }))}>Ask AI</button><Link className="button button--secondary button--small" to="/portfolio">Manage / Paper Validation</Link></div>
  </article>
}

function OpportunityCard({ item, kind }: { item: DailyBriefOpportunity; kind: 'actionable' | 'research' | 'deferred' }) {
  return <article className={`daily-card daily-card--${kind}`}>
    <div className="daily-card__heading"><div><strong>{item.ticker}</strong><span className={`badge badge--${kind === 'actionable' ? 'positive' : kind === 'research' ? 'warning' : 'neutral'}`}>{kind === 'actionable' ? 'ACTIONABLE' : kind === 'research' ? 'RESEARCH ONLY' : 'DEFERRED'}</span></div><small>{strategyLabel(item.strategy)} · {item.strategy_profile_id} v{item.strategy_profile_version}</small></div>
    <dl className="daily-card__facts"><div><dt>Reference entry</dt><dd>{formatMoney(item.reference_price)}</dd></div><div><dt>Suggested quantity</dt><dd>{item.proposed_shares}</dd></div><div><dt>Sizing</dt><dd>{sizingLabel(item.sizing_policy)}</dd></div><div><dt>Readiness</dt><dd>{item.execution_readiness}</dd></div><div><dt>Reason</dt><dd>{item.execution_readiness_reason}</dd></div><div><dt>Loss-control policy</dt><dd>{item.loss_control_policy}</dd></div><div><dt>Boundary</dt><dd>{formatMoney(item.loss_control_boundary)}</dd></div><div><dt>Trigger</dt><dd>{item.loss_control_trigger ?? 'Unavailable'}</dd></div><div><dt>Broker stop order</dt><dd>{item.broker_stop_order ? 'Yes' : 'No'}</dd></div><div><dt>Loss-control distance</dt><dd>{formatMoney(item.loss_control_distance_dollars)} / {formatPercent(item.loss_control_distance_pct)}</dd></div></dl>
    {kind === 'research' ? <p className="inline-note inline-note--warning">AlphaPilot found a BUY signal, but this opportunity is not approved for actionable execution.</p> : null}
    {kind === 'deferred' ? <p className="inline-note">Workflow status: {item.workflow_status}. Existing portfolio cash is unchanged; no required-exit proceeds are assumed.</p> : null}
    <Link className="button button--secondary button--small" to="/portfolio">Review in Portfolio Plan</Link>
  </article>
}

function Section({ title, eyebrow, empty, children }: { title: string; eyebrow: string; empty: string; children: ReactNode[] }) {
  return <section className="daily-section"><div className="section-heading"><div><p className="eyebrow">{eyebrow}</p><h2>{title}</h2></div></div>{children.length ? <div className="daily-grid">{children}</div> : <p className="empty-inline">{empty}</p>}</section>
}

export function DailyPortfolioManager({ brief, opportunities, opportunitiesLoading, opportunitiesError, refreshing, onRefresh, onViewAllResearch }: { brief: DailyPortfolioBrief; opportunities: DailyBriefOpportunities | undefined; opportunitiesLoading: boolean; opportunitiesError: boolean; refreshing: boolean; onRefresh: () => void; onViewAllResearch: () => void }) {
  const [intelligencePositionId, setIntelligencePositionId] = useState<string | null>(null)
  return <div className="page-stack daily-manager">
    <section className={`panel daily-status daily-status--${brief.data_status.readiness.toLowerCase()}`}>
      <div className="section-heading"><div><p className="eyebrow">Latest completed daily session</p><h2>{formatDate(brief.data_status.brief_session)}</h2></div><div className="table-actions"><span className="badge badge--neutral">{brief.data_status.readiness}</span><button className="button button--secondary button--small" type="button" onClick={onRefresh} disabled={refreshing}>{refreshing ? 'Refreshing…' : 'Refresh Daily Brief'}</button></div></div>
      <p>{brief.data_status.explanation}</p>
      <dl className="config-grid"><div><dt>Expected completed session</dt><dd>{formatDate(brief.data_status.expected_completed_session)}</dd></div><div><dt>Latest synchronized session</dt><dd>{formatDate(brief.data_status.latest_synchronized_session)}</dd></div><div><dt>Daily Brief session</dt><dd>{formatDate(brief.data_status.brief_session)}</dd></div><div><dt>Sync status</dt><dd>{brief.data_status.sync_status}</dd></div></dl>
      {brief.data_status.readiness !== 'READY' ? <p className="inline-note inline-note--warning">New-entry decisions may be blocked because stored market data is not fully current. Existing guidance retains its actual as-of date. Use Data Management to run a sync; Refresh does not sync data.</p> : null}
    </section>
    <section className="summary-grid daily-summary" aria-label="Daily portfolio summary"><article><span>Portfolio value</span><strong>{formatMoney(brief.summary.portfolio_value)}</strong></article><article><span>Cash</span><strong>{formatMoney(brief.summary.cash)}</strong><small>{formatPercent(brief.summary.cash_pct)}</small></article><article><span>Invested</span><strong>{formatMoney(brief.summary.invested_market_value)}</strong></article><article><span>Open positions</span><strong>{brief.summary.open_positions} / {brief.summary.max_positions}</strong></article><article><span>Action required</span><strong>{brief.required_actions.length}</strong></article><article><span>Attention</span><strong>{brief.attention_positions.length}</strong></article></section>
    {brief.workflow_status === 'WAITING_FOR_REQUIRED_EXITS' ? <p className="inline-note inline-note--warning" role="status">Resolve required exits before relying on new-entry execution quantities. AlphaPilot has not assumed sell proceeds or changed portfolio cash.</p> : null}
    <Section eyebrow="Priority 1" title="Action Required" empty="No positions require action.">{brief.required_actions.map((item) => <PositionCard key={item.position_id} item={item} priority="sell" onInspect={() => setIntelligencePositionId(item.position_id)} />)}</Section>
    <Section eyebrow="Priority 2" title="Attention" empty="No positions currently need attention.">{brief.attention_positions.map((item) => <PositionCard key={item.position_id} item={item} priority="attention" onInspect={() => setIntelligencePositionId(item.position_id)} />)}</Section>
    {opportunitiesLoading ? <section className="panel opportunity-loading" aria-live="polite"><p className="eyebrow">Opportunity discovery</p><h2>Scanning today&apos;s opportunities…</h2><p>Position management remains available while AlphaPilot evaluates the governed universe.</p></section> : null}
    {opportunitiesError ? <section className="panel data-health--warning" role="alert"><p className="eyebrow">Opportunity discovery unavailable</p><h2>Positions remain current</h2><p>The opportunity scan could not be loaded. Existing SELL, ATTENTION, and HOLD guidance above remains available.</p></section> : null}
    {opportunities ? <>
      <Section eyebrow="Priority 3" title={`New Actionable Opportunities (${opportunities.actionable_total_count})`} empty="No actionable new opportunities passed current loss-control readiness.">{opportunities.actionable_opportunities.map((item) => <OpportunityCard key={`${item.source_plan_id}-${item.ticker}`} item={item} kind="actionable" />)}</Section>
      <section className="daily-section"><div className="section-heading"><div><p className="eyebrow">Priority 4</p><h2>Research-only Opportunities ({opportunities.research_only_total_count})</h2></div>{opportunities.research_only_opportunities.length < opportunities.research_only_total_count ? <button className="button button--secondary button--small" type="button" onClick={onViewAllResearch}>View all {opportunities.research_only_total_count}</button> : null}</div>{opportunities.research_only_opportunities.length ? <div className="daily-grid">{opportunities.research_only_opportunities.map((item) => <OpportunityCard key={`${item.source_plan_id}-${item.ticker}`} item={item} kind="research" />)}</div> : <p className="empty-inline">No research-only BUY signals are present.</p>}</section>
      {opportunities.deferred_opportunities.length ? <Section eyebrow="Workflow blocked" title={`Deferred Opportunities (${opportunities.deferred_total_count})`} empty="No deferred opportunities.">{opportunities.deferred_opportunities.map((item) => <OpportunityCard key={`${item.source_plan_id}-${item.ticker}`} item={item} kind="deferred" />)}</Section> : null}
    </> : null}
    <Section eyebrow="Lower priority" title="Hold / No Action" empty="No HOLD positions.">{brief.hold_positions.map((item) => <PositionCard key={item.position_id} item={item} priority="hold" onInspect={() => setIntelligencePositionId(item.position_id)} />)}</Section>
    <Section eyebrow="Data unavailable" title="Unavailable Position Guidance" empty="No positions have unavailable guidance.">{brief.unavailable_positions.map((item) => <PositionCard key={item.position_id} item={item} priority="unavailable" onInspect={() => setIntelligencePositionId(item.position_id)} />)}</Section>
    {intelligencePositionId ? <PositionIntelligencePanel portfolioId={brief.portfolio_id} positionId={intelligencePositionId} onClose={() => setIntelligencePositionId(null)} /> : null}
  </div>
}
