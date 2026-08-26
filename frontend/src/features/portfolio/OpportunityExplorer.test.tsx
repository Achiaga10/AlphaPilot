import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { planFixture } from '../../test/fixtures'
import type { CandidateStatus, PortfolioDecision } from '../../types/portfolio'
import { OpportunityExplorer } from './OpportunityExplorer'

function renderExplorer(decisions = planFixture.decisions, statuses = planFixture.candidate_statuses) {
  return render(<MemoryRouter><OpportunityExplorer decisions={decisions} statuses={statuses} /></MemoryRouter>)
}

test('tabs show live counts and approved buys are the default view', () => {
  renderExplorer()
  expect(screen.getByRole('tab', { name: 'Approved Buys 1' })).toHaveAttribute('aria-selected', 'true')
  expect(screen.getByRole('tab', { name: 'Approved Sells 1' })).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: 'Sell Signals 1' })).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: 'Skipped 1' })).toBeInTheDocument()
  expect(screen.getByText('NVDA')).toBeInTheDocument()
  expect(screen.queryByText('AAPL')).not.toBeInTheDocument()
})

test('approved BUY order and backend candidate ranks are preserved', () => {
  const second: PortfolioDecision = { ...planFixture.decisions[0]!, ticker: 'AAPL', ranking_score: '-0.02' }
  const statuses: CandidateStatus[] = [
    { ...planFixture.candidate_statuses[0]!, ticker: 'NVDA', candidate_rank: 1 },
    { ...planFixture.candidate_statuses[0]!, ticker: 'AAPL', candidate_rank: 2, ranking_score: '-0.02' },
  ]
  renderExplorer([planFixture.decisions[0]!, second], statuses)
  const cards = document.querySelectorAll('.decision-card')
  expect(within(cards[0] as HTMLElement).getByText('NVDA')).toBeInTheDocument()
  expect(within(cards[1] as HTMLElement).getByText('AAPL')).toBeInTheDocument()
  expect(within(cards[1] as HTMLElement).getByText('-0.0200')).toBeInTheDocument()
  expect(within(cards[1] as HTMLElement).getByLabelText('BUY candidate rank 2')).toBeInTheDocument()
})

test('all evaluated defaults to disclosed A-Z ordering, not recommendation order', async () => {
  const user = userEvent.setup()
  renderExplorer([], [
    { ...planFixture.candidate_statuses[0]!, ticker: 'ZZZ' },
    { ...planFixture.candidate_statuses[0]!, ticker: 'AAA' },
  ])
  await user.click(screen.getByRole('tab', { name: 'All Evaluated 2' }))
  expect(screen.getByText('Sorted A-Z')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Universe Evaluation' })).toBeInTheDocument()
  expect(screen.getByText('View all 2 returned tickers')).toBeInTheDocument()
  const rows = screen.getAllByRole('row').slice(1)
  expect(within(rows[0]!).getByText('AAA')).toBeInTheDocument()
  expect(within(rows[1]!).getByText('ZZZ')).toBeInTheDocument()
})

test('returned rows can be searched and filtered by decision, signal, sector, and status', async () => {
  const user = userEvent.setup()
  renderExplorer()
  await user.click(screen.getByRole('tab', { name: /All Decisions/ }))
  await user.type(screen.getByLabelText('Search ticker or company'), 'aapl')
  expect(screen.getByText('AAPL')).toBeInTheDocument()
  expect(screen.queryByText('NVDA')).not.toBeInTheDocument()
  await user.clear(screen.getByLabelText('Search ticker or company'))
  await user.selectOptions(screen.getByLabelText('Decision'), 'SKIP')
  await user.selectOptions(screen.getByLabelText('Signal'), 'BUY')
  await user.selectOptions(screen.getByLabelText('Sector'), 'Information Technology')
  expect(screen.getByText('AAPL')).toBeInTheDocument()
  await user.selectOptions(screen.getByLabelText('Data status'), 'READY')
  expect(screen.getByText('No portfolio decisions')).toBeInTheDocument()
})

test('large universe results paginate instead of rendering one enormous table', async () => {
  const user = userEvent.setup()
  const statuses: CandidateStatus[] = Array.from({ length: 30 }, (_, index) => ({
    ticker: `T${String(index).padStart(2, '0')}`,
    status: 'NO_ACTION', data_as_of_date: '2026-08-20', signal: 'HOLD', reason: 'NO_ACTION',
  }))
  renderExplorer([], statuses)
  await user.click(screen.getByRole('tab', { name: 'All Evaluated 30' }))
  expect(screen.getByText('Page 1 of 2 · 30 returned rows')).toBeInTheDocument()
  expect(screen.getAllByRole('row')).toHaveLength(26)
  await user.click(screen.getByRole('button', { name: 'Next' }))
  expect(screen.getByText('Page 2 of 2 · 30 returned rows')).toBeInTheDocument()
  expect(screen.getAllByRole('row')).toHaveLength(6)
})

test('unscored SELL and HOLD decisions are labeled rather than assigned fabricated RS20', async () => {
  const user = userEvent.setup()
  renderExplorer()
  await user.click(screen.getByRole('tab', { name: /All Decisions/ }))
  expect(screen.getAllByText('Not scored')).toHaveLength(2)
})

test('apply actions are limited to approved portfolio decisions on a clean plan', async () => {
  const user = userEvent.setup()
  const rejectedSell: PortfolioDecision = { ...planFixture.decisions[1]!, ticker: 'FLAT', decision: 'SKIP', reason: 'NO_POSITION_TO_SELL', current_shares: 0, cash_after_decision: null }
  render(<MemoryRouter><OpportunityExplorer decisions={[...planFixture.decisions, rejectedSell]} statuses={planFixture.candidate_statuses} canApplyDecisions /></MemoryRouter>)
  expect(screen.getByRole('button', { name: 'Review Add' })).toBeInTheDocument()
  await user.click(screen.getByRole('tab', { name: 'Approved Sells 1' }))
  expect(screen.getByRole('button', { name: 'Apply Sell' })).toBeInTheDocument()
  await user.click(screen.getByRole('tab', { name: 'Sell Signals 2' }))
  expect(screen.getAllByRole('button', { name: 'Apply Sell' })).toHaveLength(1)
  await user.click(screen.getByRole('tab', { name: 'Skipped 2' }))
  expect(screen.queryByRole('button', { name: /Apply|Review Add/ })).not.toBeInTheDocument()
})
