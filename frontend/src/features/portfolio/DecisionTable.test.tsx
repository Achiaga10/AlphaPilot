import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { planFixture } from '../../test/fixtures'
import { DecisionTable } from './DecisionTable'

test('equal-slot uses not-applicable risk semantics and exposes frozen exit guidance', async () => {
  const user = userEvent.setup()
  render(<DecisionTable decisions={[planFixture.decisions[0]!]} sizingPolicy="equal-slot" />)
  await user.click(screen.getByText('Decision details'))
  expect(screen.getAllByText('Not used by Equal-slot')).toHaveLength(5)
  expect(screen.getByRole('heading', { name: 'Exit Guidance' })).toBeInTheDocument()
  expect(screen.getByText('None in current strategy')).toBeInTheDocument()
  expect(screen.getByText('29.90%')).toBeInTheDocument()
  expect(screen.getByText(/not live monitoring/i)).toBeInTheDocument()
})

test('candidate rank tooltip explains that recommendation priority is optional', async () => {
  const user = userEvent.setup()
  render(<DecisionTable decisions={[planFixture.decisions[0]!]} rankByTicker={{ NVDA: 1 }} />)
  await user.click(screen.getByLabelText('About candidate rank'))
  expect(screen.getByRole('tooltip')).toHaveTextContent('not required to add positions in this order')
})
