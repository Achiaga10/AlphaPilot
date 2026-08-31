import { mkdir } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright-core'

const url = process.env.ALPHAPILOT_FRONTEND_URL ?? 'http://127.0.0.1:5173'
const browserPath = process.env.ALPHAPILOT_BROWSER_PATH ?? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const output = resolve(dirname(fileURLToPath(import.meta.url)), '../../backend/backtest_reports/sprint21/daily-manager-smoke.png')
const portfolioId = '11111111-1111-4111-8111-111111111111'
let briefRequests = 0
let syncRequests = 0

const position = (ticker, status, extra = {}) => ({
  position_id: `${ticker.toLowerCase()}-position`, ticker, company_name: `${ticker} Company`, strategy: 'micho-150',
  strategy_profile_id: 'micho-150-v1', strategy_profile_version: 1, status, reason: `${status}_REASON`,
  explanation: `${ticker} deterministic ${status} guidance.`, quantity: 10, latest_completed_close: '100',
  unrealized_pnl: '50', unrealized_pnl_pct: '5', as_of_session: '2026-08-28', sticky_sell: false,
  exit_triggered_on: null, loss_control_policy: 'SMA150_COMPLETED_CLOSE_EXIT', loss_control_boundary: '95',
  loss_control_trigger: 'COMPLETED_DAILY_CLOSE_BELOW', broker_stop_order: false, references: [], ...extra,
})
const opportunity = (ticker, readiness, workflow = 'READY_FOR_REVIEW') => ({
  ticker, strategy: ticker === 'EMA' ? 'ema20-pullback' : 'micho-150',
  strategy_profile_id: ticker === 'EMA' ? 'ema20-pullback-v1' : 'micho-150-v1', strategy_profile_version: 1,
  source_plan_id: `${ticker}-plan`, portfolio_revision: 4, selection_policy: 'relative-strength-20',
  sizing_policy: 'atr-volatility-normalized', decision: 'BUY', decision_reason: 'BUY_APPROVED', ranking_score: '0.1',
  reference_price: '120', proposed_shares: 80, target_allocation_dollars: '9600', target_weight_pct: '9.6',
  sector: 'Industrials', execution_readiness: readiness,
  execution_readiness_reason: readiness === 'ACTIONABLE' ? 'LOSS_CONTROL_READY' : 'NO_APPROVED_LOSS_CONTROL_POLICY',
  loss_control_policy: readiness === 'ACTIONABLE' ? 'SMA150_COMPLETED_CLOSE_EXIT' : 'NONE',
  loss_control_boundary: readiness === 'ACTIONABLE' ? '108' : null,
  loss_control_trigger: readiness === 'ACTIONABLE' ? 'COMPLETED_DAILY_CLOSE_BELOW' : null,
  loss_control_distance_dollars: readiness === 'ACTIONABLE' ? '12' : null,
  loss_control_distance_pct: readiness === 'ACTIONABLE' ? '10' : null, broker_stop_order: false,
  strategy_references: [], analysis_as_of_date: '2026-08-28', action_id: `4:BUY:${ticker}`, workflow_status: workflow,
})
const brief = {
  portfolio_id: portfolioId, portfolio_revision: 4, generated_at: '2026-08-29T10:00:00Z',
  data_status: { readiness: 'READY', expected_completed_session: '2026-08-28', latest_synchronized_session: '2026-08-28', brief_session: '2026-08-28', sync_status: 'SUCCEEDED', explanation: 'Stored facts are aligned to the latest completed SPY session.' },
  workflow_status: 'WAITING_FOR_REQUIRED_EXITS',
  summary: { portfolio_value: '100000', cash: '30000', invested_market_value: '70000', cash_pct: '30', open_positions: 3, max_positions: 10, valuation_readiness: 'COMPLETE', modeled_risk_dollars: null },
  required_actions: [position('EXIT', 'SELL', { sticky_sell: true, exit_triggered_on: '2026-08-28' })],
  attention_positions: [position('ATTN', 'ATTENTION')], actionable_opportunities: [],
  research_only_opportunities: [opportunity('EMA', 'RESEARCH_ONLY')],
  deferred_opportunities: [opportunity('MCHO', 'ACTIONABLE', 'WAITING_FOR_REQUIRED_EXITS')],
  hold_positions: [position('HOLD', 'HOLD')], unavailable_positions: [], blockers: ['REQUIRED_EXITS_MUST_BE_RESOLVED_FIRST'],
}
const opportunities = {
  portfolio_id: portfolioId, portfolio_revision: 4, generated_at: '2026-08-29T10:00:00Z', analysis_as_of_date: '2026-08-28',
  workflow_status: brief.workflow_status, actionable_opportunities: brief.actionable_opportunities,
  research_only_opportunities: brief.research_only_opportunities, deferred_opportunities: brief.deferred_opportunities,
  actionable_total_count: brief.actionable_opportunities.length, research_only_total_count: 89,
  deferred_total_count: brief.deferred_opportunities.length, research_only_limit: 10,
}
const portfolio = {
  portfolio_id: portfolioId, stable_key: 'default', name: 'Research Portfolio', revision: 4, cash: '30000', realized_pnl: '0',
  total_cost_basis: '70000', positions_market_value: '70000', total_equity: '100000', cash_pct: '30', invested_pct: '70',
  total_unrealized_pnl: '0', latest_completed_trading_day: '2026-08-28', valuation_status: 'COMPLETE', positions: [],
}

await mkdir(dirname(output), { recursive: true })
const browser = await chromium.launch({ executablePath: browserPath, headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  await page.route('**/api/v1/**', async (route) => {
    const requestUrl = route.request().url()
    if (requestUrl.endsWith('/health/')) return route.fulfill({ json: { status: 'ok', application: 'AlphaPilot' } })
    if (requestUrl.endsWith('/admin/data/capability')) return route.fulfill({ json: { enabled: false, warning: 'disabled', market_data_provider: 'Alpaca', market_data_feed: 'iex' } })
    if (requestUrl.endsWith('/portfolio/current')) return route.fulfill({ json: portfolio })
    if (requestUrl.includes('/daily-brief/opportunities')) {
      briefRequests += 1
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 1200))
      return route.fulfill({ json: opportunities })
    }
    if (requestUrl.includes('/daily-brief')) { briefRequests += 1; return route.fulfill({ json: brief }) }
    if (requestUrl.includes('/sync')) { syncRequests += 1; return route.fulfill({ status: 500, body: 'unexpected sync' }) }
    if (requestUrl.includes('/ai/copilot/portfolio/') && requestUrl.endsWith('/query')) {
      const { question } = await route.request().postDataJSON()
      const emaQuestion = question.toLowerCase().includes('ema')
      return route.fulfill({ json: { answer: emaQuestion ? 'EMA is research-only because NO_APPROVED_LOSS_CONTROL_POLICY blocks actionable execution.' : 'EXIT requires action first. MCHO is deferred until the required exit is resolved; EMA is research-only.', scope: 'PORTFOLIO', portfolio_id: portfolioId, position_id: null, ticker: null, as_of_date: '2026-08-28', intent: 'DAILY_BRIEF', result_status: 'ANSWERED', resolution_status: 'RESOLVED', grounding_status: 'GROUNDED', fact_refs: [{ fact_id: 'daily.required', source: 'daily_portfolio_brief', field: 'required_actions', label: 'Required exits', value: 1 }], limitations: ['Read only'], provider: 'alphapilot', model: 'deterministic' } })
    }
    return route.fulfill({ status: 404, json: { detail: `Unhandled smoke route: ${requestUrl}` } })
  })
  await page.goto(url, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: 'Action Required' }).waitFor()
  await page.getByRole('heading', { name: /Scanning today.s opportunities/ }).waitFor()
  const actionY = (await page.getByRole('heading', { name: 'Action Required' }).boundingBox()).y
  const attentionY = (await page.getByRole('heading', { name: 'Attention' }).boundingBox()).y
  const opportunitiesY = (await page.getByRole('heading', { name: 'New Actionable Opportunities' }).boundingBox()).y
  if (!(actionY < attentionY && attentionY < opportunitiesY)) throw new Error('Workflow priority order is incorrect')
  await page.getByText('Loss-control boundary').first().waitFor()
  await page.getByText('NO_APPROVED_LOSS_CONTROL_POLICY').waitFor()
  await page.getByRole('heading', { name: 'Research-only Opportunities (89)' }).waitFor()
  await page.getByRole('button', { name: 'View all 89' }).waitFor()
  await page.getByText(/cash is unchanged/i).waitFor()
  const beforeRefresh = briefRequests
  await page.getByRole('button', { name: 'Refresh Daily Brief' }).click()
  await page.waitForTimeout(250)
  if (briefRequests <= beforeRefresh || syncRequests !== 0) throw new Error('Refresh did not remain read-only')
  await page.getByRole('button', { name: 'Ask AI' }).first().click()
  await page.getByLabel('Question').fill('What requires action today?')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await page.getByText(/EXIT requires action first/).waitFor()
  await page.getByLabel('Question').fill("Why isn't this EMA opportunity actionable?")
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await page.getByText(/NO_APPROVED_LOSS_CONTROL_POLICY blocks actionable execution/).waitFor()
  await page.screenshot({ path: output, fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload({ waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: 'Action Required' }).waitFor()
  console.log(`Sprint 21 Daily Portfolio Manager browser smoke passed: ${output}`)
} finally {
  await browser.close()
}
