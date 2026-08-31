import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { API_BASE_URL } from '../api/client'
import { planFixture, riskConfigFixture, strategyProfilesFixture } from './fixtures'

interface TestPosition {
  ticker: string
  shares: number
  reference_price: string
  cost_basis?: string | null
  sector?: string | null
  modeled_risk_dollars?: string
}

const researchPortfolioFixture = {
  portfolio_id: planFixture.portfolio_id, stable_key: 'default', name: 'AlphaPilot Research Portfolio', revision: 0,
  cash: '30000', realized_pnl: '0', total_cost_basis: '65000', positions_market_value: '70000', total_equity: '100000',
  cash_pct: '30', invested_pct: '70', total_unrealized_pnl: '5000', latest_completed_trading_day: '2026-08-20', valuation_status: 'COMPLETE',
  positions: planFixture.portfolio.positions.map((position, index) => ({ position_id: `21111111-1111-4111-8111-11111111111${index}`, company_id: `31111111-1111-4111-8111-11111111111${index}`, ticker: position.ticker, sector: position.sector, status: 'OPEN', quantity: position.shares, average_cost: position.cost_basis ?? position.reference_price, cost_basis: String(Number(position.cost_basis ?? position.reference_price) * position.shares), entry_trading_day: '2026-01-02', entry_price: position.cost_basis, strategy: 'ema20-pullback', strategy_profile_id: 'ema20-pullback-v1', strategy_profile_version: 1, selection_policy: 'relative-strength-20', provenance_status: 'PLAN_PROFILE', modeled_risk_dollars: position.modeled_risk_dollars, latest_completed_trading_day: '2026-08-20', latest_completed_close: position.reference_price, market_value: position.market_value, portfolio_weight_pct: position.portfolio_weight_pct, unrealized_pnl: '0', unrealized_pnl_pct: '0', valuation_status: 'VALUED' })),
}

export const dailyBriefFixture = {
  portfolio_id: planFixture.portfolio_id, portfolio_revision: 0, generated_at: '2026-08-29T10:00:00Z',
  data_status: { readiness: 'READY', expected_completed_session: '2026-08-28', latest_synchronized_session: '2026-08-28', brief_session: '2026-08-28', sync_status: 'SUCCEEDED', explanation: 'Stored facts are aligned to the latest completed SPY session.' },
  workflow_status: 'WAITING_FOR_REQUIRED_EXITS',
  summary: { portfolio_value: '100000', cash: '30000', invested_market_value: '70000', cash_pct: '30', open_positions: 3, max_positions: 10, valuation_readiness: 'COMPLETE', modeled_risk_dollars: null },
  required_actions: [{ position_id: 'sell-position', ticker: 'MCHO', company_name: 'Micho Corp', strategy: 'micho-150', strategy_profile_id: 'micho-150-v1', strategy_profile_version: 1, status: 'SELL', reason: 'SMA150_BREAKDOWN', explanation: 'SMA150 breakdown triggered the stored strategy exit.', quantity: 20, latest_completed_close: '100', unrealized_pnl: '-200', unrealized_pnl_pct: '-9.09', as_of_session: '2026-08-28', sticky_sell: true, exit_triggered_on: '2026-08-28', loss_control_policy: 'SMA150_COMPLETED_CLOSE_EXIT', loss_control_boundary: '105', loss_control_trigger: 'COMPLETED_DAILY_CLOSE_BELOW', broker_stop_order: false, references: [] }],
  attention_positions: [{ position_id: 'attention-position', ticker: 'APA', company_name: 'APA Corp', strategy: 'ema20-pullback', strategy_profile_id: 'ema20-pullback-v1', strategy_profile_version: 1, status: 'ATTENTION', reason: 'EMA20_LOST_STRONG_TREND_HOLD', explanation: 'EMA20 was lost, but the frozen HYBRID strong-trend exception remains active.', quantity: 25, latest_completed_close: '42.53', unrealized_pnl: '35.25', unrealized_pnl_pct: '0.35', as_of_session: '2026-08-28', sticky_sell: false, exit_triggered_on: null, loss_control_policy: 'NONE', loss_control_boundary: null, loss_control_trigger: null, broker_stop_order: false, references: [] }],
  actionable_opportunities: [],
  research_only_opportunities: [{ ticker: 'EMA', strategy: 'ema20-pullback', strategy_profile_id: 'ema20-pullback-v1', strategy_profile_version: 1, source_plan_id: 'ema-plan', portfolio_revision: 0, selection_policy: 'relative-strength-20', sizing_policy: 'equal-slot', decision: 'BUY', decision_reason: 'BUY_APPROVED', ranking_score: '0.05', reference_price: '50', proposed_shares: 100, target_allocation_dollars: '5000', target_weight_pct: '5', sector: 'Technology', execution_readiness: 'RESEARCH_ONLY', execution_readiness_reason: 'NO_APPROVED_LOSS_CONTROL_POLICY', loss_control_policy: 'NONE', loss_control_boundary: null, loss_control_trigger: null, loss_control_distance_dollars: null, loss_control_distance_pct: null, broker_stop_order: false, strategy_references: [], analysis_as_of_date: '2026-08-28', action_id: '1:BUY:EMA', workflow_status: 'READY_FOR_REVIEW' }],
  deferred_opportunities: [{ ticker: 'FAST', strategy: 'micho-150', strategy_profile_id: 'micho-150-v1', strategy_profile_version: 1, source_plan_id: 'micho-plan', portfolio_revision: 0, selection_policy: 'relative-strength-20', sizing_policy: 'atr-volatility-normalized', decision: 'BUY', decision_reason: 'BUY_APPROVED', ranking_score: '0.10', reference_price: '120', proposed_shares: 80, target_allocation_dollars: '9600', target_weight_pct: '9.6', sector: 'Industrials', execution_readiness: 'ACTIONABLE', execution_readiness_reason: 'LOSS_CONTROL_READY', loss_control_policy: 'SMA150_COMPLETED_CLOSE_EXIT', loss_control_boundary: '108', loss_control_trigger: 'COMPLETED_DAILY_CLOSE_BELOW', loss_control_distance_dollars: '12', loss_control_distance_pct: '10', broker_stop_order: false, strategy_references: [], analysis_as_of_date: '2026-08-28', action_id: '1:BUY:FAST', workflow_status: 'WAITING_FOR_REQUIRED_EXITS' }],
  hold_positions: [{ position_id: 'hold-position', ticker: 'MSFT', company_name: 'Microsoft', strategy: 'ema20-pullback', strategy_profile_id: 'ema20-pullback-v1', strategy_profile_version: 1, status: 'HOLD', reason: 'EMA20_HELD', explanation: 'EMA20 is still held.', quantity: 100, latest_completed_close: '400', unrealized_pnl: '5000', unrealized_pnl_pct: '14.28', as_of_session: '2026-08-28', sticky_sell: false, exit_triggered_on: null, loss_control_policy: 'NONE', loss_control_boundary: null, loss_control_trigger: null, broker_stop_order: false, references: [] }],
  unavailable_positions: [], blockers: ['REQUIRED_EXITS_MUST_BE_RESOLVED_FIRST'],
}

export const liveBriefFixture = {
  portfolio_id: planFixture.portfolio_id, portfolio_revision: 0,
  completed_session: '2026-08-28', live_refresh_timestamp: '2026-08-31T14:43:21Z',
  provider: 'alpaca', feed: 'iex', overall_readiness: 'LIVE',
  requested_tickers: 1, successful_tickers: 1, partial_failures: [],
  positions: [{
    position_id: 'attention-position', ticker: 'APA', company_name: 'APA Corp',
    strategy_profile_id: 'ema20-pullback-v1', strategy_profile_version: 1,
    quantity: 25, average_cost: '42.38', completed_session: '2026-08-28',
    latest_completed_close: '42.53',
    live: { ticker: 'APA', company_id: '31111111-1111-4111-8111-111111111110', session_date: '2026-08-31', last_price: '39.80', session_open: '42.40', session_high: '42.75', session_low: '39.70', volume: 123456, previous_completed_close: '42.53', quote_timestamp: '2026-08-31T14:42:50Z', received_at: '2026-08-31T14:43:21Z', provider: 'alpaca', feed: 'iex', freshness: 'LIVE', age_seconds: 31, coverage_note: 'IEX is a real-time single-exchange feed with limited market-wide coverage.' },
    today_change_dollars: '-2.73', today_change_pct: '-6.42',
    completed_ema20: '41.25', provisional_ema20: '41.11', completed_ema50: '40.05', provisional_ema50: '40.04',
    completed_sma150: '38.50', provisional_sma150: '38.49', completed_atr14: '1.15', provisional_atr14: '1.27',
    distance_to_ema20_dollars: '-1.31', distance_to_ema20_pct: '-3.19', distance_to_ema50_dollars: '-0.24', distance_to_ema50_pct: '-0.60',
    distance_to_sma150_dollars: '1.31', distance_to_sma150_pct: '3.40',
    confirmed_status: 'ATTENTION', confirmed_reason: 'EMA20_LOST_STRONG_TREND_HOLD',
    live_status: 'CRITICAL_ATTENTION', live_reason: 'LIVE_PRICE_BELOW_EMA50',
    projected_signal_if_closed_now: 'SELL', projected_reason: 'EMA50_EXIT', projection_is_official: false,
    confirmed_sell_required: false, loss_control_policy: 'HYBRID_COMPLETED_CLOSE_EXIT', loss_control_boundary: '40.05',
    loss_control_trigger: 'COMPLETED_DAILY_CLOSE_BELOW', broker_stop_order: false,
  }],
}

function summarize(portfolio: { cash: string; positions: TestPosition[] }) {
  const cash = Number(portfolio.cash) || 0
  const values = portfolio.positions.map((position) => Number(position.reference_price) * position.shares)
  const invested = values.reduce((total, value) => total + value, 0)
  const equity = cash + invested
  return {
    equity: String(equity), cash: String(cash), cash_pct: equity ? String(cash / equity * 100) : '0',
    invested_value: String(invested), invested_pct: equity ? String(invested / equity * 100) : '0',
    open_positions: portfolio.positions.length,
    positions: portfolio.positions.map((position, index) => ({
      ...position, ticker: position.ticker.toUpperCase(), market_value: String(values[index] ?? 0),
      portfolio_weight_pct: equity ? String((values[index] ?? 0) / equity * 100) : '0',
      cost_basis: position.cost_basis ?? null, sector: position.sector ?? null,
      modeled_risk_dollars: position.modeled_risk_dollars ?? '0',
    })),
  }
}

export const dailyOpportunitiesFixture = {
  portfolio_id: dailyBriefFixture.portfolio_id,
  portfolio_revision: dailyBriefFixture.portfolio_revision,
  generated_at: dailyBriefFixture.generated_at,
  analysis_as_of_date: '2026-08-28',
  workflow_status: dailyBriefFixture.workflow_status,
  actionable_opportunities: dailyBriefFixture.actionable_opportunities,
  research_only_opportunities: dailyBriefFixture.research_only_opportunities,
  deferred_opportunities: dailyBriefFixture.deferred_opportunities,
  actionable_total_count: dailyBriefFixture.actionable_opportunities.length,
  research_only_total_count: dailyBriefFixture.research_only_opportunities.length,
  deferred_total_count: dailyBriefFixture.deferred_opportunities.length,
  research_only_limit: 10,
}

export const handlers = [
  http.get(`${API_BASE_URL}/api/v1/health/`, () => HttpResponse.json({ status: 'ok', application: 'AlphaPilot' })),
  http.get(`${API_BASE_URL}/api/v1/portfolio/risk-config`, () => HttpResponse.json(riskConfigFixture)),
  http.get(`${API_BASE_URL}/api/v1/portfolio/strategy-profiles`, () => HttpResponse.json(strategyProfilesFixture)),
  http.get(`${API_BASE_URL}/api/v1/portfolio/current`, () => HttpResponse.json(researchPortfolioFixture)),
  http.get(`${API_BASE_URL}/api/v1/portfolio/:portfolioId/daily-brief`, () => HttpResponse.json(dailyBriefFixture)),
  http.post(`${API_BASE_URL}/api/v1/portfolio/:portfolioId/live-refresh`, () => HttpResponse.json(liveBriefFixture)),
  http.get(`${API_BASE_URL}/api/v1/portfolio/:portfolioId/daily-brief/opportunities`, () => HttpResponse.json(dailyOpportunitiesFixture)),
  http.get(`${API_BASE_URL}/api/v1/portfolio/:portfolioId/monitoring`, () => HttpResponse.json([])),
  http.get(`${API_BASE_URL}/api/v1/portfolio/:portfolioId/positions/:positionId/intelligence`, ({ params }) => HttpResponse.json({ portfolio_id: String(params.portfolioId), portfolio_revision: 0, position_id: String(params.positionId), company_id: '31111111-1111-4111-8111-111111111110', ticker: 'MSFT', company_name: 'Microsoft', position_status: 'OPEN', provenance_status: 'PLAN_PROFILE', quantity: 100, entry_trading_day: '2026-01-02', entry_price: '400', average_cost: '400', cost_basis: '40000', strategy_guidance_available: true, guidance_unavailable_reason: null, strategy: 'ema20-pullback', strategy_profile_id: 'ema20-pullback-v1', strategy_profile_version: 1, strategy_profile_snapshot: {}, selection_policy: 'relative-strength-20', entry_decision: 'BUY', entry_reason: 'BUY_APPROVED', latest_completed_trading_day: '2026-08-20', latest_completed_close: '400', market_value: '40000', unrealized_pnl: '0', unrealized_pnl_pct: '0', realized_pnl: '0', monitoring_readiness: 'READY', monitoring_status: 'HOLD', monitoring_reason: 'EMA20_HELD', monitoring_completed_trading_day: '2026-08-20', indicator_facts: { ema20: '390' }, previous_monitoring_status: null, latest_monitoring_transition: null, exit_triggered: false, exit_triggered_on: null, exit_trigger_reason: null, active_exit_policy: 'HYBRID exit with frozen 2% threshold', protective_stop_policy: 'NONE', trailing_stop_policy: 'NONE', profit_target_policy: 'NONE', research_only_stop_candidate: 'Static 3 × ATR14', research_only_stop_status: 'NOT_ACTIVE', price_change_since_entry: '0', explanation: 'EMA20 is still held.', trade_event_count: 1, reconciliation_event_count: 0 })),
  http.get(`${API_BASE_URL}/api/v1/portfolio/:portfolioId/positions/:positionId/paper-validations`, () => HttpResponse.json([])),
  http.post(`${API_BASE_URL}/api/v1/ai/copilot/portfolio/:portfolioId/positions/:positionId/ask`, ({ params }) => HttpResponse.json({ answer: 'There is no active protective stop. EMA50 at $19.16 is the hard strategy-exit reference and requires a completed daily close below it. EMA20 at $20.10 is conditional under HYBRID 2%. These are not broker stop orders.', scope: 'POSITION', portfolio_id: String(params.portfolioId), position_id: String(params.positionId), ticker: 'MSFT', as_of_date: '2026-08-20', grounding_status: 'GROUNDED', fact_refs: [{ fact_id: 'guidance.protective_stop', source: 'stop_exit_guidance', field: 'protective_stop', label: 'Active protective stop', value: 'NONE' }, { fact_id: 'guidance.reference.0', source: 'stop_exit_guidance', field: 'references', label: 'EMA50_HARD_BREAKDOWN', value: { reference_type: 'EMA50_HARD_BREAKDOWN', value: '19.16', condition: 'COMPLETED_DAILY_CLOSE_BELOW' } }, { fact_id: 'guidance.reference.1', source: 'stop_exit_guidance', field: 'references', label: 'EMA20_CONDITIONAL_BREAKDOWN', value: { reference_type: 'EMA20_CONDITIONAL_BREAKDOWN', value: '20.10', condition: 'COMPLETED_DAILY_CLOSE_BELOW_CONDITIONAL' } }, { fact_id: 'guidance.research_only', source: 'stop_exit_guidance', field: 'research_only_candidate', label: 'Research-only stop evidence', value: { candidate: 'Static 3 × ATR14', status: 'NOT_ACTIVE' } }], limitations: ['Explanatory research only; no broker order or portfolio mutation.'], provider: 'fake', model: 'deterministic-test' })),
  http.post(`${API_BASE_URL}/api/v1/ai/copilot/portfolio/:portfolioId/query`, async ({ params, request }) => {
    const body = await request.json() as { question: string; active_ticker: string | null; pending_intent: string | null }
    const normalized = body.question.toLowerCase()
    const base = { portfolio_id: String(params.portfolioId), as_of_date: '2026-08-20', grounding_status: 'GROUNDED', limitations: [], provider: 'alphapilot', model: 'deterministic-test', result_status: 'ANSWERED', resolution_status: 'RESOLVED' }
    if (normalized.includes('where do i sync')) return HttpResponse.json({ ...base, answer: 'Open Data Management from the left sidebar (/admin/data).', scope: 'GENERAL', position_id: null, ticker: null, intent: 'NAVIGATION', fact_refs: [{ fact_id: 'navigation.data', source: 'product_navigation', field: 'navigation', label: 'Data Management', value: { route: '/admin/data' } }] })
    if (normalized === 'how many shares do i own?') return HttpResponse.json({ ...base, answer: 'Which ticker do you mean?', scope: 'POSITION', position_id: null, ticker: null, intent: 'QUANTITY', result_status: 'CLARIFICATION_REQUIRED', resolution_status: 'CLARIFICATION_REQUIRED', grounding_status: 'LIMITED', fact_refs: [] })
    if (normalized === 'apa' && body.pending_intent === 'QUANTITY') return HttpResponse.json({ ...base, answer: 'You own 235 shares of APA.', scope: 'POSITION', position_id: 'apa-position', ticker: 'APA', intent: 'QUANTITY', fact_refs: [{ fact_id: 'position.quantity', source: 'position_intelligence', field: 'quantity', label: 'Quantity', value: 235 }] })
    if (normalized.includes('what about fast')) return HttpResponse.json({ ...base, answer: "I'll use FAST for your next position question.", scope: 'POSITION', position_id: 'fast-position', ticker: 'FAST', intent: 'GENERAL', result_status: 'ENTITY_ESTABLISHED', resolution_status: 'ENTITY_ESTABLISHED', grounding_status: 'LIMITED', fact_refs: [] })
    const ticker = normalized.includes('fast') || body.active_ticker === 'FAST' ? 'FAST' : normalized.includes('apa') || body.active_ticker === 'APA' ? 'APA' : null
    if (normalized.includes('average cost') && ticker) return HttpResponse.json({ ...base, answer: `Your average cost for ${ticker} is ${ticker === 'APA' ? '$42.38' : '$65.20'} per share.`, scope: 'POSITION', position_id: `${ticker.toLowerCase()}-position`, ticker, intent: 'AVERAGE_COST', fact_refs: [{ fact_id: 'position.average_cost', source: 'position_intelligence', field: 'average_cost', label: 'Average cost', value: ticker === 'APA' ? '42.38' : '65.20' }] })
    if (normalized.includes('how many shares') && ticker === 'FAST') return HttpResponse.json({ ...base, answer: 'You own 101 shares of FAST.', scope: 'POSITION', position_id: 'fast-position', ticker: 'FAST', intent: 'QUANTITY', fact_refs: [{ fact_id: 'position.quantity', source: 'position_intelligence', field: 'quantity', label: 'Quantity', value: 101 }] })
    return HttpResponse.json({ ...base, answer: `${ticker ?? 'This position'} remains HOLD based on AlphaPilot facts.`, scope: ticker ? 'POSITION' : 'GENERAL', position_id: ticker ? `${ticker.toLowerCase()}-position` : null, ticker, intent: 'EXPLANATION', provider: 'fake', model: 'ollama-test', fact_refs: ticker ? [{ fact_id: 'position.monitoring_status', source: 'position_intelligence', field: 'monitoring_status', label: 'Monitoring', value: 'HOLD' }] : [] })
  }),
  http.post(`${API_BASE_URL}/api/v1/portfolio/initialize`, () => HttpResponse.json(researchPortfolioFixture)),
  http.get(`${API_BASE_URL}/api/v1/admin/data/capability`, () => HttpResponse.json({ enabled: false, warning: 'Research admin tools are disabled by configuration.', market_data_provider: 'Alpaca', market_data_feed: 'iex' })),
  http.get(`${API_BASE_URL}/api/v1/admin/data/summary`, () => HttpResponse.json({ active_company_count: 503, active_sp500_count: 502, active_custom_tracked_count: 0, latest_spy_date: '2026-08-20', earliest_active_stock_latest_date: '2026-08-19', latest_active_stock_latest_date: '2026-08-20', fresh_tracked_ticker_count: 501, stale_tracked_ticker_count: 1, no_data_tracked_ticker_count: 0, latest_sync_job: null, last_universe_sync_at: null, last_candle_sync_at: null, market_data_provider: 'Alpaca', market_data_feed: 'iex' })),
  http.get(`${API_BASE_URL}/api/v1/admin/data/custom-tickers`, () => HttpResponse.json([])),
  http.get(`${API_BASE_URL}/api/v1/admin/data/scheduler`, () => HttpResponse.json({ enabled: false, timezone: 'America/New_York', scheduled_local_time: '16:30', last_run_started: null, last_run_completed: null, last_status: null, last_successful_completed_session: null, last_error: null })),
  http.post(`${API_BASE_URL}/api/v1/portfolio/state-summary`, async ({ request }) => {
    const portfolio = await request.json() as { cash: string; positions: TestPosition[] }
    return HttpResponse.json(summarize(portfolio))
  }),
  http.post(`${API_BASE_URL}/api/v1/portfolio/preview-action`, async ({ request }) => actionResponse(request, false)),
  http.post(`${API_BASE_URL}/api/v1/portfolio/apply-action`, async ({ request }) => actionResponse(request, true)),
  http.get(`${API_BASE_URL}/api/v1/portfolio/latest-price/:ticker`, ({ params }) => HttpResponse.json({ ticker: String(params.ticker), price: '150', price_date: '2026-08-20' })),
  http.post(`${API_BASE_URL}/api/v1/portfolio/manual-sell/preview`, async ({ request }) => manualSellResponse(request, false)),
  http.post(`${API_BASE_URL}/api/v1/portfolio/manual-sell`, async ({ request }) => manualSellResponse(request, true)),
  http.post(`${API_BASE_URL}/api/v1/portfolio/plan`, () => HttpResponse.json(planFixture)),
]

async function actionResponse(request: Request, apply: boolean) {
    const body = await request.json() as { decision: typeof planFixture.decisions[number]; applied_action_ids: string[]; requested_shares: number | null }
    const { decision } = body
    const originalPortfolio: { cash: string; positions: TestPosition[] } = { cash: planFixture.portfolio.cash, positions: planFixture.portfolio.positions }
    if (decision.action_id === null || body.applied_action_ids.includes(decision.action_id)) {
      return HttpResponse.json({ applied: false, reason: 'ALREADY_APPLIED', action_id: decision.action_id, portfolio: originalPortfolio, summary: summarize(originalPortfolio), portfolio_id: planFixture.portfolio_id, portfolio_revision: 0 })
    }
    const portfolio = structuredClone(originalPortfolio)
    const requestedShares = body.requested_shares ?? decision.proposed_shares
    const requestedAllocation = requestedShares * Number(decision.reference_price)
    const cashBefore = Number(portfolio.cash)
    if (decision.decision === 'BUY') {
      portfolio.cash = String(cashBefore - requestedAllocation)
      portfolio.positions.push({ ticker: decision.ticker, shares: requestedShares, reference_price: decision.reference_price, cost_basis: decision.reference_price, sector: decision.sector, modeled_risk_dollars: '0' })
    } else {
      portfolio.cash = String(Number(portfolio.cash) + Number(decision.estimated_proceeds))
      portfolio.positions = portfolio.positions.filter((position) => position.ticker !== decision.ticker)
    }
    const equity = cashBefore + originalPortfolio.positions.reduce((total, item) => total + item.shares * Number(item.reference_price), 0)
    const semantics = requestedShares === decision.proposed_shares ? 'SAME_PLAN_ACTION' : 'USER_QUANTITY_OVERRIDE'
    return HttpResponse.json({
      plan_id: 'test-plan', applied: apply, reason: apply ? 'APPLIED' : 'READY', validation_status: 'VALID',
      quantity_semantics: semantics, action_id: decision.action_id, action_type: decision.decision,
      cash_before: String(cashBefore), cash_impact: String(-requestedAllocation), cash_after: portfolio.cash,
      position_before: null, position_after: decision.decision === 'BUY' ? portfolio.positions.at(-1) : null,
      portfolio: apply ? portfolio : originalPortfolio, summary: summarize(apply ? portfolio : originalPortfolio), portfolio_id: planFixture.portfolio_id, portfolio_revision: apply ? 1 : 0,
      recommended_shares: decision.proposed_shares, requested_shares: requestedShares,
      recommended_allocation_dollars: decision.target_allocation_dollars,
      requested_allocation_dollars: String(requestedAllocation), resulting_position_weight_pct: String(requestedAllocation / equity * 100),
      sector_weight_before_pct: '0', sector_weight_after_pct: String(requestedAllocation / equity * 100),
      modeled_position_risk_dollars: null, portfolio_risk_after_dollars: null, cash_reserve_requirement: null,
    })
}

async function manualSellResponse(request: Request, apply: boolean) {
  const body = await request.json() as { ticker: string; shares_to_sell: number; execution_price: string | null }
  const originalPortfolio: { cash: string; positions: TestPosition[] } = { cash: planFixture.portfolio.cash, positions: planFixture.portfolio.positions }
  const position = originalPortfolio.positions.find((item) => item.ticker === body.ticker)
  const price = body.execution_price ?? '150'
  const remaining = (position?.shares ?? 0) - body.shares_to_sell
  const portfolio = structuredClone(originalPortfolio)
  if (apply && position) {
    portfolio.cash = String(Number(portfolio.cash) + body.shares_to_sell * Number(price))
    portfolio.positions = remaining === 0
      ? portfolio.positions.filter((item) => item.ticker !== body.ticker)
      : portfolio.positions.map((item) => item.ticker === body.ticker ? { ...item, shares: remaining } : item)
  }
  return HttpResponse.json({ applied: apply && Boolean(position), reason: position ? 'READY' : 'POSITION_NOT_HELD', ticker: body.ticker, shares_sold: body.shares_to_sell, shares_remaining: remaining, execution_price: price, price_source: body.execution_price ? 'USER_PROVIDED' : 'LATEST_STORED_CANDLE', price_date: body.execution_price ? null : '2026-08-20', gross_proceeds: String(body.shares_to_sell * Number(price)), cash_before: originalPortfolio.cash, cash_after: portfolio.cash, position_removed: remaining === 0, portfolio, summary: summarize(portfolio), portfolio_id: planFixture.portfolio_id, portfolio_revision: apply ? 1 : 0 })
}

export const server = setupServer(...handlers)
