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
