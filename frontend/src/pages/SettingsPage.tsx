import { ErrorState, LoadingState } from '../components/AsyncState'
import { RiskSummary } from '../features/portfolio/RiskSummary'
import { usePortfolioWorkspace } from '../features/portfolio/PortfolioWorkspace'
import { useRiskConfigQuery, useStrategyProfilesQuery } from '../hooks/usePortfolioApi'
import { classificationLabel, sizingLabel, strategyLabel } from '../utils/format'
import { InfoTooltip } from '../components/InfoTooltip'
import { HELP_TEXT } from '../features/portfolio/helpText'

export function SettingsPage() {
  const query = useRiskConfigQuery()
  const profiles = useStrategyProfilesQuery()
  const { draft } = usePortfolioWorkspace()
  const selectedProfile = profiles.data?.find((profile) => profile.strategy === draft.strategy)
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
      {profiles.isPending ? <LoadingState label="Loading backend strategy profiles" /> : null}
      {profiles.isError ? <ErrorState error={profiles.error} onRetry={() => void profiles.refetch()} /> : null}
      {query.data && selectedProfile ? <RiskSummary config={query.data} sizingPolicy={selectedProfile.sizing_policy} /> : null}

      <section className="panel" aria-labelledby="classification-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Sprint 10B evidence</p>
            <h2 id="classification-title" className="heading-with-help">Sizing policy classifications <InfoTooltip label="About sizing policy classifications">{HELP_TEXT.sizing}</InfoTooltip></h2>
          </div>
          <span className="muted">None are production-ready</span>
        </div>
        <div className="classification-grid">
          {profiles.data?.map((profile) => (
            <article key={profile.profile_id}>
              <h3>{strategyLabel(profile.strategy)}</h3>
              <ul>
                <li><span>Profile</span><strong>{profile.profile_id} v{profile.version}</strong></li>
                <li><span>Sizing</span><strong>{sizingLabel(profile.sizing_policy)}</strong></li>
                <li><span>Classification</span><strong>{classificationLabel(profile.classification)}</strong></li>
                <li><span>Strategy exit</span><strong>{profile.strategy_exit_description}</strong></li>
                <li><span>Default stop / profit</span><strong>{profile.protective_stop_default} / {profile.profit_management_default}</strong></li>
              </ul>
              <p className="muted">Research-only stop candidate: {profile.research_only_stop_candidate}</p>
            </article>
          ))}
        </div>
      </section>
      <section className="panel prose-panel">
        <h2>Frozen strategy configuration</h2>
        <p>These facts are loaded from the backend profile registry. The browser does not resolve sizing, entry mode, or strategy exits.</p>
        <p>RS20 remains AlphaPilot Research Ranking Baseline V1. This UI does not expose research parameter tuning.</p>
      </section>
    </div>
  )
}
