import { screen } from '@testing-library/react'
import { renderApp } from '../test/renderApp'
import { http, HttpResponse } from 'msw'
import { API_BASE_URL } from '../api/client'
import { server } from '../test/server'

test('settings loads backend defaults and research classifications', async () => {
  renderApp('/settings')
  expect(await screen.findByText('14 trading bars')).toBeInTheDocument()
  expect(screen.getByText('8.00%')).toBeInTheDocument()
  expect(screen.getAllByText('Promising research baseline')).toHaveLength(2)
  expect(screen.queryByText('PRODUCTION READY')).not.toBeInTheDocument()
  expect(screen.getByText('HYBRID exit with frozen 2% threshold')).toBeInTheDocument()
  expect(screen.getByText(/Close below SMA150/i)).toBeInTheDocument()
  expect(screen.getByText('ema20-pullback-v1 v1')).toBeInTheDocument()
  expect(screen.getByText('micho-150-v1 v1')).toBeInTheDocument()
})

test('settings rejects malformed backend profile data safely', async () => {
  server.use(
    http.get(`${API_BASE_URL}/api/v1/portfolio/strategy-profiles`, () =>
      HttpResponse.json([{ profile_id: 'unsafe', sizing_policy: 'invented' }]),
    ),
  )
  renderApp('/settings')
  expect(await screen.findByRole('alert')).toHaveTextContent(/invalid response/i)
  expect(screen.queryByText('unsafe')).not.toBeInTheDocument()
})
