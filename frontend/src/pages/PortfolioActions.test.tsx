import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { API_BASE_URL } from '../api/client'
import { planFixture } from '../test/fixtures'
import { renderApp } from '../test/renderApp'
import { server } from '../test/server'

test('normal plan and BUY action use persistent portfolio identity and revision', async () => {
  const user = userEvent.setup()
  let planBody: Record<string, unknown> | null = null
  let actionBody: Record<string, unknown> | null = null
  server.use(
    http.post(`${API_BASE_URL}/api/v1/portfolio/plan`, async ({ request }) => {
      planBody = await request.json() as Record<string, unknown>
      return HttpResponse.json(planFixture)
    }),
    http.post(`${API_BASE_URL}/api/v1/portfolio/apply-action`, async ({ request }) => {
      actionBody = await request.json() as Record<string, unknown>
      return HttpResponse.json({
        plan_id: planFixture.plan_id, applied: true, reason: 'APPLIED', action_id: '1:BUY:NVDA', action_type: 'BUY',
        cash_before: '30000', cash_impact: '-9900', cash_after: '20100', position_before: null, position_after: null,
        portfolio: { cash: '20100', positions: [] }, summary: { equity: '100000', cash: '20100', cash_pct: '20.1', invested_value: '79900', invested_pct: '79.9', open_positions: 3, positions: [] },
        validation_status: 'VALID', quantity_semantics: 'SAME_PLAN_ACTION', recommended_shares: 55, requested_shares: 55,
        recommended_allocation_dollars: '9900', requested_allocation_dollars: '9900', resulting_position_weight_pct: '9.9',
        sector_weight_before_pct: '20', sector_weight_after_pct: '29.9', modeled_position_risk_dollars: null,
        portfolio_risk_after_dollars: null, cash_reserve_requirement: null, portfolio_id: planFixture.portfolio_id, portfolio_revision: 1,
      })
    }),
  )
  renderApp('/portfolio')
  await user.click(await screen.findByRole('button', { name: 'Generate Portfolio Plan' }))
  await user.click(await screen.findByRole('button', { name: 'Review Add' }))
  await user.click(await screen.findByRole('button', { name: 'Add to Research Portfolio' }))
  expect(planBody).toMatchObject({ portfolio_id: planFixture.portfolio_id })
  expect(planBody).not.toHaveProperty('portfolio')
  expect(actionBody).toMatchObject({ portfolio_id: planFixture.portfolio_id, portfolio_revision: 0 })
  expect(actionBody).not.toHaveProperty('portfolio')
  expect(await screen.findByText('Displayed plan is stale')).toBeInTheDocument()
})

test('existing backend portfolio wins over legacy local financial state', async () => {
  window.localStorage.setItem('alphapilot.plan-draft.v1', JSON.stringify({ cash: '1', positions: [{ ticker: 'FAKE', shares: 999, reference_price: '999' }] }))
  renderApp('/')
  expect((await screen.findAllByText('$30,000.00')).length).toBeGreaterThan(0)
  expect(screen.queryByText('FAKE')).not.toBeInTheDocument()
})

test('legacy browser portfolio is imported only when no backend portfolio exists', async () => {
  window.localStorage.setItem('alphapilot.plan-draft.v1', JSON.stringify({ cash: '7500', positions: [{ ticker: 'MSFT', shares: 2, reference_price: '350', cost_basis: '300' }], strategy: 'micho-150' }))
  let initialization: Record<string, unknown> | null = null
  server.use(
    http.get(`${API_BASE_URL}/api/v1/portfolio/current`, () => HttpResponse.json(null)),
    http.post(`${API_BASE_URL}/api/v1/portfolio/initialize`, async ({ request }) => {
      initialization = await request.json() as Record<string, unknown>
      return HttpResponse.json({ portfolio_id: planFixture.portfolio_id, stable_key: 'default', name: 'AlphaPilot Research Portfolio', revision: 1, cash: '7500', realized_pnl: '0', total_cost_basis: '600', positions_market_value: null, total_equity: null, cash_pct: null, invested_pct: null, total_unrealized_pnl: null, latest_completed_trading_day: null, valuation_status: 'UNAVAILABLE', positions: [] })
    }),
  )
  renderApp('/portfolio')
  await waitFor(() => expect(initialization).not.toBeNull())
  expect(initialization).toMatchObject({ starting_cash: '7500', imported_positions: [{ ticker: 'MSFT', quantity: 2, average_cost: '300' }] })
  expect(JSON.parse(window.localStorage.getItem('alphapilot.plan-draft.v1') ?? '{}')).not.toHaveProperty('cash')
})

test('malformed persistent portfolio responses fail safely', async () => {
  server.use(http.get(`${API_BASE_URL}/api/v1/portfolio/current`, () => HttpResponse.json({ portfolio_id: 'broken', revision: 0, cash: '100' })))
  renderApp('/portfolio')
  expect(await screen.findByRole('alert')).toHaveTextContent('invalid response')
  expect(screen.queryByRole('button', { name: 'Generate Portfolio Plan' })).not.toBeInTheDocument()
})
