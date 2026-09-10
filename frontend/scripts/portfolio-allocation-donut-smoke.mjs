import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { chromium } from 'playwright-core'

const frontendUrl = process.env.ALPHAPILOT_FRONTEND_URL ?? 'http://127.0.0.1:5173'
const backendUrl = process.env.ALPHAPILOT_BACKEND_URL ?? 'http://127.0.0.1:8000'
const edgePath = process.env.ALPHAPILOT_BROWSER_PATH
  ?? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const assert = (condition, message) => { if (!condition) throw new Error(message) }

function durablePaper(paper) {
  const { generated_at: _generatedAt, ...durable } = paper
  return durable
}

function allocationRows(portfolio) {
  return [
    ...portfolio.positions
      .filter((position) => position.market_value !== null && position.portfolio_weight_pct !== null)
      .sort((left, right) => left.ticker.localeCompare(right.ticker))
      .map((position) => ({
        label: position.ticker,
        value: position.market_value,
        weight: position.portfolio_weight_pct,
      })),
    { label: 'Cash', value: portfolio.cash, weight: portfolio.cash_pct },
  ]
}

async function assertRing(svg, activeLabel = null) {
  const result = await svg.evaluate((node, activeLabel) => {
    const slices = [...node.querySelectorAll('path[role="img"]')]
    const geometry = slices.map((slice) => {
      const style = getComputedStyle(slice)
      return {
        label: slice.dataset.allocationLabel,
        arcRadii: [...slice.getAttribute('d').matchAll(/ A (\d+) \d+ /g)].map((match) => Number(match[1])),
        active: slice === document.activeElement,
        stroke: style.stroke,
        filter: style.filter,
      }
    })
    // Test the actual filled geometry, not just declared arc radii. Points are in
    // each path's local coordinates (all slices share the same -90deg transform).
    const defects = []
    for (let step = 0; step < 3600; step += 1) {
      const angle = (step + 0.5) * Math.PI / 1800
      for (const radius of [34.5, 35.5, 44, 52.5, 54, 55.5]) {
        const point = new DOMPoint(60 + radius * Math.cos(angle), 60 + radius * Math.sin(angle))
        const hits = slices.filter((slice) => slice.isPointInFill(point))
        const ringInterior = radius > 35 && radius < 53
        const invalid = ringInterior ? hits.length !== 1
          : radius === 54 ? hits.length > 1 || hits.some((slice) => slice.dataset.allocationLabel !== activeLabel)
            : hits.length !== 0
        if (invalid && defects.length < 5) defects.push({ angle, radius, hits: hits.map((slice) => slice.dataset.allocationLabel) })
      }
    }
    return { geometry, defects, paths: node.querySelectorAll('path').length }
  }, activeLabel)
  assert(result.paths === result.geometry.length, 'Unexpected duplicate active-sector path')
  assert(result.geometry.every((item) => {
    const outer = item.label === activeLabel ? 55 : 53
    return JSON.stringify(item.arcRadii) === JSON.stringify([outer, outer, 35, 35])
  }), 'Incorrect idle/active radii or intrusion into the inner hole')
  assert(result.geometry.every((item) => item.active === (item.label === activeLabel)), 'Click focus did not transfer cleanly')
  assert(result.geometry.every((item) => item.stroke === 'none' && item.filter === 'none'), 'Slice joins have a stroke/shadow artifact')
  assert(result.defects.length === 0, `Rendered ring has a gap/overlap: ${JSON.stringify(result.defects)}`)
}

async function inspectViewport(browser, viewport, expectedRows) {
  const page = await browser.newPage({ viewport, deviceScaleFactor: 1 })
  const pageErrors = []
  const mutations = []
  page.on('pageerror', (error) => pageErrors.push(String(error)))
  await page.route('**/api/v1/**', (route) => {
    const request = route.request()
    if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) {
      mutations.push(`${request.method()} ${request.url()}`)
      return route.abort()
    }
    return route.continue()
  })

  await page.goto(`${frontendUrl}/portfolio`, { waitUntil: 'domcontentloaded', timeout: 30_000 })
  await page.getByRole('heading', { name: 'Portfolio Allocation' }).waitFor({ timeout: 30_000 })
  const panel = page.locator('.allocation-panel')
  const svg = page.locator('.allocation-donut')
  const slices = svg.locator('path[role="img"]')
  const legendRows = page.locator('.allocation-legend li')
  const actualSlices = await slices.evaluateAll((nodes) => nodes.map((node) => ({
    label: node.dataset.allocationLabel,
    value: node.dataset.allocationValue,
    weight: node.dataset.allocationWeight,
  })))
  const actualLegend = await legendRows.evaluateAll((nodes) => nodes.map((node) => ({
    label: node.dataset.allocationLabel,
    value: node.dataset.allocationValue,
    weight: node.dataset.allocationWeight,
  })))
  assert(JSON.stringify(actualSlices) === JSON.stringify(expectedRows), 'Donut slices diverged from backend allocation')
  assert(JSON.stringify(actualLegend) === JSON.stringify(expectedRows), 'Legend rows diverged from backend allocation')
  assert(await slices.count() === expectedRows.length, 'Unexpected donut slice count')
  assert(await legendRows.count() === expectedRows.length, 'Unexpected legend row count')

  await panel.scrollIntoViewIfNeeded()
  await assertRing(svg)
  const idleScreenshot = join(tmpdir(), `alphapilot-allocation-${viewport.width}px-idle.png`)
  await panel.screenshot({ path: idleScreenshot })
  const allocationFacts = () => slices.evaluateAll((nodes) => nodes.map((node) => ({
    data: { ...node.dataset }, label: node.getAttribute('aria-label'), fill: node.getAttribute('fill'),
  })))
  const initialFacts = await allocationFacts()
  const initialLegend = await page.locator('.allocation-legend').innerHTML()
  const initialPanelBox = await panel.boundingBox()
  const box = await svg.boundingBox()
  assert(box, 'Donut bounding box unavailable')
  const clicks = []
  let cumulativeWeight = 0
  for (let index = 0; index < expectedRows.length; index += 1) {
    const label = expectedRows[index].label
    const weight = Number(expectedRows[index].weight)
    const angle = (-90 + 3.6 * (cumulativeWeight + weight / 2)) * Math.PI / 180
    const radius = box.width * 44 / 120
    const x = box.x + box.width / 2 + radius * Math.cos(angle)
    const y = box.y + box.height / 2 + radius * Math.sin(angle)
    await page.mouse.move(x, y)
    const targetLabel = await page.evaluate(({ x, y }) => {
      const target = document.elementFromPoint(x, y)
      return target instanceof SVGPathElement ? target.dataset.allocationLabel : null
    }, { x, y })
    assert(targetLabel === label, `Pointer target mismatch for ${label}`)
    await page.mouse.click(x, y)
    await assertRing(svg, label)
    // Preserve the original native-focus semantics: repeated clicks stay active.
    await page.mouse.click(x, y)
    assert(await slices.nth(index).evaluate((node) => node === document.activeElement), `Repeated click deselected ${label}`)
    assert(JSON.stringify(await allocationFacts()) === JSON.stringify(initialFacts), 'Click duplicated or changed allocation facts')
    assert(await page.locator('.allocation-legend').innerHTML() === initialLegend, 'Click changed legend')
    assert(JSON.stringify(await panel.boundingBox()) === JSON.stringify(initialPanelBox), 'Click changed card dimensions')
    const screenshot = join(tmpdir(), `alphapilot-allocation-${viewport.width}px-active-${label}.png`)
    await panel.screenshot({ path: screenshot })
    clicks.push({ label, clean: true, repeatedClickStaysActive: true, screenshot })
    cumulativeWeight += weight
  }
  // Clicking outside a slice clears focus, as it did in the original chart.
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2)
  await assertRing(svg)
  assert(pageErrors.length === 0, `Browser errors: ${pageErrors.join('; ')}`)
  assert(mutations.length === 0, `Unexpected mutating request: ${mutations.join('; ')}`)
  await page.close()
  return { viewport, slices: expectedRows.length, idleScreenshot, clicks, ringSamplesPerState: 21_600 }
}

const browser = await chromium.launch({ executablePath: edgePath, headless: true })
try {
  const request = (await browser.newContext()).request
  const health = await request.get(`${backendUrl}/api/v1/health/`)
  assert(health.ok(), 'Real FastAPI health endpoint unavailable')
  const currentResponse = await request.get(`${backendUrl}/api/v1/portfolio/current`)
  assert(currentResponse.ok(), 'Real current portfolio endpoint unavailable')
  const current = await currentResponse.json()
  assert(current?.portfolio_id, 'Current ResearchPortfolio missing')
  const rows = allocationRows(current)
  assert(new Set(rows.map((row) => row.label)).size === rows.length, 'Duplicate allocation label')
  assert(rows.every((row) => Number(row.value) > 0), 'Nonpositive allocation slice')
  const valueTotal = rows.reduce((total, row) => total + Number(row.value), 0)
  const weightTotal = rows.reduce((total, row) => total + Number(row.weight), 0)
  assert(Math.abs(valueTotal - Number(current.total_equity)) < 0.01, 'Allocation values do not reconcile')
  assert(Math.abs(weightTotal - 100) < 0.0001, 'Allocation weights do not reconcile')

  const paperBeforeResponse = await request.get(`${backendUrl}/api/v1/portfolio/${current.portfolio_id}/paper-analytics`)
  assert(paperBeforeResponse.ok(), 'Paper analytics unavailable before acceptance')
  const paperBefore = durablePaper(await paperBeforeResponse.json())
  const views = []
  views.push(await inspectViewport(browser, { width: 1440, height: 1100 }, rows))
  views.push(await inspectViewport(browser, { width: 800, height: 1200 }, rows))

  const currentAfterResponse = await request.get(`${backendUrl}/api/v1/portfolio/current`)
  const paperAfterResponse = await request.get(`${backendUrl}/api/v1/portfolio/${current.portfolio_id}/paper-analytics`)
  assert(currentAfterResponse.ok() && paperAfterResponse.ok(), 'Post-acceptance state read failed')
  assert(JSON.stringify(await currentAfterResponse.json()) === JSON.stringify(current), 'ResearchPortfolio changed')
  assert(JSON.stringify(durablePaper(await paperAfterResponse.json())) === JSON.stringify(paperBefore), 'Paper evidence changed')
  console.log(JSON.stringify({ health: 'PASS', allocation: rows, views, mutations: 0, portfolioMutation: false, paperMutation: false }, null, 2))
} finally {
  await browser.close()
}
