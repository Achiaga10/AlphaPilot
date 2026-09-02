import { mkdir } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright-core'

const frontendUrl = process.env.ALPHAPILOT_FRONTEND_URL ?? 'http://127.0.0.1:5174'
const backendUrl = process.env.ALPHAPILOT_BACKEND_URL ?? 'http://127.0.0.1:8010'
const edgePath = process.env.ALPHAPILOT_BROWSER_PATH ?? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const screenshotPath = resolve(dirname(fileURLToPath(import.meta.url)), '../../backend/backtest_reports/sprint24/browser-acceptance.png')
const assert = (condition, message) => { if (!condition) throw new Error(message) }

await mkdir(dirname(screenshotPath), { recursive: true })
const browser = await chromium.launch({
  executablePath: edgePath,
  headless: true,
  args: ['--disable-web-security'],
})
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } })
  const health = await page.request.get(`${backendUrl}/api/v1/health/`)
  assert(health.ok(), 'Real FastAPI health failed')
  const currentResponse = await page.request.get(`${backendUrl}/api/v1/portfolio/current`)
  assert(currentResponse.ok(), 'Real current portfolio failed')
  const current = await currentResponse.json()
  assert(current?.portfolio_id, 'Current portfolio is missing')
  const before = JSON.stringify({ revision: current.revision, cash: current.cash, positions: current.positions })
  const newsResponse = await page.request.get(`${backendUrl}/api/v1/portfolio/${current.portfolio_id}/news`)
  assert(newsResponse.ok(), 'Real persisted News endpoint failed')
  const news = await newsResponse.json()
  assert(news.length > 0, 'Real persisted News is empty')
  assert(news.some((item) => item.classification?.classification_status === 'CLASSIFIED'), 'No real hosted classification is persisted')
  const sentimentResponse = await page.request.get(`${backendUrl}/api/v1/portfolio/${current.portfolio_id}/news-sentiment`)
  assert(sentimentResponse.ok(), 'Real persisted Adanos sentiment endpoint failed')
  const sentiment = await sentimentResponse.json()
  assert(sentiment.length > 0, 'Real persisted Adanos sentiment is empty')
  assert(sentiment.every((item) => item.provider === 'ADANOS'), 'Unexpected aggregate sentiment provider')
  const copilot = await page.request.post(`${backendUrl}/api/v1/ai/copilot/portfolio/${current.portfolio_id}/query`, { data: { question: 'What does AlphaPilot think about this APA news?', active_ticker: 'APA', pending_intent: null } })
  assert(copilot.ok(), 'Deterministic News Copilot failed with generative AI disabled')
  const copilotBody = await copilot.json()
  assert(copilotBody.model === 'deterministic-news-v1', 'News Copilot called the wrong path')
  await page.goto(frontendUrl, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: 'News Intelligence' }).waitFor()
  await page.getByText('External News Sentiment — Adanos').waitFor()
  await page.getByText(/Adanos cannot directly create BUY, SELL, or EXIT_REQUIRED/).waitFor()
  await page.getByText('WEAK EVIDENCE', { exact: true }).first().waitFor()
  await page.getByText(/Attributable News Evidence — Finnhub/).waitFor()
  await page.getByText(/AI interprets event impact only/i).waitFor()
  await page.getByRole('button', { name: 'Refresh open holdings' }).waitFor()
  await page.getByText(/Classification:/).or(page.getByText(/Classified by GOOGLE_GEMINI/)).first().waitFor()
  const after = await (await page.request.get(`${backendUrl}/api/v1/portfolio/current`)).json()
  assert(JSON.stringify({ revision: after.revision, cash: after.cash, positions: after.positions }) === before, 'Read-only News smoke mutated ResearchPortfolio')
  await page.screenshot({ path: screenshotPath, fullPage: true })
  console.log(`SPRINT24_BROWSER_ACCEPTANCE PASS articles=${news.length} classified=${news.filter((item) => item.classification?.classification_status === 'CLASSIFIED').length} adanos=${sentiment.length} copilot=${copilotBody.model} screenshot=${screenshotPath}`)
} finally {
  await browser.close()
}
