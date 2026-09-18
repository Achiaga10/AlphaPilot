import { execFileSync } from 'node:child_process'
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'
import { chromium } from 'playwright-core'

const frontendUrl = process.env.ALPHAPILOT_FRONTEND_URL ?? 'http://127.0.0.1:5180'
const edgePath = process.env.ALPHAPILOT_BROWSER_PATH ?? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const output = resolve('../backend/backtest_reports/sprint29')

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

function fixture(mode) {
  execFileSync('uv', ['run', 'python', 'scripts/sprint29_browser_fixture.py', mode], {
    cwd: resolve('../backend'), env: process.env, stdio: 'inherit',
  })
}

await mkdir(output, { recursive: true })
fixture('reset')
const browser = await chromium.launch({ executablePath: edgePath, headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } })
try {
  await page.goto(frontendUrl, { waitUntil: 'networkidle' })
  await page.getByRole('heading', { name: 'Notification Delivery' }).waitFor()
  let body = await page.locator('body').innerText()
  assert(body.includes('Disabled'), 'Expected disabled preference state')

  fixture('seed')
  await page.reload({ waitUntil: 'networkidle' })
  await page.getByRole('heading', { name: 'Notification Delivery' }).waitFor()
  body = await page.locator('body').innerText()
  assert(body.includes('DEGRADED'), 'Expected critical health')
  assert(body.includes('MANUAL EXIT ACTION OVERDUE'), 'Expected overdue critical incident')
  assert(body.includes('ACKNOWLEDGED'), 'Expected acknowledged incident')
  assert(body.includes('EXTERNAL BUY ACTION UPCOMING'), 'Expected INFO incident')
  assert(body.includes('NOT ELIGIBLE'), 'Expected INFO notification ineligibility')
  assert(body.includes('DELIVERED'), 'Expected delivered incident state')

  await page.getByText(/Notification history \([1-9]/).click()
  body = await page.locator('body').innerText()
  assert(body.includes('[AlphaPilot][CRITICAL] Manual exit overdue — HAL'), 'Expected critical email')
  assert(body.includes('[AlphaPilot][CRITICAL] Reminder'), 'Expected critical reminder')
  assert(body.includes('[AlphaPilot][WARNING] Forward engine stale'), 'Expected warning email')
  assert(body.includes('[AlphaPilot][RECOVERED] Broker sync restored'), 'Expected recovery email')
  assert(body.includes('[AlphaPilot][SUMMARY] Operations'), 'Expected daily summary')
  assert(body.includes('FAILED'), 'Expected provider failure evidence')

  await page.getByText('Notification preferences', { exact: true }).click()
  await page.getByRole('button', { name: 'Send test email' }).click()
  await page.getByText(/TEST notification queued/).waitFor()
  fixture('deliver')
  await page.reload({ waitUntil: 'networkidle' })
  await page.getByText(/Notification history \([1-9]/).click()
  body = await page.locator('body').innerText()
  assert(body.includes('[AlphaPilot][TEST] Operational notification'), 'Expected durable TEST delivery')
  const operations = page.locator('section.operations-center')
  assert(await operations.getByRole('button', { name: /submit order|cancel order|buy|sell/i }).count() === 0, 'No broker controls expected')
  await page.screenshot({ path: resolve(output, 'operational-notifications.png'), fullPage: true })
  console.log('Sprint 29 real FastAPI/Vite/FakeNotificationProvider browser acceptance passed')
} finally {
  await browser.close()
}
