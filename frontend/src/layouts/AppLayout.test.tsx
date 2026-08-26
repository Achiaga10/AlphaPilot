import { screen } from '@testing-library/react'
import { renderApp } from '../test/renderApp'

test('sidebar uses the real AlphaPilot image and removes placeholder branding', async () => {
  renderApp('/')
  const logo = screen.getByRole('img', { name: 'AlphaPilot' })
  expect(logo).toHaveAttribute('src', expect.stringContaining('alphapilot-logo.png'))
  expect(logo).toHaveClass('brand__logo')
  expect(document.querySelector('.brand__mark')).not.toBeInTheDocument()
  expect(screen.getByText('Research Decision Dashboard', { selector: '.brand__subtitle' })).toBeInTheDocument()
  expect(await screen.findByText('Backend connected')).toBeInTheDocument()
})

test('admin navigation is hidden when the safe feature gate is disabled', async () => {
  renderApp('/')
  await screen.findByText('Backend connected')
  expect(screen.queryByRole('link', { name: 'Research admin' })).not.toBeInTheDocument()
})
