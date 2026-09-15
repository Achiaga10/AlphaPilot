import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { API_BASE_URL } from '../../api/client'
import { server } from '../../test/server'
import { AlpacaReadOnlyPanel } from './AlpacaReadOnlyPanel'

const execution = {
  id: 'execution-1', provenance: 'ALPACA_READ_ONLY_SYNC', environment: 'PAPER',
  broker_activity_id: 'activity-1', broker_order_id: 'order-1', symbol: 'AAA', side: 'BUY',
  quantity: '100.00000000', price: '100.60000000', fee: null,
  executed_at: '2026-09-15T14:35:00Z', match_state: 'UNMATCHED',
  match_reason: 'OUTSIDE_FORWARD_OR_EXECUTION_WINDOW', external_case_id: null,
  matched_at: null, ignored_reason: null,
}

const action = {
  id: 'case-1', forward_order_id: 'order-forward-1', ticker: 'AAA', side: 'BUY',
  status: 'AWAITING_RECORD', reconciliation_status: 'MISSING_RECORD', planned_shares: 100,
  recorded_shares: 0, fills: [], broker_executions: [], events: [],
}

test('shows PAPER read-only state, comparison, and explicit manual matching without trading controls', async () => {
  let unmatched = [{ ...execution }]
  server.use(
    http.get(`${API_BASE_URL}/api/v1/broker/alpaca/status`, () => HttpResponse.json({ enabled: true, configured: true, environment: 'PAPER', scheduler_running: true, status: 'SUCCEEDED', last_attempt_at: '2026-09-15T14:36:00Z', last_success_at: '2026-09-15T14:36:00Z', last_error: null, data_age_seconds: 30, account_snapshots: 1, positions: 1, orders: 1, executions: 1, unmatched_executions: unmatched.length, interval_seconds: 300, initial_lookback_days: 14, overlap_minutes: 10, provenance: 'ALPACA_READ_ONLY_SYNC' })),
    http.get(`${API_BASE_URL}/api/v1/broker/alpaca/account`, () => HttpResponse.json({ environment: 'PAPER', status: 'ACTIVE', currency: 'USD', cash: '9000.12', equity: '10100.34', buying_power: '18000.24', observed_at: '2026-09-15T14:36:00Z' })),
    http.get(`${API_BASE_URL}/api/v1/broker/alpaca/positions`, () => HttpResponse.json([{ environment: 'PAPER', symbol: 'AAA', side: 'LONG', quantity: '100.00000000', average_entry_price: '100.25', current_price: '101.50', market_value: '10150', unrealized_pnl: '125', observed_at: '2026-09-15T14:36:00Z' }])),
    http.get(`${API_BASE_URL}/api/v1/broker/alpaca/orders`, () => HttpResponse.json([])),
    http.get(`${API_BASE_URL}/api/v1/broker/alpaca/activity`, () => HttpResponse.json(unmatched)),
    http.get(`${API_BASE_URL}/api/v1/broker/alpaca/unmatched`, () => HttpResponse.json(unmatched)),
    http.get(`${API_BASE_URL}/api/v1/forward-portfolio/portfolio-1/external-actions`, () => HttpResponse.json([action])),
    http.get(`${API_BASE_URL}/api/v1/forward-portfolio/portfolio-1/reconciliation`, () => HttpResponse.json([])),
    http.get(`${API_BASE_URL}/api/v1/forward-portfolio/portfolio-1/execution-analytics`, () => HttpResponse.json({ expected_actions: 1, recorded_actions: 0, skipped_actions: 0, missing_records: 1, partial_actions: 0, actions_awaiting_execution: 0, actions_awaiting_recording: 1, diverged_actions: 0, recording_rate_pct: null, completed_fully_reconciled_trades: 0, matched_virtual_pnl: null, matched_recorded_execution_pnl: null, matched_pnl_difference: null, manual_actions: 0, broker_actions: 0, conflict_actions: 0 })),
    http.post(`${API_BASE_URL}/api/v1/broker/alpaca/activity/execution-1/manual-match`, () => {
      unmatched = []
      return HttpResponse.json({ ...execution, match_state: 'MANUAL_MATCHED', external_case_id: 'case-1', matched_at: '2026-09-15T14:40:00Z' })
    }),
  )
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(<QueryClientProvider client={queryClient}><AlpacaReadOnlyPanel portfolioId="portfolio-1" forwardPositions={[{ ticker: 'AAA', status: 'OPEN', shares: 100, modeled_entry_price: '100.05' } as never]} /></QueryClientProvider>)
  expect(await screen.findByRole('heading', { name: 'ALPACA — READ ONLY' })).toBeInTheDocument()
  expect(screen.getByText(/cannot submit, replace, cancel, or close/)).toBeInTheDocument()
  expect(await screen.findByText('$10,100.34')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /buy|sell|cancel order|close position/i })).not.toBeInTheDocument()
  const activityItem = (await screen.findAllByText(/AAA · BUY 100.00000000/))[0]!.closest('li')
  expect(activityItem).not.toBeNull()
  const user = userEvent.setup()
  await user.click(within(activityItem!).getByRole('button', { name: 'Link to Forward action' }))
  expect(within(activityItem!).getByRole('alertdialog')).toBeInTheDocument()
  await user.click(within(activityItem!).getByRole('button', { name: 'Confirm match' }))
  expect(await screen.findByText('No unmatched Alpaca fill activity.')).toBeInTheDocument()
})

test('surfaces stale failure health and preserves ambiguous and conflicting evidence', async () => {
  const ambiguous = { ...execution, id: 'execution-ambiguous', match_state: 'AMBIGUOUS', match_reason: 'MULTIPLE_FORWARD_CANDIDATES' }
  const conflict = { ...execution, id: 'execution-conflict', broker_activity_id: 'activity-conflict', match_state: 'CONFLICT', match_reason: 'MANUAL_AND_BROKER_FACTS_DIFFER', external_case_id: 'case-1' }
  server.use(
    http.get(`${API_BASE_URL}/api/v1/broker/alpaca/status`, () => HttpResponse.json({ enabled: true, configured: true, environment: 'PAPER', scheduler_running: true, status: 'FAILED', last_attempt_at: '2026-09-15T14:40:00Z', last_success_at: '2026-09-15T14:30:00Z', last_error: 'PROVIDER_UNAVAILABLE', data_age_seconds: 600, account_snapshots: 1, positions: 0, orders: 1, executions: 2, unmatched_executions: 1, interval_seconds: 300, initial_lookback_days: 14, overlap_minutes: 10, provenance: 'ALPACA_READ_ONLY_SYNC' })),
    http.get(`${API_BASE_URL}/api/v1/broker/alpaca/account`, () => HttpResponse.json(null)),
    http.get(`${API_BASE_URL}/api/v1/broker/alpaca/positions`, () => HttpResponse.json([])),
    http.get(`${API_BASE_URL}/api/v1/broker/alpaca/orders`, () => HttpResponse.json([])),
    http.get(`${API_BASE_URL}/api/v1/broker/alpaca/activity`, () => HttpResponse.json([ambiguous, conflict])),
    http.get(`${API_BASE_URL}/api/v1/broker/alpaca/unmatched`, () => HttpResponse.json([ambiguous])),
    http.get(`${API_BASE_URL}/api/v1/forward-portfolio/portfolio-1/external-actions`, () => HttpResponse.json([{ ...action, status: 'PARTIALLY_RECORDED', reconciliation_status: 'BROKER_CONFLICT', canonical_execution_source: 'ALPACA_READ_ONLY_SYNC', broker_match_state: 'CONFLICT', recorded_shares: '40.50000000', broker_executions: [conflict] }])),
    http.get(`${API_BASE_URL}/api/v1/forward-portfolio/portfolio-1/reconciliation`, () => HttpResponse.json([])),
    http.get(`${API_BASE_URL}/api/v1/forward-portfolio/portfolio-1/execution-analytics`, () => HttpResponse.json({ expected_actions: 1, recorded_actions: 0, skipped_actions: 0, missing_records: 0, partial_actions: 1, actions_awaiting_execution: 0, actions_awaiting_recording: 1, diverged_actions: 1, recording_rate_pct: null, completed_fully_reconciled_trades: 0, matched_virtual_pnl: null, matched_recorded_execution_pnl: null, matched_pnl_difference: null, manual_actions: 0, broker_actions: 1, conflict_actions: 1 })),
  )
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(<QueryClientProvider client={queryClient}><AlpacaReadOnlyPanel portfolioId="portfolio-1" forwardPositions={[]} /></QueryClientProvider>)
  expect(await screen.findByText(/FAILED/)).toBeInTheDocument()
  expect(screen.getByText('PROVIDER_UNAVAILABLE')).toBeInTheDocument()
  expect(screen.getAllByText(/AMBIGUOUS/).length).toBeGreaterThan(0)
  expect(screen.getByText(/MULTIPLE FORWARD CANDIDATES/)).toBeInTheDocument()
  expect(screen.getByText('No Alpaca account snapshot stored.')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /buy|sell|cancel order|close position/i })).not.toBeInTheDocument()
})
