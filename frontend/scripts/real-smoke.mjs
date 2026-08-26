import { mkdir } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright-core'

const frontendUrl = process.env.ALPHAPILOT_FRONTEND_URL ?? 'http://127.0.0.1:5173'
const edgePath = process.env.ALPHAPILOT_BROWSER_PATH ?? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const scriptDirectory = dirname(fileURLToPath(import.meta.url))
const screenshotPath = resolve(scriptDirectory, '../../backend/backtest_reports/sprint11d/ui-smoke.png')

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

function summary(portfolio) {
  const values = portfolio.positions.map((position) => Number(position.reference_price) * position.shares)
  const invested = values.reduce((total, value) => total + value, 0)
  const cash = Number(portfolio.cash)
  const equity = cash + invested
  return {
    equity: String(equity), cash: String(cash), cash_pct: equity ? String(cash / equity * 100) : '0',
    invested_value: String(invested), invested_pct: equity ? String(invested / equity * 100) : '0',
    open_positions: portfolio.positions.length,
    positions: portfolio.positions.map((position, index) => ({
      ...position, cost_basis: position.cost_basis ?? null, sector: position.sector ?? null,
      modeled_risk_dollars: position.modeled_risk_dollars ?? '0', market_value: String(values[index]),
      portfolio_weight_pct: equity ? String(values[index] / equity * 100) : '0',
    })),
  }
}

function buy(ticker, price, shares, order, dependencies) {
  const outlay = Number(price) * shares
  return {
    ticker, signal: 'BUY', decision: 'BUY', reason: 'BUY_APPROVED', ranking_score: String(0.1 - order / 100),
    reference_price: String(price), atr: '4', stop_distance: '8', risk_budget_dollars: '1000',
    target_allocation_dollars: String(outlay), target_weight_pct: '1', proposed_shares: shares,
    modeled_position_risk_dollars: '200', sector: 'Information Technology', sector_weight_before_pct: '0',
    sector_weight_after_pct: '1', current_shares: 0, estimated_proceeds: null,
    normalized_sizing_weight: null, estimated_cash_outlay: String(outlay), cash_after_decision: String(30000 - order * 1000),
    modeled_stop_reference_price: String(Number(price) - 8), action_id: `${order}:BUY:${ticker}`,
    application_order: order, depends_on_action_ids: dependencies,
  }
}

function controlledPlan(request) {
  const decisions = [
    buy('NVDA', 100, 10, 1, []),
    buy('AMD', 50, 20, 2, ['1:BUY:NVDA']),
    buy('AAPL', 200, 5, 3, ['1:BUY:NVDA', '2:BUY:AMD']),
  ]
  return {
    plan_id: 'controlled-sprint11d-plan',
    portfolio: {
      ...summary(request.portfolio), cash_reserve_requirement: '0', current_portfolio_risk: '0',
      current_portfolio_risk_pct: '0', available_portfolio_risk: '8000', available_portfolio_risk_pct: '8',
      modeled_risk_complete: true,
    },
    config: request.risk_config, strategy: request.strategy, selection_policy: request.selection_policy,
    sizing_policy: request.sizing_policy, requested_as_of_date: request.as_of_date,
    analysis_as_of_date: '2026-08-25', decisions,
    candidate_statuses: decisions.map((decision, index) => ({
      ticker: decision.ticker, status: 'READY', data_as_of_date: '2026-08-25', signal: 'BUY',
      reason: 'EMA20_PULLBACK_RECLAIM', company_name: decision.ticker, sector: decision.sector,
      ranking_score: decision.ranking_score, atr: decision.atr, decision: 'BUY', decision_reason: 'BUY_APPROVED',
      candidate_rank: index + 1, is_custom_tracked: false,
    })),
    readiness: {
      status: 'READY', requested_tickers: 3, evaluated_tickers: 3, fresh_tickers: 3,
      stale_tickers: 0, no_data_tickers: 0, insufficient_history_tickers: 0,
      company_not_found_tickers: 0, buy_signals: 3, approved_buys: 3, approved_sells: 0,
      actionable_decisions: 3, latest_ticker_data_date: '2026-08-25', buy_rejections_by_reason: {},
    },
  }
}

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
}

async function installControlledPortfolio(page) {
  await page.route('**/api/v1/portfolio/state-summary', async (route) => {
    await fulfillJson(route, summary(route.request().postDataJSON()))
  })
  await page.route('**/api/v1/portfolio/plan', async (route) => {
    await fulfillJson(route, controlledPlan(route.request().postDataJSON()))
  })
  await page.route('**/api/v1/portfolio/apply-action', async (route) => {
    const body = route.request().postDataJSON()
    const decision = body.decision
    const portfolio = structuredClone(body.portfolio)
    const missing = decision.depends_on_action_ids.some((id) => !body.applied_action_ids.includes(id))
    if (missing) {
      await fulfillJson(route, { plan_id: body.plan_id, applied: false, reason: 'PRIOR_ACTION_REQUIRED', action_id: decision.action_id, action_type: decision.decision, cash_before: portfolio.cash, cash_impact: '0', cash_after: portfolio.cash, position_before: null, position_after: null, portfolio, summary: summary(portfolio) })
      return
    }
    const cashBefore = Number(portfolio.cash)
    portfolio.cash = String(cashBefore - Number(decision.estimated_cash_outlay))
    const position = { ticker: decision.ticker, shares: decision.proposed_shares, reference_price: decision.reference_price, cost_basis: decision.reference_price, sector: decision.sector, modeled_risk_dollars: decision.modeled_position_risk_dollars }
    portfolio.positions.push(position)
    await fulfillJson(route, { plan_id: body.plan_id, applied: true, reason: 'APPLIED', action_id: decision.action_id, action_type: 'BUY', cash_before: String(cashBefore), cash_impact: `-${decision.estimated_cash_outlay}`, cash_after: portfolio.cash, position_before: null, position_after: position, portfolio, summary: summary(portfolio) })
  })
  await page.route('**/api/v1/portfolio/latest-price/JNJ', (route) => fulfillJson(route, { ticker: 'JNJ', price: '150', price_date: '2026-08-25', source: 'LATEST_STORED_CANDLE' }))
  for (const suffix of ['manual-sell/preview', 'manual-sell']) {
    await page.route(`**/api/v1/portfolio/${suffix}`, async (route) => {
      const body = route.request().postDataJSON()
      const apply = !suffix.endsWith('preview')
      const portfolio = structuredClone(body.portfolio)
      const position = portfolio.positions.find((item) => item.ticker === body.ticker)
      const price = body.execution_price ?? '150'
      const remaining = position.shares - body.shares_to_sell
      const cashBefore = Number(portfolio.cash)
      const proceeds = Number(price) * body.shares_to_sell
      if (apply) {
        portfolio.cash = String(cashBefore + proceeds)
        portfolio.positions = remaining === 0
          ? portfolio.positions.filter((item) => item.ticker !== body.ticker)
          : portfolio.positions.map((item) => item.ticker === body.ticker ? { ...item, shares: remaining } : item)
      }
      await fulfillJson(route, {
        applied: apply, reason: apply ? 'APPLIED' : 'READY', ticker: body.ticker,
        shares_sold: body.shares_to_sell, shares_remaining: remaining, execution_price: String(price),
        price_source: body.execution_price ? 'USER_PROVIDED' : 'LATEST_STORED_CANDLE',
        price_date: body.execution_price ? null : '2026-08-25', gross_proceeds: String(proceeds),
        cash_before: String(cashBefore), cash_after: String(cashBefore + proceeds), position_removed: remaining === 0,
        portfolio, summary: summary(portfolio),
      })
    })
  }
}

await mkdir(dirname(screenshotPath), { recursive: true })
const browser = await chromium.launch({ executablePath: edgePath, headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  await page.addInitScript(() => window.localStorage.clear())
  await installControlledPortfolio(page)
  const networkUrls = []
  page.on('request', (request) => networkUrls.push(request.url()))
  page.on('dialog', (dialog) => dialog.accept())
  await page.goto(`${frontendUrl}/portfolio`, { waitUntil: 'networkidle' })
  await page.getByText('Backend connected').waitFor()

  const logoFacts = await page.getByRole('img', { name: 'AlphaPilot' }).evaluate((image) => ({
    naturalWidth: image.naturalWidth, naturalHeight: image.naturalHeight,
    width: image.getBoundingClientRect().width, height: image.getBoundingClientRect().height,
    objectFit: getComputedStyle(image).objectFit,
  }))
  assert(logoFacts.naturalWidth === 1024 && logoFacts.naturalHeight === 1024, 'Official logo dimensions changed')
  assert(Math.abs(logoFacts.width - logoFacts.height) < 1 && logoFacts.objectFit === 'contain', 'Logo is distorted')

  await page.getByLabel('Cash (USD)').fill('30000')
  await page.getByRole('button', { name: 'Add position' }).click()
  const held = page.getByRole('group', { name: 'Position 1' })
  await held.getByLabel('Ticker').fill('JNJ')
  await held.getByLabel('Shares').fill('200')
  await held.getByLabel('Reference price').fill('150')
  await page.getByRole('button', { name: 'Generate Portfolio Plan' }).click()
  await page.getByRole('heading', { name: 'Analysis data ready' }).waitFor()

  const cashSequence = []
  for (const expectedCash of ['29000', '28000', '27000']) {
    await page.getByRole('button', { name: 'Add to Portfolio' }).click()
    await page.getByText(/was added to the research portfolio/).waitFor()
    cashSequence.push(await page.getByLabel('Cash (USD)').inputValue())
    assert(cashSequence.at(-1) === expectedCash, `Unexpected cash after ordered action: ${cashSequence.at(-1)}`)
  }
  assert((await page.getByRole('button', { name: 'Applied' }).count()) === 3, 'Applied actions were not locked against duplicates')
  assert((await page.getByText('Displayed plan is stale').count()) === 0, 'Exact same-plan actions incorrectly invalidated plan')

  await page.getByRole('link', { name: 'Dashboard' }).click()
  for (const ticker of ['NVDA', 'AMD', 'AAPL']) await page.getByRole('img', { name: new RegExp(`^${ticker}:`) }).waitFor()
  await page.getByRole('img', { name: /Cash: \$27,000\.00/ }).waitFor()

  await page.getByRole('link', { name: 'Portfolio plan' }).click()
  await page.getByLabel('Cash (USD)').fill('27001')
  await page.getByText('Displayed plan is stale').waitFor()
  await page.getByRole('button', { name: 'Regenerate plan' }).click()
  await page.getByRole('heading', { name: 'Analysis data ready' }).waitFor()
  await page.getByRole('link', { name: 'Dashboard' }).click()

  const jnjRow = page.locator('.research-portfolio-panel table tbody tr').filter({ hasText: 'JNJ' })
  await jnjRow.getByRole('button', { name: 'Sell Position' }).click()
  const defaultShares = await page.getByLabel('Shares to sell').inputValue()
  const defaultPrice = await page.getByLabel('Execution price').inputValue()
  const storedDateShown = await page.getByText('Aug 25, 2026').first().isVisible()
  assert(defaultShares === '200' && defaultPrice === '150' && storedDateShown, 'Manual sale defaults are incorrect')
  await page.getByLabel('Shares to sell').fill('40')
  await page.getByRole('button', { name: 'Review Sale' }).click()
  await page.getByRole('button', { name: 'Update Research Portfolio' }).click()
  await page.getByRole('img', { name: /^JNJ: \$24,000\.00/ }).waitFor()
  await page.getByText('Displayed plan is stale').waitFor()

  await jnjRow.getByRole('button', { name: 'Sell Position' }).click()
  await page.getByLabel('Shares to sell').fill('160')
  await page.getByRole('button', { name: 'Review Sale' }).click()
  await page.getByRole('button', { name: 'Update Research Portfolio' }).click()
  await page.getByRole('img', { name: /Cash: \$57,001\.00/ }).waitFor()
  assert((await jnjRow.count()) === 0, 'Full sale did not remove JNJ')
  await page.screenshot({ path: screenshotPath, fullPage: true })

  const brokerLikeRequests = networkUrls.filter((url) => /broker|orders?|trades?/i.test(new URL(url).pathname))
  assert(brokerLikeRequests.length === 0, `Unexpected broker/order request: ${brokerLikeRequests.join(', ')}`)

  const admin = await browser.newPage({ viewport: { width: 1280, height: 900 } })
  let polls = 0
  const progress = (attempted, state) => ({
    job_id: 'controlled-sync', state, requested_at: '2026-08-26T01:00:00Z', started_at: '2026-08-26T01:00:01Z',
    finished_at: state === 'SUCCEEDED' ? '2026-08-26T01:01:00Z' : null, start_date: '2025-01-01', end_date: '2026-08-26',
    operation: 'MARKET_CANDLES_SYNC', provider: 'Alpaca', feed: 'iex', active_constituents: 502,
    companies_created: 0, companies_updated: 0, companies_unchanged: 0, memberships_added: 0, memberships_removed: 0,
    failed_stage: null, failed_ticker: null, error_code: null, error: null,
    progress: { total: 503, attempted, synced: attempted, skipped: 0, failed: 0, failed_tickers: [], stage: state === 'SUCCEEDED' ? 'complete' : 'stock_candles', current_ticker: state === 'SUCCEEDED' ? null : 'MSFT' },
  })
  await admin.route('**/api/v1/admin/data/capability', (route) => fulfillJson(route, { enabled: true, warning: 'enabled', market_data_provider: 'Alpaca', market_data_feed: 'iex' }))
  await admin.route('**/api/v1/admin/data/summary', (route) => fulfillJson(route, { active_company_count: 505, active_sp500_count: 502, active_custom_tracked_count: 2, latest_spy_date: '2026-08-25', earliest_active_stock_latest_date: '2026-08-25', latest_active_stock_latest_date: '2026-08-25', fresh_tracked_ticker_count: 504, stale_tracked_ticker_count: 0, no_data_tracked_ticker_count: 0, latest_sync_job: null, last_universe_sync_at: null, last_candle_sync_at: '2026-08-26T01:01:00Z', market_data_provider: 'Alpaca', market_data_feed: 'iex' }))
  await admin.route('**/api/v1/admin/data/custom-tickers', (route) => fulfillJson(route, []))
  await admin.route('**/api/v1/admin/data/sync/candles', (route) => fulfillJson(route, { started: true, job: progress(0, 'RUNNING') }))
  await admin.route('**/api/v1/admin/data/sync/jobs/controlled-sync', (route) => fulfillJson(route, progress(++polls >= 2 ? 503 : 250, polls >= 2 ? 'SUCCEEDED' : 'RUNNING')))
  await admin.goto(`${frontendUrl}/admin/data`, { waitUntil: 'networkidle' })
  await admin.getByRole('button', { name: 'Sync Market Candles' }).click()
  const bar = admin.getByRole('progressbar', { name: 'MARKET CANDLES SYNC progress' })
  await bar.waitFor()
  await admin.getByText('Completed.').waitFor({ timeout: 20_000 })
  assert(await bar.getAttribute('aria-valuenow') === '503', 'Controlled sync did not reach 100 percent')
  await admin.close()

  process.stdout.write(`${JSON.stringify({
    logoFacts, cashSequence, appliedActions: 3, dashboardReactive: true,
    manualPartialAndFull: true, planStaleAfterManualChange: true,
    noBrokerOrderRequest: true, controlledSyncComplete: true, screenshotPath,
  }, null, 2)}\n`)
} finally {
  await browser.close()
}
