import { useState } from 'react'
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncState'
import { DailyPortfolioManager } from '../features/dashboard/DailyPortfolioManager'
import { usePortfolioWorkspace } from '../features/portfolio/PortfolioWorkspace'
import { useDailyBriefOpportunitiesQuery, useDailyPortfolioBriefQuery, useLivePortfolioRefreshMutation } from '../hooks/usePortfolioApi'

export function DashboardPage() {
  const { portfolio, portfolioPending } = usePortfolioWorkspace()
  const [researchLimit, setResearchLimit] = useState(10)
  const brief = useDailyPortfolioBriefQuery(portfolio?.portfolio_id ?? null)
  const opportunities = useDailyBriefOpportunitiesQuery(
    portfolio?.portfolio_id ?? null,
    researchLimit,
  )
  const live = useLivePortfolioRefreshMutation(portfolio?.portfolio_id ?? null)
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">AlphaPilot · Today</p>
          <h1>Daily Portfolio Manager</h1>
          <p>Review required exits, monitored positions, and governed opportunities from the latest completed session.</p>
        </div>
        <span className="research-label">RESEARCH / DEVELOPMENT</span>
      </header>
      {portfolioPending ? <LoadingState label="Loading research portfolio…" /> : null}
      {!portfolioPending && !portfolio ? <EmptyState title="Research portfolio unavailable">Initialize the persistent research portfolio before generating a Daily Brief.</EmptyState> : null}
      {brief.isPending && portfolio ? <LoadingState label="Building Daily Portfolio Brief…" /> : null}
      {brief.isError ? <ErrorState error={brief.error} onRetry={() => void brief.refetch()} /> : null}
      {brief.data ? <DailyPortfolioManager brief={brief.data} live={live.data} liveError={live.isError} opportunities={opportunities.data} opportunitiesLoading={opportunities.isPending} opportunitiesError={opportunities.isError} refreshing={brief.isFetching || live.isPending} onRefresh={() => { void live.mutateAsync().then(() => brief.refetch()) }} onViewAllResearch={() => setResearchLimit(100)} /> : null}
    </div>
  )
}
