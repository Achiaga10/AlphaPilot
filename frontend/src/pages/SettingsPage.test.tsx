import { screen } from '@testing-library/react'
import { renderApp } from '../test/renderApp'

test('settings loads backend defaults and research classifications', async () => {
  renderApp('/settings')
  expect(await screen.findByText('14 trading bars')).toBeInTheDocument()
  expect(screen.getByText('8.00%')).toBeInTheDocument()
  expect(screen.getAllByText('Promising research baseline')).toHaveLength(3)
  expect(screen.getAllByText('Research only')).toHaveLength(3)
  expect(screen.queryByText('PRODUCTION READY')).not.toBeInTheDocument()
  expect(screen.getByText(/HYBRID exit with the frozen 2% threshold/i)).toBeInTheDocument()
  expect(screen.getByText(/V1 with BOTH entry mode/i)).toBeInTheDocument()
})
