import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { API_BASE_URL } from '../api/client'
import { dailyBriefFixture, dailyOpportunitiesFixture, liveBriefFixture, server } from '../test/server'
import { renderApp } from '../test/renderApp'

test('dashboard explains the Micho and EMA20 News advisory rule', async () => {
  renderApp('/')
  expect(await screen.findByText(/For Micho and EMA20 Pullback, all News is advisory only, including hard events/)).toBeInTheDocument()
})

test('dashboard renders the daily portfolio manager in priority order', async () => {
  renderApp('/')
  expect(screen.getByRole('heading', { name: 'Daily Portfolio Manager' })).toBeInTheDocument()
  expect((await screen.findAllByText('Aug 28, 2026')).length).toBeGreaterThan(0)
  expect(screen.getByText('READY')).toBeInTheDocument()
  expect(screen.getByText('$100,000.00')).toBeInTheDocument()
  const action = screen.getByRole('heading', { name: 'Required Exits' })
  const attention = screen.getByRole('heading', { name: 'Needs Attention' })
  const hold = screen.getByRole('heading', { name: 'Hold / No Action' })
  expect(action.compareDocumentPosition(attention) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  expect(attention.compareDocumentPosition(hold) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  expect(screen.getByText('SMA150_BREAKDOWN')).toBeInTheDocument()
  expect(screen.getByText('EMA20_LOST_STRONG_TREND_HOLD')).toBeInTheDocument()
  expect(screen.getByText('EMA20_HELD')).toBeInTheDocument()
  expect(await screen.findByText('Backend connected')).toBeInTheDocument()
  expect(screen.getByText(/not live-trading validated/i)).toBeInTheDocument()
})

test('backend unavailable is distinguished from a domain empty state', async () => {
  server.use(http.get(`${API_BASE_URL}/api/v1/health/`, () => HttpResponse.error()))
  renderApp('/')
  expect(await screen.findByText('Backend unavailable')).toBeInTheDocument()
  expect(await screen.findByRole('heading', { name: 'Daily Portfolio Manager' })).toBeInTheDocument()
})

test('News Intelligence renders persisted classification provenance and refreshes holdings only', async () => {
  const user = userEvent.setup()
  let refreshRequests = 0
  server.use(http.post(
    `${API_BASE_URL}/api/v1/portfolio/:portfolioId/news-refresh`,
    ({ params }) => {
      refreshRequests += 1
      return HttpResponse.json({ portfolio_id: String(params.portfolioId), tickers: ['APA'], fetched: 1, inserted: 0, duplicates: 1, classified: 0, classification_failures: 0, provider_failures: [], refreshed_at: '2026-09-01T10:00:00Z', scope: 'OPEN_POSITIONS', coverage: [['APA', 'CURRENT']], aggregate_requested: ['APA'], aggregate_returned: ['APA'], aggregate_reused: [], aggregate_missing: [], aggregate_api_calls: 1, aggregate_observations_persisted: 1, attributable_requested: ['APA'], attributable_api_calls: 1, targeted_classification_attempts: 0 })
    },
  ))
  renderApp('/')
  expect(await screen.findByRole('heading', { name: 'News Intelligence' })).toBeInTheDocument()
  const newsSummary = await screen.findByText((_, element) => element?.tagName === 'SUMMARY' && Boolean(element.textContent?.includes('APA · POSITIVE CONTEXT')))
  await user.click(newsSummary)
  expect(await screen.findByText('APA updates full-year guidance')).toBeInTheDocument()
  expect(screen.getByText(/Gemini:/).parentElement).toHaveTextContent(/NEGATIVE · HIGH · GUIDANCE/)
  expect(screen.getByText(/cannot issue BUY or SELL/i)).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Adanos aggregate context' })).toBeInTheDocument()
  expect(screen.getByText(/SUFFICIENT/)).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Refresh open holdings' }))
  expect(refreshRequests).toBe(1)
  expect(await screen.findByText(/APA CURRENT/)).toBeInTheDocument()
  expect(screen.getByText(/Stored articles do not imply current or complete coverage/)).toBeInTheDocument()
})

test('navigation reaches every required route', async () => {
  const user = userEvent.setup()
  renderApp('/')
  await user.click(screen.getByRole('link', { name: 'Portfolio plan' }))
  expect(await screen.findByRole('heading', { name: 'Portfolio Plan', level: 1 })).toBeInTheDocument()
  await user.click(screen.getByRole('link', { name: 'Evaluate stock' }))
  expect(await screen.findByRole('heading', { name: 'Evaluate Stock' })).toBeInTheDocument()
  await user.click(screen.getByRole('link', { name: 'Research settings' }))
  expect(await screen.findByRole('heading', { name: 'Research Settings' })).toBeInTheDocument()
})

test('dashboard shows approved EMA20 BUY with mandatory manual-stop warning', async () => {
  renderApp('/')
  const approvedBadge = await screen.findByText('APPROVED BUY')
  const approvedCard = approvedBadge.closest('article')
  if (!approvedCard) throw new Error('Expected the approved EMA20 opportunity card')
  expect(within(approvedCard).getByText('MANUAL STOP REQUIRED.')).toBeInTheDocument()
  expect(within(approvedCard).getAllByText(/No system stop/).length).toBeGreaterThan(0)
  await userEvent.click(within(approvedCard).getByText('View details'))
  expect(within(approvedCard).getByText('USER_MANUAL')).toBeInTheDocument()
  expect(within(approvedCard).getByText('MANUAL_STOP_REQUIRED')).toBeInTheDocument()
  const sellPolicy = screen.getByText('SMA150_COMPLETED_CLOSE_EXIT')
  const sellCard = sellPolicy.closest('article')
  if (!sellCard) throw new Error('Expected the required-exit card')
  await userEvent.click(within(sellCard).getByText('View details'))
  expect(screen.getByText('COMPLETED_DAILY_CLOSE_BELOW')).toBeInTheDocument()
  expect(screen.getByText(/Resolve required exits before relying/)).toBeInTheDocument()
})

test('refresh loads open-position live intelligence and refetches the daily brief without syncing', async () => {
  const user = userEvent.setup()
  let briefRequests = 0
  let liveRequests = 0
  let syncRequests = 0
  server.use(
    http.get(`${API_BASE_URL}/api/v1/portfolio/:portfolioId/daily-brief`, () => {
      briefRequests += 1
      return HttpResponse.json(dailyBriefFixture)
    }),
    http.post(`${API_BASE_URL}/api/v1/admin/data/sync`, () => {
      syncRequests += 1
      return HttpResponse.json({})
    }),
    http.post(`${API_BASE_URL}/api/v1/portfolio/:portfolioId/live-refresh`, () => {
      liveRequests += 1
      return HttpResponse.json(liveBriefFixture)
    }),
  )
  renderApp('/')
  await user.click(await screen.findByRole('button', { name: 'Refresh Market & Brief' }))
  expect(briefRequests).toBeGreaterThanOrEqual(2)
  expect(liveRequests).toBe(1)
  expect(syncRequests).toBe(0)
  expect(await screen.findByRole('heading', { name: 'Live Market Monitor' })).toBeInTheDocument()
  expect(screen.getByText('CRITICAL ATTENTION')).toBeInTheDocument()
  expect(screen.getByText('Completed EMA20')).toBeInTheDocument()
  expect(screen.getByText('$41.25')).toBeInTheDocument()
  expect(screen.getByText('Provisional EMA20')).toBeInTheDocument()
  expect(screen.getByText('$41.11')).toBeInTheDocument()
  expect(screen.getByText((_, element) => element?.textContent?.includes('If session closed now: SELL') ?? false, { selector: 'p' })).toBeInTheDocument()
  expect(screen.getByText((_, element) => element?.textContent?.includes('Confirmed completed-session SELL: NO') ?? false, { selector: 'p' })).toBeInTheDocument()
})

test('core positions render while opportunity discovery loads and shortlist is bounded', async () => {
  let release: (() => void) | undefined
  const pending = new Promise<void>((resolve) => { release = resolve })
  const ranked = Array.from({ length: 89 }, (_, index) => ({
    ...dailyOpportunitiesFixture.actionable_opportunities[0],
    ticker: `R${String(index + 1).padStart(2, '0')}`,
    ranking_score: String(1 - index / 100),
    execution_readiness: 'RESEARCH_ONLY',
    execution_readiness_reason: 'NO_APPROVED_LOSS_CONTROL_POLICY',
    loss_control_source: 'NONE',
    manual_stop_required: false,
  }))
  server.use(http.get(
    `${API_BASE_URL}/api/v1/portfolio/:portfolioId/daily-brief/opportunities`,
    async ({ request }) => {
      await pending
      const limit = Number(new URL(request.url).searchParams.get('research_only_limit'))
      return HttpResponse.json({
        ...dailyOpportunitiesFixture,
        research_only_opportunities: ranked.slice(0, limit),
        research_only_total_count: 89,
        research_only_limit: limit,
      })
    },
  ))
  renderApp('/')
  expect(await screen.findByRole('heading', { name: 'Required Exits' })).toBeInTheDocument()
  expect(screen.getByText('SMA150_BREAKDOWN')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: /Scanning today.s opportunities/ })).toBeInTheDocument()
  release?.()
  expect(await screen.findByRole('heading', { name: 'Research-only Opportunities (89)' })).toBeInTheDocument()
  expect(screen.getAllByText('RESEARCH ONLY')).toHaveLength(10)
  expect(screen.getByRole('button', { name: 'View all 89' })).toBeInTheDocument()
  expect(screen.getByText('R01')).toBeInTheDocument()
  expect(screen.getByText('R10')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'View all 89' }))
  expect(await screen.findByText('R89')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'View all 89' })).not.toBeInTheDocument()
})

test('opportunity failure does not erase existing position management', async () => {
  server.use(http.get(
    `${API_BASE_URL}/api/v1/portfolio/:portfolioId/daily-brief/opportunities`,
    () => HttpResponse.error(),
  ))
  renderApp('/')
  expect(await screen.findByRole('heading', { name: 'Required Exits' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Hold / No Action' })).toBeInTheDocument()
  expect(await screen.findByRole('heading', { name: 'Positions remain current' })).toBeInTheDocument()
})
