import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderApp } from '../test/renderApp'

test('every plan-affecting form area marks the displayed result stale and regeneration clears it', async () => {
  const user = userEvent.setup()
  renderApp('/portfolio')
  await user.click(await screen.findByRole('button', { name: 'Generate Portfolio Plan' }))
  await screen.findByRole('heading', { name: 'Portfolio plan generated' })

  const expectDirty = async () => expect(await screen.findByText('Displayed plan is stale')).toBeInTheDocument()
  const regenerate = async () => {
    await user.click(screen.getByRole('button', { name: 'Regenerate plan' }))
    await waitFor(() => expect(screen.queryByText('Displayed plan is stale')).not.toBeInTheDocument())
  }

  await user.clear(screen.getByLabelText('Cash (USD)'))
  await user.type(screen.getByLabelText('Cash (USD)'), '90000')
  await expectDirty(); await regenerate()

  await user.selectOptions(screen.getByLabelText('Strategy'), 'micho-150')
  await expectDirty(); await regenerate()

  await user.selectOptions(screen.getByLabelText('Selection policy'), 'ticker-ascending')
  await expectDirty(); await regenerate()

  await user.selectOptions(screen.getByLabelText('Sizing policy'), 'atr-risk')
  await expectDirty(); await regenerate()

  await user.clear(screen.getByLabelText('Requested analysis date'))
  await user.type(screen.getByLabelText('Requested analysis date'), '2026-08-19')
  await expectDirty(); await regenerate()

  await user.type(screen.getByLabelText('Optional ticker scope'), 'AAPL')
  await expectDirty(); await regenerate()

  await user.click(screen.getByRole('button', { name: 'Add position' }))
  await expectDirty()
})

test('failed regeneration leaves the prior plan visible and stale', async () => {
  const user = userEvent.setup()
  renderApp('/portfolio')
  await user.click(await screen.findByRole('button', { name: 'Generate Portfolio Plan' }))
  await screen.findByRole('heading', { name: 'Portfolio plan generated' })
  await user.type(screen.getByLabelText('Optional ticker scope'), 'MSFT')
  expect(await screen.findByText('Displayed plan is stale')).toBeInTheDocument()
  expect(screen.getByText('Portfolio plan generated')).toBeInTheDocument()
})
