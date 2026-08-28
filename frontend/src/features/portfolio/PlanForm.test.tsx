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
      '11111111-1111-4111-8111-111111111111',
    )
    expect(request.tickers).toEqual(['NVDA', 'AAPL'])
    expect(request.portfolio_id).toBe('11111111-1111-4111-8111-111111111111')
    expect(request).not.toHaveProperty('portfolio')
    expect(request).not.toHaveProperty('exit_mode')
    expect(request).not.toHaveProperty('hybrid_trend_threshold_pct')
    expect(request).not.toHaveProperty('micho_entry_mode')
    expect(request).not.toHaveProperty('sizing_policy')
    expect(JSON.stringify(request)).not.toMatch(/ranking_score|"atr"|stop_distance|strategy_signal/)
  })

  test('validates only locally editable plan preferences', () => {
    expect(validateDraft({ ...defaultDraft, asOfDate: '' }).asOfDate).toBeDefined()
    expect(validateDraft({ ...defaultDraft, cash: '-1' })).toEqual({})
  })
})
