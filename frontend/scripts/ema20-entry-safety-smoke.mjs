import { mkdir } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright-core'

const frontendUrl = process.env.ALPHAPILOT_FRONTEND_URL ?? 'http://127.0.0.1:5174'
const backendUrl = process.env.ALPHAPILOT_BACKEND_URL ?? 'http://127.0.0.1:8010'
const edgePath = process.env.ALPHAPILOT_BROWSER_PATH ?? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const screenshotPath = resolve(dirname(fileURLToPath(import.meta.url)), '../../backend/backtest_reports/ema20_entry_safety/browser-acceptance.png')
const assert = (condition, message) => { if (!condition) throw new Error(message) }

await mkdir(dirname(screenshotPath), { recursive: true })
const browser = await chromium.launch({ executablePath: edgePath, headless: true, args: ['--disable-web-security'] })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } })
  const health = await page.request.get(`${backendUrl}/api/v1/health/`)
  assert(health.ok(), 'Real FastAPI health endpoint unavailable')
  const currentResponse = await page.request.get(`${backendUrl}/api/v1/portfolio/current`)
  assert(currentResponse.ok(), 'Real current portfolio endpoint unavailable')
  const current = await currentResponse.json()
  assert(current?.portfolio_id, 'Current portfolio missing')
  const paperResponse = await page.request.get(`${backendUrl}/api/v1/portfolio/${current.portfolio_id}/paper-analytics`)
  assert(paperResponse.ok(), 'Real Paper Analytics endpoint unavailable')
  const paper = await paperResponse.json()
  const signature = (portfolio, analytics) => JSON.stringify({
    revision: portfolio.revision,
    cash: portfolio.cash,
    positions: portfolio.positions,
    paperTotal: analytics.total_trade_count,
    paperOpen: analytics.open_trade_count,
    paperClosed: analytics.closed_trade_count,
  })
  const before = signature(current, paper)

  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    if (url.port !== '8000') return route.continue()
    url.protocol = 'http:'
    url.hostname = '127.0.0.1'
    url.port = '8010'
    return route.continue({ url: url.toString() })
  })
  await page.goto(`${frontendUrl}/portfolio`, { waitUntil: 'networkidle' })
  await page.locator('input[aria-label="Requested analysis date"]').fill('2026-09-02')
  await page.locator('input[aria-label="Optional ticker scope"]').fill('NEM, CRL')
  const planResponsePromise = page.waitForResponse((response) => response.url().includes('/api/v1/portfolio/plan') && response.request().method() === 'POST')
  await page.getByRole('button', { name: 'Generate Portfolio Plan' }).click()
  const planResponse = await planResponsePromise
  assert(planResponse.ok(), `Real portfolio plan failed: ${planResponse.status()}`)
  const plan = await planResponse.json()
  await page.getByText('Portfolio plan generated').waitFor()

  const blocked = plan.decisions.find((item) => item.entry_safety?.status === 'BLOCKED')
  const eligible = plan.decisions.find((item) => item.entry_safety?.status === 'ELIGIBLE' && item.decision === 'SKIP')
    ?? plan.decisions.find((item) => item.entry_safety?.status === 'ELIGIBLE')
  assert(blocked, 'No real extended EMA20 BUY candidate was available for browser acceptance')
  assert(blocked.decision === 'SKIP', 'Extended EMA20 candidate was not skipped')
  assert(blocked.reason === 'ENTRY_TOO_EXTENDED_ABOVE_EMA20', 'Extended candidate did not preserve the hard safety reason')
  assert(blocked.final_action === 'DO_NOT_BUY', 'Extended candidate final action was not DO_NOT_BUY')
  assert(eligible, 'No real in-zone EMA20 BUY candidate was available as a positive control')

  await page.getByRole('tab', { name: /Skipped/ }).click()
  const search = page.getByLabel('Search ticker or company')
  await search.fill(blocked.ticker)
  const blockedCard = page.locator('article.decision-card').filter({ hasText: blocked.ticker }).first()
  await blockedCard.getByText('Decision details').click()
  await blockedCard.getByText('ENTRY_TOO_EXTENDED_ABOVE_EMA20').first().waitFor()
  await blockedCard.getByText('DO_NOT_BUY').first().waitFor()
  await blockedCard.getByText('BLOCKED', { exact: true }).first().waitFor()
  await blockedCard.getByText(blocked.entry_safety.entry_price_source).first().waitFor()

  const eligibleTab = eligible.decision === 'BUY' ? /Approved Buys/ : eligible.decision === 'SELL' ? /Sells/ : eligible.decision === 'HOLD' ? /Held/ : /Skipped/
  await page.getByRole('tab', { name: eligibleTab }).click()
  await search.fill(eligible.ticker)
  const eligibleCard = page.locator('article.decision-card').filter({ hasText: eligible.ticker }).first()
  await eligibleCard.getByText('Decision details').click()
  await eligibleCard.getByText('ELIGIBLE', { exact: true }).first().waitFor()
  await eligibleCard.getByText(eligible.entry_safety.reason, { exact: true }).first().waitFor()

  const afterPortfolio = await (await page.request.get(`${backendUrl}/api/v1/portfolio/current`)).json()
  const afterPaper = await (await page.request.get(`${backendUrl}/api/v1/portfolio/${current.portfolio_id}/paper-analytics`)).json()
  assert(signature(afterPortfolio, afterPaper) === before, 'Read-only browser acceptance mutated portfolio or Paper history')
  await page.screenshot({ path: screenshotPath, fullPage: true })
  console.log(`EMA20_ENTRY_SAFETY_BROWSER_ACCEPTANCE PASS blocked=${blocked.ticker} eligible=${eligible.ticker} decisions=${plan.decisions.length} screenshot=${screenshotPath}`)
} finally {
  await browser.close()
}
