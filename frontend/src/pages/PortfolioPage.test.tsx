import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { API_BASE_URL } from '../api/client'
import type { PortfolioPlanRequest } from '../types/portfolio'
import { planFixture } from '../test/fixtures'
import { renderApp } from '../test/renderApp'
import { server } from '../test/server'
import { vi } from 'vitest'

async function renderReadyPortfolio() {
  renderApp('/portfolio')
  return screen.findByRole('button', { name: 'Generate Portfolio Plan' })
}

test('position editor adds and removes a current position', async () => {
  const user = userEvent.setup()
  await renderReadyPortfolio()
  expect(screen.getByText('No current positions.')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Add position' }))
  const group = screen.getByRole('group', { name: 'Position 1' })
  await user.type(within(group).getByLabelText('Ticker'), 'ibm')
  expect(within(group).getByLabelText('Ticker')).toHaveValue('IBM')
  await user.click(screen.getByRole('button', { name: 'Remove IBM' }))
  expect(screen.queryByRole('group', { name: 'Position 1' })).not.toBeInTheDocument()
})

test('portfolio form reports validation errors without calling the API', async () => {
  const user = userEvent.setup()
  const submit = await renderReadyPortfolio()
  const cash = screen.getByLabelText('Cash (USD)')
  await user.clear(cash)
  await user.type(cash, '-1')
  await user.click(submit)
  expect(screen.getByRole('alert')).toHaveTextContent('Cash must be zero or greater.')
})

test('strategy and sizing choices preserve frozen research configuration', async () => {
  const user = userEvent.setup()
  await renderReadyPortfolio()
  await user.selectOptions(screen.getByLabelText(/^Strategy/), 'micho-150')
  await user.selectOptions(screen.getByLabelText('Sizing policy'), 'atr-volatility-normalized')
  expect(screen.getByText('Entry mode · BOTH')).toBeInTheDocument()
  expect(screen.getByText('Promising research baseline')).toBeInTheDocument()
  expect(screen.queryByRole('slider')).not.toBeInTheDocument()
})

test('strategy, ranking, sizing, date, and scope help is accessible and economically accurate', async () => {
  const user = userEvent.setup()
  await renderReadyPortfolio()
  await user.hover(screen.getByRole('button', { name: 'About strategy choices' }))
  expect(screen.getByRole('tooltip')).toHaveTextContent('SMA150')
  await user.unhover(screen.getByRole('button', { name: 'About strategy choices' }))
  await user.hover(screen.getByRole('button', { name: 'About selection policy' }))
  expect(screen.getByRole('tooltip')).toHaveTextContent('economically meaningless deterministic control')
  await user.unhover(screen.getByRole('button', { name: 'About selection policy' }))
  await user.hover(screen.getByRole('button', { name: 'About sizing policy' }))
  expect(screen.getByRole('tooltip')).toHaveTextContent('none is production-ready')
  for (const name of ['About requested analysis date', 'About optional ticker scope']) {
    const trigger = screen.getByRole('button', { name })
    await user.hover(trigger)
    expect(trigger).toHaveAttribute('aria-describedby')
    await user.unhover(trigger)
  }
})

test('plan request is exact and response renders BUY SELL HOLD SKIP plus dates and statuses', async () => {
  const user = userEvent.setup()
  const captured: { value?: PortfolioPlanRequest } = {}
  server.use(
    http.post(`${API_BASE_URL}/api/v1/portfolio/plan`, async ({ request }) => {
      captured.value = (await request.json()) as PortfolioPlanRequest
      return HttpResponse.json(planFixture)
    }),
  )
  const submit = await renderReadyPortfolio()
  await user.clear(screen.getByLabelText(/^Requested analysis date/))
  await user.type(screen.getByLabelText(/^Requested analysis date/), '2026-08-23')
  await user.type(screen.getByLabelText(/^Optional ticker scope/), 'nvda, aapl')
  await user.click(submit)

  expect(await screen.findByRole('heading', { name: 'Portfolio plan generated' })).toBeInTheDocument()
  await waitFor(() => expect(captured.value).toBeDefined())
  const received = captured.value
  if (!received) throw new Error('Expected the plan request to be captured')
  expect(received.tickers).toEqual(['NVDA', 'AAPL'])
  expect(received.selection_policy).toBe('relative-strength-20')
  expect(received.portfolio).toEqual({ cash: '100000', positions: [] })
  expect(JSON.stringify(received)).not.toContain('ranking_score')

  expect(screen.getAllByText('BUY').length).toBeGreaterThan(0)
  await user.click(screen.getByRole('tab', { name: /All Decisions/ }))
  expect(screen.getAllByText('SELL').length).toBeGreaterThan(0)
  expect(screen.getAllByText('HOLD').length).toBeGreaterThan(0)
  expect(screen.getAllByText('SKIP').length).toBeGreaterThan(0)
  expect(screen.getByText('0.0842')).toBeInTheDocument()
  expect(screen.getAllByText('$9,900.00').length).toBeGreaterThan(0)
  expect(screen.getByText(/Existing-position modeled risk is incomplete/i)).toBeInTheDocument()
  expect(screen.getByText('Sector limit reached')).toBeInTheDocument()
  expect(screen.getByText('SECTOR_LIMIT')).toBeInTheDocument()
  expect(screen.getAllByText('Aug 23, 2026')).toHaveLength(1)
  expect(screen.getAllByText('Aug 20, 2026').length).toBeGreaterThan(0)
  await user.click(screen.getByRole('tab', { name: /All Evaluated/ }))
  expect(screen.getAllByText('Aug 20, 2026').length).toBeGreaterThan(1)
  expect(screen.getAllByText('STALE_DATA').length).toBeGreaterThan(0)
  expect(screen.getAllByText('INSUFFICIENT_HISTORY').length).toBeGreaterThan(0)
})

test('plan generation has a loading state and prevents duplicate submissions', async () => {
  const user = userEvent.setup()
  server.use(
    http.post(`${API_BASE_URL}/api/v1/portfolio/plan`, async () => {
      await delay(150)
      return HttpResponse.json(planFixture)
    }),
  )
  const submit = await renderReadyPortfolio()
  await user.click(submit)
  expect(screen.getByRole('button', { name: 'Generating plan…' })).toBeDisabled()
  expect(screen.getByText('Using stored AlphaPilot data. This may take a moment.')).toBeInTheDocument()
  expect(await screen.findByRole('heading', { name: 'Portfolio plan generated' })).toBeInTheDocument()
})

test('empty decisions and no approved BUY opportunities are explicit', async () => {
  const user = userEvent.setup()
  server.use(
    http.post(`${API_BASE_URL}/api/v1/portfolio/plan`, () =>
      HttpResponse.json({ ...planFixture, decisions: [] }),
    ),
  )
  const submit = await renderReadyPortfolio()
  await user.click(submit)
  expect(await screen.findByText('No approved BUYs')).toBeInTheDocument()
  expect(screen.getByText(/No approved BUYs in the usable portion/i)).toBeInTheDocument()
})

test('invalid API responses fail safely with a useful error', async () => {
  const user = userEvent.setup()
  server.use(
    http.post(`${API_BASE_URL}/api/v1/portfolio/plan`, () => HttpResponse.json({ unexpected: true })),
  )
  const submit = await renderReadyPortfolio()
  await user.click(submit)
  expect(await screen.findByRole('alert')).toHaveTextContent('AlphaPilot backend returned an invalid response.')
})

test('FastAPI 422 validation details are rendered without a raw traceback', async () => {
  const user = userEvent.setup()
  server.use(
    http.post(`${API_BASE_URL}/api/v1/portfolio/plan`, () =>
      HttpResponse.json(
        { detail: [{ loc: ['body', 'portfolio', 'cash'], msg: 'Input should be greater than or equal to 0', type: 'greater_than_equal' }] },
        { status: 422 },
      ),
    ),
  )
  const submit = await renderReadyPortfolio()
  await user.click(submit)
  expect(await screen.findByRole('alert')).toHaveTextContent('Please correct the highlighted request fields.')
  expect(screen.getByText(/body › portfolio › cash/i)).toBeInTheDocument()
})

test('dense decision and status tables use responsive scroll containers', async () => {
  const user = userEvent.setup()
  const submit = await renderReadyPortfolio()
  await user.click(submit)
  await screen.findByRole('heading', { name: 'Portfolio plan generated' })
  await user.click(screen.getByRole('tab', { name: /All Evaluated/ }))
  expect(screen.getByText('Sorted A-Z')).toBeInTheDocument()
  expect(document.querySelector('.universe-evaluation .table-scroll')).toBeInTheDocument()
  expect(document.querySelector('.app-shell')).toBeInTheDocument()
})

test('approved BUY applies exact backend shares and cash once while preserving the clean plan', async () => {
  const user = userEvent.setup()
  let regenerated: PortfolioPlanRequest | undefined
  let calls = 0
  server.use(http.post(`${API_BASE_URL}/api/v1/portfolio/plan`, async ({ request }) => {
    calls += 1
    if (calls > 1) regenerated = (await request.json()) as PortfolioPlanRequest
    return HttpResponse.json(planFixture)
  }))
  const submit = await renderReadyPortfolio()
  await user.click(submit)
  await user.click(await screen.findByRole('button', { name: 'Review Add' }))
  expect(await screen.findByRole('dialog')).toHaveTextContent('55 shares')
  await user.click(screen.getByRole('button', { name: 'Add to Research Portfolio' }))
  expect(screen.getByLabelText('Cash (USD)')).toHaveValue('90100')
  const applied = screen.getByRole('group', { name: 'Position 1' })
  expect(within(applied).getByLabelText('Ticker')).toHaveValue('NVDA')
  expect(within(applied).getByLabelText('Shares')).toHaveValue(55)
  expect(screen.getByText(/NVDA was added to the research portfolio/i)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Applied' })).toBeDisabled()
  expect(screen.queryByText('Displayed plan is stale')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Generate Portfolio Plan' }))
  await waitFor(() => expect(regenerated).toBeDefined())
  expect(regenerated?.portfolio).toEqual({ cash: '90100', positions: [{ ticker: 'NVDA', shares: 55, reference_price: '180', cost_basis: '180', sector: 'Information Technology', modeled_risk_dollars: '0' }] })
})

test('approved SELL removes the full held position using backend cash-after value', async () => {
  const user = userEvent.setup()
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
  window.localStorage.setItem('alphapilot.plan-draft.v1', JSON.stringify({
    cash: '30000', positions: [{ ticker: 'JNJ', shares: 200, reference_price: '150', cost_basis: null }],
    strategy: 'ema20-pullback', selectionPolicy: 'relative-strength-20', sizingPolicy: 'equal-slot',
    asOfDate: '2026-08-23', tickerScope: '',
  }))
  const submit = await renderReadyPortfolio()
  await user.click(submit)
  await user.click(await screen.findByRole('tab', { name: 'Approved Sells 1' }))
  await user.click(screen.getByRole('button', { name: 'Apply Sell' }))
  expect(confirm).toHaveBeenCalledWith(expect.stringContaining('Estimated proceeds: $30,000.00'))
  expect(screen.getByLabelText('Cash (USD)')).toHaveValue('60000')
  expect(screen.queryByRole('group', { name: 'Position 1' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Apply Sell' })).not.toBeInTheDocument()
})
