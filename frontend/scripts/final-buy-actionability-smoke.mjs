import { chromium } from 'playwright-core'

const frontendUrl = process.env.ALPHAPILOT_FRONTEND_URL ?? 'http://localhost:5173'
const backendUrl = process.env.ALPHAPILOT_BACKEND_URL ?? 'http://127.0.0.1:8000'
const edgePath = process.env.ALPHAPILOT_BROWSER_PATH
  ?? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const assert = (condition, message) => { if (!condition) throw new Error(message) }

function stateSignature(portfolio, paper) {
  const { generated_at: _requestTimestamp, ...durablePaper } = paper
  return JSON.stringify({ portfolio, paper: durablePaper })
}

function assertBlockedAllocationCandidate(decision, ticker) {
  assert(decision, `${ticker} decision missing`)
  assert(decision.signal === 'BUY', `${ticker} technical signal was not BUY`)
  assert(decision.decision === 'BUY', `${ticker} allocation decision was not BUY`)
  assert(decision.allocation_reason === 'BUY_APPROVED', `${ticker} allocation evidence changed`)
  assert(Number(decision.target_allocation_dollars) > 0, `${ticker} candidate allocation missing`)
  assert(decision.final_action === 'NOT_ACTIONABLE', `${ticker} final action was not NOT_ACTIONABLE`)
  assert(decision.reason === 'LOSS_CONTROL_UNAVAILABLE', `${ticker} legacy reason was stale`)
  assert(decision.terminal_reason === 'LOSS_CONTROL_UNAVAILABLE', `${ticker} terminal blocker changed`)
  assert(decision.execution_readiness === 'RESEARCH_ONLY', `${ticker} readiness changed`)
  assert(decision.is_final_actionable === false, `${ticker} was unexpectedly actionable`)
  assert(decision.loss_control_active === false, `${ticker} unexpectedly had loss control`)
  assert(decision.entry_safety?.status === 'ELIGIBLE', `${ticker} EMA20 safety was not eligible`)
  assert(decision.news_coverage === 'NEVER_REFRESHED', `${ticker} unexpectedly reached News`)
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

  let planRequestCount = 0
  page.on('request', (request) => {
    if (request.url().includes('/api/v1/portfolio/plan') && request.method() === 'POST') {
      planRequestCount += 1
    }
  })
  await page.goto(`${frontendUrl}/portfolio`, { waitUntil: 'networkidle' })
  await page.locator('input[aria-label="Requested analysis date"]').fill('2026-09-03')
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
  assert(planRequestCount === 1, `Expected one portfolio plan request, saw ${planRequestCount}`)

  const approved = plan.decisions.filter(
    (decision) => decision.final_action === 'BUY' && decision.is_final_actionable,
  )
  assert(plan.readiness.final_approved_buys === approved.length, 'Approved BUY count diverged')
  assert(approved.length === 0, 'Expected the reproduced real plan to have zero approved BUYs')
  const ibkr = plan.decisions.find((decision) => decision.ticker === 'IBKR')
  const eog = plan.decisions.find((decision) => decision.ticker === 'EOG')
  assertBlockedAllocationCandidate(ibkr, 'IBKR')
  assertBlockedAllocationCandidate(eog, 'EOG')

  await page.getByRole('tab', { name: /Returned Decision Records/ }).click()
  const search = page.getByLabel('Search ticker or company')
  for (const ticker of ['IBKR', 'EOG']) {
    await search.fill(ticker)
    const card = page.locator('.decision-card').filter({ hasText: ticker })
    await card.waitFor()
    await card.getByText('Final action NOT ACTIONABLE', { exact: true }).waitFor()
    await card.locator('.field-label').filter({ hasText: 'Candidate allocation' }).first().waitFor()
    await card.getByText('Loss control unavailable', { exact: true }).waitFor()
    await card.locator('p.inline-note').filter({
      hasText: 'No approved numeric loss-control policy',
    }).waitFor()
    assert(await card.getByText('Buy approved', { exact: true }).count() === 0, `${ticker} showed stale approval`)
    assert(await card.getByRole('button', { name: 'Review Add' }).count() === 0, `${ticker} exposed Add`)
  }
  await page.getByRole('tab', { name: 'Approved Buys 0' }).click()
  assert(await page.getByText('IBKR', { exact: true }).count() === 0, 'IBKR appeared in Approved Buys')
  assert(await page.getByText('EOG', { exact: true }).count() === 0, 'EOG appeared in Approved Buys')

  const afterPortfolioResponse = await page.request.get(`${backendUrl}/api/v1/portfolio/current`)
  const afterPaperResponse = await page.request.get(
    `${backendUrl}/api/v1/portfolio/${current.portfolio_id}/paper-analytics`,
  )
  assert(afterPortfolioResponse.ok() && afterPaperResponse.ok(), 'Post-run state lookup failed')
  const after = stateSignature(
    await afterPortfolioResponse.json(),
    await afterPaperResponse.json(),
  )
  assert(after === before, 'Read-only browser acceptance mutated portfolio or Paper state')

  console.log(JSON.stringify({
    result: 'FINAL_BUY_ACTIONABILITY_BROWSER_ACCEPTANCE PASS',
    plan_id: plan.plan_id,
    portfolio_revision: plan.portfolio_revision,
    requested_as_of_date: plan.requested_as_of_date,
    analysis_as_of_date: plan.analysis_as_of_date,
    evaluated_tickers: plan.readiness.evaluated_tickers,
    technical_buy_signals: plan.readiness.technical_buy_signals,
    final_approved_buys: plan.readiness.final_approved_buys,
    plan_requests: planRequestCount,
    decisions: [ibkr, eog].map((decision) => ({
      ticker: decision.ticker,
      signal: decision.signal,
      candidate_decision: decision.decision,
      allocation_reason: decision.allocation_reason,
      candidate_allocation: decision.target_allocation_dollars,
      final_action: decision.final_action,
      terminal_reason: decision.terminal_reason,
      execution_readiness: decision.execution_readiness,
      is_final_actionable: decision.is_final_actionable,
      loss_control_active: decision.loss_control_active,
      entry_safety: decision.entry_safety?.status,
      news_coverage: decision.news_coverage,
    })),
    portfolio_mutated: false,
    paper_mutated: false,
    broker_action: false,
  }, null, 2))
} finally {
  await browser.close()
}
