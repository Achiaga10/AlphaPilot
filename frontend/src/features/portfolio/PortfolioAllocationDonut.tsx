import type { PortfolioDraftSummary } from '../../types/portfolio'
import { formatMoney, formatPercent } from '../../utils/format'

const POSITION_COLORS = ['#2f6fdf', '#7c5ce0', '#12a594', '#d9822b', '#d14f70', '#4f86a8', '#7a9b36', '#b35cbb', '#4575c4', '#b9783b']
const CASH_COLOR = '#c8d0da'

interface Slice {
  label: string
  value: string
  weight: string
  color: string
}

export function PortfolioAllocationDonut({ summary }: { summary: PortfolioDraftSummary }) {
  const positions = [...summary.positions].sort((a, b) => a.ticker.localeCompare(b.ticker))
  const slices: Slice[] = [
    ...positions.map((position, index) => ({
      label: position.ticker,
      value: position.market_value,
      weight: position.portfolio_weight_pct,
      color: POSITION_COLORS[index % POSITION_COLORS.length] ?? POSITION_COLORS[0]!,
    })),
    { label: 'Cash', value: summary.cash, weight: summary.cash_pct, color: CASH_COLOR },
  ]
  const radius = 44
  const circumference = 2 * Math.PI * radius
  let cumulative = 0

  return (
    <section className="panel allocation-panel" aria-labelledby="allocation-title">
      <div className="section-heading"><div><p className="eyebrow">Research Portfolio Draft</p><h2 id="allocation-title">Portfolio Allocation</h2></div><strong>{formatMoney(summary.equity)}</strong></div>
      <div className="allocation-layout">
        <svg className="allocation-donut" viewBox="0 0 120 120" role="group" aria-label="Portfolio value allocation">
          <circle cx="60" cy="60" r={radius} fill="none" stroke="#edf0f4" strokeWidth="18" />
          {slices.map((slice) => {
            const weight = Math.max(Number(slice.weight), 0)
            const length = circumference * weight / 100
            const offset = -circumference * cumulative / 100
            cumulative += weight
            return (
              <circle
                key={slice.label}
                cx="60"
                cy="60"
                r={radius}
                fill="none"
                stroke={slice.color}
                strokeWidth="18"
                strokeDasharray={`${length} ${Math.max(circumference - length, 0)}`}
                strokeDashoffset={offset}
                transform="rotate(-90 60 60)"
                tabIndex={0}
                role="img"
                aria-label={`${slice.label}: ${formatMoney(slice.value)}, ${formatPercent(slice.weight)}`}
              >
                <title>{slice.label}: {formatMoney(slice.value)} · {formatPercent(slice.weight)}</title>
              </circle>
            )
          })}
          <text x="60" y="57" textAnchor="middle" className="donut-center-label">{summary.open_positions === 0 ? 'All cash' : `${summary.open_positions} held`}</text>
          <text x="60" y="67" textAnchor="middle" className="donut-center-value">{formatPercent(summary.cash_pct)} cash</text>
        </svg>
        <ul className="allocation-legend" aria-label="Allocation legend">
          {slices.map((slice) => <li key={slice.label}><span className="allocation-swatch" style={{ backgroundColor: slice.color }} aria-hidden="true" /><strong>{slice.label}</strong><span>{formatMoney(slice.value)}</span><span>{formatPercent(slice.weight)}</span></li>)}
        </ul>
      </div>
    </section>
  )
}
