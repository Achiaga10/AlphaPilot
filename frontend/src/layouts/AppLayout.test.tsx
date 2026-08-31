import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { beforeEach, vi } from 'vitest'
import { API_BASE_URL } from '../api/client'
import { OPEN_COPILOT_EVENT } from '../features/copilot/FloatingCopilot'
import { renderApp } from '../test/renderApp'
import { server } from '../test/server'

const scrollTo = vi.fn()
Object.defineProperty(HTMLElement.prototype, 'scrollTo', { configurable: true, value: scrollTo })

beforeEach(() => scrollTo.mockClear())

test('sidebar uses the real AlphaPilot image and removes placeholder branding', async () => {
  renderApp('/')
  const logo = screen.getByRole('img', { name: 'AlphaPilot' })
  expect(logo).toHaveAttribute('src', expect.stringContaining('alphapilot-logo.png'))
  expect(logo).toHaveClass('brand__logo')
  expect(document.querySelector('.brand__mark')).not.toBeInTheDocument()
  expect(screen.getByText('Daily Portfolio Manager', { selector: '.brand__subtitle' })).toBeInTheDocument()
  expect(await screen.findByText('Backend connected')).toBeInTheDocument()
})

test('unified Copilot opens globally without a visible context selector', async () => {
  const user = userEvent.setup()
  renderApp('/')
  await user.click(screen.getByRole('button', { name: 'Ask AI' }))
  expect(screen.queryByLabelText('Copilot context')).not.toBeInTheDocument()
  expect(screen.getByLabelText('Question')).toBeEnabled()
  expect(screen.queryByText(/Currently discussing:/)).not.toBeInTheDocument()
  await user.type(screen.getByLabelText('Question'), 'Where do I sync market data?')
  await user.click(screen.getByRole('button', { name: 'Send' }))
  expect(await screen.findByText(/Open Data Management/)).toBeInTheDocument()
  expect(screen.getByText('General · You')).toBeInTheDocument()
})

test('explicit FAST resolves automatically and keeps factual answer deterministic', async () => {
  const user = userEvent.setup()
  renderApp('/')
  await user.click(screen.getByRole('button', { name: 'Ask AI' }))
  await user.type(screen.getByLabelText('Question'), 'How many shares do I own? FAST')
  await user.click(screen.getByRole('button', { name: 'Send' }))
  expect(await screen.findByText('You own 101 shares of FAST.')).toBeInTheDocument()
  expect(screen.getByText('Currently discussing: FAST')).toBeInTheDocument()
  expect(screen.getByText('FAST · You')).toBeInTheDocument()
  expect(screen.getByText('FAST · AlphaPilot AI')).toBeInTheDocument()
})

test('clarification accepts APA alone, follow-up reuses APA, and natural switch changes only future attribution', async () => {
  const requests: Array<{ question: string; active_ticker: string | null; pending_intent: string | null }> = []
  server.use(http.post(`${API_BASE_URL}/api/v1/ai/copilot/portfolio/:portfolioId/query`, async ({ params, request }) => {
    const body = await request.json() as { question: string; active_ticker: string | null; pending_intent: string | null }
    requests.push(body)
    const normalized = body.question.toLowerCase()
    const base = { portfolio_id: String(params.portfolioId), as_of_date: '2026-08-20', grounding_status: 'GROUNDED', limitations: [], provider: 'alphapilot', model: 'deterministic-test', result_status: 'ANSWERED', resolution_status: 'RESOLVED' }
    if (normalized === 'how many shares do i own?') return HttpResponse.json({ ...base, answer: 'Which ticker do you mean?', scope: 'POSITION', position_id: null, ticker: null, intent: 'QUANTITY', result_status: 'CLARIFICATION_REQUIRED', resolution_status: 'CLARIFICATION_REQUIRED', grounding_status: 'LIMITED', fact_refs: [] })
    if (normalized === 'apa') return HttpResponse.json({ ...base, answer: 'You own 235 shares of APA.', scope: 'POSITION', position_id: 'apa-position', ticker: 'APA', intent: 'QUANTITY', fact_refs: [] })
    if (normalized.includes('what about fast')) return HttpResponse.json({ ...base, answer: "I'll use FAST for your next position question.", scope: 'POSITION', position_id: 'fast-position', ticker: 'FAST', intent: 'GENERAL', result_status: 'ENTITY_ESTABLISHED', resolution_status: 'ENTITY_ESTABLISHED', grounding_status: 'LIMITED', fact_refs: [] })
    const ticker = body.active_ticker
    return HttpResponse.json({ ...base, answer: `Your average cost for ${ticker} is ${ticker === 'APA' ? '$42.38' : '$65.20'} per share.`, scope: 'POSITION', position_id: `${ticker?.toLowerCase()}-position`, ticker, intent: 'AVERAGE_COST', fact_refs: [] })
  }))
  const user = userEvent.setup()
  renderApp('/')
  await user.click(screen.getByRole('button', { name: 'Ask AI' }))
  const composer = screen.getByLabelText('Question')
  await user.type(composer, 'How many shares do I own?')
  await user.click(screen.getByRole('button', { name: 'Send' }))
  expect(await screen.findByText('Which ticker do you mean?')).toBeInTheDocument()
  await waitFor(() => expect(composer).toBeEnabled())
  await user.type(composer, 'APA')
  await user.click(screen.getByRole('button', { name: 'Send' }))
  await waitFor(() => expect(requests).toHaveLength(2))
  expect(requests[1]?.question).toBe('APA')
  expect(requests[1]?.pending_intent).toBe('QUANTITY')
  expect(await screen.findByText('You own 235 shares of APA.')).toBeInTheDocument()
  await waitFor(() => expect(composer).toBeEnabled())
  await user.type(composer, 'What is my average cost?')
  await user.click(screen.getByRole('button', { name: 'Send' }))
  expect(await screen.findByText('Your average cost for APA is $42.38 per share.')).toBeInTheDocument()
  await waitFor(() => expect(composer).toBeEnabled())
  await user.type(composer, 'What about FAST?')
  await user.click(screen.getByRole('button', { name: 'Send' }))
  expect(await screen.findByText("I'll use FAST for your next position question.")).toBeInTheDocument()
  await waitFor(() => expect(composer).toBeEnabled())
  await user.type(composer, 'What is my average cost?')
  await user.click(screen.getByRole('button', { name: 'Send' }))
  expect(await screen.findByText('Your average cost for FAST is $65.20 per share.')).toBeInTheDocument()
  expect(screen.getAllByText('APA · AlphaPilot AI').length).toBeGreaterThan(0)
  expect(screen.getAllByText('FAST · AlphaPilot AI').length).toBeGreaterThan(0)
})

test('Why this position handoff seeds ticker without creating a visible mode selector', async () => {
  renderApp('/')
  await screen.findByText('Backend connected')
  window.dispatchEvent(new CustomEvent(OPEN_COPILOT_EVENT, { detail: { positionId: '21111111-1111-4111-8111-111111111110' } }))
  expect(await screen.findByText('Currently discussing: MSFT')).toBeInTheDocument()
  expect(screen.queryByLabelText('Copilot context')).not.toBeInTheDocument()
})

test('provider failure retains the question, retries, and auto-scrolls the inner history', async () => {
  let attempts = 0
  server.use(http.post(`${API_BASE_URL}/api/v1/ai/copilot/portfolio/:portfolioId/query`, ({ params }) => {
    attempts += 1
    if (attempts === 1) return HttpResponse.json({ detail: { code: 'AI_PROVIDER_UNAVAILABLE' } }, { status: 503 })
    return HttpResponse.json({ answer: 'Open Data Management.', scope: 'GENERAL', portfolio_id: String(params.portfolioId), position_id: null, ticker: null, as_of_date: null, grounding_status: 'GROUNDED', fact_refs: [{ fact_id: 'navigation.data', source: 'product_navigation', field: 'navigation', label: 'Data Management', value: { route: '/admin/data' } }], limitations: [], provider: 'fake', model: 'test', result_status: 'ANSWERED', intent: 'NAVIGATION', resolution_status: 'RESOLVED' })
  }))
  const user = userEvent.setup()
  renderApp('/')
  await user.click(screen.getByRole('button', { name: 'Ask AI' }))
  await user.type(screen.getByLabelText('Question'), 'Why is AlphaPilot unavailable?')
  await user.click(screen.getByRole('button', { name: 'Send' }))
  expect(await screen.findByText(/Check the local Ollama service/)).toBeInTheDocument()
  expect(screen.getAllByText('Why is AlphaPilot unavailable?')).toHaveLength(1)
  await user.click(screen.getByRole('button', { name: 'Retry' }))
  expect(await screen.findByText('Open Data Management.')).toBeInTheDocument()
  expect(screen.getAllByText('Why is AlphaPilot unavailable?')).toHaveLength(1)
  expect(scrollTo).toHaveBeenCalled()
  expect(scrollTo.mock.instances.every((item) => item === screen.getByLabelText('Copilot message history'))).toBe(true)
})

test('auto-scroll runs for user send, typing, deterministic response, clarification, and error', async () => {
  server.use(http.post(`${API_BASE_URL}/api/v1/ai/copilot/portfolio/:portfolioId/query`, async ({ params }) => {
    await delay(100)
    return HttpResponse.json({ answer: 'Which ticker do you mean?', scope: 'POSITION', portfolio_id: String(params.portfolioId), position_id: null, ticker: null, as_of_date: null, grounding_status: 'LIMITED', fact_refs: [], limitations: [], provider: 'alphapilot', model: 'deterministic-test', result_status: 'CLARIFICATION_REQUIRED', intent: 'QUANTITY', resolution_status: 'CLARIFICATION_REQUIRED' })
  }))
  const user = userEvent.setup()
  renderApp('/')
  await user.click(screen.getByRole('button', { name: 'Ask AI' }))
  scrollTo.mockClear()
  await user.type(screen.getByLabelText('Question'), 'How many shares do I own?')
  await user.click(screen.getByRole('button', { name: 'Send' }))
  expect(screen.getByLabelText('AlphaPilot AI is preparing a response')).toBeInTheDocument()
  expect(await screen.findByText('Which ticker do you mean?')).toBeInTheDocument()
  await waitFor(() => expect(scrollTo.mock.calls.length).toBeGreaterThanOrEqual(2))
})

test('invalid provider response remains distinct from controlled unavailable fact', async () => {
  server.use(http.post(`${API_BASE_URL}/api/v1/ai/copilot/portfolio/:portfolioId/query`, () => HttpResponse.json({ detail: { code: 'AI_RESPONSE_INVALID' } }, { status: 502 })))
  const user = userEvent.setup()
  renderApp('/')
  await user.click(screen.getByRole('button', { name: 'Ask AI' }))
  await user.type(screen.getByLabelText('Question'), 'Explain AlphaPilot')
  await user.click(screen.getByRole('button', { name: 'Send' }))
  expect(await screen.findByText('AlphaPilot received an invalid AI response. Please retry.')).toBeInTheDocument()
})

test('admin navigation is hidden when the safe feature gate is disabled', async () => {
  renderApp('/')
  await screen.findByText('Backend connected')
  expect(screen.queryByRole('link', { name: 'Research admin' })).not.toBeInTheDocument()
})
