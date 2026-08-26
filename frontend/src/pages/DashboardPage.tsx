import { PlanOverview } from '../features/dashboard/PlanOverview'
import { usePortfolioWorkspace } from '../features/portfolio/PortfolioWorkspace'
import { useAdminDataSummaryQuery } from '../hooks/usePortfolioApi'
import { formatDate } from '../utils/format'
import { ResearchPortfolioPanel } from '../features/portfolio/ResearchPortfolioPanel'

export function DashboardPage() {
  const { plan, isPlanDirty, hasAppliedPlanActions, appliedActionIds, actionPendingId, previewDecision, applyDecision } = usePortfolioWorkspace()
  const dataSummary = useAdminDataSummaryQuery(true)
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">AlphaPilot</p>
          <h1>Research Decision Dashboard</h1>
          <p>Review the most recent backend-generated portfolio plan and its risk context.</p>
        </div>
        <span className="research-label">RESEARCH / DEVELOPMENT</span>
      </header>
      <ResearchPortfolioPanel />
      <section className="section-divider"><p className="eyebrow">Analysis snapshot</p><h2>Latest Portfolio Plan</h2></section>
      <PlanOverview plan={plan} isDirty={isPlanDirty} hasAppliedActions={hasAppliedPlanActions} appliedActionIds={appliedActionIds} actionPendingId={actionPendingId} onApplyDecision={applyDecision} onPreviewDecision={previewDecision} />
      {dataSummary.data ? <section className={`panel data-health ${dataSummary.data.stale_tracked_ticker_count > 0 || dataSummary.data.no_data_tracked_ticker_count > 0 ? 'data-health--warning' : ''}`} aria-labelledby="data-health-title"><div><p className="eyebrow">Stored completed daily data · not live</p><h2 id="data-health-title">{dataSummary.data.fresh_tracked_ticker_count === 0 ? 'Data refresh required' : 'Data health'}</h2><p>Stored completed market data as of {formatDate(dataSummary.data.latest_spy_date)}.</p></div><dl><div><dt>Latest stored completed SPY session</dt><dd>{formatDate(dataSummary.data.latest_spy_date)}</dd></div><div><dt>Fresh tracked tickers</dt><dd>{dataSummary.data.fresh_tracked_ticker_count}</dd></div><div><dt>Stale tracked tickers</dt><dd>{dataSummary.data.stale_tracked_ticker_count}</dd></div><div><dt>No-data tickers</dt><dd>{dataSummary.data.no_data_tracked_ticker_count}</dd></div><div><dt>Tracked coverage</dt><dd>{dataSummary.data.active_sp500_count} S&amp;P + {dataSummary.data.active_custom_tracked_count} custom</dd></div><div><dt>Last successful candle sync</dt><dd>{formatDate(dataSummary.data.last_candle_sync_at)}</dd></div></dl></section> : null}
    </div>
  )
}
