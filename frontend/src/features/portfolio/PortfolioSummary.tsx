import { MetricCard } from '../../components/MetricCard'
import type { PortfolioSummary as PortfolioSummaryType } from '../../types/portfolio'
import { formatMoney, formatPercent } from '../../utils/format'
import { HELP_TEXT } from './helpText'

export function PortfolioSummary({ summary, snapshot = false }: { summary: PortfolioSummaryType; snapshot?: boolean }) {
  return (
    <section aria-labelledby="portfolio-summary-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">{snapshot ? 'Last analysis snapshot' : 'Current state'}</p>
          <h2 id="portfolio-summary-title">{snapshot ? 'Analysis portfolio summary' : 'Portfolio summary'}</h2>
        </div>
        <span className="muted">{snapshot ? 'Frozen when plan was generated' : 'Before proposed decisions'}</span>
      </div>
      <div className="metric-grid">
        <MetricCard label="Equity" value={formatMoney(summary.equity)} />
        <MetricCard label="Cash" value={formatMoney(summary.cash)} detail={formatPercent(summary.cash_pct)} />
        <MetricCard
          label="Invested value"
          value={formatMoney(summary.invested_value)}
          detail={`${formatPercent(summary.invested_pct)} exposure`}
        />
        <MetricCard
          label="Modeled risk"
          value={formatMoney(summary.current_portfolio_risk)}
          detail={formatPercent(summary.current_portfolio_risk_pct)}
          description={HELP_TEXT.modeledRisk}
        />
        <MetricCard
          label="Available modeled risk"
          value={formatMoney(summary.available_portfolio_risk)}
          detail={formatPercent(summary.available_portfolio_risk_pct)}
          description={HELP_TEXT.availableRisk}
        />
        <MetricCard label="Open positions" value={String(summary.open_positions)} />
      </div>
      {!summary.modeled_risk_complete ? (
        <p className="inline-note inline-note--warning" role="status">
          Existing-position modeled risk is incomplete. Manually entered holdings do not include their frozen entry-risk facts, so current and available modeled risk may be understated.
        </p>
      ) : null}
    </section>
  )
}
