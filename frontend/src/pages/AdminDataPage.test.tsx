import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { API_BASE_URL } from '../api/client'
import { renderApp } from '../test/renderApp'
import { server } from '../test/server'

const enabled = http.get(`${API_BASE_URL}/api/v1/admin/data/capability`, () => HttpResponse.json({ enabled: true, warning: 'Research admin tools are enabled. This feature gate is not authentication.', market_data_provider: 'Alpaca', market_data_feed: 'iex' }))
const summary = http.get(`${API_BASE_URL}/api/v1/admin/data/summary`, () => HttpResponse.json({ active_company_count: 503, active_sp500_count: 502, active_custom_tracked_count: 1, latest_spy_date: '2026-08-20', earliest_active_stock_latest_date: '2026-08-19', latest_active_stock_latest_date: '2026-08-20', fresh_tracked_ticker_count: 501, stale_tracked_ticker_count: 1, no_data_tracked_ticker_count: 0, latest_sync_job: null, last_universe_sync_at: null, last_candle_sync_at: null, market_data_provider: 'Alpaca', market_data_feed: 'iex' }))

test('disabled admin route explains the safe default and does not render actions', async () => {
  renderApp('/admin/data')
  expect(await screen.findByRole('heading', { name: 'Research admin tools are disabled by backend configuration' })).toBeInTheDocument()
  expect(screen.getByText('ADMIN_TOOLS_ENABLED=true')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Full Sync' })).not.toBeInTheDocument()
})

test('enabled admin view renders freshness and warns that the gate is not authentication', async () => {
  server.use(enabled, summary)
  renderApp('/admin/data')
  expect(await screen.findByText('503')).toBeInTheDocument()
  expect(screen.getByText('502')).toBeInTheDocument()
  expect(screen.getAllByText('Aug 20, 2026').length).toBeGreaterThan(0)
  expect(screen.getByText(/not authentication/i)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Sync S&P 500 Universe' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Sync Market Candles' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Custom Tracked Tickers' })).toBeInTheDocument()
})

test('known-ticker sync reports explicit company-not-found without fabricating metadata', async () => {
  const user = userEvent.setup()
  server.use(
    enabled,
    summary,
    http.post(`${API_BASE_URL}/api/v1/admin/data/sync/ticker`, () => HttpResponse.json({ ticker: 'FAKE', state: 'COMPANY_NOT_FOUND', message: 'Company is not stored. AlphaPilot cannot safely infer custom metadata.' })),
  )
  renderApp('/admin/data')
  await user.type((await screen.findAllByLabelText('Ticker'))[1]!, 'fake')
  await user.click(screen.getByRole('button', { name: 'Sync stored ticker candles' }))
  expect(await screen.findByText(/FAKE: COMPANY_NOT_FOUND/)).toBeInTheDocument()
  expect(screen.getByText(/cannot safely infer/i)).toBeInTheDocument()
})

test('full sync starts a background job and renders provider-safe progress', async () => {
  const user = userEvent.setup()
  const job = { job_id: '12345678-abcd', state: 'RUNNING', requested_at: '2026-08-25T00:00:00Z', started_at: '2026-08-25T00:00:01Z', finished_at: null, start_date: '2025-07-21', end_date: '2026-08-25', progress: { total: 502, attempted: 100, synced: 99, skipped: 1, failed: 0, failed_tickers: [], stage: 'stock_candles', current_ticker: 'MSFT' }, operation: 'FULL_SYNC', provider: 'Alpaca', feed: 'iex', active_constituents: 502, companies_created: 0, companies_updated: 0, companies_unchanged: 502, memberships_added: 0, memberships_removed: 0, failed_stage: null, failed_ticker: null, error_code: null, error: null }
  server.use(
    enabled,
    summary,
    http.post(`${API_BASE_URL}/api/v1/admin/data/sync/all`, () => HttpResponse.json({ started: true, job })),
    http.get(`${API_BASE_URL}/api/v1/admin/data/sync/jobs/${job.job_id}`, () => HttpResponse.json({ ...job, state: 'SUCCEEDED', finished_at: '2026-08-25T00:01:00Z', progress: { ...job.progress, attempted: 502, synced: 500, skipped: 2 } })),
  )
  renderApp('/admin/data')
  await user.click(await screen.findByRole('button', { name: 'Full Sync' }))
  expect(await screen.findByRole('progressbar', { name: 'FULL SYNC progress' })).toHaveAttribute('aria-valuenow', '502')
  expect(screen.getByText('Completed.')).toBeInTheDocument()
  expect(await screen.findByText('500 / 2 / 0')).toBeInTheDocument()
  expect(document.body.textContent).not.toContain('SECRET_KEY')
})

test('admin navigation remains discoverable and unlocks when capability is enabled', async () => {
  server.use(enabled, summary)
  renderApp('/')
  expect(await screen.findByRole('link', { name: 'Data Management' })).toBeInTheDocument()
})

test('custom ticker Add & Sync exposes non-S&P result and management actions', async () => {
  const user = userEvent.setup()
  let tracked = false
  const item = { ticker: 'SBET', company_name: 'SharpLink Gaming, Inc.', exchange: 'NASDAQ', sector: null, is_custom_tracked: true, is_sp500_member: false, stored_candle_count: 277, first_candle_date: '2025-07-22', latest_candle_date: '2026-08-25' }
  server.use(
    enabled,
    summary,
    http.get(`${API_BASE_URL}/api/v1/admin/data/custom-tickers`, () => HttpResponse.json(tracked ? [item] : [])),
    http.post(`${API_BASE_URL}/api/v1/admin/data/custom-tickers`, async () => {
      await delay(50)
      tracked = true
      return HttpResponse.json({ ...item, state: 'TRACKED_AND_SYNCED', message: 'Custom ticker tracked and market data synchronized.' })
    }),
    http.post(`${API_BASE_URL}/api/v1/admin/data/custom-tickers/SBET/deactivate`, () => {
      tracked = false
      return HttpResponse.json({ ...item, state: 'DEACTIVATED', is_custom_tracked: false, message: 'Custom tracking deactivated; stored history was preserved.' })
    }),
  )
  renderApp('/admin/data')
  await user.type(await screen.findByLabelText('Custom ticker'), 'sbet')
  await user.click(screen.getByRole('button', { name: 'Add & Sync' }))
  expect(screen.getByRole('button', { name: 'Adding & syncing…' })).toBeDisabled()
  expect(await screen.findByText(/SBET: TRACKED_AND_SYNCED/)).toBeInTheDocument()
  expect(screen.getByText(/Tracked: Yes · S&P 500: No · Candles: 277/)).toBeInTheDocument()
  expect(await screen.findByRole('link', { name: 'Evaluate' })).toHaveAttribute('href', '/evaluate?ticker=SBET')
  expect(screen.getByRole('button', { name: 'Sync Candles' })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Deactivate Tracking' }))
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Deactivate Tracking' })).not.toBeInTheDocument())
})

test('custom onboarding reports S&P duplicate, invalid symbol, and provider failure safely', async () => {
  const user = userEvent.setup()
  let state = 'ALREADY_SP500'
  server.use(
    enabled,
    summary,
    http.post(`${API_BASE_URL}/api/v1/admin/data/custom-tickers`, () => HttpResponse.json({ ticker: 'AAPL', state, company_name: 'Apple Inc.', exchange: 'NASDAQ', sector: 'Technology', is_custom_tracked: false, is_sp500_member: true, stored_candle_count: 300, first_candle_date: '2025-01-01', latest_candle_date: '2026-08-25', message: state === 'METADATA_PROVIDER_FAILED' ? 'Company metadata provider failed safely.' : 'Ticker already exists as a current S&P 500 constituent.' })),
  )
  renderApp('/admin/data')
  const input = await screen.findByLabelText('Custom ticker')
  await user.type(input, 'aapl')
  await user.click(screen.getByRole('button', { name: 'Add & Sync' }))
  expect(await screen.findByText(/ALREADY_SP500/)).toBeInTheDocument()
  await user.clear(input)
  await user.type(input, 'INVALID!')
  expect(input).toHaveAttribute('pattern', '[A-Za-z0-9.-]+')
  await user.clear(input)
  state = 'METADATA_PROVIDER_FAILED'
  await user.type(input, 'FAIL')
  await user.click(screen.getByRole('button', { name: 'Add & Sync' }))
  expect(await screen.findByText(/Company metadata provider failed safely/)).toBeInTheDocument()
  expect(document.body.textContent).not.toContain('API_KEY')
})
