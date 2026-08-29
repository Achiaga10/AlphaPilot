import { chromium } from 'playwright-core'

const frontendUrl = process.env.ALPHAPILOT_FRONTEND_URL ?? 'http://127.0.0.1:4173'
const edgePath = process.env.ALPHAPILOT_BROWSER_PATH
  ?? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const portfolioId = '11111111-1111-4111-8111-111111111111'
const positionId = '21111111-1111-4111-8111-111111111111'
const json = (route, body) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
let copilotCalls = 0

const browser = await chromium.launch({ executablePath: edgePath, headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/v1/health/') return json(route, { status: 'ok', application: 'AlphaPilot' })
    if (path === '/api/v1/portfolio/current') return json(route, { portfolio_id: portfolioId, stable_key: 'default', name: 'Research', revision: 0, cash: '50000', realized_pnl: '0', total_cost_basis: '1000', positions_market_value: '1100', total_equity: '51100', cash_pct: '97.84', invested_pct: '2.16', total_unrealized_pnl: '100', latest_completed_trading_day: '2026-08-28', valuation_status: 'COMPLETE', positions: [{ position_id: positionId, company_id: '31111111-1111-4111-8111-111111111111', ticker: 'AAPL', sector: 'Technology', status: 'OPEN', quantity: 10, average_cost: '100', cost_basis: '1000', entry_trading_day: '2026-01-02', entry_price: '100', strategy: 'ema20-pullback', strategy_profile_id: 'ema20-pullback-v1', strategy_profile_version: 1, selection_policy: 'relative-strength-20', provenance_status: 'PLAN_PROFILE', modeled_risk_dollars: '50', latest_completed_trading_day: '2026-08-28', latest_completed_close: '110', market_value: '1100', portfolio_weight_pct: '2.15', unrealized_pnl: '100', unrealized_pnl_pct: '10', valuation_status: 'VALUED' }] })
    if (path.endsWith('/monitoring')) return json(route, [])
    if (path.endsWith('/intelligence')) return json(route, { portfolio_id: portfolioId, portfolio_revision: 0, position_id: positionId, company_id: '31111111-1111-4111-8111-111111111111', ticker: 'AAPL', company_name: 'Apple', position_status: 'OPEN', provenance_status: 'PLAN_PROFILE', quantity: 10, entry_trading_day: '2026-01-02', entry_price: '100', average_cost: '100', cost_basis: '1000', strategy_guidance_available: true, guidance_unavailable_reason: null, strategy: 'ema20-pullback', strategy_profile_id: 'ema20-pullback-v1', strategy_profile_version: 1, strategy_profile_snapshot: {}, selection_policy: 'relative-strength-20', entry_decision: 'BUY', entry_reason: 'BUY_APPROVED', latest_completed_trading_day: '2026-08-28', latest_completed_close: '110', market_value: '1100', unrealized_pnl: '100', unrealized_pnl_pct: '10', realized_pnl: '0', monitoring_readiness: 'READY', monitoring_status: 'HOLD', monitoring_reason: 'EMA20_HELD', monitoring_completed_trading_day: '2026-08-28', indicator_facts: { ema20: '20.10', ema50: '19.16' }, previous_monitoring_status: null, latest_monitoring_transition: null, exit_triggered: false, exit_triggered_on: null, exit_trigger_reason: null, active_exit_policy: 'HYBRID exit with frozen 2% threshold', protective_stop_policy: 'NONE', trailing_stop_policy: 'NONE', profit_target_policy: 'NONE', research_only_stop_candidate: 'Static 3 × ATR14', research_only_stop_status: 'NOT_ACTIVE', price_change_since_entry: '10', explanation: 'EMA20 is still held.', trade_event_count: 1, reconciliation_event_count: 0 })
    if (path.endsWith('/paper-validations')) return json(route, [])
    if (path.endsWith('/ask')) { copilotCalls += 1; return json(route, { answer: 'There is no active protective stop. EMA50 at $19.16 is the hard strategy-exit reference and requires a completed daily close. EMA20 at $20.10 is conditional under HYBRID 2%. Neither is a broker stop order.', scope: 'POSITION', portfolio_id: portfolioId, position_id: positionId, ticker: 'AAPL', as_of_date: '2026-08-28', grounding_status: 'GROUNDED', fact_refs: [{ fact_id: 'guidance.protective_stop', source: 'stop_exit_guidance', field: 'protective_stop', label: 'Active protective stop', value: 'NONE' }, { fact_id: 'guidance.reference.0', source: 'stop_exit_guidance', field: 'references', label: 'EMA50_HARD_BREAKDOWN', value: { value: '19.16', condition: 'COMPLETED_DAILY_CLOSE_BELOW' } }, { fact_id: 'guidance.reference.1', source: 'stop_exit_guidance', field: 'references', label: 'EMA20_CONDITIONAL_BREAKDOWN', value: { value: '20.10', condition: 'COMPLETED_DAILY_CLOSE_BELOW_CONDITIONAL' } }], limitations: ['Explanatory research only; no broker order or portfolio mutation.'], provider: 'fake', model: 'controlled' }) }
    return json(route, { detail: `Unhandled controlled route ${path}` })
  })
  await page.goto(`${frontendUrl}/portfolio`, { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: 'Why this position?' }).click()
  await page.getByLabel('Question for AAPL').fill('What is my stop?')
  await page.getByRole('button', { name: 'Ask AlphaPilot AI' }).click()
  await page.getByRole('heading', { name: 'Based on AlphaPilot data' }).waitFor()
  const text = await page.locator('body').innerText()
  for (const expected of ['NONE', 'EMA50_HARD_BREAKDOWN', '19.16', 'EMA20_CONDITIONAL_BREAKDOWN', '20.10', 'completed session']) {
    if (!text.includes(expected)) throw new Error(`Missing controlled evidence: ${expected}`)
  }
  if (text.includes('Stop Loss')) throw new Error('Strategy reference was mislabeled Stop Loss')
  if (copilotCalls !== 1) throw new Error(`Expected one Copilot request, received ${copilotCalls}`)
  process.stdout.write(JSON.stringify({ ticker: 'AAPL', copilotCalls, activeProtectiveStop: 'NONE', ema50: '19.16', ema20: '20.10', completedCloseSemantics: true, brokerCalls: 0, result: 'PASS' }))
} finally {
  await browser.close()
}
