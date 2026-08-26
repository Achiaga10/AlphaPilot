import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { InfoTooltip } from './InfoTooltip'

test('information tooltip is described, focusable, hoverable, and click/tap toggleable', async () => {
  const user = userEvent.setup()
  render(<InfoTooltip label="About RS20">Twenty-bar relative strength.</InfoTooltip>)
  const trigger = screen.getByRole('button', { name: 'About RS20' })
  expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  await user.hover(trigger)
  const tooltip = screen.getByRole('tooltip')
  expect(trigger).toHaveAttribute('aria-describedby', tooltip.id)
  expect(tooltip).toHaveTextContent('Twenty-bar relative strength.')
  await user.unhover(trigger)
  expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  await user.tab()
  expect(trigger).toHaveFocus()
  expect(screen.getByRole('tooltip')).toBeInTheDocument()
  await user.tab()
  expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  await user.click(trigger)
  expect(screen.getByRole('tooltip')).toBeInTheDocument()
  await user.click(trigger)
  expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
})
