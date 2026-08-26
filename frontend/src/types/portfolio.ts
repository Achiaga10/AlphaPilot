export type StrategyName = 'ema20-pullback' | 'micho-150'
export type SelectionPolicy = 'relative-strength-20' | 'ticker-ascending'
export type SizingPolicy = 'equal-slot' | 'atr-risk' | 'atr-volatility-normalized'
export type StrategySignal = 'BUY' | 'HOLD' | 'SELL'
export type PortfolioDecisionType = 'BUY' | 'HOLD' | 'SELL' | 'SKIP'

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
  exit_mode: 'hybrid'
  hybrid_trend_threshold_pct: '2'
  micho_entry_mode: 'both'
  selection_policy: SelectionPolicy
  sizing_policy: SizingPolicy
  as_of_date: string
  tickers: string[] | null
  portfolio: CurrentPortfolioInput
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
  portfolio: PortfolioSummary
  config: PortfolioRiskConfig
  strategy: StrategyName
  selection_policy: SelectionPolicy
  sizing_policy: SizingPolicy
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
  portfolio: CurrentPortfolioInput
  decision: PortfolioDecision
  applied_action_ids: string[]
  requested_shares: number | null
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
  quantity_semantics: 'SAME_PLAN_ACTION' | 'USER_QUANTITY_OVERRIDE'
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
}

export interface LatestStoredPrice {
  ticker: string
  price: string | null
  price_date: string | null
  source: 'LATEST_STORED_CANDLE'
}

export interface ManualSellRequest {
  portfolio: CurrentPortfolioInput
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
  sizingPolicy: SizingPolicy
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
