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

test('shows the preserved technical, news, and final decision stack', async () => {
  const user = userEvent.setup()
  const decision = {
    ...planFixture.decisions[0]!,
    base_decision: 'BUY' as const,
    decision: 'SKIP' as const,
    news_effect: 'BUY_BLOCKED',
    final_action: 'DO_NOT_BUY',
    news_reason: 'Fresh high-severity adverse guidance',
    news_policy_version: 'news-decision-overlay-v1',
    supporting_news_article_ids: ['article-1'],
  }
  render(<DecisionTable decisions={[decision]} sizingPolicy="equal-slot" />)

  await user.click(screen.getByText('Decision details'))

  expect(screen.getByText('Base technical decision')).toBeInTheDocument()
  expect(screen.getByText('BUY_BLOCKED')).toBeInTheDocument()
  expect(screen.getByText('DO_NOT_BUY')).toBeInTheDocument()
  expect(screen.getByText('article-1')).toBeInTheDocument()
})
