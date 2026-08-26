import type { PortfolioRiskConfig, SizingPolicy } from '../../types/portfolio'
import { formatPercent, sizingLabel } from '../../utils/format'
import { HELP_TEXT } from './helpText'

export function RiskSummary({
  config,
  sizingPolicy,
}: {
  config: PortfolioRiskConfig
  sizingPolicy: SizingPolicy
}) {
  return (
    <section className="panel" aria-labelledby="risk-summary-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Research configuration</p>
          <h2 id="risk-summary-title" className="heading-with-help">Risk & allocation constraints <InfoTooltip label="About risk and allocation constraints">{HELP_TEXT.constraints}</InfoTooltip></h2>
        </div>
        <span className="badge badge--neutral">{sizingLabel(sizingPolicy)}</span>
      </div>
      <dl className="config-grid">
        <div><dt>Risk per position</dt><dd>{formatPercent(config.risk_per_position_pct)}</dd></div>
        <div><dt>Maximum position weight</dt><dd>{formatPercent(config.max_position_weight_pct)}</dd></div>
        <div><dt>Maximum portfolio risk</dt><dd>{formatPercent(config.max_portfolio_risk_pct)}</dd></div>
        <div><dt>Minimum cash reserve</dt><dd>{formatPercent(config.minimum_cash_reserve_pct)}</dd></div>
        <div><dt>Maximum sector weight</dt><dd>{formatPercent(config.max_sector_weight_pct)}</dd></div>
        <div><dt>Maximum positions</dt><dd>{config.max_positions}</dd></div>
        <div><dt>ATR period</dt><dd>{config.atr_period} trading bars</dd></div>
        <div><dt>ATR stop proxy</dt><dd>{config.atr_stop_multiple}× ATR14</dd></div>
      </dl>
      <p className="inline-note">Research constraints are advisory model assumptions, not guaranteed risk controls.</p>
    </section>
  )
}
import { InfoTooltip } from '../../components/InfoTooltip'
