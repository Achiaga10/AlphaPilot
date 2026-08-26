import { render, screen } from '@testing-library/react'
import { planFixture } from '../../test/fixtures'
import type { PortfolioDraftSummary } from '../../types/portfolio'
import { PortfolioAllocationDonut } from './PortfolioAllocationDonut'

test('donut uses backend values with deterministic distinct position colors and a cash slice', () => {
  render(<PortfolioAllocationDonut summary={planFixture.portfolio} />)
  const msft = screen.getByRole('img', { name: 'MSFT: $40,000.00, 40.00%' })
  const jnj = screen.getByRole('img', { name: 'JNJ: $30,000.00, 30.00%' })
  const cash = screen.getByRole('img', { name: 'Cash: $30,000.00, 30.00%' })
  expect(msft).toHaveAttribute('tabindex', '0')
  expect(jnj.getAttribute('stroke')).not.toBe(msft.getAttribute('stroke'))
  expect(cash.getAttribute('stroke')).not.toBe(msft.getAttribute('stroke'))
  expect(screen.getByRole('list', { name: 'Allocation legend' })).toHaveTextContent('MSFT$40,000.0040.00%')
})

test('no-position donut renders an accessible all-cash state without calculating new values', () => {
  const summary: PortfolioDraftSummary = {
    equity: '25000', cash: '25000', cash_pct: '100', invested_value: '0',
    invested_pct: '0', open_positions: 0, positions: [],
  }
  render(<PortfolioAllocationDonut summary={summary} />)
  expect(screen.getByText('All cash')).toBeInTheDocument()
  expect(screen.getByRole('img', { name: 'Cash: $25,000.00, 100.00%' })).toBeInTheDocument()
})
