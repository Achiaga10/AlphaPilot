import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { API_BASE_URL } from '../api/client'
import { planFixture } from '../test/fixtures'
import { renderApp } from '../test/renderApp'
import { server } from '../test/server'
import type { PortfolioDecision, PortfolioPlan } from '../types/portfolio'

function multiBuyPlan(): PortfolioPlan {
  const first = planFixture.decisions[0]!
  const second: PortfolioDecision = {
    ...first, ticker: 'AMD', ranking_score: '0.04', reference_price: '100',
    proposed_shares: 50, target_allocation_dollars: '5000', estimated_cash_outlay: '5000',
    target_weight_pct: '5', modeled_position_risk_dollars: '300',
    action_id: '2:BUY:AMD', application_order: 2, depends_on_action_ids: [],
  }
  return {
    ...planFixture,
    decisions: [first, second],
    candidate_statuses: [
      planFixture.candidate_statuses[0]!,
      { ...planFixture.candidate_statuses[0]!, ticker: 'AMD', candidate_rank: 2, ranking_score: '0.04' },
    ],
    readiness: { ...planFixture.readiness, status: 'READY', requested_tickers: 2, evaluated_tickers: 2, fresh_tickers: 2, stale_tickers: 0, insufficient_history_tickers: 0, approved_buys: 2, actionable_decisions: 2 },
  }
}

test('BUY recommendations may be selected out of rank order and update Dashboard immediately', async () => {
  const user = userEvent.setup()
  server.use(http.post(`${API_BASE_URL}/api/v1/portfolio/plan`, () => HttpResponse.json(multiBuyPlan())))
  renderApp('/portfolio')
  await user.click(await screen.findByRole('button', { name: 'Generate Portfolio Plan' }))
  const reviewButtons = await screen.findAllByRole('button', { name: 'Review Add' })
  await user.click(reviewButtons[1]!)
  await user.click(await screen.findByRole('button', { name: 'Add to Research Portfolio' }))
  expect(await screen.findByRole('button', { name: 'Applied' })).toBeDisabled()
  expect(screen.queryByText('Displayed plan is stale')).not.toBeInTheDocument()
  expect(screen.getByLabelText('Cash (USD)')).toHaveValue('95000')

  await user.click(screen.getByRole('button', { name: 'Review Add' }))
  await user.click(await screen.findByRole('button', { name: 'Add to Research Portfolio' }))
  await waitFor(() => expect(screen.getAllByRole('button', { name: 'Applied' })).toHaveLength(2))
  expect(screen.getByLabelText('Cash (USD)')).toHaveValue('85100')
  expect(screen.queryByRole('button', { name: 'Review Add' })).not.toBeInTheDocument()

  await user.click(screen.getByRole('link', { name: 'Dashboard' }))
  expect(await screen.findByRole('img', { name: 'NVDA: $9,900.00, 9.90%' })).toBeInTheDocument()
  expect(screen.getByRole('img', { name: 'AMD: $5,000.00, 5.00%' })).toBeInTheDocument()
  expect(screen.getByRole('img', { name: 'Cash: $85,100.00, 85.10%' })).toBeInTheDocument()
  expect(screen.getByText(/holdings and allocation are current; analysis metrics reflect the previous plan snapshot/i)).toBeInTheDocument()
})

test('manual draft mutation makes an active plan stale and regeneration resets applied actions', async () => {
  const user = userEvent.setup()
  server.use(http.post(`${API_BASE_URL}/api/v1/portfolio/plan`, () => HttpResponse.json(multiBuyPlan())))
  renderApp('/portfolio')
  await user.click(await screen.findByRole('button', { name: 'Generate Portfolio Plan' }))
  await user.click((await screen.findAllByRole('button', { name: 'Review Add' }))[0]!)
  await user.click(await screen.findByRole('button', { name: 'Add to Research Portfolio' }))
  await screen.findByRole('button', { name: 'Applied' })
  await user.clear(screen.getByLabelText('Cash (USD)'))
  await user.type(screen.getByLabelText('Cash (USD)'), '80000')
  expect(await screen.findByText('Displayed plan is stale')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Review Add' })).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Regenerate plan' }))
  await waitFor(() => expect(screen.queryByText('Displayed plan is stale')).not.toBeInTheDocument())
  expect(screen.getAllByRole('button', { name: 'Review Add' })).toHaveLength(2)
})

test('user share override is previewed by backend and keeps remaining recommendations available', async () => {
  const user = userEvent.setup()
  server.use(http.post(`${API_BASE_URL}/api/v1/portfolio/plan`, () => HttpResponse.json(multiBuyPlan())))
  renderApp('/portfolio')
  await user.click(await screen.findByRole('button', { name: 'Generate Portfolio Plan' }))
  const shares = screen.getByLabelText('Shares to add for NVDA')
  await user.clear(shares)
  await user.type(shares, '30')
  await user.click(screen.getAllByRole('button', { name: 'Review Add' })[0]!)
  const dialog = await screen.findByRole('dialog')
  expect(within(dialog).getByText('55 shares')).toBeInTheDocument()
  expect(within(dialog).getByText('30 shares')).toBeInTheDocument()
  expect(within(dialog).getByText(/larger|smaller than AlphaPilot/i)).toBeInTheDocument()
  await user.click(within(dialog).getByRole('button', { name: 'Add to Research Portfolio' }))
  expect(await screen.findByText(/Portfolio differs from AlphaPilot's original sizing plan/i)).toBeInTheDocument()
  expect(screen.getByLabelText('Cash (USD)')).toHaveValue('94600')
  expect(screen.getByRole('button', { name: 'Review Add' })).toBeInTheDocument()
})

function storedPosition(shares = 10) {
  window.localStorage.setItem('alphapilot.plan-draft.v1', JSON.stringify({
    cash: '1000', positions: [{ ticker: 'JNJ', shares, reference_price: '150', cost_basis: '120', sector: 'Health Care', modeled_risk_dollars: '100' }],
    strategy: 'ema20-pullback', selectionPolicy: 'relative-strength-20', sizingPolicy: 'equal-slot',
    asOfDate: '2026-08-26', tickerScope: '',
  }))
}

test('manual partial sell defaults to stored price/full quantity, updates draft, and marks the plan stale', async () => {
  const user = userEvent.setup()
  storedPosition()
  renderApp('/portfolio')
  await user.click(await screen.findByRole('button', { name: 'Generate Portfolio Plan' }))
  await user.click(screen.getByRole('link', { name: 'Dashboard' }))
  await user.click(await screen.findByRole('button', { name: 'Sell Position' }))
  expect(await screen.findByText('Latest stored completed close')).toBeInTheDocument()
  expect(screen.getByLabelText('Shares to sell')).toHaveValue(10)
  expect(await screen.findByLabelText('Execution price')).toHaveValue('150')
  expect(screen.getAllByText('Aug 20, 2026').length).toBeGreaterThan(0)
  await user.clear(screen.getByLabelText('Shares to sell'))
  await user.type(screen.getByLabelText('Shares to sell'), '4')
  await user.click(screen.getByRole('button', { name: 'Review Sale' }))
  expect(await screen.findByText(/Sell 4 shares of JNJ at \$150.00/)).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Update Research Portfolio' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  const currentTable = screen.getAllByRole('table')[0]!
  expect(within(currentTable).getByRole('row', { name: /JNJ 6/ })).toBeInTheDocument()
  expect(screen.getByRole('img', { name: 'Cash: $1,600.00, 64.00%' })).toBeInTheDocument()
  expect(screen.getByText('Displayed plan is stale')).toBeInTheDocument()
})

test('manual full sell with a user price override removes the position', async () => {
  const user = userEvent.setup()
  storedPosition(2)
  renderApp('/')
  await user.click(await screen.findByRole('button', { name: 'Sell Position' }))
  const price = await screen.findByLabelText('Execution price')
  await user.clear(price)
  await user.type(price, '160')
  await user.click(screen.getByRole('button', { name: 'Review Sale' }))
  expect(await screen.findByText('User-provided execution price')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Update Research Portfolio' }))
  expect(await screen.findByText('No current positions')).toBeInTheDocument()
  expect(screen.getByRole('img', { name: 'Cash: $1,320.00, 100.00%' })).toBeInTheDocument()
})

test('missing stored price requires a manual price and invalid share quantities stay blocked', async () => {
  const user = userEvent.setup()
  storedPosition()
  server.use(http.get(`${API_BASE_URL}/api/v1/portfolio/latest-price/JNJ`, () => HttpResponse.json({ ticker: 'JNJ', price: null, price_date: null, source: 'LATEST_STORED_CANDLE' })))
  renderApp('/')
  await user.click(await screen.findByRole('button', { name: 'Sell Position' }))
  expect(await screen.findByText('No stored market price is available for this ticker. Enter an execution price manually.')).toBeInTheDocument()
  const review = screen.getByRole('button', { name: 'Review Sale' })
  expect(review).toBeDisabled()
  await user.clear(screen.getByLabelText('Shares to sell'))
  await user.type(screen.getByLabelText('Shares to sell'), '0')
  expect(screen.getByText(/Enter a whole-share quantity from 1 to 10/)).toBeInTheDocument()
  await user.clear(screen.getByLabelText('Shares to sell'))
  await user.type(screen.getByLabelText('Shares to sell'), '11')
  expect(review).toBeDisabled()
})
