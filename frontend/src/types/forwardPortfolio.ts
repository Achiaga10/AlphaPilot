export type ForwardPortfolioStatus = 'ACTIVE' | 'PAUSED' | 'ARCHIVED'
export type ForwardOrderStatus = 'PENDING' | 'FILLED' | 'CANCELLED'
export type ForwardOrderSide = 'ENTRY' | 'EXIT'

export interface ForwardPortfolio {
  id: string
  strategy_id: 'micho-150-v1'
  strategy_version: 1
  execution_mode: 'VIRTUAL'
  broker_execution_mode: 'MANUAL_EXTERNAL'
  status: ForwardPortfolioStatus
  created_at: string
  updated_at: string
  forward_start_session: string
  initial_cash: string
  cash_balance: string
  equity: string
  realized_pnl: string
  revision: number
  last_processed_session: string | null
  last_successful_cycle: string | null
  last_error: string | null
}

export interface ForwardOrder {
  id: string
  ticker: string
  side: ForwardOrderSide
  status: ForwardOrderStatus
  source_signal_session: string
  planned_execution_session: string | null
  actual_execution_session: string | null
  approved_allocation: string
  planned_shares: number
  filled_shares: number | null
  raw_fill_price: string | null
  modeled_fill_price: string | null
  friction_bps: string
  friction_dollars: string | null
  reason_code: string
  strategy_id: string
  strategy_version: number
  ranking_score: string | null
  ranking_position: number | null
  loss_control_policy: string
  loss_control_boundary: string | null
  loss_control_trigger: string | null
  risk_per_share: string | null
  planned_risk_dollars: string | null
  planned_risk_pct: string | null
  evidence: Record<string, unknown>
  created_at: string
}

export interface ForwardPosition {
  id: string
  ticker: string
  status: 'OPEN' | 'CLOSED'
  shares: number
  signal_session: string
  entry_session: string
  raw_entry_price: string
  modeled_entry_price: string
  entry_friction: string
  cost_basis: string
  last_mark_session: string
  last_close: string
  market_value: string
  unrealized_pnl: string
  unrealized_return_pct: string
  loss_control_policy: string
  loss_control_boundary: string
  loss_control_trigger: string
  loss_control_source: string
  risk_per_share: string
  planned_risk_dollars: string
  holding_sessions: number
  holding_calendar_days: number
  exit_signal_session: string | null
  closed_session: string | null
  management_status: string
}

export interface ForwardTrade {
  id: string
  ticker: string
  strategy_id: string
  strategy_version: number
  signal_session: string
  entry_session: string
  raw_entry_price: string
  modeled_entry_price: string
  entry_friction: string
  approved_allocation: string
  shares: number
  loss_control_policy: string
  initial_loss_control_boundary: string
  loss_control_trigger: string
  loss_control_source: string
  risk_per_share: string
  planned_risk_dollars: string
  entry_evidence: Record<string, unknown>
  exit_signal_session: string
  exit_session: string
  raw_exit_price: string
  modeled_exit_price: string
  exit_friction: string
  exit_reason: string
  gross_pnl: string
  net_pnl: string
  return_pct: string
  holding_sessions: number
  holding_calendar_days: number
}

export interface ForwardEvent {
  id: string
  event_type: string
  trading_session: string | null
  ticker: string | null
  strategy_id: string
  reason_code: string
  numeric_provenance: Record<string, unknown>
  created_at: string
}

export interface ForwardAnalytics {
  starting_equity: string
  current_equity: string
  cash: string
  market_value: string
  realized_pnl: string
  unrealized_pnl: string
  total_pnl: string
  net_return_pct: string
  max_drawdown_pct: string
  completed_trades: number
  open_trades: number
  win_rate_pct: string | null
  profit_factor: string | null
  expectancy: string | null
  average_winner: string | null
  average_loser: string | null
  worst_trade: string | null
  average_holding_sessions: string | null
  turnover_pct: string
  friction_dollars: string
  current_exposure_pct: string
  average_exposure_pct: string | null
  max_concurrent_positions: number
  stop_exits: number
  strategy_exits: number
}

export interface ForwardHealth {
  scheduler_running: boolean
  scheduler_status: string
  portfolio_status: ForwardPortfolioStatus | null
  last_successful_cycle: string | null
  last_processed_session: string | null
  latest_completed_market_session: string | null
  pending_sessions: number
  data_ready: boolean
  last_error: string | null
  latest_cycle_status: string | null
}

export interface ForwardCycleResult {
  portfolio_id: string | null
  latest_completed_market_session: string | null
  processed_sessions: string[]
  skipped_sessions: string[]
}

export type ExternalActionStatus = 'AWAITING_ACTION' | 'AWAITING_RECORD' | 'PARTIALLY_RECORDED' | 'RECORDED' | 'SKIPPED' | 'VIRTUAL_CANCELLED'
export type ExternalReconciliationStatus = 'MISSING_RECORD' | 'INCOMPLETE' | 'PARTIAL' | 'ALIGNED' | 'PRICE_DIVERGENCE' | 'QUANTITY_DIVERGENCE' | 'PRICE_AND_QUANTITY_DIVERGENCE' | 'SKIPPED' | 'VIRTUAL_CANCELLED' | 'EXECUTED_AFTER_VIRTUAL_CANCEL' | 'BROKER_CONFLICT'
export type BrokerMatchState = 'UNMATCHED' | 'AUTO_MATCHED' | 'AMBIGUOUS' | 'MANUAL_MATCHED' | 'IGNORED_EXTERNAL' | 'CONFLICT'

export interface ExternalFill {
  id: string
  side: 'BUY' | 'SELL'
  quantity: number
  price: string
  executed_at: string
  fee: string | null
  mark_complete: boolean
  source: string
  voided_at: string | null
  void_reason: string | null
}

export interface ExternalEvent {
  id: string
  event_type: string
  reason_code: string
  source: string
  facts: Record<string, unknown>
  created_at: string
}

export interface ExternalAction {
  id: string
  forward_portfolio_id: string
  forward_order_id: string
  position_id: string | null
  ticker: string
  side: 'BUY' | 'SELL'
  strategy_id: string
  strategy_version: number
  broker: string
  provenance: string
  canonical_execution_source: 'NONE' | 'MANUAL_USER_RECORDED' | 'ALPACA_READ_ONLY_SYNC'
  broker_match_state: BrokerMatchState | null
  source_signal_session: string
  planned_execution_session: string | null
  actual_virtual_execution_session: string | null
  expected_timing: string
  planned_shares: number
  virtual_filled_shares: number | null
  virtual_order_status: ForwardOrderStatus
  virtual_modeled_fill_price: string | null
  loss_control_policy: string
  loss_control_boundary: string | null
  decision_reason: string
  created_at: string
  status: ExternalActionStatus
  reconciliation_status: ExternalReconciliationStatus
  due_status: string
  recorded_shares: number | string
  weighted_fill_price: string | null
  recorded_notional: string | null
  recorded_fees: string | null
  fee_coverage_complete: boolean
  share_variance_vs_planned: number | string | null
  share_variance_vs_virtual: number | string | null
  price_difference_per_share: string | null
  price_difference_bps: string | null
  virtual_notional: string | null
  notional_variance: string | null
  timing_difference_seconds: number | null
  skip_reason: string | null
  fills: ExternalFill[]
  broker_executions: BrokerExecution[]
  events: ExternalEvent[]
}

export interface ExternalFillInput {
  request_key: string
  side: 'BUY' | 'SELL'
  quantity: number
  price: string
  executed_at: string
  fee: string | null
  mark_complete: boolean
}

export interface ExternalTradeComparison {
  forward_trade_id: string
  ticker: string
  completeness: string
  virtual_shares: number
  recorded_entry_shares: number | string | null
  recorded_exit_shares: number | string | null
  virtual_entry_price: string
  recorded_entry_price: string | null
  virtual_exit_price: string
  recorded_exit_price: string | null
  virtual_net_pnl: string
  recorded_gross_pnl: string | null
  recorded_execution_pnl: string | null
  pnl_difference: string | null
  recorded_fees: string | null
  quantity_variance: number | string | null
}

export interface ExternalExecutionAnalytics {
  expected_actions: number
  recorded_actions: number
  skipped_actions: number
  missing_records: number
  partial_actions: number
  actions_awaiting_execution: number
  actions_awaiting_recording: number
  diverged_actions: number
  recording_rate_pct: string | null
  completed_fully_reconciled_trades: number
  matched_virtual_pnl: string | null
  matched_recorded_execution_pnl: string | null
  matched_pnl_difference: string | null
  manual_actions: number
  broker_actions: number
  conflict_actions: number
}

export interface AlpacaSyncStatus {
  enabled: boolean
  configured: boolean
  environment: 'PAPER' | 'LIVE'
  scheduler_running: boolean
  status: string
  last_attempt_at: string | null
  last_success_at: string | null
  last_error: string | null
  data_age_seconds: number | null
  account_snapshots: number
  positions: number
  orders: number
  executions: number
  unmatched_executions: number
  interval_seconds: number
  initial_lookback_days: number
  overlap_minutes: number
  provenance: 'ALPACA_READ_ONLY_SYNC'
}

export interface BrokerAccount {
  environment: 'PAPER' | 'LIVE'
  status: string
  currency: string
  cash: string
  equity: string
  buying_power: string
  observed_at: string
}

export interface BrokerPosition {
  environment: 'PAPER' | 'LIVE'
  symbol: string
  side: string
  quantity: string
  average_entry_price: string | null
  current_price: string | null
  market_value: string | null
  unrealized_pnl: string | null
  observed_at: string
}

export interface BrokerOrder {
  id: string
  environment: 'PAPER' | 'LIVE'
  broker_order_id: string
  client_order_id: string | null
  symbol: string
  side: string
  status: string
  order_type: string
  quantity: string | null
  filled_quantity: string
  filled_average_price: string | null
  submitted_at: string | null
  broker_updated_at: string | null
}

export interface BrokerExecution {
  id: string
  provenance: 'ALPACA_READ_ONLY_SYNC'
  environment: 'PAPER' | 'LIVE'
  broker_activity_id: string
  broker_order_id: string | null
  symbol: string
  side: 'BUY' | 'SELL'
  quantity: string
  price: string
  fee: string | null
  executed_at: string
  match_state: BrokerMatchState
  match_reason: string
  external_case_id: string | null
  matched_at: string | null
  ignored_reason: string | null
}
