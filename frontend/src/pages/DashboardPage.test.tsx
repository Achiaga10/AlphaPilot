import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { API_BASE_URL } from '../api/client'
import { dailyBriefFixture, dailyOpportunitiesFixture, liveBriefFixture, server } from '../test/server'
import { renderApp } from '../test/renderApp'

test('dashboard renders the daily portfolio manager in priority order', async () => {
  renderApp('/')
  expect(screen.getByRole('heading', { name: 'Daily Portfolio Manager' })).toBeInTheDocument()
  expect((await screen.findAllByText('Aug 28, 2026')).length).toBeGreaterThan(0)
  expect(screen.getByText('READY')).toBeInTheDocument()
  expect(screen.getByText('$100,000.00')).toBeInTheDocument()
  const action = screen.getByRole('heading', { name: 'Action Required' })
  const attention = screen.getByRole('heading', { name: 'Attention' })
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

test('dashboard distinguishes research-only and deferred actionable opportunities', async () => {
  renderApp('/')
  expect(await screen.findByText('RESEARCH ONLY')).toBeInTheDocument()
  expect(screen.getByText('NO_APPROVED_LOSS_CONTROL_POLICY')).toBeInTheDocument()
  expect(screen.getByText('SMA150_COMPLETED_CLOSE_EXIT')).toBeInTheDocument()
  expect(screen.getByText('COMPLETED_DAILY_CLOSE_BELOW')).toBeInTheDocument()
  expect(screen.getAllByText('No', { selector: 'dd' }).length).toBeGreaterThan(0)
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
    ...dailyOpportunitiesFixture.research_only_opportunities[0],
    ticker: `R${String(index + 1).padStart(2, '0')}`,
    ranking_score: String(1 - index / 100),
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
  expect(await screen.findByRole('heading', { name: 'Action Required' })).toBeInTheDocument()
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
  expect(await screen.findByRole('heading', { name: 'Action Required' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Hold / No Action' })).toBeInTheDocument()
  expect(await screen.findByRole('heading', { name: 'Positions remain current' })).toBeInTheDocument()
})
