import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import { applyPortfolioPlanAction, previewPortfolioPlanAction, summarizePortfolioState } from '../../api/portfolio'
import type {
  CurrentPortfolioInput,
  ManualSellResult,
  PlanDraft,
  PortfolioDecision,
  PortfolioDraftSummary,
  PortfolioPlan,
  PortfolioPlanActionResult,
  PortfolioPositionInput,
} from '../../types/portfolio'

const STORAGE_KEY = 'alphapilot.plan-draft.v1'

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

export const defaultDraft: PlanDraft = {
  cash: '100000',
  positions: [],
  strategy: 'ema20-pullback',
  selectionPolicy: 'relative-strength-20',
  asOfDate: today(),
  tickerScope: '',
}

function loadDraft(): PlanDraft {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    if (!saved) return defaultDraft
    const parsed: unknown = JSON.parse(saved)
    if (typeof parsed !== 'object' || parsed === null) return defaultDraft
    const value = parsed as Record<string, unknown>
    const positions = Array.isArray(value.positions)
      ? value.positions.flatMap((item): PortfolioPositionInput[] => {
        if (typeof item !== 'object' || item === null) return []
        const position = item as Record<string, unknown>
        if (
          typeof position.ticker !== 'string'
          || typeof position.shares !== 'number'
          || typeof position.reference_price !== 'string'
        ) return []
        return [{
          ticker: position.ticker,
          shares: position.shares,
          reference_price: position.reference_price,
          cost_basis: typeof position.cost_basis === 'string' ? position.cost_basis : null,
          sector: typeof position.sector === 'string' ? position.sector : null,
          modeled_risk_dollars: typeof position.modeled_risk_dollars === 'string'
            ? position.modeled_risk_dollars
            : '0',
        }]
      })
      : defaultDraft.positions
    return {
      cash: typeof value.cash === 'string' ? value.cash : defaultDraft.cash,
      positions,
      strategy: value.strategy === 'micho-150' ? 'micho-150' : 'ema20-pullback',
      selectionPolicy: value.selectionPolicy === 'ticker-ascending'
        ? 'ticker-ascending'
        : 'relative-strength-20',
      asOfDate: typeof value.asOfDate === 'string' ? value.asOfDate : defaultDraft.asOfDate,
      tickerScope: typeof value.tickerScope === 'string' ? value.tickerScope : '',
    }
  } catch {
    return defaultDraft
  }
}

export function portfolioInputFromDraft(draft: PlanDraft): CurrentPortfolioInput {
  return {
    cash: draft.cash,
    positions: draft.positions.map((position) => ({
      ticker: position.ticker.trim().toUpperCase(),
      shares: position.shares,
      reference_price: position.reference_price,
      cost_basis: position.cost_basis ?? null,
      sector: position.sector ?? null,
      modeled_risk_dollars: position.modeled_risk_dollars ?? '0',
    })),
  }
}

function updateDraftPortfolio(draft: PlanDraft, portfolio: CurrentPortfolioInput): PlanDraft {
  return { ...draft, cash: portfolio.cash, positions: portfolio.positions }
}

interface WorkspaceValue {
  draft: PlanDraft
  setDraft: (draft: PlanDraft) => void
  draftSummary: PortfolioDraftSummary | null
  plan: PortfolioPlan | null
  setPlanResult: (plan: PortfolioPlan, draft: PlanDraft) => void
  previewDecision: (decision: PortfolioDecision, requestedShares: number) => Promise<PortfolioPlanActionResult | null>
  applyDecision: (decision: PortfolioDecision, requestedShares?: number) => Promise<PortfolioPlanActionResult | null>
  applyManualSellResult: (result: ManualSellResult) => void
  appliedActionIds: ReadonlySet<string>
  actionPendingId: string | null
  lastActionMessage: string | null
  hasAppliedPlanActions: boolean
  isPlanDirty: boolean
  hasPlanDeviation: boolean
}

const WorkspaceContext = createContext<WorkspaceValue | null>(null)

export function PortfolioWorkspaceProvider({ children }: { children: ReactNode }) {
  const [draftState, setDraftState] = useState(loadDraft)
  const [draftSummary, setDraftSummary] = useState<PortfolioDraftSummary | null>(null)
  const [plan, setPlan] = useState<PortfolioPlan | null>(null)
  const [expectedDraftSnapshot, setExpectedDraftSnapshot] = useState<string | null>(null)
  const [appliedActionIds, setAppliedActionIds] = useState<ReadonlySet<string>>(new Set())
  const [actionPendingId, setActionPendingId] = useState<string | null>(null)
  const [lastActionMessage, setLastActionMessage] = useState<string | null>(null)
  const [hasPlanDeviation, setHasPlanDeviation] = useState(false)

  const currentDraftSnapshot = JSON.stringify(draftState)

  useEffect(() => {
    let active = true
    void summarizePortfolioState(portfolioInputFromDraft(draftState))
      .then((summary) => { if (active) setDraftSummary(summary) })
      .catch(() => { if (active) setDraftSummary(null) })
    return () => { active = false }
  }, [currentDraftSnapshot, draftState])

  useEffect(() => {
    function syncOtherTab(event: StorageEvent) {
      if (event.key === STORAGE_KEY && event.newValue) setDraftState(loadDraft())
    }
    window.addEventListener('storage', syncOtherTab)
    return () => window.removeEventListener('storage', syncOtherTab)
  }, [])

  function persist(nextDraft: PlanDraft) {
    setDraftState(nextDraft)
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(nextDraft))
  }

  const value = useMemo<WorkspaceValue>(
    () => ({
      draft: draftState,
      setDraft: (draft) => {
        persist(draft)
        setLastActionMessage(
          plan ? 'Portfolio changed manually. Regenerate Portfolio Plan before applying remaining recommendations.' : null,
        )
      },
      draftSummary,
      plan,
      setPlanResult: (nextPlan, submittedDraft) => {
        setPlan(nextPlan)
        setExpectedDraftSnapshot(JSON.stringify(submittedDraft))
        setAppliedActionIds(new Set())
        setActionPendingId(null)
        setLastActionMessage(null)
        setHasPlanDeviation(false)
      },
      previewDecision: async (decision, requestedShares) => {
        if (
          plan === null
          || expectedDraftSnapshot !== currentDraftSnapshot
          || decision.action_id === null
          || appliedActionIds.has(decision.action_id)
          || actionPendingId !== null
        ) return null
        setActionPendingId(decision.action_id)
        try {
          return await previewPortfolioPlanAction({
            plan_id: plan.plan_id,
            portfolio: portfolioInputFromDraft(draftState),
            decision,
            applied_action_ids: [...appliedActionIds],
            requested_shares: requestedShares,
            strategy_profile_id: plan.strategy_profile.profile_id,
            strategy_profile_version: plan.strategy_profile.version,
            sizing_policy: plan.sizing_policy,
            risk_config: plan.config,
          })
        } finally {
          setActionPendingId(null)
        }
      },
      applyDecision: async (decision, requestedShares = decision.proposed_shares) => {
        if (
          plan === null
          || expectedDraftSnapshot !== currentDraftSnapshot
          || decision.action_id === null
          || appliedActionIds.has(decision.action_id)
          || actionPendingId !== null
        ) return null
        setActionPendingId(decision.action_id)
        try {
          const result = await applyPortfolioPlanAction({
            plan_id: plan.plan_id,
            portfolio: portfolioInputFromDraft(draftState),
            decision,
            applied_action_ids: [...appliedActionIds],
            requested_shares: requestedShares,
            strategy_profile_id: plan.strategy_profile.profile_id,
            strategy_profile_version: plan.strategy_profile.version,
            sizing_policy: plan.sizing_policy,
            risk_config: plan.config,
          })
          if (!result.applied || result.action_id === null) {
            setLastActionMessage(
              `${decision.ticker} was not applied: ${result.reason.replaceAll('_', ' ').toLowerCase()}. Regenerate if the draft has changed.`,
            )
            return result
          }
          const nextDraft = updateDraftPortfolio(draftState, result.portfolio)
          persist(nextDraft)
          setDraftSummary(result.summary)
          setExpectedDraftSnapshot(JSON.stringify(nextDraft))
          setAppliedActionIds((current) => new Set([...current, result.action_id!]))
          if (result.quantity_semantics === 'USER_QUANTITY_OVERRIDE') {
            setHasPlanDeviation(true)
            setLastActionMessage('Portfolio differs from AlphaPilot\'s original sizing plan. Remaining recommendations will be revalidated before application.')
          } else {
            setLastActionMessage(
              `${decision.ticker} ${decision.decision === 'BUY' ? 'was added to' : 'was removed from'} the research portfolio. Other recommendations from this plan remain available and will be revalidated.`,
            )
          }
          return result
        } finally {
          setActionPendingId(null)
        }
      },
      applyManualSellResult: (result) => {
        if (!result.applied) return
        const nextDraft = updateDraftPortfolio(draftState, result.portfolio)
        persist(nextDraft)
        setDraftSummary(result.summary)
        setLastActionMessage('Portfolio changed manually. Regenerate Portfolio Plan before applying remaining recommendations.')
      },
      appliedActionIds,
      actionPendingId,
      lastActionMessage,
      hasAppliedPlanActions: appliedActionIds.size > 0,
      isPlanDirty: plan !== null && expectedDraftSnapshot !== currentDraftSnapshot,
      hasPlanDeviation,
    }),
    [
      actionPendingId,
      appliedActionIds,
      currentDraftSnapshot,
      draftState,
      draftSummary,
      expectedDraftSnapshot,
      lastActionMessage,
      hasPlanDeviation,
      plan,
    ],
  )

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}

export function usePortfolioWorkspace(): WorkspaceValue {
  const value = useContext(WorkspaceContext)
  if (!value) throw new Error('usePortfolioWorkspace must be used inside its provider')
  return value
}
