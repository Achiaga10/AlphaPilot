import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { API_BASE_URL } from '../../api/client'
import { renderApp } from '../../test/renderApp'
import { operationsHealthFixture, server } from '../../test/server'

test('renders healthy operations with disabled broker as informational only', async () => {
  renderApp('/')
  expect(await screen.findByRole('heading', { name: 'Operations Center' })).toBeInTheDocument()
  expect(await screen.findByText('HEALTHY')).toBeInTheDocument()
  expect(screen.getByText('BROKER SYNC DISABLED')).toBeInTheDocument()
  expect(screen.getByText('UNKNOWN / NOT EVALUATED')).toBeInTheDocument()
  expect(screen.getByText(/cannot trade, change Micho decisions/)).toBeInTheDocument()
})

test('prioritizes a critical overdue manual exit and permits acknowledgement', async () => {
  const user = userEvent.setup()
  let acknowledgements = 0
  const critical = {
    ...operationsHealthFixture.active_incidents[0],
    id: 'critical-exit',
    incident_type: 'MANUAL_EXIT_ACTION_OVERDUE',
    severity: 'CRITICAL',
    source_domain: 'EXTERNAL_EXECUTION',
    summary: 'Manual exit action is overdue for APA',
    evidence: { ticker: 'APA', expected_session: '2026-09-14' },
  }
  server.use(
    http.get(`${API_BASE_URL}/api/v1/operations/health`, () => HttpResponse.json({
      ...operationsHealthFixture,
      overall_health: 'DEGRADED', critical_count: 1, info_count: 0,
      active_incidents: [critical],
    })),
    http.post(`${API_BASE_URL}/api/v1/operations/incidents/:incidentId/acknowledge`, () => {
      acknowledgements += 1
      return HttpResponse.json({ ...critical, status: 'ACKNOWLEDGED' })
    }),
  )
  renderApp('/')
  expect(await screen.findByText('DEGRADED')).toBeInTheDocument()
  expect(screen.getByText('MANUAL EXIT ACTION OVERDUE')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Acknowledge' }))
  await user.click(screen.getByRole('button', { name: 'Confirm acknowledgement' }))
  expect(acknowledgements).toBe(1)
})

test('shows drift only from an authoritative snapshot and retains resolved history', async () => {
  server.use(
    http.get(`${API_BASE_URL}/api/v1/operations/health`, () => HttpResponse.json({
      ...operationsHealthFixture,
      broker: { ...operationsHealthFixture.broker, enabled: true, configured: true, status: 'SUCCEEDED', snapshot_authoritative: true },
      position_drifts: [{ ticker: 'APA', forward_quantity: '100', broker_quantity: '95', difference: '-5', evaluated_at: '2026-09-15T17:00:00Z' }],
    })),
    http.get(`${API_BASE_URL}/api/v1/operations/incidents`, () => HttpResponse.json([{
      ...operationsHealthFixture.active_incidents[0], id: 'resolved-1', status: 'RESOLVED', resolved_at: '2026-09-15T16:00:00Z', occurrence: 2,
    }])),
  )
  renderApp('/')
  expect((await screen.findAllByText('APA')).length).toBeGreaterThan(0)
  expect(screen.queryByText(/Drift is unknown and not evaluated/)).not.toBeInTheDocument()
  expect(screen.getByText('Resolved incident history (1)')).toBeInTheDocument()
})

test('shows disabled notification delivery and backend-owned suppression state', async () => {
  renderApp('/')
  expect(await screen.findByRole('heading', { name: 'Notification Delivery' })).toBeInTheDocument()
  const operations = screen.getByRole('heading', { name: 'Operations Center' }).closest('section')!
  expect(within(operations).getByText('Disabled')).toBeInTheDocument()
  expect(within(operations).getByText(/NOT ELIGIBLE/)).toBeInTheDocument()
  expect(within(operations).getByRole('button', { name: 'Send test email' })).toBeDisabled()
})

test('edits preferences, queues test email, shows history and retries failure', async () => {
  const user = userEvent.setup()
  let preferencesSaved = 0
  let testsQueued = 0
  let retries = 0
  const notification = {
    id: 'notification-1', incident_id: 'critical-exit', channel: 'EMAIL', status: 'DELIVERED',
    kind: 'INCIDENT', priority: 'CRITICAL', transition: 'OPENED', generation: 1,
    recipient: 'operator@example.com', subject: '[AlphaPilot][CRITICAL] Manual exit overdue — APA',
    deduplication_key: 'incident:critical-exit:OPENED:1:EMAIL', trading_session: null,
    scheduled_at: '2026-09-16T12:00:00Z', next_attempt_at: '2026-09-16T12:00:00Z',
    sent_at: '2026-09-16T12:00:01Z', last_attempt_at: '2026-09-16T12:00:00Z',
    attempt_count: 1, failure_category: null, provider_message_reference: 'smtp-1',
    created_at: '2026-09-16T12:00:00Z', updated_at: '2026-09-16T12:00:01Z', attempts: [],
  }
  const critical = {
    ...operationsHealthFixture.active_incidents[0], id: 'critical-exit',
    incident_type: 'MANUAL_EXIT_ACTION_OVERDUE', severity: 'CRITICAL',
    source_domain: 'EXTERNAL_EXECUTION', summary: 'Manual exit action is overdue for APA',
    evidence: { ticker: 'APA', side: 'SELL' }, notification_state: 'DELIVERED',
  }
  server.use(
    http.get(`${API_BASE_URL}/api/v1/operations/health`, () => HttpResponse.json({
      ...operationsHealthFixture, overall_health: 'DEGRADED', critical_count: 1,
      info_count: 0, active_incidents: [critical],
    })),
    http.get(`${API_BASE_URL}/api/v1/notifications/status`, () => HttpResponse.json({
      enabled: true, email_enabled: true, configured: true, worker_running: true,
      queue_depth: 1, pending_count: 1, failed_count: 1,
      last_delivery_at: '2026-09-16T12:00:01Z', last_error: 'CONNECTION',
    })),
    http.get(`${API_BASE_URL}/api/v1/notifications/preferences`, () => HttpResponse.json({
      notifications_enabled: true, email_enabled: true, recipient: 'operator@example.com',
      warning_enabled: true, critical_enabled: true, recovery_enabled: true,
      daily_summary_enabled: false,
    })),
    http.get(`${API_BASE_URL}/api/v1/notifications`, () => HttpResponse.json([
      notification, { ...notification, id: 'notification-2', status: 'FAILED', priority: 'WARNING', subject: '[AlphaPilot][WARNING] Forward engine stale' },
    ])),
    http.put(`${API_BASE_URL}/api/v1/notifications/preferences`, async ({ request }) => {
      preferencesSaved += 1
      return HttpResponse.json(await request.json())
    }),
    http.post(`${API_BASE_URL}/api/v1/notifications/test`, () => {
      testsQueued += 1
      return HttpResponse.json({ ...notification, id: 'test-1', status: 'PENDING', kind: 'TEST', priority: 'TEST' }, { status: 201 })
    }),
    http.post(`${API_BASE_URL}/api/v1/notifications/:notificationId/retry`, () => {
      retries += 1
      return HttpResponse.json({ ...notification, id: 'notification-2', status: 'RETRY_PENDING' })
    }),
  )
  renderApp('/')
  await screen.findByRole('heading', { name: 'Notification Delivery' })
  const operations = screen.getByRole('heading', { name: 'Operations Center' }).closest('section')!
  expect(within(operations).getByText('Enabled')).toBeInTheDocument()
  expect(within(operations).getByText('1 / 1')).toBeInTheDocument()
  expect(within(operations).getByText(/External notification:/).parentElement).toHaveTextContent('DELIVERED')
  await user.click(within(operations).getByText('Notification preferences'))
  await user.click(within(operations).getByRole('checkbox', { name: 'Daily Operations summary' }))
  await user.click(within(operations).getByRole('button', { name: 'Save notification preferences' }))
  expect(preferencesSaved).toBe(1)
  await user.click(within(operations).getByRole('button', { name: 'Send test email' }))
  expect(await within(operations).findByText(/TEST notification queued/)).toBeInTheDocument()
  expect(testsQueued).toBe(1)
  await user.click(within(operations).getByText('Notification history (2)'))
  expect(within(operations).getByText('[AlphaPilot][WARNING] Forward engine stale')).toBeInTheDocument()
  await user.click(within(operations).getByRole('button', { name: 'Retry' }))
  expect(retries).toBe(1)
  expect(within(operations).queryByRole('button', { name: /submit|cancel order|buy|sell/i })).not.toBeInTheDocument()
})
