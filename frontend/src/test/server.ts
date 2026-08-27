import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { API_BASE_URL } from '../api/client'
import { planFixture, riskConfigFixture, strategyProfilesFixture } from './fixtures'

interface TestPosition {
  ticker: string
  shares: number
  reference_price: string
  cost_basis?: string | null
  sector?: string | null
  modeled_risk_dollars?: string
}

function summarize(portfolio: { cash: string; positions: TestPosition[] }) {
  const cash = Number(portfolio.cash) || 0
  const values = portfolio.positions.map((position) => Number(position.reference_price) * position.shares)
  const invested = values.reduce((total, value) => total + value, 0)
  const equity = cash + invested
  return {
    equity: String(equity), cash: String(cash), cash_pct: equity ? String(cash / equity * 100) : '0',
    invested_value: String(invested), invested_pct: equity ? String(invested / equity * 100) : '0',
    open_positions: portfolio.positions.length,
    positions: portfolio.positions.map((position, index) => ({
      ...position, ticker: position.ticker.toUpperCase(), market_value: String(values[index] ?? 0),
      portfolio_weight_pct: equity ? String((values[index] ?? 0) / equity * 100) : '0',
      cost_basis: position.cost_basis ?? null, sector: position.sector ?? null,
      modeled_risk_dollars: position.modeled_risk_dollars ?? '0',
    })),
  }
}

export const handlers = [
  http.get(`${API_BASE_URL}/api/v1/health/`, () => HttpResponse.json({ status: 'ok', application: 'AlphaPilot' })),
  http.get(`${API_BASE_URL}/api/v1/portfolio/risk-config`, () => HttpResponse.json(riskConfigFixture)),
  http.get(`${API_BASE_URL}/api/v1/portfolio/strategy-profiles`, () => HttpResponse.json(strategyProfilesFixture)),
  http.get(`${API_BASE_URL}/api/v1/admin/data/capability`, () => HttpResponse.json({ enabled: false, warning: 'Research admin tools are disabled by configuration.', market_data_provider: 'Alpaca', market_data_feed: 'iex' })),
  http.get(`${API_BASE_URL}/api/v1/admin/data/summary`, () => HttpResponse.json({ active_company_count: 503, active_sp500_count: 502, active_custom_tracked_count: 0, latest_spy_date: '2026-08-20', earliest_active_stock_latest_date: '2026-08-19', latest_active_stock_latest_date: '2026-08-20', fresh_tracked_ticker_count: 501, stale_tracked_ticker_count: 1, no_data_tracked_ticker_count: 0, latest_sync_job: null, last_universe_sync_at: null, last_candle_sync_at: null, market_data_provider: 'Alpaca', market_data_feed: 'iex' })),
  http.get(`${API_BASE_URL}/api/v1/admin/data/custom-tickers`, () => HttpResponse.json([])),
  http.post(`${API_BASE_URL}/api/v1/portfolio/state-summary`, async ({ request }) => {
    const portfolio = await request.json() as { cash: string; positions: TestPosition[] }
    return HttpResponse.json(summarize(portfolio))
  }),
  http.post(`${API_BASE_URL}/api/v1/portfolio/preview-action`, async ({ request }) => actionResponse(request, false)),
  http.post(`${API_BASE_URL}/api/v1/portfolio/apply-action`, async ({ request }) => actionResponse(request, true)),
  http.get(`${API_BASE_URL}/api/v1/portfolio/latest-price/:ticker`, ({ params }) => HttpResponse.json({ ticker: String(params.ticker), price: '150', price_date: '2026-08-20' })),
  http.post(`${API_BASE_URL}/api/v1/portfolio/manual-sell/preview`, async ({ request }) => manualSellResponse(request, false)),
  http.post(`${API_BASE_URL}/api/v1/portfolio/manual-sell`, async ({ request }) => manualSellResponse(request, true)),
  http.post(`${API_BASE_URL}/api/v1/portfolio/plan`, () => HttpResponse.json(planFixture)),
]

async function actionResponse(request: Request, apply: boolean) {
    const body = await request.json() as { portfolio: { cash: string; positions: TestPosition[] }; decision: typeof planFixture.decisions[number]; applied_action_ids: string[]; requested_shares: number | null }
    const { decision } = body
    if (decision.action_id === null || body.applied_action_ids.includes(decision.action_id)) {
      return HttpResponse.json({ applied: false, reason: 'ALREADY_APPLIED', action_id: decision.action_id, portfolio: body.portfolio, summary: summarize(body.portfolio) })
    }
    const portfolio = structuredClone(body.portfolio)
    const requestedShares = body.requested_shares ?? decision.proposed_shares
    const requestedAllocation = requestedShares * Number(decision.reference_price)
    const cashBefore = Number(portfolio.cash)
    if (decision.decision === 'BUY') {
      portfolio.cash = String(cashBefore - requestedAllocation)
      portfolio.positions.push({ ticker: decision.ticker, shares: requestedShares, reference_price: decision.reference_price, cost_basis: decision.reference_price, sector: decision.sector, modeled_risk_dollars: '0' })
    } else {
      portfolio.cash = String(Number(portfolio.cash) + Number(decision.estimated_proceeds))
      portfolio.positions = portfolio.positions.filter((position) => position.ticker !== decision.ticker)
    }
    const equity = cashBefore + body.portfolio.positions.reduce((total, item) => total + item.shares * Number(item.reference_price), 0)
    const semantics = requestedShares === decision.proposed_shares ? 'SAME_PLAN_ACTION' : 'USER_QUANTITY_OVERRIDE'
    return HttpResponse.json({
      plan_id: 'test-plan', applied: apply, reason: apply ? 'APPLIED' : 'READY', validation_status: 'VALID',
      quantity_semantics: semantics, action_id: decision.action_id, action_type: decision.decision,
      cash_before: String(cashBefore), cash_impact: String(-requestedAllocation), cash_after: portfolio.cash,
      position_before: null, position_after: decision.decision === 'BUY' ? portfolio.positions.at(-1) : null,
      portfolio: apply ? portfolio : body.portfolio, summary: summarize(apply ? portfolio : body.portfolio),
      recommended_shares: decision.proposed_shares, requested_shares: requestedShares,
      recommended_allocation_dollars: decision.target_allocation_dollars,
      requested_allocation_dollars: String(requestedAllocation), resulting_position_weight_pct: String(requestedAllocation / equity * 100),
      sector_weight_before_pct: '0', sector_weight_after_pct: String(requestedAllocation / equity * 100),
      modeled_position_risk_dollars: null, portfolio_risk_after_dollars: null, cash_reserve_requirement: null,
    })
}

async function manualSellResponse(request: Request, apply: boolean) {
  const body = await request.json() as { portfolio: { cash: string; positions: TestPosition[] }; ticker: string; shares_to_sell: number; execution_price: string | null }
  const position = body.portfolio.positions.find((item) => item.ticker === body.ticker)
  const price = body.execution_price ?? '150'
  const remaining = (position?.shares ?? 0) - body.shares_to_sell
  const portfolio = structuredClone(body.portfolio)
  if (apply && position) {
    portfolio.cash = String(Number(portfolio.cash) + body.shares_to_sell * Number(price))
    portfolio.positions = remaining === 0
      ? portfolio.positions.filter((item) => item.ticker !== body.ticker)
      : portfolio.positions.map((item) => item.ticker === body.ticker ? { ...item, shares: remaining } : item)
  }
  return HttpResponse.json({ applied: apply && Boolean(position), reason: position ? 'READY' : 'POSITION_NOT_HELD', ticker: body.ticker, shares_sold: body.shares_to_sell, shares_remaining: remaining, execution_price: price, price_source: body.execution_price ? 'USER_PROVIDED' : 'LATEST_STORED_CANDLE', price_date: body.execution_price ? null : '2026-08-20', gross_proceeds: String(body.shares_to_sell * Number(price)), portfolio, summary: summarize(portfolio) })
}

export const server = setupServer(...handlers)
