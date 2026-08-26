import { Link } from 'react-router-dom'
import { EmptyState } from '../../components/AsyncState'
import type { PortfolioPlan } from '../../types/portfolio'
import { formatDate, selectionLabel, sizingLabel, strategyLabel } from '../../utils/format'
import { OpportunityExplorer } from '../portfolio/OpportunityExplorer'
import { PortfolioSummary } from '../portfolio/PortfolioSummary'
import { PositionsTable } from '../portfolio/PositionsTable'
import { RiskSummary } from '../portfolio/RiskSummary'
import { StalePlanWarning } from '../portfolio/StalePlanWarning'
import { PlanReadinessBanner } from '../portfolio/PlanReadinessBanner'
import type { PortfolioDecision, PortfolioPlanActionResult } from '../../types/portfolio'

export function PlanOverview({ plan, isDirty = false, hasAppliedActions = false, appliedActionIds, actionPendingId, onApplyDecision, onPreviewDecision }: { plan: PortfolioPlan | null; isDirty?: boolean; hasAppliedActions?: boolean; appliedActionIds?: ReadonlySet<string>; actionPendingId?: string | null; onApplyDecision?: (decision: PortfolioDecision, requestedShares?: number) => void | Promise<unknown>; onPreviewDecision?: (decision: PortfolioDecision, requestedShares: number) => Promise<PortfolioPlanActionResult | null> }) {
  if (!plan) {
    return (
      <EmptyState title="No portfolio plan yet">
        Enter a current portfolio and generate a stored-data analysis on the{' '}
        <Link to="/portfolio">Portfolio Plan page</Link>.
      </EmptyState>
    )
  }
  return (
    <div className="page-stack">
      {isDirty ? <StalePlanWarning /> : null}
      {!isDirty && hasAppliedActions ? <p className="inline-note inline-note--warning" role="status">Portfolio updated — holdings and allocation are current; analysis metrics reflect the previous plan snapshot.</p> : null}
      <div className="analysis-strip">
        <div><span>Strategy</span><strong>{strategyLabel(plan.strategy)}</strong></div>
        <div><span>Selection</span><strong>{selectionLabel(plan.selection_policy)}</strong></div>
        <div><span>Sizing</span><strong>{sizingLabel(plan.sizing_policy)}</strong></div>
        <div><span>Requested</span><strong>{formatDate(plan.requested_as_of_date)}</strong></div>
        <div><span>Completed analysis session</span><strong>{formatDate(plan.analysis_as_of_date)}</strong></div>
        <div><span>Coverage / approved BUY</span><strong>{plan.readiness.evaluated_tickers} / {plan.readiness.requested_tickers} · {plan.readiness.approved_buys}</strong></div>
      </div>
      <PlanReadinessBanner readiness={plan.readiness} />
      <PortfolioSummary summary={plan.portfolio} snapshot />
      <PositionsTable positions={plan.portfolio.positions} snapshot />
      <OpportunityExplorer decisions={plan.decisions} statuses={plan.candidate_statuses} readiness={plan.readiness} canApplyDecisions={!isDirty && Boolean(onApplyDecision)} onApplyDecision={onApplyDecision} onPreviewDecision={onPreviewDecision} sizingPolicy={plan.sizing_policy} appliedActionIds={appliedActionIds} actionPendingId={actionPendingId} />
      <RiskSummary config={plan.config} sizingPolicy={plan.sizing_policy} />
    </div>
  )
}
