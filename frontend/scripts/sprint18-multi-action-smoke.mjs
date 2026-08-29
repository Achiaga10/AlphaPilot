import { chromium } from 'playwright-core'

const frontendUrl = process.env.ALPHAPILOT_FRONTEND_URL ?? 'http://127.0.0.1:5173'
const edgePath = process.env.ALPHAPILOT_BROWSER_PATH
  ?? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const portfolioId = '11111111-1111-4111-8111-111111111111'
const config = { risk_per_position_pct: '1', atr_period: 14, atr_stop_multiple: '2', max_position_weight_pct: '10', max_portfolio_risk_pct: '8', minimum_cash_reserve_pct: '10', max_sector_weight_pct: '30', max_positions: 10 }
const profile = { profile_id: 'ema20-pullback-v1', version: 1, strategy: 'ema20-pullback', display_name: 'EMA20 Pullback', classification: 'PROMISING_RESEARCH_BASELINE', entry_description: 'Existing EMA20 Pullback reclaim entry', recommended_selection_policy: 'relative-strength-20', allowed_selection_policies: ['relative-strength-20', 'ticker-ascending'], sizing_policy: 'equal-slot', strategy_exit_description: 'HYBRID exit with frozen 2% threshold', ema_exit_mode: 'hybrid', hybrid_trend_threshold_pct: '2', micho_entry_mode: null, protective_stop_default: 'NONE', profit_management_default: 'NONE', research_only_stop_candidate: 'Static 3 × ATR14' }
const decision = (ticker, order) => ({ ticker, signal: 'BUY', decision: 'BUY', reason: 'BUY_APPROVED', ranking_score: String(1 - order / 10), reference_price: '100', atr: '4', stop_distance: '8', risk_budget_dollars: '1000', target_allocation_dollars: '10000', target_weight_pct: '10', proposed_shares: 100, modeled_position_risk_dollars: '0', sector: order === 1 ? 'Technology' : 'Industrials', sector_weight_before_pct: '0', sector_weight_after_pct: '10', current_shares: 0, estimated_proceeds: null, normalized_sizing_weight: null, estimated_cash_outlay: '10000', cash_after_decision: String(100000 - order * 10000), modeled_stop_reference_price: '92', action_id: `${order}:BUY:${ticker}`, application_order: order, depends_on_action_ids: [], exit_context: null })
const decisions = [decision('AAPL', 1), decision('MSFT', 2)]
const status = (item, rank) => ({ ticker: item.ticker, status: 'READY', data_as_of_date: '2026-08-20', signal: 'BUY', reason: 'EMA20_PULLBACK_RECLAIM', company_name: item.ticker, company_id: `${rank}1111111-1111-4111-8111-111111111111`, sector: item.sector, ranking_score: item.ranking_score, atr: item.atr, decision: 'BUY', decision_reason: 'BUY_APPROVED', candidate_rank: rank, is_custom_tracked: false })

let revision = 0
let cash = 100000
const applied = []
const previewRevisions = []
const current = () => ({ portfolio_id: portfolioId, stable_key: 'default', name: 'AlphaPilot Research Portfolio', revision, cash: String(cash), realized_pnl: '0', total_cost_basis: '0', positions_market_value: '0', total_equity: String(cash), cash_pct: '100', invested_pct: '0', total_unrealized_pnl: '0', latest_completed_trading_day: null, valuation_status: 'COMPLETE', positions: [] })
const plan = { plan_id: 'controlled-multi-action', portfolio_id: portfolioId, portfolio_revision: 0, portfolio: { equity: '100000', cash: '100000', cash_pct: '100', invested_value: '0', invested_pct: '0', cash_reserve_requirement: '0', current_portfolio_risk: '0', current_portfolio_risk_pct: '0', available_portfolio_risk: '8000', available_portfolio_risk_pct: '8', modeled_risk_complete: true, open_positions: 0, positions: [] }, config, strategy: 'ema20-pullback', selection_policy: 'relative-strength-20', sizing_policy: 'equal-slot', strategy_profile: profile, requested_as_of_date: '2026-08-20', analysis_as_of_date: '2026-08-20', evaluation_target_ticker: null, decisions, candidate_statuses: decisions.map(status), readiness: { status: 'READY', requested_tickers: 2, evaluated_tickers: 2, fresh_tickers: 2, stale_tickers: 0, no_data_tickers: 0, insufficient_history_tickers: 0, company_not_found_tickers: 0, buy_signals: 2, approved_buys: 2, approved_sells: 0, actionable_decisions: 2, latest_ticker_data_date: '2026-08-20', buy_rejections_by_reason: {} } }

const json = (route, body, statusCode = 200) => route.fulfill({ status: statusCode, contentType: 'application/json', body: JSON.stringify(body) })
const actionResult = (body, apply) => {
  if (body.portfolio_revision !== revision) return null
  const shares = body.requested_shares ?? body.decision.proposed_shares
  const allocation = shares * Number(body.decision.reference_price)
  const cashBefore = cash
  if (apply) { cash -= allocation; revision += 1; applied.push(body.decision.action_id) }
  return { plan_id: body.plan_id, applied: apply, reason: apply ? 'APPLIED' : 'READY', action_id: body.decision.action_id, action_type: 'BUY', cash_before: String(cashBefore), cash_impact: String(-allocation), cash_after: String(cashBefore - allocation), position_before: null, position_after: null, portfolio: { cash: String(cash), positions: [] }, summary: { equity: String(cash), cash: String(cash), cash_pct: '100', invested_value: '0', invested_pct: '0', open_positions: revision, positions: [] }, validation_status: 'VALID', quantity_semantics: 'SAME_PLAN_ACTION', recommended_shares: shares, requested_shares: shares, recommended_allocation_dollars: String(allocation), requested_allocation_dollars: String(allocation), resulting_position_weight_pct: '10', sector_weight_before_pct: '0', sector_weight_after_pct: '10', modeled_position_risk_dollars: null, portfolio_risk_after_dollars: null, cash_reserve_requirement: null, portfolio_id: portfolioId, portfolio_revision: revision }
}

const browser = await chromium.launch({ executablePath: edgePath, headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (path === '/api/v1/health/') return json(route, { status: 'ok', application: 'AlphaPilot' })
    if (path === '/api/v1/portfolio/risk-config') return json(route, config)
    if (path === '/api/v1/portfolio/strategy-profiles') return json(route, [profile])
    if (path === '/api/v1/portfolio/current') return json(route, current())
    if (path.endsWith('/monitoring')) return json(route, [])
    if (path === '/api/v1/admin/data/capability') return json(route, { enabled: false, warning: 'disabled', market_data_provider: 'Alpaca', market_data_feed: 'iex' })
    if (path === '/api/v1/portfolio/plan') return json(route, plan)
    if (path.endsWith('/preview-action')) {
      const body = request.postDataJSON()
      previewRevisions.push(body.portfolio_revision)
      const result = actionResult(body, false)
      return result ? json(route, result) : json(route, { detail: 'stale' }, 409)
    }
    if (path.endsWith('/apply-action')) {
      const result = actionResult(request.postDataJSON(), true)
      return result ? json(route, result) : json(route, { detail: 'stale' }, 409)
    }
    return json(route, { detail: `Unhandled controlled route ${path}` }, 404)
  })
  await page.goto(`${frontendUrl}/portfolio`, { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: 'Generate Portfolio Plan' }).click()
  for (let index = 0; index < 2; index += 1) {
    await page.getByRole('button', { name: 'Review Add' }).first().click()
    await page.getByRole('button', { name: 'Add to Research Portfolio' }).click()
    await page.getByRole('button', { name: 'Applied' }).nth(index).waitFor()
    if (await page.getByText('Displayed plan is stale').count()) throw new Error('Plan was incorrectly forced stale')
  }
  if (previewRevisions.join(',') !== '0,1') throw new Error(`Wrong preview revisions: ${previewRevisions}`)
  if (revision !== 2 || applied.length !== 2) throw new Error('Two actions were not applied')
  process.stdout.write(JSON.stringify({ sequentialActions: applied, previewRevisions, finalRevision: revision, fullRegenerationRequired: false, result: 'PASS' }))
} finally {
  await browser.close()
}
