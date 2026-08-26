import { render, screen } from '@testing-library/react'
import type { AdminSyncJob } from '../types/portfolio'
import { InlineSyncProgress, SyncProgress } from './SyncProgress'

const base: AdminSyncJob = {
  job_id: 'job-1', state: 'RUNNING', requested_at: '2026-08-26T01:00:00Z',
  started_at: '2026-08-26T01:00:01Z', finished_at: null,
  start_date: '2025-01-01', end_date: '2026-08-26', operation: 'MARKET_CANDLES_SYNC',
  provider: 'Alpaca', feed: 'iex', active_constituents: 502,
  companies_created: 0, companies_updated: 0, companies_unchanged: 0,
  memberships_added: 0, memberships_removed: 0, failed_stage: null,
  failed_ticker: null, error_code: null, error: null,
  progress: { total: 10, attempted: 0, synced: 0, skipped: 0, failed: 0, failed_tickers: [], stage: 'benchmark', current_ticker: 'SPY' },
}

test('queued and preparing sync use accessible indeterminate progress', () => {
  render(<SyncProgress job={{ ...base, state: 'QUEUED', progress: { ...base.progress, total: 0, current_ticker: null } }} />)
  const progress = screen.getByRole('progressbar', { name: 'MARKET CANDLES SYNC progress' })
  expect(progress).not.toHaveAttribute('aria-valuenow')
  expect(progress).toHaveAttribute('aria-valuetext', 'Benchmark')
  expect(screen.getByText(/Preparing/)).toBeInTheDocument()
})

test('determinate sync exposes zero and partial values plus current ticker', () => {
  const { rerender } = render(<SyncProgress job={base} />)
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '0')
  rerender(<SyncProgress job={{ ...base, progress: { ...base.progress, attempted: 4, synced: 3, skipped: 1, stage: 'stock_candles', current_ticker: 'AAPL' } }} />)
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '4')
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuetext', 'Stock Candles, AAPL')
  expect(screen.getByText('40%')).toBeInTheDocument()
})

test('full sync renders phases and retains a 100 percent completion summary', () => {
  render(<SyncProgress job={{ ...base, operation: 'FULL_SYNC', state: 'SUCCEEDED', finished_at: '2026-08-26T02:00:00Z', progress: { ...base.progress, attempted: 10, synced: 10, stage: 'complete', current_ticker: null } }} />)
  expect(screen.getByText('Universe COMPLETE')).toBeInTheDocument()
  expect(screen.getByText('Candles COMPLETE')).toBeInTheDocument()
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '10')
  expect(screen.getByText('Completed.')).toBeInTheDocument()
})

test('failure, universe progress, ticker progress, and custom stages remain explicit', () => {
  const { rerender } = render(<SyncProgress job={{ ...base, operation: 'UNIVERSE_SYNC', state: 'FAILED', error_code: 'PROVIDER_FAILED', error: 'Safe failure', progress: { ...base.progress, failed: 1, failed_tickers: ['BAD'], stage: 'company_metadata', current_ticker: 'BAD' } }} />)
  expect(screen.getByText('PROVIDER_FAILED')).toBeInTheDocument()
  expect(screen.getByText(/Inspect failed tickers/)).toBeInTheDocument()
  rerender(<InlineSyncProgress label="SBET" pending complete={false} failed={false} stages={['Ticker validation', 'Metadata', 'Company persistence', 'Historical candles']} />)
  expect(screen.getByRole('progressbar', { name: 'SBET progress' })).toBeInTheDocument()
  expect(screen.getByText('Ticker validation')).toHaveClass('is-active')
})
