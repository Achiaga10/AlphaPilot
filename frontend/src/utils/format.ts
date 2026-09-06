export function formatMoney(value: string | number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(Number(value))
}

export function formatPercent(value: string | number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return '—'
  return `${Number(value).toFixed(digits)}%`
}

export function formatScore(value: string | null): string {
  if (value === null || !Number.isFinite(Number(value))) return 'Not scored'
  return Number(value).toFixed(4)
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return 'Not available'
  const [year, month, day] = value.split('-').map(Number)
  if (!year || !month || !day) return value
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(new Date(year, month - 1, day))
}

const REASON_LABELS: Record<string, string> = {
  BUY_APPROVED: 'Buy approved',
  SELL_APPROVED: 'Sell approved',
  ALREADY_HELD: 'Already held',
  NO_POSITION_TO_SELL: 'No position to sell',
  MAX_POSITIONS: 'Maximum positions reached',
  INSUFFICIENT_CASH: 'Insufficient cash',
  CASH_RESERVE: 'Cash reserve protected',
  MAX_POSITION_WEIGHT: 'Maximum position weight reached',
  PORTFOLIO_RISK_LIMIT: 'Portfolio risk limit reached',
  SECTOR_LIMIT: 'Sector limit reached',
  INSUFFICIENT_HISTORY: 'Insufficient technical history',
  INVALID_RISK_DISTANCE: 'Invalid risk distance',
  RANKING_NOT_SELECTED: 'Not selected by ranking',
  INSUFFICIENT_ALLOCATION: 'Allocation cannot purchase one share',
  STALE_DATA: 'Stored data is stale',
  NO_ACTION: 'No portfolio action',
  ENTRY_TOO_EXTENDED_ABOVE_EMA20: 'Entry too extended above EMA20',
  EMA20_ENTRY_SAFETY_BLOCKED: 'EMA20 entry safety blocked',
  EMA20_ENTRY_REVALIDATION_UNAVAILABLE: 'EMA20 entry revalidation unavailable',
  USER_EXCLUDED_FROM_RECOMMENDATIONS: 'Excluded by you',
  USER_EXCLUDED: 'Excluded by you',
  LOSS_CONTROL_UNAVAILABLE: 'Loss control unavailable',
  PORTFOLIO_POSITION_CONSTRAINT: 'Portfolio position constraint',
  SECTOR_CONSTRAINT: 'Sector constraint',
  CASH_ALLOCATION_CONSTRAINT: 'Cash or allocation constraint',
  NEWS_AGGREGATE_UNAVAILABLE: 'News aggregate unavailable',
  NEWS_AGGREGATE_STALE: 'News aggregate stale',
  NEWS_WEAK_EVIDENCE: 'Weak News evidence',
  TARGETED_NEWS_REVIEW_REQUIRED: 'Targeted News review required',
  ATTRIBUTABLE_NEWS_UNAVAILABLE: 'Attributable News unavailable',
  GEMINI_REQUIRED_BUT_UNAVAILABLE: 'Required Gemini review unavailable',
  NEWS_BUY_BLOCKED_ADVERSE_EVIDENCE: 'Adverse News blocked BUY',
  FINAL_APPROVED_BUY: 'Final actionable BUY',
}

export function humanizeReason(value: string): string {
  return REASON_LABELS[value] ?? value.toLowerCase().replaceAll('_', ' ')
}

export function strategyLabel(strategy: string): string {
  return strategy === 'micho-150' ? 'Micho 150' : 'EMA20 Pullback'
}

export function sizingLabel(policy: string): string {
  if (policy === 'atr-risk') return 'ATR risk'
  if (policy === 'atr-volatility-normalized') return 'ATR volatility normalized'
  return 'Equal slot'
}

export function selectionLabel(policy: string): string {
  return policy === 'relative-strength-20' ? 'RS20 ranking' : 'Ticker ascending control'
}

export function classificationLabel(value: string): string {
  return value === 'PROMISING_RESEARCH_BASELINE'
    ? 'Promising research baseline'
    : 'Research only'
}
