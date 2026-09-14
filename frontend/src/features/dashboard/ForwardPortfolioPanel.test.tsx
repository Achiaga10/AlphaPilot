import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { API_BASE_URL } from '../../api/client'
import { renderApp } from '../../test/renderApp'
import { server } from '../../test/server'

const portfolio = {
  id: '71111111-1111-4111-8111-111111111111', strategy_id: 'micho-150-v1',
  strategy_version: 1, execution_mode: 'VIRTUAL', broker_execution_mode: 'MANUAL_EXTERNAL',
  status: 'ACTIVE', created_at: '2026-09-10T20:00:00Z', updated_at: '2026-09-11T20:00:00Z',
  forward_start_session: '2026-09-10', initial_cash: '100000.0000',
  cash_balance: '90095.0500', equity: '100193.0500', realized_pnl: '0.0000', revision: 2,
  last_processed_session: '2026-09-11', last_successful_cycle: '2026-09-11T20:16:00Z',
  last_error: null,
}

function installForwardHandlers() {
  let current = { ...portfolio }
  server.use(
    http.get(`${API_BASE_URL}/api/v1/forward-portfolio/current`, () => HttpResponse.json(current)),
    http.get(`${API_BASE_URL}/api/v1/forward-portfolio/:id/positions`, () => HttpResponse.json([{
      id: 'position-1', ticker: 'AAA', status: 'OPEN', shares: 99,
      signal_session: '2026-09-10', entry_session: '2026-09-11', raw_entry_price: '100',
      modeled_entry_price: '100.05', entry_friction: '4.95', cost_basis: '9904.95',
      last_mark_session: '2026-09-11', last_close: '102', market_value: '10098',
      unrealized_pnl: '193.05', unrealized_return_pct: '1.949',
      loss_control_policy: 'SMA150_COMPLETED_CLOSE_EXIT',
      loss_control_boundary: '90', loss_control_trigger: 'COMPLETED_DAILY_CLOSE_BELOW',
      loss_control_source: 'APPROVED_SYSTEM_POLICY', risk_per_share: '10.05',
      planned_risk_dollars: '994.95', holding_sessions: 1, holding_calendar_days: 0,
      exit_signal_session: null, closed_session: null, management_status: 'OPEN',
    }])),
    http.get(`${API_BASE_URL}/api/v1/forward-portfolio/:id/orders`, () => HttpResponse.json([{
      id: 'order-1', ticker: 'BBB', side: 'ENTRY', status: 'PENDING',
      source_signal_session: '2026-09-11', planned_execution_session: null,
      actual_execution_session: null, approved_allocation: '9500', planned_shares: 50,
      filled_shares: null, raw_fill_price: null, modeled_fill_price: null,
      friction_bps: '5', friction_dollars: null, reason_code: 'FINAL_ACTIONABLE_BUY',
      strategy_id: 'micho-150-v1', strategy_version: 1, ranking_score: '0.05',
      ranking_position: 1, loss_control_policy: 'SMA150_COMPLETED_CLOSE_EXIT',
      loss_control_boundary: '170', loss_control_trigger: 'COMPLETED_DAILY_CLOSE_BELOW',
      risk_per_share: '20', planned_risk_dollars: '1000', planned_risk_pct: '1',
      evidence: {}, created_at: '2026-09-11T20:16:00Z',
    }])),
    http.get(`${API_BASE_URL}/api/v1/forward-portfolio/:id/trades`, () => HttpResponse.json([])),
    http.get(`${API_BASE_URL}/api/v1/forward-portfolio/:id/events`, () => HttpResponse.json([{
      id: 'event-1', event_type: 'POSITION_OPENED', trading_session: '2026-09-11',
      ticker: 'AAA', strategy_id: 'micho-150-v1', reason_code: 'ENTRY_FILLED',
      numeric_provenance: {}, created_at: '2026-09-11T20:16:00Z',
    }])),
    http.get(`${API_BASE_URL}/api/v1/forward-portfolio/:id/analytics`, () => HttpResponse.json({
      starting_equity: '100000', current_equity: '100193.05', cash: '90095.05',
      market_value: '10098', realized_pnl: '0', unrealized_pnl: '193.05', total_pnl: '193.05',
      net_return_pct: '0.19305', max_drawdown_pct: '0', completed_trades: 0, open_trades: 1,
      win_rate_pct: null, profit_factor: null, expectancy: null, average_winner: null,
      average_loser: null, worst_trade: null, average_holding_sessions: null,
      turnover_pct: '9.90495', friction_dollars: '4.95', current_exposure_pct: '10.08',
      average_exposure_pct: '10.08',
      max_concurrent_positions: 1, stop_exits: 0, strategy_exits: 0,
    })),
    http.get(`${API_BASE_URL}/api/v1/forward-portfolio/:id/health`, () => HttpResponse.json({
      scheduler_running: true, scheduler_status: 'SUCCEEDED', portfolio_status: current.status,
      last_successful_cycle: current.last_successful_cycle, last_processed_session: '2026-09-11',
      latest_completed_market_session: '2026-09-11', pending_sessions: 0, data_ready: true,
      last_error: null, latest_cycle_status: 'COMPLETED',
    })),
    http.post(`${API_BASE_URL}/api/v1/forward-portfolio/:id/pause`, () => {
      current = { ...current, status: 'PAUSED', revision: 3 }
      return HttpResponse.json(current)
    }),
  )
}

test('shows deliberate initialization and the broker boundary when no Forward portfolio exists', async () => {
  renderApp('/')
  expect(await screen.findByRole('heading', { name: 'Micho Forward Portfolio' })).toBeInTheDocument()
  expect(screen.getByText(/does not connect to or read your Alpaca balance/i)).toBeInTheDocument()
  expect(screen.getByLabelText('Initial virtual cash')).toHaveValue(null)
  expect(screen.getByLabelText('Forward start session')).toBeRequired()
  expect(screen.getByText(/Forward automation is not enabled for EMA20/i)).toBeInTheDocument()
})

test('renders backend-owned Forward state and explicitly confirms pause', async () => {
  installForwardHandlers()
  const user = userEvent.setup()
  renderApp('/')
  const panel = (await screen.findByRole('heading', { name: 'Micho Forward Portfolio' })).closest('section')
  if (!panel) throw new Error('Forward panel not found')
  expect(within(panel).getByText(/VIRTUAL FORWARD PORTFOLIO/)).toBeInTheDocument()
  expect(within(panel).getByText(/manual external broker/i)).toBeInTheDocument()
  expect(await within(panel).findByText('AAA')).toBeInTheDocument()
  expect(within(panel).getByText('$193.05')).toBeInTheDocument()
  expect(within(panel).getByText(/\$193\.05 · 1\.95%/)).toBeInTheDocument()
  expect(within(panel).getByText(/BBB · PENDING VIRTUAL ENTRY/)).toBeInTheDocument()
  expect(within(panel).getByText(/Scheduler running/)).toBeInTheDocument()
  await user.click(within(panel).getByRole('button', { name: 'Pause new entries' }))
  expect(within(panel).getByRole('alertdialog', { name: 'Confirm pause' })).toHaveTextContent(
    /Existing positions continue automatic Micho exit management/,
  )
  await user.click(within(panel).getByRole('button', { name: 'Confirm pause' }))
  expect(await within(panel).findByText('PAUSED')).toBeInTheDocument()
})
