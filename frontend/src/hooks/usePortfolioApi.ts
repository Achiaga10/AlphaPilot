import { useMutation, useQuery } from '@tanstack/react-query'
import {
  applyManualSell,
  createPortfolioPlan,
  getHealth,
  getLatestStoredPrice,
  getRiskConfig,
  previewManualSell,
} from '../api/portfolio'
import {
  addCustomTicker,
  deactivateCustomTicker,
  getCustomTickers,
  getAdminCapability,
  getAdminDataSummary,
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

export function usePortfolioPlanMutation() {
  return useMutation({
    mutationFn: (request: PortfolioPlanRequest) => createPortfolioPlan(request),
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
