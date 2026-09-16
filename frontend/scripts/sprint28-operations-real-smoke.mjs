import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'
import { chromium } from 'playwright-core'

const frontendUrl = process.env.ALPHAPILOT_FRONTEND_URL ?? 'http://127.0.0.1:5180'
const expectedHealth = process.env.ALPHAPILOT_EXPECTED_HEALTH ?? 'DEGRADED'
const edgePath = process.env.ALPHAPILOT_BROWSER_PATH ?? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const output = resolve('../backend/backtest_reports/sprint28')

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

await mkdir(output, { recursive: true })
const browser = await chromium.launch({ executablePath: edgePath, headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } })
try {
  await page.goto(frontendUrl, { waitUntil: 'networkidle' })
  await page.getByRole('heading', { name: 'Operations Center' }).waitFor()
  const body = await page.locator('body').innerText()
  assert(body.includes('Observational only'), 'Expected authority boundary')
  assert(body.includes('UNKNOWN / NOT EVALUATED'), 'Expected non-authoritative drift state')
  if (expectedHealth === 'DEGRADED') {
    assert(body.includes('DEGRADED'), 'Expected DEGRADED health')
    assert(body.includes('BROKER ENVIRONMENT MISMATCH'), 'Expected environment mismatch')
    assert(body.includes('BROKER SYNC MISCONFIGURED'), 'Expected warning state')
    await page.screenshot({ path: resolve(output, 'operations-degraded.png'), fullPage: true })
    await page.getByRole('button', { name: 'Acknowledge' }).first().click()
    await page.getByRole('button', { name: 'Confirm acknowledgement' }).click()
    await page.getByText(/ACKNOWLEDGED/).first().waitFor()
    await page.screenshot({ path: resolve(output, 'operations-acknowledged.png'), fullPage: true })
    console.log('Sprint 28 degraded/warning/acknowledgement browser acceptance passed')
  } else {
    assert(body.includes('HEALTHY'), 'Expected HEALTHY recovery')
    assert(/Resolved incident history \([1-9]/.test(body), 'Expected resolved occurrence history')
    await page.getByText(/Resolved incident history \([1-9]/).click()
    await page.screenshot({ path: resolve(output, 'operations-recovered.png'), fullPage: true })
    console.log('Sprint 28 recovery/history browser acceptance passed')
  }
} finally {
  await browser.close()
}
