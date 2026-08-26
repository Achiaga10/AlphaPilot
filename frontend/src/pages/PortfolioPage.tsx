import { ErrorState, LoadingState } from '../components/AsyncState'
import { OpportunityExplorer } from '../features/portfolio/OpportunityExplorer'
import { buildPlanRequest, PlanForm } from '../features/portfolio/PlanForm'
import { PortfolioSummary } from '../features/portfolio/PortfolioSummary'
import { PositionsTable } from '../features/portfolio/PositionsTable'
import { RiskSummary } from '../features/portfolio/RiskSummary'
import { StalePlanWarning } from '../features/portfolio/StalePlanWarning'
import { usePortfolioWorkspace } from '../features/portfolio/PortfolioWorkspace'
import { useAdminCapabilityQuery, useAdminTickerSyncMutation, useDeactivateCustomTickerMutation, usePortfolioPlanMutation, useRiskConfigQuery } from '../hooks/usePortfolioApi'
import type { PortfolioPlanRequest } from '../types/portfolio'
import { formatDate } from '../utils/format'
import { PlanReadinessBanner } from '../features/portfolio/PlanReadinessBanner'

export function PortfolioPage() {
  const { draft, setDraft, plan, setPlanResult, previewDecision, applyDecision, appliedActionIds, actionPendingId, lastActionMessage, hasAppliedPlanActions, isPlanDirty } = usePortfolioWorkspace()
  const riskConfig = useRiskConfigQuery()
  const mutation = usePortfolioPlanMutation()
  const admin = useAdminCapabilityQuery()
  const syncTicker = useAdminTickerSyncMutation()
  const deactivateTicker = useDeactivateCustomTickerMutation()

  function submit(request: PortfolioPlanRequest) {
    const submittedDraft = structuredClone(draft)
    mutation.mutate(request, { onSuccess: (result) => setPlanResult(result, submittedDraft) })
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Interactive research workflow</p>
          <h1>Portfolio Plan</h1>
          <p>Provide current state and ask the backend to evaluate stored market data.</p>
        </div>
      </header>

      {riskConfig.isPending ? <LoadingState label="Loading research configuration" /> : null}
      {riskConfig.isError ? <ErrorState error={riskConfig.error} onRetry={() => void riskConfig.refetch()} /> : null}
      {riskConfig.data ? (
        <PlanForm
          draft={draft}
          riskConfig={riskConfig.data}
          isSubmitting={mutation.isPending}
          onChange={setDraft}
          onSubmit={submit}
        />
      ) : null}

      {mutation.isPending ? <LoadingState label="Generating portfolio plan" /> : null}
      {mutation.isError ? <ErrorState error={mutation.error} onRetry={() => mutation.reset()} /> : null}

      {plan ? (
        <div className="page-stack plan-results" aria-live="polite">
          {isPlanDirty ? <StalePlanWarning message={lastActionMessage} onRegenerate={() => riskConfig.data && submit(buildPlanRequest(draft, riskConfig.data))} /> : null}
          {!isPlanDirty && hasAppliedPlanActions ? <p className="inline-note inline-note--warning" role="status">{lastActionMessage} Analysis metrics remain the original plan snapshot; current draft holdings and cash update on Dashboard.</p> : null}
          <section className="result-banner" aria-labelledby="plan-result-title">
            <div>
              <p className="eyebrow">Analysis complete</p>
              <h2 id="plan-result-title">Portfolio plan generated</h2>
            </div>
            <dl>
              <div><dt>Requested analysis date</dt><dd>{formatDate(plan.requested_as_of_date)}</dd></div>
              <div><dt>Completed analysis session</dt><dd>{formatDate(plan.analysis_as_of_date)}</dd></div>
            </dl>
          </section>
          <PlanReadinessBanner readiness={plan.readiness} />
          <PortfolioSummary summary={plan.portfolio} snapshot />
          <PositionsTable positions={plan.portfolio.positions} snapshot />
          <OpportunityExplorer decisions={plan.decisions} statuses={plan.candidate_statuses} readiness={plan.readiness} canApplyDecisions={!isPlanDirty} onApplyDecision={applyDecision} onPreviewDecision={previewDecision} sizingPolicy={plan.sizing_policy} appliedActionIds={appliedActionIds} actionPendingId={actionPendingId} adminEnabled={admin.data?.enabled} onSyncTicker={(ticker) => syncTicker.mutate({ ticker, start_date: new Date(Date.now() - 400 * 86_400_000).toISOString().slice(0, 10), end_date: new Date().toISOString().slice(0, 10) })} onDeactivateTicker={(ticker) => deactivateTicker.mutate(ticker)} />
          <RiskSummary config={plan.config} sizingPolicy={plan.sizing_policy} />
        </div>
      ) : null}
    </div>
  )
}
