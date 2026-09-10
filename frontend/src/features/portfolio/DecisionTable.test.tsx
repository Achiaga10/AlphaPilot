import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { planFixture } from '../../test/fixtures'
import { DecisionTable } from './DecisionTable'

test.each([
  ['EMA20 Pullback', 'NEWS_ASSESSMENT_UNAVAILABLE'],
  ['EMA20 Pullback', 'BUY_BLOCKED'],
  ['EMA20 Pullback', 'EXIT_REQUIRED'],
  ['Micho', 'NEWS_ASSESSMENT_UNAVAILABLE'],
  ['Micho', 'BUY_BLOCKED'],
  ['Micho', 'EXIT_REQUIRED'],
])('approved %s decision remains primary under advisory %s', async (_strategy, newsEffect) => {
  const user = userEvent.setup()
  const decision = { ...planFixture.decisions[0]!, news_advisory_only: true, news_effect: newsEffect, final_action: 'BUY' as const, terminal_reason: 'BUY_APPROVED' as const, is_final_actionable: true }
  render(<DecisionTable decisions={[decision]} sizingPolicy="equal-slot" canApplyDecisions />)
  expect(screen.getByText('Final action APPROVED BUY')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Review Add' })).toBeInTheDocument()
  await user.click(screen.getByText('Decision details'))
  expect(screen.getByText('News advisory context')).toBeInTheDocument()
  expect(screen.getByText('Advisory only — does not approve, block or change this decision.')).toBeInTheDocument()
  expect(screen.queryByText('NOT ACTIONABLE')).not.toBeInTheDocument()
})

test('candidate allocation is not labeled as an approved BUY', () => {
  const decision = {
    ...planFixture.decisions[0]!,
    allocation_reason: 'BUY_APPROVED' as const,
    terminal_reason: 'LOSS_CONTROL_UNAVAILABLE' as const,
    final_action: 'NOT_ACTIONABLE' as const,
    is_final_actionable: false,
  }

  render(<DecisionTable decisions={[decision]} sizingPolicy="equal-slot" />)

  expect(screen.getAllByText('Candidate allocation')).toHaveLength(2)
  expect(screen.queryByText(/APPROVED BUY/)).not.toBeInTheDocument()
})

test('equal-slot uses not-applicable risk semantics and exposes frozen exit guidance', async () => {
  const user = userEvent.setup()
  render(<DecisionTable decisions={[planFixture.decisions[0]!]} sizingPolicy="equal-slot" />)
  await user.click(screen.getByText('Decision details'))
  expect(screen.getAllByText('Not used by Equal-slot')).toHaveLength(5)
  expect(screen.getByRole('heading', { name: 'Exit Guidance' })).toBeInTheDocument()
  expect(screen.getByText('None in current strategy')).toBeInTheDocument()
  expect(screen.getByText('29.90%')).toBeInTheDocument()
  expect(screen.getByText(/not live monitoring/i)).toBeInTheDocument()
  expect(screen.getByText('EMA20 entry safety')).toBeInTheDocument()
  expect(screen.getByText('ENTRY_TOUCHING_OR_NEAR_EMA20')).toBeInTheDocument()
  expect(screen.getByText((_, element) => element?.textContent === '$1.00 / 0.57%')).toBeInTheDocument()
})

test('renders an extended EMA entry as blocked using backend facts', async () => {
  const user = userEvent.setup()
  const decision = {
    ...planFixture.decisions[0]!,
    decision: 'SKIP' as const,
    reason: 'ENTRY_TOO_EXTENDED_ABOVE_EMA20' as const,
    allocation_reason: 'ENTRY_TOO_EXTENDED_ABOVE_EMA20' as const,
    terminal_reason: 'ENTRY_TOO_EXTENDED_ABOVE_EMA20' as const,
    final_action: 'NOT_ACTIONABLE' as const,
    is_final_actionable: false,
    entry_safety: {
      ...planFixture.decisions[0]!.entry_safety!,
      entry_price: '180',
      distance_to_ema20: '5',
      distance_to_ema20_pct: '2.85714286',
      relation: 'EXTENDED_ABOVE' as const,
      status: 'BLOCKED' as const,
      reason: 'ENTRY_TOO_EXTENDED_ABOVE_EMA20' as const,
    },
  }
  render(<DecisionTable decisions={[decision]} sizingPolicy="equal-slot" />)
  await user.click(screen.getByText('Decision details'))
  expect(screen.getByText('BLOCKED')).toBeInTheDocument()
  expect(screen.getAllByText('ENTRY_TOO_EXTENDED_ABOVE_EMA20')).toHaveLength(2)
  expect(screen.getByText('2.86%')).toBeInTheDocument()
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
    allocation_reason: 'BUY_APPROVED' as const,
    terminal_reason: 'NEWS_RISK_BLOCK' as const,
    news_effect: 'BUY_BLOCKED',
    final_action: 'NOT_ACTIONABLE' as const,
    is_final_actionable: false,
    news_reason: 'Fresh high-severity adverse guidance',
    news_policy_version: 'news-decision-overlay-v1',
    supporting_news_article_ids: ['article-1'],
  }
  render(<DecisionTable decisions={[decision]} sizingPolicy="equal-slot" />)

  await user.click(screen.getByText('Decision details'))

  expect(screen.getByText('Portfolio candidate decision')).toBeInTheDocument()
  expect(screen.getByText('BUY_BLOCKED')).toBeInTheDocument()
  expect(screen.getAllByText(/NOT ACTIONABLE/)).not.toHaveLength(0)
  expect(screen.queryByText('Buy approved')).not.toBeInTheDocument()
  expect(screen.getByText('article-1')).toBeInTheDocument()
})

test('allocation BUY without loss control is visibly non-actionable and cannot be applied', () => {
  const decision = {
    ...planFixture.decisions[0]!,
    allocation_reason: 'BUY_APPROVED' as const,
    terminal_reason: 'LOSS_CONTROL_UNAVAILABLE' as const,
    final_action: 'NOT_ACTIONABLE' as const,
    execution_readiness: 'RESEARCH_ONLY' as const,
    execution_readiness_reason: 'NO_APPROVED_LOSS_CONTROL_POLICY' as const,
    loss_control_active: false,
    loss_control_source: 'NONE' as const,
    manual_stop_required: false,
    is_final_actionable: false,
  }
  render(<DecisionTable decisions={[decision]} sizingPolicy="equal-slot" canApplyDecisions />)

  expect(screen.getAllByText(/NOT ACTIONABLE/)).not.toHaveLength(0)
  expect(screen.getAllByText('Candidate allocation')).toHaveLength(2)
  expect(screen.getByText('Loss control unavailable')).toBeInTheDocument()
  expect(screen.getByText('LOSS CONTROL')).toBeInTheDocument()
  expect(screen.getAllByText('No approved numeric loss-control policy')).toHaveLength(2)
  expect(screen.queryByText('Buy approved')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Review Add' })).not.toBeInTheDocument()
})

test('approved EMA20 manual-stop BUY is actionable without a system boundary', async () => {
  const user = userEvent.setup()
  const decision = {
    ...planFixture.decisions[0]!,
    approved_protective_stop_price: null,
    loss_control_boundary_price: null,
    loss_control_trigger: null,
    loss_control_active: false,
    loss_control_source: 'USER_MANUAL' as const,
    manual_stop_required: true,
    execution_readiness: 'ACTIONABLE' as const,
    execution_readiness_reason: 'MANUAL_STOP_REQUIRED' as const,
  }
  render(<DecisionTable decisions={[decision]} sizingPolicy="equal-slot" canApplyDecisions />)

  expect(screen.getByText('Final action APPROVED BUY')).toBeInTheDocument()
  expect(screen.getByText('MANUAL STOP REQUIRED')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Review Add' })).toBeInTheDocument()
  await user.click(screen.getByText('Decision details'))
  expect(screen.getByText('USER_MANUAL')).toBeInTheDocument()
  expect(screen.getAllByText(/No system stop/).length).toBeGreaterThan(0)
})

test('approved system policy displays its numeric automatic stop without manual warning', async () => {
  const user = userEvent.setup()
  const decision = {
    ...planFixture.decisions[0]!,
    approved_protective_stop_price: '170',
    loss_control_boundary_price: '170',
    loss_control_trigger: 'AUTOMATIC_STOP',
    loss_control_active: true,
    loss_control_source: 'APPROVED_SYSTEM_POLICY' as const,
    manual_stop_required: false,
    execution_readiness: 'ACTIONABLE' as const,
    execution_readiness_reason: 'LOSS_CONTROL_READY' as const,
  }
  render(<DecisionTable decisions={[decision]} sizingPolicy="equal-slot" canApplyDecisions />)

  expect(screen.queryByText('MANUAL STOP REQUIRED')).not.toBeInTheDocument()
  await user.click(screen.getByText('Decision details'))
  expect(screen.getByText('APPROVED_SYSTEM_POLICY')).toBeInTheDocument()
  expect(screen.getByText('$170.00')).toBeInTheDocument()
})

test('hard-gated BUY candidates show their terminal blocker instead of allocation approval', () => {
  const blockers = [
    'ENTRY_TOO_EXTENDED_ABOVE_EMA20',
    'NEWS_BUY_BLOCKED_ADVERSE_EVIDENCE',
    'USER_EXCLUDED_FROM_RECOMMENDATIONS',
  ] as const
  const decisions = blockers.map((terminalReason, index) => ({
    ...planFixture.decisions[0]!,
    ticker: `BLOCK${index}`,
    decision: 'SKIP' as const,
    reason: terminalReason,
    allocation_reason: 'BUY_APPROVED' as const,
    terminal_reason: terminalReason,
    final_action: 'NOT_ACTIONABLE' as const,
    is_final_actionable: false,
  }))

  render(<DecisionTable decisions={decisions} sizingPolicy="equal-slot" canApplyDecisions />)

  expect(screen.queryByText('Buy approved')).not.toBeInTheDocument()
  expect(screen.getByText('Entry too extended above EMA20')).toBeInTheDocument()
  expect(screen.getByText('Adverse News blocked BUY')).toBeInTheDocument()
  expect(screen.getByText('Excluded by you')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Review Add' })).not.toBeInTheDocument()
})
