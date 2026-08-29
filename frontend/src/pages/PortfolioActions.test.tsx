import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { API_BASE_URL } from '../api/client'
import type { PortfolioDecision } from '../types/portfolio'
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
  expect(await screen.findByText(/Remaining candidates will be freshly revalidated/)).toBeInTheDocument()
  expect(screen.queryByText('Displayed plan is stale')).not.toBeInTheDocument()
})

test('two BUYs from one plan apply sequentially through fresh current revisions', async () => {
  const user = userEvent.setup()
  let revision = 0
  const seenPreviewRevisions: number[] = []
  const secondBuy = {
    ...planFixture.decisions[0]!,
    ticker: 'AMD',
    action_id: '3:BUY:AMD',
    application_order: 3,
    reference_price: '100',
    proposed_shares: 50,
    target_allocation_dollars: '5000',
    estimated_cash_outlay: '5000',
  }
  const multiPlan = {
    ...planFixture,
    decisions: [planFixture.decisions[0]!, secondBuy],
    candidate_statuses: [
      planFixture.candidate_statuses[0]!,
      { ...planFixture.candidate_statuses[0]!, ticker: 'AMD', candidate_rank: 2 },
    ],
  }
  const current = () => ({
    portfolio_id: planFixture.portfolio_id,
    stable_key: 'default',
    name: 'AlphaPilot Research Portfolio',
    revision,
    cash: String(30000 - revision * 5000),
    realized_pnl: '0',
    total_cost_basis: '0',
    positions_market_value: '0',
    total_equity: String(30000 - revision * 5000),
    cash_pct: '100',
    invested_pct: '0',
    total_unrealized_pnl: '0',
    latest_completed_trading_day: null,
    valuation_status: 'COMPLETE',
    positions: [],
  })
  type ActionBody = {
    plan_id: string
    portfolio_revision: number
    requested_shares: number | null
    decision: PortfolioDecision
  }
  const actionResult = (body: ActionBody, apply: boolean) => {
    if (apply) revision += 1
    const shares = body.requested_shares ?? body.decision.proposed_shares
    const allocation = Number(shares) * Number(body.decision.reference_price)
    return {
      plan_id: body.plan_id, applied: apply, reason: apply ? 'APPLIED' : 'READY',
      action_id: body.decision.action_id, action_type: 'BUY', cash_before: current().cash,
      cash_impact: String(-allocation), cash_after: String(Number(current().cash) - allocation),
      position_before: null, position_after: null, portfolio: { cash: current().cash, positions: [] },
      summary: { equity: current().total_equity, cash: current().cash, cash_pct: '100', invested_value: '0', invested_pct: '0', open_positions: revision, positions: [] },
      validation_status: 'VALID', quantity_semantics: 'SAME_PLAN_ACTION',
      recommended_shares: shares, requested_shares: shares,
      recommended_allocation_dollars: String(allocation), requested_allocation_dollars: String(allocation),
      resulting_position_weight_pct: '10', sector_weight_before_pct: '0', sector_weight_after_pct: '10',
      modeled_position_risk_dollars: null, portfolio_risk_after_dollars: null,
      cash_reserve_requirement: null, portfolio_id: planFixture.portfolio_id, portfolio_revision: revision,
    }
  }
  server.use(
    http.get(`${API_BASE_URL}/api/v1/portfolio/current`, () => HttpResponse.json(current())),
    http.post(`${API_BASE_URL}/api/v1/portfolio/plan`, () => HttpResponse.json(multiPlan)),
    http.post(`${API_BASE_URL}/api/v1/portfolio/preview-action`, async ({ request }) => {
      const body = await request.json() as ActionBody
      seenPreviewRevisions.push(body.portfolio_revision)
      return HttpResponse.json(actionResult(body, false))
    }),
    http.post(`${API_BASE_URL}/api/v1/portfolio/apply-action`, async ({ request }) => {
      const body = await request.json() as ActionBody
      return HttpResponse.json(actionResult(body, true))
    }),
  )

  renderApp('/portfolio')
  await user.click(await screen.findByRole('button', { name: 'Generate Portfolio Plan' }))
  await user.click((await screen.findAllByRole('button', { name: 'Review Add' }))[0]!)
  await user.click(await screen.findByRole('button', { name: 'Add to Research Portfolio' }))
  await waitFor(() => expect(screen.getAllByRole('button', { name: 'Applied' })).toHaveLength(1))
  expect(screen.queryByText('Displayed plan is stale')).not.toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Review Add' }))
  await user.click(await screen.findByRole('button', { name: 'Add to Research Portfolio' }))
  await waitFor(() => expect(screen.getAllByRole('button', { name: 'Applied' })).toHaveLength(2))
  expect(seenPreviewRevisions).toEqual([0, 1])
  expect(revision).toBe(2)
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
