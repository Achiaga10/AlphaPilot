import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { applyPortfolioPlanAction, getCurrentResearchPortfolio, initializeResearchPortfolio, previewPortfolioPlanAction } from '../../api/portfolio'
import type { ManualSellResult, PlanDraft, PortfolioDecision, PortfolioDraftSummary, PortfolioPlan, PortfolioPlanActionResult, PortfolioPositionInput, ResearchPortfolio } from '../../types/portfolio'

const STORAGE_KEY = 'alphapilot.plan-draft.v1'
const today = () => new Date().toISOString().slice(0, 10)
export const defaultDraft: PlanDraft = { cash: '100000', positions: [], strategy: 'ema20-pullback', selectionPolicy: 'relative-strength-20', asOfDate: today(), tickerScope: '' }

function loadDraft(): PlanDraft {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    if (!saved) return defaultDraft
    const value = JSON.parse(saved) as Record<string, unknown>
    const positions = Array.isArray(value.positions) ? value.positions.flatMap((item): PortfolioPositionInput[] => {
      if (typeof item !== 'object' || item === null) return []
      const position = item as Record<string, unknown>
      if (typeof position.ticker !== 'string' || typeof position.shares !== 'number' || typeof position.reference_price !== 'string') return []
      return [{ ticker: position.ticker, shares: position.shares, reference_price: position.reference_price, cost_basis: typeof position.cost_basis === 'string' ? position.cost_basis : null }]
    }) : []
    return { ...defaultDraft, cash: typeof value.cash === 'string' ? value.cash : defaultDraft.cash, positions, strategy: value.strategy === 'micho-150' ? 'micho-150' : 'ema20-pullback', selectionPolicy: value.selectionPolicy === 'ticker-ascending' ? 'ticker-ascending' : 'relative-strength-20', asOfDate: typeof value.asOfDate === 'string' ? value.asOfDate : defaultDraft.asOfDate, tickerScope: typeof value.tickerScope === 'string' ? value.tickerScope : '' }
  } catch { return defaultDraft }
}

function persistPreferences(draft: PlanDraft) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ strategy: draft.strategy, selectionPolicy: draft.selectionPolicy, asOfDate: draft.asOfDate, tickerScope: draft.tickerScope, portfolioMigrated: true }))
}

function summary(portfolio: ResearchPortfolio): PortfolioDraftSummary | null {
  if (portfolio.total_equity === null || portfolio.positions_market_value === null || portfolio.cash_pct === null || portfolio.invested_pct === null) return null
  return { equity: portfolio.total_equity, cash: portfolio.cash, cash_pct: portfolio.cash_pct, invested_value: portfolio.positions_market_value, invested_pct: portfolio.invested_pct, open_positions: portfolio.positions.length, positions: portfolio.positions.flatMap((position) => position.latest_completed_close !== null && position.market_value !== null && position.portfolio_weight_pct !== null ? [{ ticker: position.ticker, shares: position.quantity, reference_price: position.latest_completed_close, market_value: position.market_value, portfolio_weight_pct: position.portfolio_weight_pct, cost_basis: position.cost_basis, sector: position.sector ?? 'UNCLASSIFIED', modeled_risk_dollars: position.modeled_risk_dollars }] : []) }
}

interface WorkspaceValue {
  draft: PlanDraft; setDraft: (draft: PlanDraft) => void
  portfolio: ResearchPortfolio | null; portfolioPending: boolean; portfolioError: Error | null; refreshPortfolio: () => Promise<void>
  draftSummary: PortfolioDraftSummary | null; plan: PortfolioPlan | null
  setPlanResult: (plan: PortfolioPlan, draft: PlanDraft) => void
  previewDecision: (decision: PortfolioDecision, requestedShares: number) => Promise<PortfolioPlanActionResult | null>
  applyDecision: (decision: PortfolioDecision, requestedShares?: number) => Promise<PortfolioPlanActionResult | null>
  applyManualSellResult: (result: ManualSellResult) => void
  appliedActionIds: ReadonlySet<string>; actionPendingId: string | null; lastActionMessage: string | null
  hasAppliedPlanActions: boolean; isPlanDirty: boolean; hasPlanDeviation: boolean
}
const WorkspaceContext = createContext<WorkspaceValue | null>(null)

export function PortfolioWorkspaceProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [draft, setDraftState] = useState(loadDraft)
  const [plan, setPlan] = useState<PortfolioPlan | null>(null)
  const [planPreferences, setPlanPreferences] = useState<string | null>(null)
  const [appliedActionIds, setAppliedActionIds] = useState<ReadonlySet<string>>(new Set())
  const [actionPendingId, setActionPendingId] = useState<string | null>(null)
  const [lastActionMessage, setLastActionMessage] = useState<string | null>(null)
  const [hasPlanDeviation, setHasPlanDeviation] = useState(false)
  const [manualMutation, setManualMutation] = useState(false)
  const initializationStarted = useRef(false)
  const portfolioQuery = useQuery({ queryKey: ['research-portfolio'], queryFn: ({ signal }) => getCurrentResearchPortfolio(signal) })

  useEffect(() => {
    if (portfolioQuery.isPending || portfolioQuery.isError || portfolioQuery.data !== null || initializationStarted.current) return
    initializationStarted.current = true
    void initializeResearchPortfolio({ starting_cash: draft.cash, imported_positions: draft.positions.map((position) => ({ ticker: position.ticker.trim().toUpperCase(), quantity: position.shares, average_cost: position.cost_basis ?? position.reference_price })) })
      .then((created) => { persistPreferences(draft); queryClient.setQueryData(['research-portfolio'], created) })
      .catch(() => { initializationStarted.current = false })
  }, [draft, portfolioQuery.data, portfolioQuery.isError, portfolioQuery.isPending, queryClient])

  const refreshPortfolio = useCallback(async () => { await queryClient.invalidateQueries({ queryKey: ['research-portfolio'] }) }, [queryClient])
  const portfolio = portfolioQuery.data ?? null
  const value = useMemo<WorkspaceValue>(() => ({
    draft,
    setDraft: (next) => { const preferences = { ...next, cash: draft.cash, positions: draft.positions }; setDraftState(preferences); persistPreferences(preferences) },
    portfolio, portfolioPending: portfolioQuery.isPending || portfolioQuery.data === null, portfolioError: portfolioQuery.error, refreshPortfolio,
    draftSummary: portfolio ? summary(portfolio) : null, plan,
    setPlanResult: (nextPlan, submittedDraft) => { setPlan(nextPlan); setPlanPreferences(JSON.stringify({ strategy: submittedDraft.strategy, selectionPolicy: submittedDraft.selectionPolicy, asOfDate: submittedDraft.asOfDate, tickerScope: submittedDraft.tickerScope })); setAppliedActionIds(new Set()); setLastActionMessage(null); setHasPlanDeviation(false); setManualMutation(false) },
    previewDecision: async (decision, requestedShares) => {
      if (!plan || !portfolio || decision.action_id === null || actionPendingId !== null || plan.portfolio_revision !== portfolio.revision) return null
      setActionPendingId(decision.action_id)
      try { return await previewPortfolioPlanAction({ plan_id: plan.plan_id, portfolio_id: portfolio.portfolio_id, portfolio_revision: plan.portfolio_revision, analysis_as_of_date: plan.analysis_as_of_date, selection_policy: plan.selection_policy, decision, applied_action_ids: [...appliedActionIds], requested_shares: requestedShares, strategy_profile_id: plan.strategy_profile.profile_id, strategy_profile_version: plan.strategy_profile.version, sizing_policy: plan.sizing_policy, risk_config: plan.config }) } finally { setActionPendingId(null) }
    },
    applyDecision: async (decision, requestedShares = decision.proposed_shares) => {
      if (!plan || !portfolio || decision.action_id === null || actionPendingId !== null || plan.portfolio_revision !== portfolio.revision) return null
      setActionPendingId(decision.action_id)
      try {
        const result = await applyPortfolioPlanAction({ plan_id: plan.plan_id, portfolio_id: portfolio.portfolio_id, portfolio_revision: plan.portfolio_revision, analysis_as_of_date: plan.analysis_as_of_date, selection_policy: plan.selection_policy, decision, applied_action_ids: [...appliedActionIds], requested_shares: requestedShares, strategy_profile_id: plan.strategy_profile.profile_id, strategy_profile_version: plan.strategy_profile.version, sizing_policy: plan.sizing_policy, risk_config: plan.config })
        if (result.applied && result.action_id) { setAppliedActionIds((current) => new Set([...current, result.action_id!])); setLastActionMessage(`${decision.ticker} research portfolio action was persisted. Regenerate the plan for the new portfolio revision.`); if (result.quantity_semantics === 'USER_QUANTITY_OVERRIDE') setHasPlanDeviation(true); await refreshPortfolio() }
        return result
      } finally { setActionPendingId(null) }
    },
    applyManualSellResult: (result) => { if (result.applied) { setManualMutation(true); setLastActionMessage('Research portfolio sale was persisted. Regenerate the plan for the new portfolio revision.'); void refreshPortfolio() } },
    appliedActionIds, actionPendingId, lastActionMessage, hasAppliedPlanActions: appliedActionIds.size > 0,
    isPlanDirty: plan !== null && (portfolio === null || plan.portfolio_revision !== portfolio.revision || appliedActionIds.size > 0 || manualMutation || planPreferences !== JSON.stringify({ strategy: draft.strategy, selectionPolicy: draft.selectionPolicy, asOfDate: draft.asOfDate, tickerScope: draft.tickerScope })), hasPlanDeviation,
  }), [actionPendingId, appliedActionIds, draft, hasPlanDeviation, lastActionMessage, manualMutation, plan, planPreferences, portfolio, portfolioQuery.data, portfolioQuery.error, portfolioQuery.isPending, refreshPortfolio])
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}

export function usePortfolioWorkspace(): WorkspaceValue {
  const value = useContext(WorkspaceContext)
  if (!value) throw new Error('usePortfolioWorkspace must be used inside its provider')
  return value
}
