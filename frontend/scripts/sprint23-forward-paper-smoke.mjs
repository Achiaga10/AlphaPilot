import { mkdir } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright-core'

const frontendUrl = process.env.ALPHAPILOT_FRONTEND_URL ?? 'http://127.0.0.1:5173'
const backendUrl = process.env.ALPHAPILOT_BACKEND_URL ?? 'http://127.0.0.1:8000'
const edgePath = process.env.ALPHAPILOT_BROWSER_PATH ?? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const screenshotPath = resolve(dirname(fileURLToPath(import.meta.url)), '../../backend/backtest_reports/sprint23/browser-acceptance.png')
const assert = (condition, message) => { if (!condition) throw new Error(message) }
const id = '11111111-1111-4111-8111-111111111111'

function record(status, completeness) {
  const full = completeness === 'FULL'
  return {
    id: status === 'OPEN' ? id : '22222222-2222-4222-8222-222222222222', portfolio_id: id,
    position_id: id, ticker: status === 'OPEN' ? 'LEG' : 'APA', status,
    execution_source: 'ALPACA_PAPER_MANUAL', position_provenance: 'PLAN_PROFILE',
    strategy: 'ema20-pullback', strategy_profile_id: 'ema20-pullback-v1', strategy_profile_version: 1,
    planned_quantity: full ? 10 : null, reference_entry_price: full ? '100' : null,
    actual_quantity: 9, actual_entry_price: '101', actual_entry_at: '2026-01-05T15:00:00Z',
    entry_fill_difference: full ? '1' : null, entry_fill_difference_bps: full ? '100' : null,
    quantity_difference: full ? -1 : null, actual_exit_quantity: status === 'CLOSED' ? 9 : null,
    actual_exit_price: status === 'CLOSED' ? '110' : null, actual_exit_at: status === 'CLOSED' ? '2026-02-05T15:00:00Z' : null,
    paper_gross_pnl: status === 'CLOSED' ? '81' : null, paper_gross_return_pct: status === 'CLOSED' ? '8.910891089' : null,
    alphapilot_exit_triggered_on: null, alphapilot_exit_reason: null, evidence_completeness: completeness,
    entry_evidence_schema_version: full ? 1 : null,
    entry_evidence: full ? { decision: { source_action_id: 'controlled-action' }, loss_control: { policy: 'HYBRID_COMPLETED_CLOSE_EXIT', boundary: '95' }, completed_state: { session: '2026-01-02', ema20: '98', ema50: '95', sma150: null } } : null,
    exit_evidence_schema_version: status === 'CLOSED' ? 1 : null, exit_evidence: null,
    entry_slippage_percent: full ? '1' : null, entry_adverse_slippage_dollars_per_share: full ? '1' : null,
    quantity_adherence_percent: full ? '90' : null, planned_notional: full ? '1000' : null,
    actual_entry_notional: '909', fees_available: false, net_paper_pnl: null, calendar_days_held: status === 'CLOSED' ? 31 : null,
  }
}

const legacy = { record: record('OPEN', 'LEGACY'), evidence_domain: 'FORWARD_PAPER_EVIDENCE', completed_sessions_held: 10, calendar_days_held: 20, mfe_percent: '5', mae_percent: '-2', excursion_session_count: 10, post_exit_observations: {}, current_completed_session: '2026-08-28', current_completed_close: '105', current_unrealized_pnl: '36' }
const closed = { record: record('CLOSED', 'FULL'), evidence_domain: 'FORWARD_PAPER_EVIDENCE', completed_sessions_held: 20, calendar_days_held: 31, mfe_percent: '12', mae_percent: '-4', excursion_session_count: 20, post_exit_observations: { '5': { status: 'COMPLETE' }, '10': { status: 'COMPLETE' }, '20': { status: 'INCOMPLETE' } }, current_completed_session: '2026-08-28', current_completed_close: '111', current_unrealized_pnl: null }
const analytics = { portfolio_id: id, evidence_domain: 'FORWARD_PAPER_EVIDENCE', generated_at: new Date().toISOString(), total_trade_count: 2, open_trade_count: 1, closed_trade_count: 1, wins: 1, losses: 0, breakeven: 0, gross_realized_pnl: '81', win_rate_percent: '100', average_return_percent: '8.91', evidence_maturity: 'VERY_LOW_SAMPLE', complete_evidence_count: 1, partial_evidence_count: 0, legacy_evidence_count: 1, strategy_breakdown: [{ strategy_profile_id: 'ema20-pullback-v1', strategy_profile_version: 1, open_trade_count: 1, closed_trade_count: 1, wins: 1, losses: 0, breakeven: 0, win_rate_percent: '100', average_return_percent: '8.91', gross_total_pnl: '81', evidence_maturity: 'VERY_LOW_SAMPLE' }], open_trades: [legacy], closed_trades: [closed] }

await mkdir(dirname(screenshotPath), { recursive: true })
const browser = await chromium.launch({ executablePath: edgePath, headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } })
  const health = await page.request.get(`${backendUrl}/api/v1/health/`)
  assert(health.ok(), 'Real FastAPI health endpoint unavailable')
  const current = await page.request.get(`${backendUrl}/api/v1/portfolio/current`)
  assert(current.ok(), 'Real FastAPI portfolio endpoint unavailable')
  const portfolio = await current.json()
  assert(portfolio?.portfolio_id, 'Real portfolio missing')
  const realAnalytics = await page.request.get(`${backendUrl}/api/v1/portfolio/${portfolio.portfolio_id}/paper-analytics`)
  assert(realAnalytics.ok(), 'Real Forward Paper Analytics endpoint unavailable')
  const realBody = await realAnalytics.json()
  assert(realBody.evidence_domain === 'FORWARD_PAPER_EVIDENCE', 'Real API mixed evidence domains')
  const before = JSON.stringify({ revision: portfolio.revision, cash: portfolio.cash, positions: portfolio.positions, paperTotal: realBody.total_trade_count, paperOpen: realBody.open_trade_count, paperClosed: realBody.closed_trade_count })
  const copilot = await page.request.post(`${backendUrl}/api/v1/ai/copilot/portfolio/${portfolio.portfolio_id}/ask`, { data: { question: 'What is my paper P&L and paper win rate?' } })
  assert(copilot.ok(), 'Deterministic Paper Copilot failed with configured generative setting')
  assert((await copilot.json()).answer.includes('Forward Paper Evidence'), 'Copilot answer was not deterministic Paper evidence')

  await page.route('**/api/v1/portfolio/*/paper-analytics', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(analytics) }))
  await page.goto(`${frontendUrl}/portfolio`, { waitUntil: 'networkidle' })
  await page.getByRole('heading', { name: 'Forward Paper Analytics' }).waitFor()
  await page.getByText(/separate from Historical Research/i).waitFor()
  await page.getByText(/Tiny forward sample/i).waitFor()
  await page.getByText('1 / 1').waitFor()
  await page.getByText(/ema20-pullback-v1/).first().waitFor()
  await page.getByText(/LEG · OPEN/).click()
  await page.getByText(/Planned price: —/).waitFor()
  await page.getByText(/Evidence: LEGACY/).waitFor()
  await page.getByText(/APA · CLOSED/).click()
  for (const text of ['AlphaPilot plan', 'Actual Paper entry', 'Entry comparison', 'At-entry strategy state', 'Outcome', 'Post-trade observations']) await page.getByRole('heading', { name: text }).last().waitFor()
  await page.getByText(/Adverse slippage: \$1.00 per share/).waitFor()
  await page.getByText(/Quantity adherence: 90.00%/).waitFor()
  await page.getByText(/Gross P&L: \$81.00/).waitFor()
  await page.getByText(/MFE: 12.00% · MAE: -4.00%/).waitFor()
  await page.getByText(/5 COMPLETE · 10 COMPLETE · 20 INCOMPLETE/).waitFor()
  assert((await page.getByText(/Historical Research/).count()) > 0, 'Domain separation missing')
  const afterPortfolio = await (await page.request.get(`${backendUrl}/api/v1/portfolio/current`)).json()
  const afterPaper = await (await page.request.get(`${backendUrl}/api/v1/portfolio/${portfolio.portfolio_id}/paper-analytics`)).json()
  const after = JSON.stringify({ revision: afterPortfolio.revision, cash: afterPortfolio.cash, positions: afterPortfolio.positions, paperTotal: afterPaper.total_trade_count, paperOpen: afterPaper.open_trade_count, paperClosed: afterPaper.closed_trade_count })
  assert(after === before, 'Read-only smoke mutated ResearchPortfolio or user Paper history')
  await page.screenshot({ path: screenshotPath, fullPage: true })
  console.log(`SPRINT23_BROWSER_ACCEPTANCE PASS real_total=${realBody.total_trade_count} controlled_full=1 controlled_legacy=1 screenshot=${screenshotPath}`)
} finally { await browser.close() }
