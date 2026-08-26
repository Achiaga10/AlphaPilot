import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { planFixture } from '../../test/fixtures'
import type { PortfolioPlanReadiness } from '../../types/portfolio'
import { PlanReadinessBanner } from './PlanReadinessBanner'

function renderReadiness(overrides: Partial<PortfolioPlanReadiness>) {
  const readiness = { ...planFixture.readiness, ...overrides }
  return render(<MemoryRouter><PlanReadinessBanner readiness={readiness} /></MemoryRouter>)
}

test('all-stale readiness requires refresh and does not imply strategy rejection', () => {
  renderReadiness({
    status: 'DATA_NOT_READY', requested_tickers: 502, evaluated_tickers: 0,
    fresh_tickers: 0, stale_tickers: 502, no_data_tickers: 0,
    insufficient_history_tickers: 0, buy_signals: 0, approved_buys: 0,
  })
  expect(screen.getByRole('heading', { name: 'Data refresh required' })).toBeInTheDocument()
  expect(screen.getByText(/No normal strategy evaluation was available/)).toBeInTheDocument()
  expect(screen.getByText('0 / 502 eligible')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Go to Data Management' })).toHaveAttribute('href', '/admin/data')
})

test('fresh zero-opportunity readiness is presented as a legitimate strategy result', () => {
  renderReadiness({
    status: 'NO_ACTION', requested_tickers: 502, evaluated_tickers: 502,
    fresh_tickers: 502, stale_tickers: 0, no_data_tickers: 0,
    insufficient_history_tickers: 0, buy_signals: 0, approved_buys: 0,
  })
  expect(screen.getByRole('heading', { name: /no actionable decision/i })).toBeInTheDocument()
  expect(screen.getByText(/No approved BUY opportunities were produced from 502 normally evaluated tickers/)).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Go to Data Management' })).not.toBeInTheDocument()
})

test('partial readiness shows coverage and constraint attribution', () => {
  renderReadiness({
    status: 'PARTIAL_DATA', requested_tickers: 10, evaluated_tickers: 7,
    fresh_tickers: 8, stale_tickers: 1, no_data_tickers: 1,
    insufficient_history_tickers: 1, buy_signals: 3, approved_buys: 1,
    buy_rejections_by_reason: { SECTOR_LIMIT: 2 },
  })
  expect(screen.getByRole('heading', { name: 'Partial analysis coverage' })).toBeInTheDocument()
  expect(screen.getByText('7 / 10 eligible')).toBeInTheDocument()
  expect(screen.getByText('Sector limit reached: 2')).toBeInTheDocument()
})
