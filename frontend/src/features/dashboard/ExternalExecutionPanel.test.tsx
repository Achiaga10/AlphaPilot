import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { API_BASE_URL } from '../../api/client'
import { server } from '../../test/server'
import { ExternalExecutionPanel } from './ExternalExecutionPanel'

const portfolioId = '71111111-1111-4111-8111-111111111111'
const root = `${API_BASE_URL}/api/v1/forward-portfolio/${portfolioId}`
const baseAction = {
  id: 'case-1', forward_portfolio_id: portfolioId, forward_order_id: 'order-1', position_id: null,
  ticker: 'AAA', side: 'BUY', strategy_id: 'micho-150-v1', strategy_version: 1,
  broker: 'ALPACA', provenance: 'MANUAL_USER_RECORDED', source_signal_session: '2026-09-10',
  planned_execution_session: '2026-09-11', actual_virtual_execution_session: '2026-09-11',
  expected_timing: 'NEXT_STORED_SESSION_OPEN', planned_shares: 99, virtual_filled_shares: 99,
  virtual_order_status: 'FILLED', virtual_modeled_fill_price: '100.0500',
  loss_control_policy: 'SMA150_COMPLETED_CLOSE_EXIT', loss_control_boundary: '90',
  decision_reason: 'FINAL_ACTIONABLE_BUY', created_at: '2026-09-10T20:00:00Z',
  status: 'AWAITING_RECORD', reconciliation_status: 'MISSING_RECORD', due_status: 'OVERDUE_RECORDING',
  recorded_shares: 0, weighted_fill_price: null, recorded_notional: null, recorded_fees: null,
  fee_coverage_complete: false, share_variance_vs_planned: null, share_variance_vs_virtual: null,
  price_difference_per_share: null, price_difference_bps: null, virtual_notional: '9904.9500',
  notional_variance: null, timing_difference_seconds: null, skip_reason: null, fills: [], events: [],
}

function renderPanel() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(<QueryClientProvider client={queryClient}><ExternalExecutionPanel portfolioId={portfolioId} /></QueryClientProvider>)
}

function installJournal(action: Record<string, unknown> = { ...baseAction }) {
  let current: Record<string, unknown> = action
  const fills: Array<Record<string, unknown>> = []
  server.use(
    http.get(`${root}/external-actions`, () => HttpResponse.json([{ ...current, fills }])),
    http.get(`${root}/reconciliation`, () => HttpResponse.json([])),
    http.get(`${root}/execution-analytics`, () => HttpResponse.json({
      expected_actions: 1, recorded_actions: current.status === 'RECORDED' ? 1 : 0,
      skipped_actions: current.status === 'SKIPPED' ? 1 : 0, missing_records: 0, partial_actions: 0,
      actions_awaiting_execution: 0, actions_awaiting_recording: 1, diverged_actions: 0,
      recording_rate_pct: null, completed_fully_reconciled_trades: 0,
      matched_virtual_pnl: null, matched_recorded_execution_pnl: null, matched_pnl_difference: null,
    })),
    http.post(`${root}/external-actions/:caseId/fills`, async ({ request }) => {
      const body = await request.json() as Record<string, unknown>
      fills.push({ id: `fill-${fills.length + 1}`, ...body, source: 'MANUAL_USER_RECORDED', voided_at: null, void_reason: null })
      const recorded = fills.filter((fill) => !fill.voided_at).reduce((sum, fill) => sum + Number(fill.quantity), 0)
      current = { ...current, status: body.mark_complete ? 'RECORDED' : 'PARTIALLY_RECORDED',
        reconciliation_status: 'PRICE_DIVERGENCE', recorded_shares: recorded,
        weighted_fill_price: String(body.price), recorded_fees: body.fee,
        price_difference_per_share: '0.1200', price_difference_bps: '11.9940',
      }
      return HttpResponse.json({ ...current, fills })
    }),
    http.post(`${root}/external-actions/:caseId/skip`, () => {
      current = { ...current, status: 'SKIPPED', reconciliation_status: 'SKIPPED', skip_reason: 'MISSED_ENTRY' }
      return HttpResponse.json({ ...current, fills })
    }),
    http.post(`${root}/external-fills/:fillId/void`, async ({ params, request }) => {
      const body = await request.json() as { reason: string }
      const fill = fills.find((item) => item.id === params.fillId)
      if (fill) { fill.voided_at = '2026-09-12T10:00:00Z'; fill.void_reason = body.reason }
      current = { ...current, status: 'AWAITING_RECORD', recorded_shares: 0,
        weighted_fill_price: null, reconciliation_status: 'MISSING_RECORD' }
      return HttpResponse.json({ ...current, fills })
    }),
  )
}

test('shows action, records partial and final fill, displays backend comparison and audited correction', async () => {
  installJournal()
  const user = userEvent.setup()
  renderPanel()
  const card = await screen.findByRole('article', { name: 'AAA external BUY action' })
  expect(within(card).getByText(/MANUAL_USER_RECORDED/)).toBeInTheDocument()
  expect(within(card).getByText(/2026-09-11 open/)).toBeInTheDocument()
  await user.click(within(card).getByText('Record a user-observed BUY fill'))
  await user.type(within(card).getByLabelText('AAA fill quantity'), '40')
  await user.type(within(card).getByLabelText('AAA fill price'), '100.17')
  await user.type(within(card).getByLabelText('AAA executed at'), '2026-09-11T09:35')
  await user.click(within(card).getByRole('checkbox', { name: /Final fill/ }))
  await user.click(within(card).getByRole('button', { name: 'Record observed fill' }))
  expect(await within(card).findByText('PARTIALLY RECORDED')).toBeInTheDocument()
  expect(within(card).getByText('$0.12 · 11.9940 bps')).toBeInTheDocument()
  await user.type(within(card).getByLabelText('AAA fill quantity'), '59')
  await user.type(within(card).getByLabelText('AAA fill price'), '100.17')
  await user.click(within(card).getByRole('checkbox', { name: /Final fill/ }))
  await user.click(within(card).getByRole('button', { name: 'Record observed fill' }))
  const recordedCard = await screen.findByRole('article', { name: 'AAA external BUY action' })
  expect(await within(recordedCard).findByText('RECORDED')).toBeInTheDocument()
  await user.click(within(recordedCard).getByText(/User-recorded fills and correction audit/))
  await user.click(within(recordedCard).getAllByRole('button', { name: 'Void / correct fill' })[0]!)
  await user.type(within(recordedCard).getByLabelText('Correction reason'), 'Mistyped fill')
  await user.click(within(recordedCard).getByRole('button', { name: 'Confirm void' }))
  expect(await screen.findByText(/correction: Mistyped fill/)).toBeInTheDocument()
})

test('skip is explicit and does not claim broker execution', async () => {
  installJournal()
  const user = userEvent.setup()
  renderPanel()
  const card = await screen.findByRole('article', { name: 'AAA external BUY action' })
  await user.click(within(card).getByRole('button', { name: 'Mark external action skipped' }))
  await user.selectOptions(within(card).getByLabelText('AAA skip reason'), 'MISSED_ENTRY')
  await user.click(within(card).getByRole('button', { name: 'Confirm skip' }))
  await waitFor(() => expect(screen.getByRole('article', { name: 'AAA external BUY action' })).toHaveTextContent('User skipped: MISSED ENTRY'))
  const skippedCard = screen.getByRole('article', { name: 'AAA external BUY action' })
  expect(within(skippedCard).getByText(/virtual Forward lifecycle remains independent/)).toBeInTheDocument()
  expect(screen.getByText(/OBSERVATIONAL ONLY/)).toBeInTheDocument()
})
