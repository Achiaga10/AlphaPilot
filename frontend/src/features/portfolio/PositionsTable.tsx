import { EmptyState } from '../../components/AsyncState'
import type { PortfolioPositionSummary } from '../../types/portfolio'
import { formatMoney, formatPercent } from '../../utils/format'

export function PositionsTable({ positions, onSellPosition, snapshot = false }: { positions: PortfolioPositionSummary[]; onSellPosition?: (position: PortfolioPositionSummary) => void; snapshot?: boolean }) {
  return (
    <section aria-labelledby="positions-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">{snapshot ? 'Analysis snapshot' : 'Holdings'}</p>
          <h2 id="positions-title">{snapshot ? 'Positions when analyzed' : 'Current positions'}</h2>
        </div>
        <span className="muted">{positions.length} positions</span>
      </div>
      {positions.length === 0 ? (
        <EmptyState title="No current positions">Add positions on the Portfolio Plan page.</EmptyState>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Ticker</th>
                <th scope="col">Shares</th>
                <th scope="col">Reference</th>
                <th scope="col">Market value</th>
                <th scope="col">Weight</th>
                <th scope="col">Sector</th>
                {onSellPosition ? <th scope="col">Actions</th> : null}
              </tr>
            </thead>
            <tbody>
              {positions.map((position) => (
                <tr key={position.ticker}>
                  <th scope="row">{position.ticker}</th>
                  <td>{position.shares}</td>
                  <td>{formatMoney(position.reference_price)}</td>
                  <td>{formatMoney(position.market_value)}</td>
                  <td>{formatPercent(position.portfolio_weight_pct)}</td>
                  <td>{position.sector}</td>
                  {onSellPosition ? <td><button className="table-action table-action--button" type="button" onClick={() => onSellPosition(position)}>Sell Position</button></td> : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
