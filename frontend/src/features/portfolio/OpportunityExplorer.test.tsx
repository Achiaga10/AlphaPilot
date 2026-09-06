import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
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
  expect(screen.getByRole('tab', { name: 'Final Approved Sells 1' })).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: 'Technical SELL Signals 1' })).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: 'Not Actionable 1' })).toBeInTheDocument()
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
  await user.click(screen.getByRole('tab', { name: 'Universe Evaluated 2' }))
  expect(screen.getByText('Sorted A-Z')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Universe Evaluation' })).toBeInTheDocument()
  expect(screen.getByText('View all 2 returned tickers')).toBeInTheDocument()
  const rows = screen.getAllByRole('row').slice(1)
  expect(within(rows[0]!).getByText('AAA')).toBeInTheDocument()
  expect(within(rows[1]!).getByText('ZZZ')).toBeInTheDocument()
})

test('returned rows can be searched and filtered by final action, candidate decision, signal, sector, and status', async () => {
  const user = userEvent.setup()
  renderExplorer()
  await user.click(screen.getByRole('tab', { name: /Returned Decision Records/ }))
  await user.type(screen.getByLabelText('Search ticker or company'), 'aapl')
  expect(screen.getByText('AAPL')).toBeInTheDocument()
  expect(screen.queryByText('NVDA')).not.toBeInTheDocument()
  await user.clear(screen.getByLabelText('Search ticker or company'))
  await user.selectOptions(screen.getByLabelText('Final action'), 'NOT_ACTIONABLE')
  await user.selectOptions(screen.getByLabelText('Candidate decision'), 'SKIP')
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
  await user.click(screen.getByRole('tab', { name: 'Universe Evaluated 30' }))
  expect(screen.getByText('Page 1 of 2 · 30 returned rows')).toBeInTheDocument()
  expect(screen.getAllByRole('row')).toHaveLength(26)
  await user.click(screen.getByRole('button', { name: 'Next' }))
  expect(screen.getByText('Page 2 of 2 · 30 returned rows')).toBeInTheDocument()
  expect(screen.getAllByRole('row')).toHaveLength(6)
})

test('unscored SELL and HOLD decisions are labeled rather than assigned fabricated RS20', async () => {
  const user = userEvent.setup()
  renderExplorer()
  await user.click(screen.getByRole('tab', { name: /Returned Decision Records/ }))
  expect(screen.getAllByText('Not scored')).toHaveLength(2)
})

test('apply actions are limited to approved portfolio decisions on a clean plan', async () => {
  const user = userEvent.setup()
  const rejectedSell: PortfolioDecision = { ...planFixture.decisions[1]!, ticker: 'FLAT', decision: 'SKIP', reason: 'NO_POSITION_TO_SELL', allocation_reason: 'NO_POSITION_TO_SELL', terminal_reason: 'NO_POSITION_TO_SELL', final_action: 'NOT_ACTIONABLE', is_final_actionable: false, current_shares: 0, cash_after_decision: null }
  render(<MemoryRouter><OpportunityExplorer decisions={[...planFixture.decisions, rejectedSell]} statuses={planFixture.candidate_statuses} canApplyDecisions /></MemoryRouter>)
  expect(screen.getByRole('button', { name: 'Review Add' })).toBeInTheDocument()
  await user.click(screen.getByRole('tab', { name: 'Final Approved Sells 1' }))
  expect(screen.getByRole('button', { name: 'Apply Sell' })).toBeInTheDocument()
  await user.click(screen.getByRole('tab', { name: 'Technical SELL Signals 2' }))
  expect(screen.getAllByRole('button', { name: 'Apply Sell' })).toHaveLength(1)
  await user.click(screen.getByRole('tab', { name: 'Not Actionable 2' }))
  expect(screen.queryByRole('button', { name: /Apply|Review Add/ })).not.toBeInTheDocument()
})

test('final actionable count and rows share the backend-approved semantics', () => {
  const blocked = { ...planFixture.decisions[0]!, is_final_actionable: false, decision: 'SKIP' as const, reason: 'NEWS_RISK_BLOCK' as const, allocation_reason: 'BUY_APPROVED' as const, terminal_reason: 'NEWS_RISK_BLOCK' as const, final_action: 'NOT_ACTIONABLE' as const }
  render(<MemoryRouter><OpportunityExplorer decisions={[blocked]} statuses={planFixture.candidate_statuses} readiness={{ ...planFixture.readiness, final_approved_buys: 0, approved_buys: 0 }} /></MemoryRouter>)
  expect(screen.getByRole('tab', { name: 'Approved Buys 0' })).toBeInTheDocument()
  expect(screen.getByText('No approved BUYs')).toBeInTheDocument()
  expect(screen.queryByText('NVDA')).not.toBeInTheDocument()
})

test('ticker exclusion and restore controls are explicit and reversible', async () => {
  const user = userEvent.setup()
  const onExclude = vi.fn()
  const onRestore = vi.fn()
  const { rerender } = render(<MemoryRouter><OpportunityExplorer decisions={planFixture.decisions} statuses={planFixture.candidate_statuses} excludedTickers={new Set()} onExcludeTicker={onExclude} onRestoreTicker={onRestore} /></MemoryRouter>)
  await user.click(screen.getByRole('button', { name: 'Exclude from future plans' }))
  expect(onExclude).toHaveBeenCalledWith('NVDA')

  rerender(<MemoryRouter><OpportunityExplorer decisions={planFixture.decisions} statuses={planFixture.candidate_statuses} excludedTickers={new Set(['NVDA'])} onExcludeTicker={onExclude} onRestoreTicker={onRestore} /></MemoryRouter>)
  expect(screen.getByText(/Excluded by you/)).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Return to recommendation pool' }))
  expect(onRestore).toHaveBeenCalledWith('NVDA')
})
