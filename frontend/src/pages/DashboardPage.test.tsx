import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { API_BASE_URL } from '../api/client'
import { server } from '../test/server'
import { renderApp } from '../test/renderApp'

test('dashboard renders research framing and empty portfolio state', async () => {
  renderApp('/')
  expect(screen.getByRole('heading', { name: 'Research Decision Dashboard' })).toBeInTheDocument()
  expect(screen.getByText('No portfolio plan yet')).toBeInTheDocument()
  expect(await screen.findByText('Backend connected')).toBeInTheDocument()
  expect(screen.getByText(/not live-trading validated/i)).toBeInTheDocument()
})

test('backend unavailable is distinguished from a domain empty state', async () => {
  server.use(http.get(`${API_BASE_URL}/api/v1/health/`, () => HttpResponse.error()))
  renderApp('/')
  expect(await screen.findByText('Backend unavailable')).toBeInTheDocument()
  expect(screen.getByText('No portfolio plan yet')).toBeInTheDocument()
})

test('navigation reaches every required route', async () => {
  const user = userEvent.setup()
  renderApp('/')
  await user.click(screen.getByRole('link', { name: 'Portfolio plan' }))
  expect(await screen.findByRole('heading', { name: 'Portfolio Plan', level: 1 })).toBeInTheDocument()
  await user.click(screen.getByRole('link', { name: 'Evaluate stock' }))
  expect(await screen.findByRole('heading', { name: 'Evaluate Stock' })).toBeInTheDocument()
  await user.click(screen.getByRole('link', { name: 'Research settings' }))
  expect(await screen.findByRole('heading', { name: 'Research Settings' })).toBeInTheDocument()
})

test('dashboard metadata includes selection policy and evaluated versus approved counts', async () => {
  const user = userEvent.setup()
  renderApp('/portfolio')
  await user.click(await screen.findByRole('button', { name: 'Generate Portfolio Plan' }))
  await screen.findByRole('heading', { name: 'Portfolio plan generated' })
  await user.click(screen.getByRole('link', { name: 'Dashboard' }))
  expect(await screen.findByText('RS20 ranking')).toBeInTheDocument()
  expect(screen.getByText(/1 \/ 3/, { selector: 'strong' })).toBeInTheDocument()
})
