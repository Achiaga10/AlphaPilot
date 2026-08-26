import { ErrorState, LoadingState } from '../components/AsyncState'
import { RiskSummary } from '../features/portfolio/RiskSummary'
import { usePortfolioWorkspace } from '../features/portfolio/PortfolioWorkspace'
import { POLICY_CLASSIFICATIONS } from '../features/portfolio/policyClassifications'
import { useRiskConfigQuery } from '../hooks/usePortfolioApi'
import { classificationLabel, sizingLabel, strategyLabel } from '../utils/format'
import { InfoTooltip } from '../components/InfoTooltip'
import { HELP_TEXT } from '../features/portfolio/helpText'

export function SettingsPage() {
  const query = useRiskConfigQuery()
  const { draft } = usePortfolioWorkspace()
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Session / research configuration</p>
          <h1>Research Settings</h1>
          <p>Backend defaults and current evidence classifications. Values are not persisted to an account.</p>
        </div>
      </header>
      {query.isPending ? <LoadingState label="Loading backend defaults" /> : null}
      {query.isError ? <ErrorState error={query.error} onRetry={() => void query.refetch()} /> : null}
      {query.data ? <RiskSummary config={query.data} sizingPolicy={draft.sizingPolicy} /> : null}

      <section className="panel" aria-labelledby="classification-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Sprint 10B evidence</p>
            <h2 id="classification-title" className="heading-with-help">Sizing policy classifications <InfoTooltip label="About sizing policy classifications">{HELP_TEXT.sizing}</InfoTooltip></h2>
          </div>
          <span className="muted">None are production-ready</span>
        </div>
        <div className="classification-grid">
          {(Object.keys(POLICY_CLASSIFICATIONS) as Array<keyof typeof POLICY_CLASSIFICATIONS>).map((strategy) => (
            <article key={strategy}>
              <h3>{strategyLabel(strategy)}</h3>
              <ul>
                {(Object.entries(POLICY_CLASSIFICATIONS[strategy])).map(([policy, classification]) => (
                  <li key={policy}>
                    <span>{sizingLabel(policy)}</span><strong>{classificationLabel(classification)}</strong>
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </section>
      <section className="panel prose-panel">
        <h2>Frozen strategy configuration</h2>
        <p><strong>EMA20 Pullback:</strong> HYBRID exit with the frozen 2% threshold.</p>
        <p><strong>Micho 150:</strong> V1 with BOTH entry mode.</p>
        <p>RS20 remains AlphaPilot Research Ranking Baseline V1. This UI does not expose research parameter tuning.</p>
      </section>
    </div>
  )
}
