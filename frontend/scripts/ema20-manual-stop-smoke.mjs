import { chromium } from 'playwright-core'

const frontendUrl = process.env.ALPHAPILOT_FRONTEND_URL ?? 'http://127.0.0.1:5173'
const backendUrl = process.env.ALPHAPILOT_BACKEND_URL ?? 'http://127.0.0.1:8000'
const requestedDate = process.env.ALPHAPILOT_ACCEPTANCE_DATE ?? '2026-09-09'
const edgePath = process.env.ALPHAPILOT_BROWSER_PATH
  ?? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const assert = (condition, message) => { if (!condition) throw new Error(message) }

function stateSignature(portfolio, paper) {
  const { generated_at: _generatedAt, ...durablePaper } = paper
  return JSON.stringify({ portfolio, paper: durablePaper })
}

function approvedDetails(decision) {
  return {
    ticker: decision.ticker,
    final_action: decision.final_action,
    allocation: decision.target_allocation_dollars,
    shares: decision.proposed_shares,
    entry_price: decision.entry_safety?.entry_price ?? decision.reference_price,
    reference_price: decision.reference_price,
    entry_safety: decision.entry_safety ?? null,
    loss_control_mode: decision.loss_control_source === 'USER_MANUAL' ? 'USER_MANUAL' : 'SYSTEM',
    manual_stop_required: decision.manual_stop_required,
    automatic_stop_price: decision.approved_protective_stop_price,
  }
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
  await page.locator('input[aria-label="Requested analysis date"]').fill(requestedDate)
  await page.locator('input[aria-label="Optional ticker scope"]').fill('')
  const results = []

  for (const strategy of ['micho-150', 'ema20-pullback']) {
    await page.getByLabel('Strategy', { exact: true }).selectOption(strategy)
    const responsePromise = page.waitForResponse(
      (response) => response.url().endsWith('/api/v1/portfolio/plan')
        && response.request().method() === 'POST',
      { timeout: 240_000 },
    )
    await page.getByRole('button', { name: 'Generate Portfolio Plan' }).click()
    const response = await responsePromise
    assert(response.ok(), `${strategy} plan failed: ${response.status()}`)
    const plan = await response.json()
    const technical = plan.decisions.filter((decision) => decision.signal === 'BUY')
    const approved = technical.filter(
      (decision) => decision.final_action === 'BUY' && decision.is_final_actionable === true,
    )
    const manual = approved.filter((decision) => decision.loss_control_source === 'USER_MANUAL')
    const automatic = approved.filter(
      (decision) => decision.loss_control_source === 'APPROVED_SYSTEM_POLICY',
    )
    const newsBlocked = technical.filter((decision) =>
      ['NEWS_RISK_BLOCK', 'NEWS_BUY_BLOCKED_ADVERSE_EVIDENCE'].includes(decision.terminal_reason)
    )

    assert(plan.readiness.final_approved_buys === approved.length, `${strategy} count diverged`)
    assert(plan.readiness.buy_funnel.news_advisory_only === true, `${strategy} News is not advisory`)
    assert(plan.readiness.buy_funnel.reached_news === 0, `${strategy} reached a News gate`)
    assert(newsBlocked.length === 0, `${strategy} had a News-blocked candidate`)
    assert(plan.news_enrichment.candidate_shortlist.length === 0, `${strategy} refreshed News`)
    assert(plan.news_enrichment.aggregate_api_calls === 0, `${strategy} called aggregate News`)
    assert(plan.news_enrichment.attributable_api_calls === 0, `${strategy} called News evidence`)

    if (strategy === 'ema20-pullback') {
      assert(approved.length > 0, 'EMA20 produced no approved BUY for manual-stop acceptance')
      for (const decision of approved) {
        assert(
          decision.loss_control_source === 'USER_MANUAL'
            || decision.loss_control_source === 'APPROVED_SYSTEM_POLICY',
          `${decision.ticker} has no typed loss-control mode`,
        )
        if (decision.loss_control_source === 'USER_MANUAL') {
          assert(decision.manual_stop_required === true, `${decision.ticker} lacks manual warning`)
          assert(decision.approved_protective_stop_price === null, `${decision.ticker} has fake stop`)
          assert(decision.loss_control_boundary_price === null, `${decision.ticker} has fake boundary`)
        }
      }
    } else {
      assert(manual.length === 0, 'Micho semantics changed to user-manual loss control')
    }

    await page.getByRole('tab', { name: `Approved Buys ${approved.length}` }).click()
    if (approved.length > 0) {
      const first = approved[0]
      const card = page.locator('.decision-card').filter({ hasText: first.ticker }).first()
      await card.getByText('Final action APPROVED BUY', { exact: true }).waitFor()
      if (first.manual_stop_required) {
        await card.getByText('MANUAL STOP REQUIRED', { exact: true }).waitFor()
        await card.getByText(/No system stop/).first().waitFor()
      }
    }

    results.push({
      strategy,
      profile: plan.strategy_profile.profile_id,
      requested_as_of_date: plan.requested_as_of_date,
      analysis_as_of_date: plan.analysis_as_of_date,
      technical_buy_count: technical.length,
      entry_safety_pass_count: technical.filter(
        (decision) => decision.entry_safety?.status === 'ELIGIBLE',
      ).length,
      allocation_pass_count: technical.filter(
        (decision) => decision.allocation_reason === 'BUY_APPROVED',
      ).length,
      automatic_stop_available_count: automatic.length,
      manual_stop_required_count: manual.length,
      approved_buy_count: approved.length,
      approved_candidates: approved.map(approvedDetails),
      first_blockers: plan.readiness.buy_funnel.groups.filter(
        (group) => group.stage !== 'FINAL_APPROVED_BUY',
      ),
      news_blocked_count: newsBlocked.length,
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
  assert(after === before, 'Browser acceptance mutated Portfolio or Paper state')

  console.log(JSON.stringify({
    result: 'EMA20_MANUAL_STOP_BROWSER_ACCEPTANCE PASS',
    results,
    portfolio_mutated: false,
    paper_mutated: false,
    broker_action: false,
  }, null, 2))
} finally {
  await browser.close()
}
