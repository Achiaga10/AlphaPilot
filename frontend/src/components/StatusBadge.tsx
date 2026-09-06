interface StatusBadgeProps {
  value: string
  label?: string
}

export function StatusBadge({ value, label = value }: StatusBadgeProps) {
  const tone = ['BUY', 'READY', 'ok'].includes(value)
    ? 'positive'
    : ['SELL', 'EXIT_REQUIRED', 'STALE_DATA', 'NO_DATA', 'COMPANY_NOT_FOUND'].includes(value)
      ? 'negative'
      : ['SKIP', 'NOT_ACTIONABLE', 'ATTENTION', 'INSUFFICIENT_HISTORY'].includes(value)
        ? 'warning'
        : 'neutral'
  return <span className={`badge badge--${tone}`}>{label}</span>
}
