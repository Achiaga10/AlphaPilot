import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { API_BASE_URL } from '../api/client'
import type { PortfolioPlanRequest } from '../types/portfolio'
import { planFixture } from '../test/fixtures'
import { renderApp } from '../test/renderApp'
import { server } from '../test/server'

async function renderReadyPortfolio() {
  renderApp('/portfolio')
  return screen.findByRole('button', { name: 'Generate Portfolio Plan' })
}

test('financial portfolio controls are backend-owned and absent from the plan form', async () => {
  await renderReadyPortfolio()
  expect(screen.getByText(/Cash, holdings, cost basis, valuation, and revision are loaded/)).toBeInTheDocument()
  expect(screen.queryByLabelText('Cash (USD)')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Add position' })).not.toBeInTheDocument()
})

test('position intelligence renders backend facts and inactive research policy', async () => {
  const user = userEvent.setup()
  await renderReadyPortfolio()
  await user.click((await screen.findAllByRole('button', { name: 'Why this position?' }))[0]!)
  expect(await screen.findByRole('heading', { name: 'Position Intelligence' })).toBeInTheDocument()
  expect(screen.getByText('EMA20 is still held.')).toBeInTheDocument()
  expect(screen.getByText(/Static 3 × ATR14 · NOT ACTIVE/)).toBeInTheDocument()
  expect(screen.getByText(/manually recorded, not broker-connected/i)).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Record Alpaca Paper Entry' })).toBeInTheDocument()
})
test('portfolio form validates the locally editable requested date', async () => {
  const user = userEvent.setup()
  const submit = await renderReadyPortfolio()
  await user.clear(screen.getByLabelText('Requested analysis date'))
  await user.click(submit)
  expect(screen.getByLabelText('Requested analysis date')).toBeInvalid()
})

test('strategy choice displays its backend-owned frozen profile', async () => {
  const user = userEvent.setup()
  await renderReadyPortfolio()
  await user.selectOptions(screen.getByLabelText(/^Strategy/), 'micho-150')
  expect(screen.getByText('Entry mode · BOTH')).toBeInTheDocument()
  expect(screen.getByText('Promising research baseline')).toBeInTheDocument()
  expect(screen.getByText(/ATR volatility normalized .* Close below SMA150/)).toBeInTheDocument()
  expect(screen.queryByLabelText('Sizing policy')).not.toBeInTheDocument()
  expect(screen.queryByRole('slider')).not.toBeInTheDocument()
})

test('strategy, ranking, backend profile, date, and scope help is accessible', async () => {
  const user = userEvent.setup()
  await renderReadyPortfolio()
  await user.hover(screen.getByRole('button', { name: 'About strategy choices' }))
  expect(screen.getByRole('tooltip')).toHaveTextContent('SMA150')
  await user.unhover(screen.getByRole('button', { name: 'About strategy choices' }))
  await user.hover(screen.getByRole('button', { name: 'About selection policy' }))
  expect(screen.getByRole('tooltip')).toHaveTextContent('economically meaningless deterministic control')
  await user.unhover(screen.getByRole('button', { name: 'About selection policy' }))
  await user.hover(screen.getByRole('button', { name: 'About backend strategy profile' }))
  expect(screen.getByRole('tooltip')).toHaveTextContent('resolved by the versioned backend profile')
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
  expect(received.portfolio_id).toBe(planFixture.portfolio_id)
  expect(received).not.toHaveProperty('portfolio')
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
