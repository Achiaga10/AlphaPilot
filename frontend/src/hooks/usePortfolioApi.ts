import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getCurrentForwardPortfolio,
  getForwardAnalytics,
  getForwardEvents,
  getForwardHealth,
  getForwardOrders,
  getForwardPositions,
  getForwardTrades,
  initializeForwardPortfolio,
  pauseForwardPortfolio,
  resumeForwardPortfolio,
  runForwardCycles,
  getExternalActions,
  getExternalReconciliation,
  getExternalExecutionAnalytics,
  recordExternalFill,
  skipExternalAction,
  voidExternalFill,
  getAlpacaSyncStatus,
  triggerAlpacaReadOnlySync,
  getAlpacaAccount,
  getAlpacaPositions,
  getAlpacaOrders,
  getAlpacaActivity,
  getAlpacaUnmatched,
  matchAlpacaExecution,
  unlinkAlpacaExecution,
  ignoreAlpacaExecution,
} from '../api/forwardPortfolio'
import type { ExternalFillInput, ForwardPortfolio } from '../types/forwardPortfolio'
import {
  applyManualSell,
  createPortfolioPlan,
  getHealth,
  getLatestStoredPrice,
  getRiskConfig,
  getStrategyProfiles,
  getPositionMonitoring,
  adjustResearchCash,
  addExternalPosition,
  reconcileResearchPosition,
  getPositionIntelligence,
  getPositionPaperValidations,
  getForwardPaperAnalytics,
  recordPaperValidationEntry,
  recordPaperValidationExit,
  askPositionCopilot,
  previewManualSell,
  getDailyPortfolioBrief,
  getDailyBriefOpportunities,
  refreshLivePortfolio,
  getPortfolioNews,
  refreshPortfolioNews,
  getPortfolioNewsSentiment,
  getExcludedTickers,
  excludeTicker,
  restoreTicker,
} from '../api/portfolio'
import {
  addCustomTicker,
  deactivateCustomTicker,
  getCustomTickers,
  getAdminCapability,
  getAdminDataSummary,
  getDailySchedulerStatus,
  getAdminSyncJob,
  startAdminFullSync,
  startAdminCandleSync,
  startAdminUniverseSync,
  syncAdminTicker,
} from '../api/admin'
import type {
  AdminFullSyncRequest,
  AdminTickerSyncRequest,
  ManualSellRequest,
  PortfolioPlanRequest,
  CashAdjustmentRequest,
  ExternalPositionRequest,
  PositionReconciliationRequest,
  PaperValidationEntryRequest,
  PaperValidationExitRequest,
} from '../types/portfolio'

export function useHealthQuery() {
  return useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => getHealth(signal),
    retry: 1,
    retryDelay: 100,
    refetchInterval: 30_000,
  })
}

export function useCurrentForwardPortfolioQuery() {
  return useQuery({
    queryKey: ['forward-portfolio'],
    queryFn: ({ signal }) => getCurrentForwardPortfolio(signal),
    refetchInterval: 60_000,
  })
}

export function useForwardPortfolioDetails(portfolioId: string | null) {
  const enabled = Boolean(portfolioId)
  return {
    positions: useQuery({
      queryKey: ['forward-positions', portfolioId],
      queryFn: ({ signal }) => getForwardPositions(portfolioId ?? '', signal), enabled,
    }),
    orders: useQuery({
      queryKey: ['forward-orders', portfolioId],
      queryFn: ({ signal }) => getForwardOrders(portfolioId ?? '', signal), enabled,
    }),
    trades: useQuery({
      queryKey: ['forward-trades', portfolioId],
      queryFn: ({ signal }) => getForwardTrades(portfolioId ?? '', signal), enabled,
    }),
    events: useQuery({
      queryKey: ['forward-events', portfolioId],
      queryFn: ({ signal }) => getForwardEvents(portfolioId ?? '', signal), enabled,
    }),
    analytics: useQuery({
      queryKey: ['forward-analytics', portfolioId],
      queryFn: ({ signal }) => getForwardAnalytics(portfolioId ?? '', signal), enabled,
    }),
    health: useQuery({
      queryKey: ['forward-health', portfolioId],
      queryFn: ({ signal }) => getForwardHealth(portfolioId ?? '', signal), enabled,
      refetchInterval: 60_000,
    }),
  }
}

export function useForwardPortfolioMutations() {
  const client = useQueryClient()
  const refresh = async () => {
    await client.invalidateQueries({ queryKey: ['forward-portfolio'] })
    await client.invalidateQueries({ predicate: (query) =>
      String(query.queryKey[0]).startsWith('forward-') })
  }
  return {
    initialize: useMutation({
      mutationFn: initializeForwardPortfolio,
      onSuccess: refresh,
    }),
    pause: useMutation({
      mutationFn: (portfolio: ForwardPortfolio) => pauseForwardPortfolio(portfolio),
      onSuccess: refresh,
    }),
    resume: useMutation({
      mutationFn: (portfolio: ForwardPortfolio) => resumeForwardPortfolio(portfolio),
      onSuccess: refresh,
    }),
    run: useMutation({
      mutationFn: runForwardCycles,
      onSuccess: refresh,
    }),
  }
}

export function useExternalExecution(portfolioId: string | null) {
  const client = useQueryClient()
  const enabled = Boolean(portfolioId)
  const refresh = async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ['forward-external-actions', portfolioId] }),
      client.invalidateQueries({ queryKey: ['forward-external-reconciliation', portfolioId] }),
      client.invalidateQueries({ queryKey: ['forward-external-analytics', portfolioId] }),
    ])
  }
  return {
    actions: useQuery({
      queryKey: ['forward-external-actions', portfolioId],
      queryFn: ({ signal }) => getExternalActions(portfolioId ?? '', signal), enabled,
      refetchInterval: 60_000,
    }),
    comparisons: useQuery({
      queryKey: ['forward-external-reconciliation', portfolioId],
      queryFn: ({ signal }) => getExternalReconciliation(portfolioId ?? '', signal), enabled,
    }),
    analytics: useQuery({
      queryKey: ['forward-external-analytics', portfolioId],
      queryFn: ({ signal }) => getExternalExecutionAnalytics(portfolioId ?? '', signal), enabled,
    }),
    record: useMutation({
      mutationFn: ({ caseId, fill }: { caseId: string; fill: ExternalFillInput }) =>
        recordExternalFill(portfolioId ?? '', caseId, fill), onSuccess: refresh,
    }),
    skip: useMutation({
      mutationFn: ({ caseId, reason }: { caseId: string; reason: string }) =>
        skipExternalAction(portfolioId ?? '', caseId, reason), onSuccess: refresh,
    }),
    voidFill: useMutation({
      mutationFn: ({ fillId, reason, requestKey }: { fillId: string; reason: string; requestKey: string }) =>
        voidExternalFill(portfolioId ?? '', fillId, reason, requestKey), onSuccess: refresh,
    }),
  }
}

export function useAlpacaReadOnly() {
  const client = useQueryClient()
  const refresh = async () => {
    await client.invalidateQueries({ predicate: (query) =>
      String(query.queryKey[0]).startsWith('alpaca-read-only') ||
      String(query.queryKey[0]).startsWith('forward-external') })
  }
  return {
    status: useQuery({ queryKey: ['alpaca-read-only-status'], queryFn: ({ signal }) => getAlpacaSyncStatus(signal), refetchInterval: 60_000 }),
    account: useQuery({ queryKey: ['alpaca-read-only-account'], queryFn: ({ signal }) => getAlpacaAccount(signal), refetchInterval: 60_000 }),
    positions: useQuery({ queryKey: ['alpaca-read-only-positions'], queryFn: ({ signal }) => getAlpacaPositions(signal), refetchInterval: 60_000 }),
    orders: useQuery({ queryKey: ['alpaca-read-only-orders'], queryFn: ({ signal }) => getAlpacaOrders(signal) }),
    activity: useQuery({ queryKey: ['alpaca-read-only-activity'], queryFn: ({ signal }) => getAlpacaActivity(signal) }),
    unmatched: useQuery({ queryKey: ['alpaca-read-only-unmatched'], queryFn: ({ signal }) => getAlpacaUnmatched(signal), refetchInterval: 60_000 }),
    sync: useMutation({ mutationFn: triggerAlpacaReadOnlySync, onSuccess: refresh }),
    match: useMutation({ mutationFn: ({ executionId, caseId, reason, requestKey }: { executionId: string; caseId: string; reason: string; requestKey: string }) => matchAlpacaExecution(executionId, caseId, reason, requestKey), onSuccess: refresh }),
    unlink: useMutation({ mutationFn: ({ executionId, reason, requestKey }: { executionId: string; reason: string; requestKey: string }) => unlinkAlpacaExecution(executionId, reason, requestKey), onSuccess: refresh }),
    ignore: useMutation({ mutationFn: ({ executionId, reason, requestKey }: { executionId: string; reason: string; requestKey: string }) => ignoreAlpacaExecution(executionId, reason, requestKey), onSuccess: refresh }),
  }
}

export function useRiskConfigQuery() {
  return useQuery({
    queryKey: ['portfolio-risk-config'],
    queryFn: ({ signal }) => getRiskConfig(signal),
    staleTime: 5 * 60_000,
  })
}

export function useStrategyProfilesQuery() {
  return useQuery({
    queryKey: ['strategy-profiles'],
    queryFn: ({ signal }) => getStrategyProfiles(signal),
    staleTime: 5 * 60_000,
  })
}

export function usePortfolioPlanMutation() {
  return useMutation({
    mutationFn: (request: PortfolioPlanRequest) => createPortfolioPlan(request),
  })
}

export function useDailyPortfolioBriefQuery(portfolioId: string | null) {
  return useQuery({
    queryKey: ['daily-portfolio-brief', portfolioId],
    queryFn: ({ signal }) => getDailyPortfolioBrief(portfolioId ?? '', signal),
    enabled: Boolean(portfolioId),
  })
}

export function useDailyBriefOpportunitiesQuery(
  portfolioId: string | null,
  researchOnlyLimit: number,
) {
  return useQuery({
    queryKey: ['daily-brief-opportunities', portfolioId, researchOnlyLimit],
    queryFn: ({ signal }) => getDailyBriefOpportunities(
      portfolioId ?? '', researchOnlyLimit, signal,
    ),
    enabled: Boolean(portfolioId),
  })
}

export function useLivePortfolioRefreshMutation(portfolioId: string | null) {
  return useMutation({ mutationFn: () => refreshLivePortfolio(portfolioId ?? '') })
}

export function usePortfolioNewsQuery(portfolioId: string | null) {
  return useQuery({
    queryKey: ['portfolio-news', portfolioId],
    queryFn: ({ signal }) => getPortfolioNews(portfolioId ?? '', signal),
    enabled: Boolean(portfolioId),
  })
}

export function usePortfolioNewsSentimentQuery(portfolioId: string | null) {
  return useQuery({
    queryKey: ['portfolio-news-sentiment', portfolioId],
    queryFn: ({ signal }) => getPortfolioNewsSentiment(portfolioId ?? '', signal),
    enabled: Boolean(portfolioId),
  })
}

export function usePortfolioNewsRefreshMutation(portfolioId: string | null) {
  return useMutation({ mutationFn: () => refreshPortfolioNews(portfolioId ?? '') })
}

export function usePositionMonitoringQuery(portfolioId: string | null) {
  return useQuery({
    queryKey: ['position-monitoring', portfolioId],
    queryFn: ({ signal }) => getPositionMonitoring(portfolioId ?? '', signal),
    enabled: Boolean(portfolioId),
  })
}

export function useExcludedTickersQuery(portfolioId: string | null) {
  return useQuery({
    queryKey: ['portfolio-excluded-tickers', portfolioId],
    queryFn: ({ signal }) => getExcludedTickers(portfolioId ?? '', signal),
    enabled: Boolean(portfolioId),
  })
}

export function useExcludeTickerMutation(portfolioId: string) {
  return useMutation({
    mutationFn: ({ ticker, expectedRevision, reason }: { ticker: string; expectedRevision: number; reason?: string }) =>
      excludeTicker(portfolioId, ticker, expectedRevision, reason),
  })
}

export function useRestoreTickerMutation(portfolioId: string) {
  return useMutation({
    mutationFn: ({ ticker, expectedRevision }: { ticker: string; expectedRevision: number }) =>
      restoreTicker(portfolioId, ticker, expectedRevision),
  })
}

export function useCashAdjustmentMutation(portfolioId: string) {
  return useMutation({ mutationFn: (request: CashAdjustmentRequest) => adjustResearchCash(portfolioId, request) })
}

export function useExternalPositionMutation(portfolioId: string) {
  return useMutation({ mutationFn: (request: ExternalPositionRequest) => addExternalPosition(portfolioId, request) })
}

export function usePositionReconciliationMutation(portfolioId: string, positionId: string) {
  return useMutation({ mutationFn: (request: PositionReconciliationRequest) => reconcileResearchPosition(portfolioId, positionId, request) })
}

export function usePositionIntelligenceQuery(portfolioId: string, positionId: string | null) {
  return useQuery({
    queryKey: ['position-intelligence', portfolioId, positionId],
    queryFn: ({ signal }) => getPositionIntelligence(portfolioId, positionId ?? '', signal),
    enabled: Boolean(positionId),
  })
}

export function usePositionPaperValidationsQuery(portfolioId: string, positionId: string | null) {
  return useQuery({
    queryKey: ['paper-validations', portfolioId, positionId],
    queryFn: ({ signal }) => getPositionPaperValidations(portfolioId, positionId ?? '', signal),
    enabled: Boolean(positionId),
  })
}

export function useForwardPaperAnalyticsQuery(portfolioId: string | null) {
  return useQuery({
    queryKey: ['forward-paper-analytics', portfolioId],
    queryFn: ({ signal }) => getForwardPaperAnalytics(portfolioId ?? '', signal),
    enabled: Boolean(portfolioId),
  })
}

export function usePaperValidationEntryMutation(portfolioId: string, positionId: string) {
  return useMutation({
    mutationFn: (request: PaperValidationEntryRequest) =>
      recordPaperValidationEntry(portfolioId, positionId, request),
  })
}

export function usePaperValidationExitMutation(portfolioId: string) {
  return useMutation({
    mutationFn: ({ validationId, request }: { validationId: string; request: PaperValidationExitRequest }) =>
      recordPaperValidationExit(portfolioId, validationId, request),
  })
}

export function usePositionCopilotMutation(portfolioId: string, positionId: string) {
  return useMutation({ mutationFn: (question: string) => askPositionCopilot(portfolioId, positionId, question) })
}

export function useLatestStoredPriceQuery(ticker: string | null) {
  return useQuery({
    queryKey: ['latest-stored-price', ticker],
    queryFn: () => getLatestStoredPrice(ticker ?? ''),
    enabled: Boolean(ticker),
  })
}

export function useManualSellPreviewMutation() {
  return useMutation({ mutationFn: (request: ManualSellRequest) => previewManualSell(request) })
}

export function useManualSellMutation() {
  return useMutation({ mutationFn: (request: ManualSellRequest) => applyManualSell(request) })
}

export function useAdminCapabilityQuery() {
  return useQuery({
    queryKey: ['admin-capability'],
    queryFn: ({ signal }) => getAdminCapability(signal),
    staleTime: 60_000,
    retry: false,
  })
}

export function useAdminDataSummaryQuery(enabled: boolean) {
  return useQuery({
    queryKey: ['admin-data-summary'],
    queryFn: ({ signal }) => getAdminDataSummary(signal),
    enabled,
  })
}

export function useDailySchedulerStatusQuery() {
  return useQuery({ queryKey: ['daily-market-scheduler'], queryFn: ({ signal }) => getDailySchedulerStatus(signal) })
}

export function useCustomTickersQuery(enabled: boolean) {
  return useQuery({ queryKey: ['admin-custom-tickers'], queryFn: ({ signal }) => getCustomTickers(signal), enabled })
}

export function useAdminTickerSyncMutation() {
  return useMutation({ mutationFn: (request: AdminTickerSyncRequest) => syncAdminTicker(request) })
}

export function useAdminFullSyncMutation() {
  return useMutation({ mutationFn: (request: AdminFullSyncRequest) => startAdminFullSync(request) })
}

export function useAdminUniverseSyncMutation() {
  return useMutation({ mutationFn: (request: AdminFullSyncRequest) => startAdminUniverseSync(request) })
}

export function useAdminCandleSyncMutation() {
  return useMutation({ mutationFn: (request: AdminFullSyncRequest) => startAdminCandleSync(request) })
}

export function useAddCustomTickerMutation() {
  return useMutation({ mutationFn: (request: AdminTickerSyncRequest) => addCustomTicker(request) })
}

export function useDeactivateCustomTickerMutation() {
  return useMutation({ mutationFn: (ticker: string) => deactivateCustomTicker(ticker) })
}

export function useAdminSyncJobQuery(jobId: string | null) {
  return useQuery({
    queryKey: ['admin-sync-job', jobId],
    queryFn: ({ signal }) => getAdminSyncJob(jobId ?? '', signal),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const state = query.state.data?.state
      return state === 'QUEUED' || state === 'RUNNING' ? 1_000 : false
    },
  })
}
