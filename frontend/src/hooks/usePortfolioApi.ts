import { useMutation, useQuery } from '@tanstack/react-query'
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
  recordPaperValidationEntry,
  recordPaperValidationExit,
  previewManualSell,
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

export function usePositionMonitoringQuery(portfolioId: string | null) {
  return useQuery({
    queryKey: ['position-monitoring', portfolioId],
    queryFn: ({ signal }) => getPositionMonitoring(portfolioId ?? '', signal),
    enabled: Boolean(portfolioId),
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
