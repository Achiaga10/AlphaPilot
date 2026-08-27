import { describe, expect, test } from 'vitest'
import { defaultDraft } from './PortfolioWorkspace'
import { buildPlanRequest, validateDraft } from './PlanForm'
import { riskConfigFixture } from '../../test/fixtures'

describe('portfolio plan request', () => {
  test('serializes only high-level inputs without client-owned profile facts', () => {
    const request = buildPlanRequest(
      {
        ...defaultDraft,
        tickerScope: 'nvda, AAPL nvda',
        positions: [{ ticker: 'msft', shares: 2, reference_price: '400', cost_basis: '350' }],
      },
      riskConfigFixture,
    )
    expect(request.tickers).toEqual(['NVDA', 'AAPL'])
    expect(request.portfolio.positions[0]?.ticker).toBe('MSFT')
    expect(request).not.toHaveProperty('exit_mode')
    expect(request).not.toHaveProperty('hybrid_trend_threshold_pct')
    expect(request).not.toHaveProperty('micho_entry_mode')
    expect(request).not.toHaveProperty('sizing_policy')
    expect(JSON.stringify(request)).not.toMatch(/ranking_score|"atr"|stop_distance|strategy_signal/)
  })

  test('validates cash, whole shares, reference prices, tickers, and duplicates', () => {
    expect(validateDraft({ ...defaultDraft, cash: '-1' }).cash).toBeDefined()
    expect(validateDraft({
      ...defaultDraft,
      positions: [{ ticker: 'AAPL', shares: 0, reference_price: '100' }],
    }).positions).toMatch(/whole numbers/i)
    expect(validateDraft({
      ...defaultDraft,
      positions: [
        { ticker: 'AAPL', shares: 1, reference_price: '100' },
        { ticker: 'aapl', shares: 1, reference_price: '100' },
      ],
    }).positions).toMatch(/only once/i)
  })
})
