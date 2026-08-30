import { chromium } from 'playwright-core'

const url = process.env.ALPHAPILOT_FRONTEND_URL ?? 'http://127.0.0.1:5173'
const browserPath = process.env.ALPHAPILOT_BROWSER_PATH ?? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const expectation = process.env.ALPHAPILOT_OLLAMA_EXPECTATION ?? 'available'
const browser = await chromium.launch({ executablePath: browserPath, headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
  await page.goto(url, { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Ask AI' }).click()
  const context = page.getByLabel('Copilot context')
  await context.selectOption({ label: 'Position · APA' })
  const composer = page.getByLabel('Question for APA')
  await composer.fill('what is the avarge cost of a share that i bought?')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await page.getByText('Your average cost for APA is $42.38 per share.').waitFor()
  await composer.fill('Why am I holding APA?')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  if (expectation === 'unavailable') {
    await page.getByText(/Check the local Ollama service/).waitFor()
    await page.getByRole('button', { name: 'Retry' }).waitFor()
  } else {
    await page.getByText(/holding APA|APA.*HOLD/i).last().waitFor({ timeout: 45000 })
  }
  console.log(`Real Sprint 20 Copilot browser smoke passed (${expectation}).`)
} finally {
  await browser.close()
}
