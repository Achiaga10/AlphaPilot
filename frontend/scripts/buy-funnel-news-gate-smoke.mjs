import { chromium } from 'playwright-core'

const frontendUrl = process.env.ALPHAPILOT_FRONTEND_URL ?? 'http://localhost:5173'
const backendUrl = process.env.ALPHAPILOT_BACKEND_URL ?? 'http://127.0.0.1:8000'
const edgePath = process.env.ALPHAPILOT_BROWSER_PATH
  ?? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const assert = (condition, message) => { if (!condition) throw new Error(message) }

function stateSignature(portfolio, paper) {
  return JSON.stringify({
    revision: portfolio.revision,
    cash: portfolio.cash,
    positions: portfolio.positions,
    paperTotal: paper.total_trade_count,
    paperOpen: paper.open_trade_count,
    paperClosed: paper.closed_trade_count,
  })
}

const browser = await chromium.launch({ executablePath: edgePath, headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } })
  const health = await page.request.get(`${backendUrl}/api/v1/health/`)
  assert(health.ok(), 'Real FastAPI health endpoint unavailable')
  const currentResponse = await page.request.get(`${backendUrl}/api/v1/portfolio/current`)
  assert(currentResponse.ok(), 'Real current portfolio endpoint unavailable')
  const current = await currentResponse.json()
  assert(current?.portfolio_id, 'Current ResearchPortfolio missing')
  const paperResponse = await page.request.get(
    `${backendUrl}/api/v1/portfolio/${current.portfolio_id}/paper-analytics`,
  )
  assert(paperResponse.ok(), 'Real Paper Analytics endpoint unavailable')
  const beforePaper = await paperResponse.json()
  const before = stateSignature(current, beforePaper)

  await page.goto(`${frontendUrl}/portfolio`, { waitUntil: 'networkidle' })
  await page.locator('input[aria-label="Requested analysis date"]').fill('2026-09-02')
  await page.locator('input[aria-label="Optional ticker scope"]').fill('')
  const responsePromise = page.waitForResponse(
    (response) => response.url().includes('/api/v1/portfolio/plan')
      && response.request().method() === 'POST',
    { timeout: 180_000 },
  )
  await page.getByRole('button', { name: 'Generate Portfolio Plan' }).click()
  const planResponse = await responsePromise
  assert(planResponse.ok(), `Real portfolio plan failed: ${planResponse.status()}`)
  const plan = await planResponse.json()
  await page.getByText('Portfolio plan generated').waitFor({ timeout: 180_000 })

  const funnel = plan.readiness.buy_funnel
  const groupTotal = funnel.groups.reduce((total, group) => total + group.count, 0)
  assert(plan.readiness.evaluated_tickers === 502, 'Expected 502 evaluated tickers')
  assert(funnel.technical_buy_signals === 65, 'Expected 65 technical BUY signals')
  assert(funnel.final_approved_buys === 0, 'Expected zero final approved BUYs')
  assert(groupTotal === funnel.technical_buy_signals, 'BUY funnel does not reconcile')
  assert(
    plan.news_enrichment.candidate_shortlist.length === funnel.reached_news,
    'News shortlist and reached-News count differ',
  )
  assert(plan.news_enrichment.aggregate_api_calls <= 1, 'Bounded shortlist used excess Adanos calls')

  await page.getByRole('heading', { name: 'BUY funnel' }).waitFor()
  await page.locator('p.inline-note').filter({ hasText: '65 technical BUY signals' }).waitFor()
  for (const group of funnel.groups) {
    if (group.count === 0) continue
    const summary = page.locator('summary').filter({ hasText: `: ${group.count}` })
    if (await summary.count()) {
      await summary.first().click()
      await page.getByText(group.tickers.join(', '), { exact: true }).waitFor()
      break
    }
  }

  const afterPortfolioResponse = await page.request.get(`${backendUrl}/api/v1/portfolio/current`)
  const afterPaperResponse = await page.request.get(
    `${backendUrl}/api/v1/portfolio/${current.portfolio_id}/paper-analytics`,
  )
  assert(afterPortfolioResponse.ok() && afterPaperResponse.ok(), 'Post-run state lookup failed')
  const after = stateSignature(
    await afterPortfolioResponse.json(),
    await afterPaperResponse.json(),
  )
  assert(after === before, 'Read-only browser acceptance mutated portfolio or Paper history')

  console.log(JSON.stringify({
    result: 'BUY_FUNNEL_NEWS_GATE_BROWSER_ACCEPTANCE PASS',
    plan_id: plan.plan_id,
    portfolio_revision: plan.portfolio_revision,
    requested_as_of_date: plan.requested_as_of_date,
    analysis_as_of_date: plan.analysis_as_of_date,
    evaluated_tickers: plan.readiness.evaluated_tickers,
    technical_buy_signals: funnel.technical_buy_signals,
    rejected_before_news: funnel.rejected_before_news,
    reached_news: funnel.reached_news,
    final_approved_buys: funnel.final_approved_buys,
    groups: funnel.groups,
    news_enrichment: plan.news_enrichment,
    final_buys: plan.decisions.filter((item) => item.is_final_actionable && item.decision === 'BUY'),
    reached_news_without_buy: plan.decisions.filter(
      (item) => item.news_assessment_reason && !(item.is_final_actionable && item.decision === 'BUY'),
    ).map((item) => ({
      ticker: item.ticker,
      reason: item.reason,
      news_assessment_reason: item.news_assessment_reason,
      news_coverage: item.news_coverage,
      news_effect: item.news_effect,
      final_action: item.final_action,
    })),
    portfolio_mutated: false,
    paper_mutated: false,
    broker_action: false,
  }, null, 2))
} finally {
  await browser.close()
}
