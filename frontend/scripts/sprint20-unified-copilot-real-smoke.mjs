import { chromium } from 'playwright-core'

const url = process.env.ALPHAPILOT_FRONTEND_URL ?? 'http://127.0.0.1:5173'
const browserPath = process.env.ALPHAPILOT_BROWSER_PATH ?? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const browser = await chromium.launch({ executablePath: browserPath, headless: true })

async function ask(page, question, expected, timeout = 15000) {
  const composer = page.getByLabel('Question')
  await composer.fill(question)
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  try {
    await page.getByText(expected).last().waitFor({ timeout })
  } catch (error) {
    const history = await page.getByLabel('Copilot message history').innerText()
    throw new Error(`Expected response was not rendered for "${question}". History:\n${history}`, { cause: error })
  }
  await page.waitForFunction(() => {
    const button = document.querySelector('.floating-copilot form button')
    return button instanceof HTMLButtonElement && !button.disabled
  })
}

try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
  await page.goto(url, { waitUntil: 'domcontentloaded' })
  const pageScrollBefore = await page.evaluate(() => window.scrollY)
  await page.getByRole('button', { name: 'Ask AI' }).click()
  if (await page.getByLabel('Copilot context').count()) throw new Error('Visible context selector still exists')

  await ask(page, 'Where do I sync market data?', /Open Data Management/)
  await ask(page, 'How many shares do I own? FAST', /You own \d+ shares of FAST/)
  await page.getByRole('button', { name: 'Clear position context' }).click()
  await ask(page, 'How many shares do I own?', 'Which ticker do you mean?')
  await ask(page, 'APA', /You own \d+ shares of APA/)
  await ask(page, 'Do you know what is stop loss?', /A stop loss is a predefined loss-control rule/)
  const glossaryReply = page.getByText(/A stop loss is a predefined loss-control rule/).last()
  if ((await glossaryReply.innerText()).includes('APA')) {
    throw new Error('Active APA context hijacked the general stop-loss definition')
  }
  await ask(page, 'What is my stop loss?', /current APA loss-control boundary|no approved protective loss-control policy for APA/)
  await ask(page, 'What is my average cost?', /average cost for APA is \$42\.38/)
  await ask(page, 'What about FAST?', /use FAST for your next position question/)
  await ask(page, 'What is my average cost?', /average cost for FAST/)

  const composer = page.getByLabel('Question')
  await composer.fill('Why am I holding FAST?')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  const typing = page.getByLabel('AlphaPilot AI is preparing a response')
  await typing.waitFor({ timeout: 5000 })
  const typingAtBottom = await page.getByLabel('Copilot message history').evaluate((element) =>
    element.scrollHeight - element.scrollTop - element.clientHeight <= 3)
  if (!typingAtBottom) throw new Error('Typing indicator was not scrolled into view')
  await typing.waitFor({ state: 'hidden', timeout: 60000 })
  const answerAtBottom = await page.getByLabel('Copilot message history').evaluate((element) =>
    element.scrollHeight - element.scrollTop - element.clientHeight <= 3)
  if (!answerAtBottom) throw new Error('Assistant answer was not scrolled into view')
  const pageScrollAfter = await page.evaluate(() => window.scrollY)
  const panelScroll = await page.locator('.floating-copilot__panel').evaluate((element) => element.scrollTop)
  if (pageScrollAfter !== pageScrollBefore || panelScroll !== 0) {
    throw new Error('Auto-scroll moved the page or outer Copilot panel')
  }
  console.log('Real Sprint 20 unified Copilot browser smoke passed.')
} finally {
  await browser.close()
}
