import { mkdir } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright-core'

const url = process.env.ALPHAPILOT_FRONTEND_URL ?? 'http://127.0.0.1:5173'
const browserPath = process.env.ALPHAPILOT_BROWSER_PATH ?? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const output = resolve(dirname(fileURLToPath(import.meta.url)), '../../backend/backtest_reports/sprint20/ui-copilot-smoke.png')
const portfolio = {
  portfolio_id: '11111111-1111-4111-8111-111111111111', stable_key: 'default', name: 'Research Portfolio', revision: 1,
  cash: '90000', realized_pnl: '0', total_cost_basis: '10000', positions_market_value: '11000', total_equity: '101000',
  cash_pct: '89.1', invested_pct: '10.9', total_unrealized_pnl: '1000', latest_completed_trading_day: '2026-08-20', valuation_status: 'COMPLETE',
  positions: [{ position_id: '22222222-2222-4222-8222-222222222222', company_id: '33333333-3333-4333-8333-333333333333', ticker: 'AAPL', sector: 'Information Technology', status: 'OPEN', quantity: 10, average_cost: '1000', cost_basis: '10000', entry_trading_day: '2026-01-02', entry_price: '1000', strategy: 'ema20-pullback', strategy_profile_id: 'ema20-pullback-v1', strategy_profile_version: 1, selection_policy: 'relative-strength-20', provenance_status: 'PLAN_PROFILE', modeled_risk_dollars: '0', latest_completed_trading_day: '2026-08-20', latest_completed_close: '1100', market_value: '11000', portfolio_weight_pct: '10.89', unrealized_pnl: '1000', unrealized_pnl_pct: '10', valuation_status: 'VALUED' }],
}

await mkdir(dirname(output), { recursive: true })
const browser = await chromium.launch({ executablePath: browserPath, headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
  await page.route('**/api/v1/health/', (route) => route.fulfill({ json: { status: 'ok', application: 'AlphaPilot' } }))
  await page.route('**/api/v1/admin/data/capability', (route) => route.fulfill({ json: { enabled: false, warning: 'disabled', market_data_provider: 'Alpaca', market_data_feed: 'iex' } }))
  await page.route('**/api/v1/portfolio/current', (route) => route.fulfill({ json: portfolio }))
  await page.route('**/api/v1/ai/copilot/general/ask', async (route) => {
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 150))
    await route.fulfill({ json: { answer: 'Open Data Management from the left sidebar to run market-data synchronization and review freshness.', scope: 'GENERAL', portfolio_id: null, position_id: null, ticker: null, as_of_date: null, grounding_status: 'GROUNDED', fact_refs: [{ fact_id: 'navigation.data-management', source: 'product_navigation', field: 'navigation', label: 'Data Management', value: { route: '/admin/data' } }], limitations: ['Read only'], provider: 'fake', model: 'smoke' } })
  })
  await page.route('**/api/v1/ai/copilot/portfolio/**/positions/**/ask', (route) => route.fulfill({ json: { answer: 'There is no active protective stop for AAPL. EMA50 is a completed-daily-close reference.', scope: 'POSITION', portfolio_id: portfolio.portfolio_id, position_id: portfolio.positions[0].position_id, ticker: 'AAPL', as_of_date: '2026-08-20', grounding_status: 'GROUNDED', fact_refs: [{ fact_id: 'guidance.protective_stop', source: 'stop_exit_guidance', field: 'protective_stop', label: 'Active protective stop', value: 'NONE' }], limitations: ['Research only'], provider: 'fake', model: 'smoke' } }))
  await page.goto(url, { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Ask AI' }).click()
  await page.getByLabel('Question').fill('Where do I update market data?')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await page.getByLabel('AlphaPilot AI is preparing a response').waitFor()
  await page.getByText(/Open Data Management/).waitFor()
  await page.getByLabel('Copilot context').selectOption(`POSITION:${portfolio.positions[0].position_id}`)
  await page.getByLabel('Question for AAPL').fill('מה הסטופ של AAPL?')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  const answer = page.getByText(/There is no active protective stop/)
  await answer.waitFor()
  if (await answer.locator('xpath=ancestor::article').getAttribute('dir') !== 'ltr') throw new Error('English answer was not LTR')
  await page.screenshot({ path: output, fullPage: true })
  console.log(`Sprint 20 Copilot browser smoke passed: ${output}`)
} finally {
  await browser.close()
}
