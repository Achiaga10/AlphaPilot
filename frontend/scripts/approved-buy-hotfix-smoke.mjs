import { chromium } from 'playwright-core'

const frontendUrl = process.env.ALPHAPILOT_FRONTEND_URL ?? 'http://127.0.0.1:5173'
const backendUrl = process.env.ALPHAPILOT_BACKEND_URL ?? 'http://127.0.0.1:8000'
const edgePath = process.env.ALPHAPILOT_BROWSER_PATH
  ?? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const assert = (condition, message) => { if (!condition) throw new Error(message) }

function stateSignature(portfolio, paper) {
  const { generated_at: _generatedAt, ...durablePaper } = paper
  return JSON.stringify({ portfolio, paper: durablePaper })
}

const browser = await chromium.launch({ executablePath: edgePath, headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } })
  const currentResponse = await page.request.get(`${backendUrl}/api/v1/portfolio/current`)
  assert(currentResponse.ok(), 'Real current portfolio endpoint unavailable')
  const current = await currentResponse.json()
  assert(current?.portfolio_id, 'Current ResearchPortfolio missing')
  const paperUrl = `${backendUrl}/api/v1/portfolio/${current.portfolio_id}/paper-analytics`
  const paperResponse = await page.request.get(paperUrl)
  assert(paperResponse.ok(), 'Real Paper Analytics endpoint unavailable')
  const before = stateSignature(current, await paperResponse.json())

  const unexpectedMutations = []
  page.on('request', (request) => {
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method())
      && !(request.method() === 'POST' && request.url().endsWith('/api/v1/portfolio/plan'))) {
      unexpectedMutations.push(`${request.method()} ${request.url()}`)
    }
  })

  await page.goto(`${frontendUrl}/portfolio`, { waitUntil: 'networkidle' })
  await page.locator('input[aria-label="Requested analysis date"]').fill('2026-09-09')
  await page.locator('input[aria-label="Optional ticker scope"]').fill('')
  const results = []

  for (const strategy of ['micho-150', 'ema20-pullback']) {
    await page.getByLabel('Strategy', { exact: true }).selectOption(strategy)
    const responsePromise = page.waitForResponse(
      (response) => response.url().endsWith('/api/v1/portfolio/plan')
        && response.request().method() === 'POST',
      { timeout: 180_000 },
    )
    await page.getByRole('button', { name: 'Generate Portfolio Plan' }).click()
    const response = await responsePromise
    assert(response.ok(), `${strategy} plan failed: ${response.status()}`)
    const plan = await response.json()
    await page.locator('.plan-results').getByText(
      `${plan.strategy_profile.profile_id} v${plan.strategy_profile.version}`,
      { exact: true },
    ).first().waitFor()

    const approved = plan.decisions.filter(
      (decision) => decision.final_action === 'BUY' && decision.is_final_actionable === true,
    )
    assert(plan.readiness.final_approved_buys === approved.length, `${strategy} count diverged`)
    assert(plan.readiness.buy_funnel.news_advisory_only === true, `${strategy} News is not advisory`)
    assert(plan.readiness.buy_funnel.reached_news === 0, `${strategy} reached a News gate`)
    assert(plan.news_enrichment.candidate_shortlist.length === 0, `${strategy} refreshed News`)
    assert(plan.news_enrichment.aggregate_api_calls === 0, `${strategy} called aggregate News`)
    assert(plan.news_enrichment.attributable_api_calls === 0, `${strategy} called attributable News`)
    await page.getByText(/News is optional advisory context, not an approval gate/).waitFor()
    await page.getByRole('tab', { name: `Approved Buys ${approved.length}` }).click()

    if (approved.length > 0) {
      const firstCard = page.locator('.decision-card').filter({ hasText: approved[0].ticker }).first()
      await firstCard.getByText('Final action APPROVED BUY', { exact: true }).waitFor()
      await firstCard.locator('.field-label').filter({ hasText: 'Approved allocation' }).waitFor()
    } else {
      await page.getByText('No approved BUYs').waitFor()
      const blocker = plan.readiness.buy_funnel.groups.find((group) => group.count > 0)
      assert(blocker, `${strategy} had neither approved BUYs nor a typed blocker`)
      await page.getByRole('tab', { name: /Not Actionable/ }).click()
      const blockedDecision = plan.decisions.find(
        (decision) => decision.final_action === 'NOT_ACTIONABLE',
      )
      assert(blockedDecision, `${strategy} missing non-actionable decision record`)
      const blockedCard = page.locator('.decision-card').filter({
        hasText: blockedDecision.ticker,
      }).first()
      await blockedCard.getByText(blockedDecision.ticker, { exact: true }).waitFor()
      await blockedCard.getByText('Decision details').click()
      await blockedCard.getByText(blockedDecision.terminal_reason, { exact: true }).first().waitFor()
    }

    results.push({
      strategy,
      profile: plan.strategy_profile.profile_id,
      analysis_as_of_date: plan.analysis_as_of_date,
      technical_buy_signals: plan.readiness.technical_buy_signals,
      final_approved_buys: approved.length,
      blockers: plan.readiness.buy_funnel.groups.filter(
        (group) => group.stage !== 'FINAL_APPROVED_BUY',
      ),
      news_blocked: 0,
    })
  }

  assert(unexpectedMutations.length === 0, `Unexpected mutations: ${unexpectedMutations.join(', ')}`)
  const afterPortfolioResponse = await page.request.get(`${backendUrl}/api/v1/portfolio/current`)
  const afterPaperResponse = await page.request.get(paperUrl)
  assert(afterPortfolioResponse.ok() && afterPaperResponse.ok(), 'Post-run state lookup failed')
  const after = stateSignature(
    await afterPortfolioResponse.json(),
    await afterPaperResponse.json(),
  )
  assert(after === before, 'Browser acceptance mutated portfolio or Paper state')

  console.log(JSON.stringify({
    result: 'APPROVED_BUY_HOTFIX_BROWSER_ACCEPTANCE PASS',
    results,
    portfolio_mutated: false,
    paper_mutated: false,
    broker_action: false,
  }, null, 2))
} finally {
  await browser.close()
}
