export type StrategyName = 'ema20-pullback' | 'micho-150'
export type SelectionPolicy = 'relative-strength-20' | 'ticker-ascending'
export type SizingPolicy = 'equal-slot' | 'atr-risk' | 'atr-volatility-normalized'
export type StrategySignal = 'BUY' | 'HOLD' | 'SELL'
export type PortfolioDecisionType = 'BUY' | 'HOLD' | 'SELL' | 'SKIP'
export type ResearchClassification = 'PROMISING_RESEARCH_BASELINE' | 'RESEARCH_ONLY'

export interface StrategyProfile {
  profile_id: string
  version: number
  strategy: StrategyName
  display_name: string
  classification: ResearchClassification
  entry_description: string
  recommended_selection_policy: SelectionPolicy
  allowed_selection_policies: SelectionPolicy[]
  sizing_policy: SizingPolicy
  strategy_exit_description: string
  ema_exit_mode: 'hybrid' | null
  hybrid_trend_threshold_pct: string | null
  micho_entry_mode: 'both' | null
  protective_stop_default: 'NONE'
  profit_management_default: 'NONE'
  research_only_stop_candidate: string
}

export type DecisionReason =
  | 'BUY_APPROVED'
  | 'SELL_APPROVED'
  | 'ALREADY_HELD'
  | 'NO_POSITION_TO_SELL'
  | 'MAX_POSITIONS'
  | 'INSUFFICIENT_CASH'
  | 'CASH_RESERVE'
  | 'MAX_POSITION_WEIGHT'
  | 'PORTFOLIO_RISK_LIMIT'
  | 'SECTOR_LIMIT'
  | 'INSUFFICIENT_HISTORY'
  | 'INVALID_RISK_DISTANCE'
  | 'RANKING_NOT_SELECTED'
  | 'INSUFFICIENT_ALLOCATION'
  | 'STALE_DATA'
  | 'NO_ACTION'

export type CandidateDataStatus =
  | 'READY'
  | 'NO_ACTION'
  | 'COMPANY_NOT_FOUND'
  | 'NO_DATA'
  | 'STALE_DATA'
  | 'INSUFFICIENT_HISTORY'

export interface PortfolioRiskConfig {
  risk_per_position_pct: string
  atr_period: number
  atr_stop_multiple: string
  max_position_weight_pct: string
  max_portfolio_risk_pct: string
  minimum_cash_reserve_pct: string
  max_sector_weight_pct: string
  max_positions: number
}

export interface PortfolioPositionInput {
  ticker: string
  shares: number
  reference_price: string
  cost_basis?: string | null
  sector?: string | null
  modeled_risk_dollars?: string
}

export interface CurrentPortfolioInput {
  cash: string
  positions: PortfolioPositionInput[]
}

export interface PortfolioPlanRequest {
  strategy: StrategyName
  selection_policy: SelectionPolicy
  as_of_date: string
  tickers: string[] | null
  portfolio_id: string
  risk_config: PortfolioRiskConfig
}

export interface PortfolioPositionSummary {
  ticker: string
  shares: number
  reference_price: string
  market_value: string
  portfolio_weight_pct: string
  cost_basis: string | null
  sector: string
  modeled_risk_dollars: string
}

export interface PortfolioSummary {
  equity: string
  cash: string
  cash_pct: string
  invested_value: string
  invested_pct: string
  cash_reserve_requirement: string
  current_portfolio_risk: string
  current_portfolio_risk_pct: string
  available_portfolio_risk: string
  available_portfolio_risk_pct: string
  modeled_risk_complete: boolean
  open_positions: number
  positions: PortfolioPositionSummary[]
}

export interface PortfolioDraftSummary {
  equity: string
  cash: string
  cash_pct: string
  invested_value: string
  invested_pct: string
  open_positions: number
  positions: PortfolioPositionSummary[]
}

export interface PortfolioDecision {
  ticker: string
  signal: StrategySignal
  decision: PortfolioDecisionType
  reason: DecisionReason
  ranking_score: string | null
  reference_price: string
  atr: string | null
  stop_distance: string | null
  risk_budget_dollars: string
  target_allocation_dollars: string
  target_weight_pct: string
  proposed_shares: number
  modeled_position_risk_dollars: string
  sector: string
  sector_weight_before_pct: string
  sector_weight_after_pct: string
  current_shares: number
  estimated_proceeds: string | null
  normalized_sizing_weight: string | null
  estimated_cash_outlay: string | null
  cash_after_decision: string | null
  modeled_stop_reference_price: string | null
  action_id: string | null
  application_order: number | null
  depends_on_action_ids: string[]
  exit_context: StrategyExitContext | null
  execution_readiness?: 'ACTIONABLE' | 'RESEARCH_ONLY' | 'UNAVAILABLE'
  execution_readiness_reason?: 'LOSS_CONTROL_READY' | 'NO_APPROVED_LOSS_CONTROL_POLICY' | 'MISSING_NUMERIC_BOUNDARY' | 'MISSING_TRIGGER_SEMANTICS' | 'NOT_A_NEW_BUY'
  loss_control_policy?: string
  loss_control_boundary_price?: string | null
  loss_control_trigger?: string | null
  loss_control_active?: boolean
  loss_control_broker_stop_order?: boolean
  approved_protective_stop_price?: string | null
}

export interface StrategyExitContext {
  strategy: StrategyName
  data_as_of_date: string
  reference_close: string
  current_signal: StrategySignal
  signal_reason: string
  exit_mode: string
  current_exit_state:
    | 'ABOVE_EMA20'
    | 'BELOW_EMA20_STRONG_TREND'
    | 'EMA20_WEAK_TREND_BREAKDOWN'
    | 'EMA50_BREAKDOWN'
    | 'ABOVE_SMA150'
    | 'SMA150_BREAKDOWN'
    | 'INSUFFICIENT_HISTORY'
  fixed_take_profit_policy: 'NONE'
  ema20: string | null
  ema50: string | null
  ema_spread_pct: string | null
  hybrid_threshold_pct: string | null
  distance_to_ema20_pct: string | null
  distance_to_ema50_pct: string | null
  sma150: string | null
  distance_to_sma150_pct: string | null
}

export interface CandidateStatus {
  ticker: string
  status: CandidateDataStatus
  data_as_of_date: string | null
  signal: StrategySignal | null
  reason: string
  company_name?: string | null
  sector?: string | null
  ranking_score?: string | null
  atr?: string | null
  decision?: PortfolioDecisionType | null
  decision_reason?: DecisionReason | null
  candidate_rank?: number | null
  is_custom_tracked?: boolean
  company_id?: string | null
}

export interface PortfolioPlan {
  plan_id: string
  portfolio_id: string
  portfolio_revision: number
  portfolio: PortfolioSummary
  config: PortfolioRiskConfig
  strategy: StrategyName
  selection_policy: SelectionPolicy
  sizing_policy: SizingPolicy
  strategy_profile: StrategyProfile
  decisions: PortfolioDecision[]
  requested_as_of_date: string
  analysis_as_of_date: string
  candidate_statuses: CandidateStatus[]
  readiness: PortfolioPlanReadiness
  evaluation_target_ticker: string | null
}

export type PlanReadinessStatus = 'READY' | 'PARTIAL_DATA' | 'DATA_NOT_READY' | 'NO_ACTION'

export interface PortfolioPlanReadiness {
  status: PlanReadinessStatus
  requested_tickers: number
  evaluated_tickers: number
  fresh_tickers: number
  stale_tickers: number
  no_data_tickers: number
  insufficient_history_tickers: number
  company_not_found_tickers: number
  buy_signals: number
  approved_buys: number
  approved_sells: number
  actionable_decisions: number
  latest_ticker_data_date: string | null
  buy_rejections_by_reason: Record<string, number>
}

export type PlanActionApplyReason =
  | 'READY'
  | 'APPLIED'
  | 'ACTION_NOT_APPROVED'
  | 'ALREADY_APPLIED'
  | 'PRIOR_ACTION_REQUIRED'
  | 'INSUFFICIENT_CURRENT_DRAFT_CASH'
  | 'POSITION_ALREADY_HELD'
  | 'POSITION_NOT_HELD'
  | 'CURRENT_DRAFT_POSITION_CHANGED'
  | 'INVALID_SHARE_QUANTITY'
  | 'MAX_POSITIONS'
  | 'MAX_POSITION_WEIGHT'
  | 'CASH_RESERVE'
  | 'SECTOR_LIMIT'
  | 'PORTFOLIO_RISK_LIMIT'
  | 'INVALID_RISK_DISTANCE'

export interface PortfolioPlanActionRequest {
  plan_id: string
  portfolio_id: string
  portfolio_revision: number
  analysis_as_of_date: string
  selection_policy: SelectionPolicy
  decision: PortfolioDecision
  applied_action_ids: string[]
  requested_shares: number | null
  strategy_profile_id: string
  strategy_profile_version: number
  sizing_policy: SizingPolicy
  risk_config: PortfolioRiskConfig
}

export interface PortfolioPlanActionResult {
  plan_id: string
  applied: boolean
  reason: PlanActionApplyReason
  action_id: string | null
  action_type: PortfolioDecisionType
  cash_before: string
  cash_impact: string
  cash_after: string
  position_before: PortfolioPositionInput | null
  position_after: PortfolioPositionInput | null
  portfolio: CurrentPortfolioInput
  summary: PortfolioDraftSummary
  validation_status: 'VALID' | 'REJECTED'
  quantity_semantics: 'SAME_PLAN_ACTION' | 'CURRENT_REVALIDATED_RECOMMENDATION' | 'USER_QUANTITY_OVERRIDE'
  recommended_shares: number
  requested_shares: number
  recommended_allocation_dollars: string
  requested_allocation_dollars: string
  resulting_position_weight_pct: string
  sector_weight_before_pct: string
  sector_weight_after_pct: string
  modeled_position_risk_dollars: string | null
  portfolio_risk_after_dollars: string | null
  cash_reserve_requirement: string | null
  portfolio_id: string
  portfolio_revision: number
}

export interface LatestStoredPrice {
  ticker: string
  price: string | null
  price_date: string | null
  source: 'LATEST_STORED_CANDLE'
}

export interface ManualSellRequest {
  portfolio_id: string
  portfolio_revision: number
  ticker: string
  shares_to_sell: number
  execution_price: string | null
}

export interface ManualSellResult {
  applied: boolean
  reason: 'READY' | 'APPLIED' | 'POSITION_NOT_HELD' | 'INVALID_SHARE_QUANTITY' | 'STORED_PRICE_UNAVAILABLE'
  ticker: string
  shares_sold: number
  shares_remaining: number
  execution_price: string | null
  price_source: 'LATEST_STORED_CANDLE' | 'USER_PROVIDED' | null
  price_date: string | null
  gross_proceeds: string
  cash_before: string
  cash_after: string
  position_removed: boolean
  portfolio: CurrentPortfolioInput
  summary: PortfolioDraftSummary
  portfolio_id: string
  portfolio_revision: number
}

export interface ResearchPositionValuation {
  position_id: string
  company_id: string
  ticker: string
  sector: string | null
  status: 'OPEN'
  quantity: number
  average_cost: string
  cost_basis: string
  entry_trading_day: string | null
  entry_price: string | null
  strategy: string | null
  strategy_profile_id: string | null
  strategy_profile_version: number | null
  selection_policy: string | null
  provenance_status: 'PLAN_PROFILE' | 'LEGACY_IMPORTED' | 'MANUAL_EXTERNAL'
  modeled_risk_dollars: string
  latest_completed_trading_day: string | null
  latest_completed_close: string | null
  market_value: string | null
  portfolio_weight_pct: string | null
  unrealized_pnl: string | null
  unrealized_pnl_pct: string | null
  valuation_status: 'VALUED' | 'PRICE_UNAVAILABLE'
}

export interface ResearchPortfolio {
  portfolio_id: string
  stable_key: string
  name: string
  revision: number
  cash: string
  realized_pnl: string
  total_cost_basis: string
  positions_market_value: string | null
  total_equity: string | null
  cash_pct: string | null
  invested_pct: string | null
  total_unrealized_pnl: string | null
  latest_completed_trading_day: string | null
  valuation_status: 'COMPLETE' | 'PARTIAL' | 'UNAVAILABLE'
  positions: ResearchPositionValuation[]
}

export interface ResearchPortfolioInitialize {
  starting_cash: string
  name?: string
  imported_positions: Array<{
    ticker: string
    quantity: number
    average_cost: string
    cost_basis?: string | null
  }>
}

export interface PositionMonitoring {
  position_id: string
  ticker: string
  strategy_profile_id: string | null
  strategy_profile_version: number | null
  readiness: 'READY' | 'UNAVAILABLE'
  status: 'HOLD' | 'ATTENTION' | 'SELL' | null
  reason: string
  completed_trading_day: string | null
  latest_close: string | null
  indicator_facts: Record<string, string | boolean | null>
  exit_triggered: boolean
  exit_triggered_on: string | null
  exit_trigger_reason: string | null
  protective_stop_policy: 'NONE'
  trailing_stop_policy: 'NONE'
  profit_target_policy: 'NONE'
}

export interface CashAdjustmentRequest {
  expected_revision: number
  delta: string
  reason_code: 'EXTERNAL_DEPOSIT' | 'EXTERNAL_WITHDRAWAL' | 'PAPER_ACCOUNT_RECONCILIATION' | 'CORRECTION' | 'OTHER'
  note: string | null
}

export interface ExternalPositionRequest {
  expected_revision: number
  ticker: string
  quantity: number
  average_cost: string
  entry_trading_day: string | null
  reason_code: 'ALPACA_PAPER_TRADE' | 'EXTERNAL_BROKER_TRADE' | 'INITIAL_PORTFOLIO_IMPORT' | 'CORRECTION' | 'OTHER'
  note: string | null
}

export interface PositionReconciliationRequest {
  expected_revision: number
  quantity: number
  average_cost: string
  entry_trading_day: string | null
  reason_code: 'PAPER_ACCOUNT_RECONCILIATION' | 'QUANTITY_CORRECTION' | 'COST_BASIS_CORRECTION' | 'ENTRY_DATE_CORRECTION' | 'OTHER'
  note: string | null
}

export interface PositionIntelligence {
  portfolio_id: string
  portfolio_revision: number
  position_id: string
  company_id: string
  ticker: string
  company_name: string | null
  position_status: string
  provenance_status: string
  quantity: number
  entry_trading_day: string | null
  entry_price: string | null
  average_cost: string
  cost_basis: string
  strategy_guidance_available: boolean
  guidance_unavailable_reason: string | null
  strategy: string | null
  strategy_profile_id: string | null
  strategy_profile_version: number | null
  strategy_profile_snapshot: Record<string, unknown> | null
  selection_policy: string | null
  entry_decision: string | null
  entry_reason: string | null
  latest_completed_trading_day: string | null
  latest_completed_close: string | null
  market_value: string | null
  unrealized_pnl: string | null
  unrealized_pnl_pct: string | null
  realized_pnl: string
  monitoring_readiness: string
  monitoring_status: 'HOLD' | 'ATTENTION' | 'SELL' | null
  monitoring_reason: string
  monitoring_completed_trading_day: string | null
  indicator_facts: Record<string, unknown>
  previous_monitoring_status: string | null
  latest_monitoring_transition: string | null
  exit_triggered: boolean
  exit_triggered_on: string | null
  exit_trigger_reason: string | null
  active_exit_policy: string | null
  protective_stop_policy: string
  trailing_stop_policy: string
  profit_target_policy: string
  research_only_stop_candidate: string | null
  research_only_stop_status: 'NOT_ACTIVE' | null
  loss_control_policy?: string
  current_loss_control_boundary?: string | null
  loss_control_trigger?: string | null
  loss_control_active?: boolean
  loss_control_broker_stop_order?: boolean
  price_change_since_entry: string | null
  explanation: string
  trade_event_count: number
  reconciliation_event_count: number
}

export interface CopilotFactReference {
  fact_id: string
  source: string
  field: string
  label: string
  value: unknown
}

export interface CopilotAnswer {
  answer: string
  scope: 'GENERAL' | 'POSITION' | 'PORTFOLIO'
  portfolio_id: string | null
  position_id: string | null
  ticker: string | null
  as_of_date: string | null
  grounding_status: 'GROUNDED' | 'LIMITED'
  fact_refs: CopilotFactReference[]
  limitations: string[]
  provider: string
  model: string
  result_status?: 'ANSWERED' | 'FACT_UNAVAILABLE' | 'CLARIFICATION_REQUIRED' | 'ENTITY_ESTABLISHED' | 'MULTIPLE_TICKERS' | 'UNKNOWN_TICKER' | 'POSITION_NOT_HELD' | 'GENERATIVE_EXPLANATION_UNAVAILABLE'
  intent?: string | null
  resolution_status?: 'RESOLVED' | 'CLARIFICATION_REQUIRED' | 'ENTITY_ESTABLISHED' | 'MULTIPLE_TICKERS' | 'UNKNOWN_TICKER' | 'POSITION_NOT_HELD'
}

export interface UnifiedCopilotQuestion {
  question: string
  active_ticker: string | null
  pending_intent: string | null
}

export interface DailyBriefReference {
  reference_type: string
  value: string
  condition: string
  qualifier: string
  distance_dollars: string | null
  distance_pct: string | null
}

export interface DailyBriefPosition {
  position_id: string
  ticker: string
  company_name: string | null
  strategy: string | null
  strategy_profile_id: string | null
  strategy_profile_version: number | null
  status: 'SELL' | 'ATTENTION' | 'HOLD' | 'UNAVAILABLE'
  reason: string
  explanation: string
  quantity: number
  latest_completed_close: string | null
  unrealized_pnl: string | null
  unrealized_pnl_pct: string | null
  as_of_session: string | null
  sticky_sell: boolean
  exit_triggered_on: string | null
  loss_control_policy: string
  loss_control_boundary: string | null
  loss_control_trigger: string | null
  broker_stop_order: boolean
  references: DailyBriefReference[]
}

export interface DailyBriefOpportunity {
  ticker: string
  strategy: StrategyName
  strategy_profile_id: string
  strategy_profile_version: number
  source_plan_id: string
  portfolio_revision: number
  selection_policy: SelectionPolicy
  sizing_policy: SizingPolicy
  decision: 'BUY' | 'SKIP'
  decision_reason: string
  ranking_score: string | null
  reference_price: string
  proposed_shares: number
  target_allocation_dollars: string
  target_weight_pct: string
  sector: string
  execution_readiness: 'ACTIONABLE' | 'PAPER_FORWARD_ONLY' | 'RESEARCH_ONLY' | 'UNAVAILABLE'
  execution_readiness_reason: string
  loss_control_policy: string
  loss_control_boundary: string | null
  loss_control_trigger: string | null
  loss_control_distance_dollars: string | null
  loss_control_distance_pct: string | null
  broker_stop_order: boolean
  strategy_references: DailyBriefReference[]
  analysis_as_of_date: string
  action_id: string | null
  workflow_status: string
}

export interface DailyPortfolioBrief {
  portfolio_id: string
  portfolio_revision: number
  generated_at: string
  data_status: {
    readiness: 'READY' | 'DEGRADED' | 'BLOCKED'
    expected_completed_session: string | null
    latest_synchronized_session: string | null
    brief_session: string | null
    sync_status: string
    explanation: string
  }
  workflow_status: 'READY_FOR_REVIEW' | 'WAITING_FOR_REQUIRED_EXITS' | 'NEW_ENTRIES_BLOCKED'
  summary: {
    portfolio_value: string | null
    cash: string
    invested_market_value: string | null
    cash_pct: string | null
    open_positions: number
    max_positions: number
    valuation_readiness: string
    modeled_risk_dollars: string | null
  }
  required_actions: DailyBriefPosition[]
  attention_positions: DailyBriefPosition[]
  hold_positions: DailyBriefPosition[]
  unavailable_positions: DailyBriefPosition[]
  blockers: string[]
}

export interface DailyBriefOpportunities {
  portfolio_id: string
  portfolio_revision: number
  generated_at: string
  analysis_as_of_date: string | null
  workflow_status: string
  actionable_opportunities: DailyBriefOpportunity[]
  research_only_opportunities: DailyBriefOpportunity[]
  deferred_opportunities: DailyBriefOpportunity[]
  actionable_total_count: number
  research_only_total_count: number
  deferred_total_count: number
  research_only_limit: number | null
}

export type LiveQuoteFreshness = 'LIVE' | 'DELAYED' | 'STALE' | 'OUTSIDE_REGULAR_SESSION' | 'UNKNOWN'
export type LiveMonitoringStatus = 'NO_ACTION' | 'ATTENTION' | 'CRITICAL_ATTENTION' | 'SELL_REQUIRED' | 'UNAVAILABLE'

export interface LiveMarketSnapshot {
  ticker: string
  company_id: string
  session_date: string
  last_price: string
  session_open: string | null
  session_high: string | null
  session_low: string | null
  volume: number | null
  previous_completed_close: string | null
  quote_timestamp: string
  received_at: string
  provider: string
  feed: string
  freshness: LiveQuoteFreshness
  age_seconds: number
  coverage_note: string
}

export interface LivePositionIntelligence {
  position_id: string
  ticker: string
  company_name: string | null
  strategy_profile_id: string | null
  strategy_profile_version: number | null
  quantity: number
  average_cost: string
  completed_session: string | null
  latest_completed_close: string | null
  live: LiveMarketSnapshot | null
  today_change_dollars: string | null
  today_change_pct: string | null
  completed_ema20: string | null
  provisional_ema20: string | null
  completed_ema50: string | null
  provisional_ema50: string | null
  completed_sma150: string | null
  provisional_sma150: string | null
  completed_atr14: string | null
  provisional_atr14: string | null
  distance_to_ema20_dollars: string | null
  distance_to_ema20_pct: string | null
  distance_to_ema50_dollars: string | null
  distance_to_ema50_pct: string | null
  distance_to_sma150_dollars: string | null
  distance_to_sma150_pct: string | null
  confirmed_status: string | null
  confirmed_reason: string
  live_status: LiveMonitoringStatus
  live_reason: string
  projected_signal_if_closed_now: string | null
  projected_reason: string | null
  projection_is_official: false
  confirmed_sell_required: boolean
  loss_control_policy: string
  loss_control_boundary: string | null
  loss_control_trigger: string | null
  broker_stop_order: boolean
}

export interface PortfolioLiveBrief {
  portfolio_id: string
  portfolio_revision: number
  completed_session: string | null
  live_refresh_timestamp: string
  provider: string
  feed: string
  overall_readiness: 'LIVE' | 'DELAYED' | 'STALE' | 'PARTIAL' | 'UNAVAILABLE' | 'OUTSIDE_REGULAR_SESSION'
  positions: LivePositionIntelligence[]
  partial_failures: string[]
  requested_tickers: number
  successful_tickers: number
}

export interface PaperValidation {
  id: string
  portfolio_id: string
  position_id: string
  ticker: string
  status: 'OPEN' | 'CLOSED'
  execution_source: 'ALPACA_PAPER_MANUAL'
  position_provenance: string
  strategy: string | null
  strategy_profile_id: string | null
  strategy_profile_version: number | null
  planned_quantity: number | null
  reference_entry_price: string | null
  actual_quantity: number
  actual_entry_price: string
  actual_entry_at: string
  entry_fill_difference: string | null
  entry_fill_difference_bps: string | null
  quantity_difference: number | null
  actual_exit_quantity: number | null
  actual_exit_price: string | null
  actual_exit_at: string | null
  paper_gross_pnl: string | null
  paper_gross_return_pct: string | null
  alphapilot_exit_triggered_on: string | null
  alphapilot_exit_reason: string | null
  evidence_completeness: 'FULL' | 'PARTIAL' | 'LEGACY'
  entry_evidence_schema_version: number | null
  entry_evidence: Record<string, unknown> | null
  exit_evidence_schema_version: number | null
  exit_evidence: Record<string, unknown> | null
  entry_slippage_percent: string | null
  entry_adverse_slippage_dollars_per_share: string | null
  quantity_adherence_percent: string | null
  planned_notional: string | null
  actual_entry_notional: string
  fees_available: boolean
  net_paper_pnl: string | null
  calendar_days_held: number | null
}

export interface PaperTradeAnalytics {
  record: PaperValidation
  evidence_domain: 'FORWARD_PAPER_EVIDENCE'
  completed_sessions_held: number | null
  calendar_days_held: number
  mfe_percent: string | null
  mae_percent: string | null
  excursion_session_count: number
  post_exit_observations: Record<string, Record<string, unknown>>
  current_completed_session: string | null
  current_completed_close: string | null
  current_unrealized_pnl: string | null
}

export interface PaperStrategyAnalytics {
  strategy_profile_id: string | null
  strategy_profile_version: number | null
  open_trade_count: number
  closed_trade_count: number
  wins: number
  losses: number
  breakeven: number
  win_rate_percent: string | null
  average_return_percent: string | null
  gross_total_pnl: string
  evidence_maturity: string
}

export interface ForwardPaperAnalytics {
  portfolio_id: string
  evidence_domain: 'FORWARD_PAPER_EVIDENCE'
  generated_at: string
  total_trade_count: number
  open_trade_count: number
  closed_trade_count: number
  wins: number
  losses: number
  breakeven: number
  gross_realized_pnl: string
  win_rate_percent: string | null
  average_return_percent: string | null
  evidence_maturity: string
  complete_evidence_count: number
  partial_evidence_count: number
  legacy_evidence_count: number
  strategy_breakdown: PaperStrategyAnalytics[]
  open_trades: PaperTradeAnalytics[]
  closed_trades: PaperTradeAnalytics[]
}

export interface PaperValidationEntryRequest {
  actual_quantity: number
  actual_average_fill_price: string
  actual_execution_at: string
  note: string | null
}

export interface PaperValidationExitRequest {
  actual_exit_quantity: number
  actual_average_exit_fill: string
  actual_execution_at: string
  note: string | null
}

export interface DailySchedulerStatus {
  enabled: boolean
  timezone: 'America/New_York'
  scheduled_local_time: '16:30'
  last_run_started: string | null
  last_run_completed: string | null
  last_status: 'NEVER_RUN' | 'RUNNING' | 'SUCCEEDED' | 'NO_NEW_SESSION' | 'FAILED'
  last_successful_completed_market_session: string | null
  last_error_summary: string | null
}

export interface DailySchedulerStatus {
  enabled: boolean
  timezone: 'America/New_York'
  scheduled_local_time: '16:30'
  last_run_started: string | null
  last_run_completed: string | null
  last_status: 'NEVER_RUN' | 'RUNNING' | 'SUCCEEDED' | 'NO_NEW_SESSION' | 'FAILED'
  last_successful_completed_market_session: string | null
  last_error_summary: string | null
}

export interface HealthResponse {
  status: string
  application: string
}

export interface PlanDraft {
  cash: string
  positions: PortfolioPositionInput[]
  strategy: StrategyName
  selectionPolicy: SelectionPolicy
  asOfDate: string
  tickerScope: string
}

export interface AdminToolsCapability {
  enabled: boolean
  warning: string
  market_data_provider: string
  market_data_feed: 'iex' | 'sip'
}

export type AdminSyncJobState = 'QUEUED' | 'RUNNING' | 'SUCCEEDED' | 'FAILED'
export type AdminSyncOperation = 'UNIVERSE_SYNC' | 'MARKET_CANDLES_SYNC' | 'TICKER_SYNC' | 'FULL_SYNC'
export type AdminTickerSyncState = 'SYNCED' | 'SKIPPED' | 'FAILED' | 'COMPANY_NOT_FOUND'

export interface AdminSyncProgress {
  total: number
  attempted: number
  synced: number
  skipped: number
  failed: number
  failed_tickers: string[]
  stage: string | null
  current_ticker: string | null
}

export interface AdminSyncJob {
  job_id: string
  state: AdminSyncJobState
  requested_at: string
  started_at: string | null
  finished_at: string | null
  start_date: string
  end_date: string
  progress: AdminSyncProgress
  operation: AdminSyncOperation
  provider: string | null
  feed: string | null
  active_constituents: number
  companies_created: number
  companies_updated: number
  companies_unchanged: number
  memberships_added: number
  memberships_removed: number
  failed_stage: string | null
  failed_ticker: string | null
  error_code: string | null
  error: string | null
}

export interface AdminDataSummary {
  active_company_count: number
  active_sp500_count: number
  active_custom_tracked_count: number
  latest_spy_date: string | null
  earliest_active_stock_latest_date: string | null
  latest_active_stock_latest_date: string | null
  stale_tracked_ticker_count: number
  fresh_tracked_ticker_count: number
  no_data_tracked_ticker_count: number
  latest_sync_job: AdminSyncJob | null
  last_universe_sync_at: string | null
  last_candle_sync_at: string | null
  market_data_provider: string
  market_data_feed: 'iex' | 'sip'
}

export interface AdminSyncRange {
  start_date: string
  end_date: string
}

export interface AdminTickerSyncRequest extends AdminSyncRange {
  ticker: string
}

export interface AdminTickerSyncResponse {
  ticker: string
  state: AdminTickerSyncState
  message: string
}

export interface AdminFullSyncRequest extends AdminSyncRange {
  batch_size: number
}

export interface AdminFullSyncStart {
  started: boolean
  job: AdminSyncJob
}

export type CustomTickerState =
  | 'TRACKED_AND_SYNCED'
  | 'REACTIVATED_AND_SYNCED'
  | 'TRACKED_NO_DATA'
  | 'TRACKED_CANDLE_SYNC_FAILED'
  | 'ALREADY_SP500'
  | 'SYMBOL_NOT_FOUND'
  | 'METADATA_PROVIDER_FAILED'
  | 'DEACTIVATED'
  | 'NOT_CUSTOM_TRACKED'

export interface AdminCustomTicker {
  ticker: string
  state: CustomTickerState
  company_name: string | null
  exchange: string | null
  sector: string | null
  is_custom_tracked: boolean
  is_sp500_member: boolean
  stored_candle_count: number
  first_candle_date: string | null
  latest_candle_date: string | null
  message: string
}

export interface AdminCustomTickerListItem {
  ticker: string
  company_name: string
  exchange: string
  sector: string | null
  is_custom_tracked: boolean
  is_sp500_member: boolean
  stored_candle_count: number
  first_candle_date: string | null
  latest_candle_date: string | null
}
