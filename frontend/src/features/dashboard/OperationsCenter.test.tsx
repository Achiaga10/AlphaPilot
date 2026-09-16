import { screen } from '@testing-library/react'
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
