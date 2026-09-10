import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { planFixture } from '../../test/fixtures'
import type { PortfolioDraftSummary } from '../../types/portfolio'
import { PortfolioAllocationDonut } from './PortfolioAllocationDonut'

test('donut uses backend values with deterministic distinct position colors and a cash slice', () => {
  render(<PortfolioAllocationDonut summary={planFixture.portfolio} />)
  const msft = screen.getByRole('img', { name: 'MSFT: $40,000.00, 40.00%' })
  const jnj = screen.getByRole('img', { name: 'JNJ: $30,000.00, 30.00%' })
  const cash = screen.getByRole('img', { name: 'Cash: $30,000.00, 30.00%' })
  expect(msft).toHaveAttribute('tabindex', '0')
  expect(jnj.getAttribute('fill')).not.toBe(msft.getAttribute('fill'))
  expect(cash.getAttribute('fill')).not.toBe(msft.getAttribute('fill'))
  expect(screen.getByRole('list', { name: 'Allocation legend' })).toHaveTextContent('MSFT$40,000.0040.00%')
})

test('no-position donut renders an accessible all-cash state without calculating new values', () => {
  const summary: PortfolioDraftSummary = {
    equity: '25000', cash: '25000', cash_pct: '100', invested_value: '0',
    invested_pct: '0', open_positions: 0, positions: [],
  }
  render(<PortfolioAllocationDonut summary={summary} />)
  expect(screen.getByText('All cash')).toBeInTheDocument()
  const cash = screen.getByRole('img', { name: 'Cash: $25,000.00, 100.00%' })
  expect(cash.getAttribute('d')?.match(/A 53 53/g)).toHaveLength(2)
  expect(cash.getAttribute('d')?.match(/A 35 35/g)).toHaveLength(2)
})

test('representative eight-position allocation keeps one stable slice per legend row', () => {
  const summary: PortfolioDraftSummary = {
    equity: '100000', cash: '20000', cash_pct: '20', invested_value: '80000',
    invested_pct: '80', open_positions: 8,
    positions: [
      ['TSCO', '10000', '10'], ['APA', '10000', '10'], ['SLB', '10000', '10'],
      ['DXCM', '10000', '10'], ['SPGI', '10000', '10'], ['APO', '10000', '10'],
      ['INTU', '10000', '10'], ['ERIE', '10000', '10'],
    ].map(([ticker, marketValue, weight]) => ({
      ticker: ticker!, shares: 1, reference_price: marketValue!, market_value: marketValue!,
      portfolio_weight_pct: weight!, cost_basis: null, sector: 'Test', modeled_risk_dollars: '0',
    })),
  }

  render(<PortfolioAllocationDonut summary={summary} />)

  const expectedLabels = ['APA', 'APO', 'DXCM', 'ERIE', 'INTU', 'SLB', 'SPGI', 'TSCO', 'Cash']
  const slices = screen.getAllByRole('img')
  const legendRows = within(screen.getByRole('list', { name: 'Allocation legend' })).getAllByRole('listitem')
  expect(slices).toHaveLength(9)
  expect(legendRows).toHaveLength(9)
  expect(slices.map((slice) => slice.getAttribute('aria-label')?.split(':')[0])).toEqual(expectedLabels)
  expect(legendRows.map((row) => row.querySelector('strong')?.textContent)).toEqual(expectedLabels)
  expect(slices.map((slice) => [slice.dataset.allocationLabel, slice.dataset.allocationValue, slice.dataset.allocationWeight])).toEqual(
    legendRows.map((row) => [row.dataset.allocationLabel, row.dataset.allocationValue, row.dataset.allocationWeight]),
  )
  expect(slices.every((slice) => slice.tagName === 'path')).toBe(true)
  expect(slices.every((slice) => slice.getAttribute('d')?.includes('A 53 53'))).toBe(true)
  expect(slices.every((slice) => slice.getAttribute('d')?.includes('A 35 35'))).toBe(true)
})

test('click focus transfers between slices including cash without duplicate geometry or changed allocation facts', async () => {
  const user = userEvent.setup()
  render(<PortfolioAllocationDonut summary={planFixture.portfolio} />)
  const slices = screen.getAllByRole('img')
  const before = slices.map((slice) => ({ label: slice.getAttribute('aria-label'), fill: slice.getAttribute('fill'), data: { ...slice.dataset } }))
  const idlePaths = slices.map((slice) => slice.getAttribute('d'))
  const legend = screen.getByRole('list', { name: 'Allocation legend' }).innerHTML

  for (const slice of slices) {
    await user.click(slice)
    expect(slice).toHaveFocus()
    expect(slices.filter((item) => item === document.activeElement)).toEqual([slice])
    expect(slice.getAttribute('d')).toContain('A 55 55')
    expect(slice.getAttribute('d')).toContain('A 35 35')
    expect(slices.every((item, index) => item === slice || item.getAttribute('d') === idlePaths[index])).toBe(true)
    // The original native focus interaction stays active on a repeated click (no toggle).
    await user.click(slice)
    expect(slice).toHaveFocus()
    expect(screen.getAllByRole('img').map((item) => ({ label: item.getAttribute('aria-label'), fill: item.getAttribute('fill'), data: { ...item.dataset } }))).toEqual(before)
    expect(screen.getByRole('list', { name: 'Allocation legend' }).innerHTML).toBe(legend)
  }

  await user.click(screen.getByRole('heading', { name: 'Portfolio Allocation' }))
  expect(slices.every((slice) => slice !== document.activeElement)).toBe(true)
  expect(slices.map((slice) => slice.getAttribute('d'))).toEqual(idlePaths)
})
