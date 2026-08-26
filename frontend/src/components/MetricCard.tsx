import { InfoTooltip } from './InfoTooltip'

interface MetricCardProps {
  label: string
  value: string
  detail?: string
  description?: string
}

export function MetricCard({ label, value, detail, description }: MetricCardProps) {
  return (
    <article className="metric-card">
      <div className="metric-card__label">{label}{description ? <InfoTooltip label={`About ${label}`}>{description}</InfoTooltip> : null}</div>
      <p className="metric-card__value">{value}</p>
      {detail ? <p className="metric-card__detail">{detail}</p> : null}
    </article>
  )
}
