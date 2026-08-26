import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { API_BASE_URL } from '../api/client'
import type { CandidateStatus, PortfolioDecision, PortfolioPlan, PortfolioPlanRequest } from '../types/portfolio'
import { planFixture } from '../test/fixtures'
import { renderApp } from '../test/renderApp'
import { server } from '../test/server'

const ids: Record<string, string> = {
  AAPL: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  LDOS: 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
  NVDA: '11111111-1111-4111-8111-111111111111',
  SBET: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
}

function candidate(ticker: string, companyName: string, sector = 'Information Technology'): CandidateStatus {
  return {
    ...planFixture.candidate_statuses[0]!,
    ticker,
    company_name: companyName,
    company_id: ids[ticker],
    sector,
  }
}

function decision(ticker: string): PortfolioDecision {
  return { ...planFixture.decisions[0]!, ticker }
}

function evaluationPlan(
  target: string,
  statuses: CandidateStatus[],
  decisions: PortfolioDecision[] = statuses.map((item) => decision(item.ticker)),
): PortfolioPlan {
  return {
    ...planFixture,
    evaluation_target_ticker: target,
    candidate_statuses: statuses,
    decisions,
  }
}

test('held LDOS cannot replace explicitly requested custom ticker SBET', async () => {
  const user = userEvent.setup()
  let requestBody: PortfolioPlanRequest | undefined
  window.localStorage.setItem('alphapilot.plan-draft.v1', JSON.stringify({
    cash: '90000',
    positions: [{ ticker: 'LDOS', shares: 10, reference_price: '100' }],
  }))
  server.use(http.post(`${API_BASE_URL}/api/v1/portfolio/plan`, async ({ request }) => {
    requestBody = await request.json() as PortfolioPlanRequest
    return HttpResponse.json(evaluationPlan('SBET', [
      candidate('LDOS', 'Leidos Holdings, Inc.', 'Industrials'),
      candidate('SBET', 'Sharplink Inc', 'Communication Services'),
    ]))
  }))

  renderApp('/evaluate?ticker=sbet')
  await user.click(await screen.findByRole('button', { name: 'Evaluate stock' }))

  expect(await screen.findByRole('heading', { name: 'Sharplink Inc' })).toBeInTheDocument()
  expect(screen.getByText('SBET · Communication Services')).toBeInTheDocument()
  expect(screen.queryByText('Leidos Holdings, Inc.')).not.toBeInTheDocument()
  expect(screen.queryByText(/already held/i)).not.toBeInTheDocument()
  expect(requestBody?.tickers).toEqual(['SBET'])
  expect(requestBody?.portfolio.positions[0]?.ticker).toBe('LDOS')
  expect(JSON.stringify(requestBody)).not.toMatch(/ranking_score|"atr"|stop_distance/)
})

test('requested date and prior completed analysis session are displayed distinctly', async () => {
  const user = userEvent.setup()
  server.use(http.post(`${API_BASE_URL}/api/v1/portfolio/plan`, () => HttpResponse.json({
    ...evaluationPlan('SBET', [{
      ...candidate('SBET', 'Sharplink Inc', 'Communication Services'),
      data_as_of_date: '2026-08-25',
    }]),
    requested_as_of_date: '2026-08-26',
    analysis_as_of_date: '2026-08-25',
  })))
  renderApp('/evaluate?ticker=SBET')
  await user.click(await screen.findByRole('button', { name: 'Evaluate stock' }))

  expect(await screen.findByText('Requested')).toBeInTheDocument()
  expect(screen.getByText('Completed analysis session')).toBeInTheDocument()
  expect(screen.getAllByText('Aug 25, 2026').length).toBeGreaterThan(0)
  expect(screen.getByText('Aug 26, 2026')).toBeInTheDocument()
  expect(screen.queryByText(/live price/i)).not.toBeInTheDocument()
})

test('requested ticker is selected explicitly when it is last in a multi-position response', async () => {
  const user = userEvent.setup()
  server.use(http.post(`${API_BASE_URL}/api/v1/portfolio/plan`, () => HttpResponse.json(
    evaluationPlan('SBET', [
      candidate('AAPL', 'Apple Inc.'),
      candidate('LDOS', 'Leidos Holdings, Inc.', 'Industrials'),
      candidate('SBET', 'Sharplink Inc', 'Communication Services'),
    ]),
  )))
  renderApp('/evaluate?ticker=SBET')
  await user.click(await screen.findByRole('button', { name: 'Evaluate stock' }))
  expect(await screen.findByRole('heading', { name: 'Sharplink Inc' })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Apple Inc.' })).not.toBeInTheDocument()
})

test('a response without the requested identity renders a safe error and never falls back', async () => {
  const user = userEvent.setup()
  const log = vi.spyOn(console, 'error').mockImplementation(() => undefined)
  server.use(http.post(`${API_BASE_URL}/api/v1/portfolio/plan`, () => HttpResponse.json(
    evaluationPlan('SBET', [candidate('LDOS', 'Leidos Holdings, Inc.', 'Industrials')]),
  )))
  renderApp('/evaluate?ticker=SBET')
  await user.click(await screen.findByRole('button', { name: 'Evaluate stock' }))
  expect(await screen.findByText('AlphaPilot could not match the evaluation response to SBET.')).toBeInTheDocument()
  expect(screen.queryByText('Leidos Holdings, Inc.')).not.toBeInTheDocument()
  expect(log).toHaveBeenCalled()
  log.mockRestore()
})

test('input draft and evaluated snapshot stay distinct until a new evaluation succeeds', async () => {
  const user = userEvent.setup()
  server.use(http.post(`${API_BASE_URL}/api/v1/portfolio/plan`, async ({ request }) => {
    const body = await request.json() as PortfolioPlanRequest
    const target = body.tickers![0]!
    return HttpResponse.json(
      target === 'LDOS'
        ? evaluationPlan('LDOS', [candidate('LDOS', 'Leidos Holdings, Inc.', 'Industrials')])
        : evaluationPlan('SBET', [candidate('SBET', 'Sharplink Inc', 'Communication Services')]),
    )
  }))
  renderApp('/evaluate?ticker=LDOS')
  await user.click(await screen.findByRole('button', { name: 'Evaluate stock' }))
  expect(await screen.findByRole('heading', { name: 'Leidos Holdings, Inc.' })).toBeInTheDocument()

  const input = screen.getByLabelText('Ticker')
  await user.clear(input)
  await user.type(input, 'sbet')
  expect(screen.getByText('Showing previous evaluation for LDOS. Evaluate SBET to update.')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Leidos Holdings, Inc.' })).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Evaluate stock' }))
  expect(await screen.findByRole('heading', { name: 'Sharplink Inc' })).toBeInTheDocument()
  expect(screen.queryByText(/Showing previous evaluation/)).not.toBeInTheDocument()
})

test('lowercase unknown ticker returns its own typed status and replaces the old company', async () => {
  const user = userEvent.setup()
  server.use(http.post(`${API_BASE_URL}/api/v1/portfolio/plan`, async ({ request }) => {
    const body = await request.json() as PortfolioPlanRequest
    const target = body.tickers![0]!
    if (target === 'LDOS') {
      return HttpResponse.json(evaluationPlan('LDOS', [candidate('LDOS', 'Leidos Holdings, Inc.')]))
    }
    return HttpResponse.json(evaluationPlan('FAKE', [{
      ticker: 'FAKE', status: 'COMPANY_NOT_FOUND', data_as_of_date: null, signal: null,
      reason: 'INSUFFICIENT_HISTORY', company_name: null, company_id: null, sector: null,
    }], []))
  }))
  renderApp('/evaluate?ticker=LDOS')
  await user.click(await screen.findByRole('button', { name: 'Evaluate stock' }))
  expect(await screen.findByRole('heading', { name: 'Leidos Holdings, Inc.' })).toBeInTheDocument()
  const input = screen.getByLabelText('Ticker')
  await user.clear(input)
  await user.type(input, 'fake')
  await user.click(screen.getByRole('button', { name: 'Evaluate stock' }))
  expect(await screen.findByRole('heading', { name: 'Company not found' })).toBeInTheDocument()
  expect(screen.getByText(/no company was fabricated/i)).toBeInTheDocument()
  expect(screen.queryByText('Leidos Holdings, Inc.')).not.toBeInTheDocument()
})

test('an older slow response cannot overwrite a newer evaluation', async () => {
  const user = userEvent.setup()
  let releaseSbet: (() => void) | undefined
  const sbetWait = new Promise<void>((resolve) => { releaseSbet = resolve })
  server.use(http.post(`${API_BASE_URL}/api/v1/portfolio/plan`, async ({ request }) => {
    const body = await request.json() as PortfolioPlanRequest
    const target = body.tickers![0]!
    if (target === 'SBET') await sbetWait
    return HttpResponse.json(
      target === 'SBET'
        ? evaluationPlan('SBET', [candidate('SBET', 'Sharplink Inc')])
        : evaluationPlan('AAPL', [candidate('AAPL', 'Apple Inc.')]),
    )
  }))
  renderApp('/evaluate?ticker=SBET')
  await user.click(await screen.findByRole('button', { name: 'Evaluate stock' }))
  const input = screen.getByLabelText('Ticker')
  await user.clear(input)
  await user.type(input, 'AAPL{enter}')
  expect(await screen.findByRole('heading', { name: 'Apple Inc.' })).toBeInTheDocument()
  releaseSbet?.()
  await waitFor(() => expect(screen.getByRole('heading', { name: 'Apple Inc.' })).toBeInTheDocument())
  expect(screen.queryByRole('heading', { name: 'Sharplink Inc' })).not.toBeInTheDocument()
})

test.each(['STALE_DATA', 'NO_DATA', 'INSUFFICIENT_HISTORY'] as const)(
  '%s is shown as a deterministic data outcome',
  async (status) => {
    const user = userEvent.setup()
    server.use(http.post(`${API_BASE_URL}/api/v1/portfolio/plan`, () => HttpResponse.json({
      ...evaluationPlan('OLD', []),
      decisions: [],
      candidate_statuses: [{ ticker: 'OLD', company_id: ids.LDOS, status, data_as_of_date: '2026-08-19', signal: null, reason: status }],
    })))
    renderApp('/evaluate?ticker=OLD')
    await user.click(await screen.findByRole('button', { name: 'Evaluate stock' }))
    expect(await screen.findByRole('heading', { name: 'Evaluation unavailable' })).toBeInTheDocument()
    expect(screen.getByText('Aug 19, 2026')).toBeInTheDocument()
  },
)
