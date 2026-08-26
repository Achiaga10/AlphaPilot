import { chromium } from 'playwright-core'

const edgePath = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const appUrl = process.env.ALPHAPILOT_UI_URL ?? 'http://localhost:5173'
const browser = await chromium.launch({ executablePath: edgePath, headless: true })

try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
  await page.goto(`${appUrl}/evaluate`, { waitUntil: 'networkidle' })
  await page.evaluate(() => {
    localStorage.setItem('alphapilot.plan-draft.v1', JSON.stringify({
      cash: '90000',
      positions: [{
        ticker: 'LDOS', shares: 10, reference_price: '187.34', cost_basis: '180',
        sector: 'Industrials', modeled_risk_dollars: '0',
      }],
      strategy: 'ema20-pullback', selectionPolicy: 'relative-strength-20',
      sizingPolicy: 'equal-slot', asOfDate: '2026-08-26', tickerScope: '',
    }))
  })
  await page.reload({ waitUntil: 'networkidle' })

  const ticker = page.getByLabel('Ticker')
  await ticker.fill('SBET')
  await page.getByRole('button', { name: 'Evaluate stock' }).click()
  const firstOutcome = await Promise.race([
    page.locator('.result-banner').waitFor().then(() => 'result'),
    page.getByRole('alert').waitFor().then(() => 'error'),
  ])
  if (firstOutcome === 'error') {
    throw new Error(`SBET evaluation failed: ${await page.getByRole('alert').innerText()}`)
  }
  const sbetHeading = (await page.locator('.result-banner h2').textContent())?.trim()
  const sbetIdentity = (await page.locator('.result-banner p').nth(1).textContent())?.trim()
  const analysisMetadata = await page.locator('.analysis-strip').innerText()
  const resultText = await page.locator('.plan-results').innerText()
  if (!sbetIdentity?.startsWith('SBET ·') || resultText.includes('Leidos Holdings')) {
    throw new Error(`SBET identity mismatch: ${sbetHeading} / ${sbetIdentity}`)
  }
  if (!analysisMetadata.includes('REQUESTED\nAug 26, 2026') || !analysisMetadata.includes('COMPLETED ANALYSIS SESSION\nAug 25, 2026')) {
    throw new Error(`Completed-session metadata mismatch: ${analysisMetadata}`)
  }

  await ticker.fill('AAPL')
  const staleNotice = (await page.getByRole('status').textContent())?.trim()
  if (staleNotice !== 'Showing previous evaluation for SBET. Evaluate AAPL to update.') {
    throw new Error(`Unexpected stale-result notice: ${staleNotice}`)
  }
  if (!(await page.locator('.result-banner p').nth(1).textContent())?.trim().startsWith('SBET ·')) {
    throw new Error('Editing the input relabeled the existing SBET evaluation')
  }

  await page.getByRole('button', { name: 'Evaluate stock' }).click()
  await page.locator('.result-banner p').nth(1).filter({ hasText: /^AAPL ·/ }).waitFor()
  const aaplHeading = (await page.locator('.result-banner h2').textContent())?.trim()
  const aaplIdentity = (await page.locator('.result-banner p').nth(1).textContent())?.trim()
  const dataAsOf = await page.locator('.metric-card', { hasText: 'Data as of' }).innerText()

  await page.getByRole('link', { name: 'Dashboard' }).click()
  await page.getByRole('button', { name: 'Sell Position' }).click()
  const completedCloseLabel = await page.getByText('Latest stored completed close', { exact: true }).textContent()
  const completedCloseDate = await page.getByRole('dialog').getByText('Aug 25, 2026').textContent()

  process.stdout.write(JSON.stringify({
    heldTicker: 'LDOS',
    firstEvaluation: { heading: sbetHeading, identity: sbetIdentity },
    staleNotice,
    secondEvaluation: { heading: aaplHeading, identity: aaplIdentity },
    analysisMetadata,
    dataAsOf,
    latestStoredCompletedClose: { label: completedCloseLabel, dataAsOf: completedCloseDate },
  }, null, 2))
} finally {
  await browser.close()
}
