import { useMemo, useState } from 'react'
import { InfoTooltip } from '../../components/InfoTooltip'
import type {
  CandidateDataStatus,
  CandidateStatus,
  PortfolioDecision,
  PortfolioFinalAction,
  PortfolioDecisionType,
  PortfolioPlanReadiness,
  PortfolioPlanActionResult,
  SizingPolicy,
  StrategySignal,
} from '../../types/portfolio'
import { isFinalApprovedBuy, isFinalApprovedSell } from '../../utils/decisionSemantics'
import { CandidateStatuses } from './CandidateStatuses'
import { DecisionTable } from './DecisionTable'
import { HELP_TEXT } from './helpText'

type OpportunityTab = 'approved-buy' | 'approved-sell' | 'sell-signal' | 'not-actionable' | 'decisions' | 'evaluated'
const PAGE_SIZE = 25

export function OpportunityExplorer({
  decisions,
  statuses,
  canApplyDecisions = false,
  onApplyDecision,
  onPreviewDecision,
  sizingPolicy = 'equal-slot',
  adminEnabled = false,
  onSyncTicker,
  onDeactivateTicker,
  readiness,
  appliedActionIds,
  actionPendingId,
  excludedTickers,
  onExcludeTicker,
  onRestoreTicker,
  preferencePending,
}: {
  decisions: PortfolioDecision[]
  statuses: CandidateStatus[]
  canApplyDecisions?: boolean
  onApplyDecision?: (decision: PortfolioDecision, requestedShares?: number) => void | Promise<unknown>
  onPreviewDecision?: (decision: PortfolioDecision, requestedShares?: number) => Promise<PortfolioPlanActionResult | null>
  sizingPolicy?: SizingPolicy
  adminEnabled?: boolean
  onSyncTicker?: (ticker: string) => void
  onDeactivateTicker?: (ticker: string) => void
  readiness?: PortfolioPlanReadiness
  appliedActionIds?: ReadonlySet<string>
  actionPendingId?: string | null
  excludedTickers?: ReadonlySet<string>
  onExcludeTicker?: (ticker: string) => void
  onRestoreTicker?: (ticker: string) => void
  preferencePending?: boolean
}) {
  const approvedCount = readiness?.final_approved_buys
    ?? decisions.filter(isFinalApprovedBuy).length
  const [tab, setTab] = useState<OpportunityTab>('approved-buy')
  const [search, setSearch] = useState('')
  const [finalActionFilter, setFinalActionFilter] = useState<'ALL' | PortfolioFinalAction>('ALL')
  const [candidateDecisionFilter, setCandidateDecisionFilter] = useState<'ALL' | PortfolioDecisionType>('ALL')
  const [signalFilter, setSignalFilter] = useState<'ALL' | StrategySignal>('ALL')
  const [sectorFilter, setSectorFilter] = useState('ALL')
  const [statusFilter, setStatusFilter] = useState<'ALL' | CandidateDataStatus>('ALL')
  const [page, setPage] = useState(1)
  const activeTab: OpportunityTab = tab

  const statusByTicker = useMemo(() => Object.fromEntries(statuses.map((item) => [item.ticker, item])), [statuses])
  const sectors = useMemo(() => [...new Set([
    ...decisions.map((item) => item.sector),
    ...statuses.map((item) => item.sector).filter((item): item is string => Boolean(item)),
  ])].sort(), [decisions, statuses])
  const tabDecisions = useMemo(() => {
    if (activeTab === 'approved-buy') return decisions.filter(isFinalApprovedBuy)
    if (activeTab === 'approved-sell') return decisions.filter(isFinalApprovedSell)
    if (activeTab === 'sell-signal') return decisions.filter((item) => item.signal === 'SELL')
    if (activeTab === 'not-actionable') return decisions.filter((item) => item.final_action === 'NOT_ACTIONABLE')
    return decisions
  }, [activeTab, decisions])
  const normalizedSearch = search.trim().toUpperCase()
  const filteredDecisions = tabDecisions.filter((item) => {
    const status = statusByTicker[item.ticker]
    return (!normalizedSearch || item.ticker.includes(normalizedSearch) || status?.company_name?.toUpperCase().includes(normalizedSearch))
      && (finalActionFilter === 'ALL' || item.final_action === finalActionFilter)
      && (candidateDecisionFilter === 'ALL' || item.decision === candidateDecisionFilter)
      && (signalFilter === 'ALL' || item.signal === signalFilter)
      && (sectorFilter === 'ALL' || item.sector === sectorFilter)
      && (statusFilter === 'ALL' || status?.status === statusFilter)
  })
  const filteredStatuses = statuses.filter((item) => (
    (!normalizedSearch || item.ticker.includes(normalizedSearch) || item.company_name?.toUpperCase().includes(normalizedSearch))
    && (candidateDecisionFilter === 'ALL' || item.decision === candidateDecisionFilter)
    && (signalFilter === 'ALL' || item.signal === signalFilter)
    && (sectorFilter === 'ALL' || item.sector === sectorFilter)
    && (statusFilter === 'ALL' || item.status === statusFilter)
  ))
  const pageCount = Math.max(Math.ceil(filteredDecisions.length / PAGE_SIZE), 1)
  const safePage = Math.min(page, pageCount)
  const visibleDecisions = filteredDecisions.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE)
  const rankByTicker = Object.fromEntries(statuses.map((item) => [item.ticker, item.candidate_rank]))
  const approvedBuyEmptyMessage = readiness?.status === 'DATA_NOT_READY'
    ? `No BUY analysis is available because ${readiness.stale_tickers} tickers were excluded as stale and ${readiness.no_data_tickers} had no stored data.`
    : readiness?.status === 'PARTIAL_DATA'
      ? `No approved BUYs in the usable portion of this partial analysis. ${readiness.stale_tickers + readiness.no_data_tickers} tickers lacked current stored data.`
      : readiness
        ? `No final actionable BUYs. ${readiness.technical_buy_signals} technical BUY signals were evaluated; ${readiness.user_excluded_buys} were excluded by you and ${readiness.skipped_or_deferred} returned decisions were skipped or deferred. Review the typed constraint outcomes below.`
        : 'No approved BUY decisions match this view.'

  const tabs: Array<{ key: OpportunityTab; label: string; count: number }> = [
    { key: 'approved-buy', label: 'Approved Buys', count: approvedCount },
    { key: 'approved-sell', label: 'Final Approved Sells', count: readiness?.final_approved_sells ?? decisions.filter(isFinalApprovedSell).length },
    { key: 'sell-signal', label: 'Technical SELL Signals', count: decisions.filter((item) => item.signal === 'SELL').length },
    { key: 'not-actionable', label: 'Not Actionable', count: decisions.filter((item) => item.final_action === 'NOT_ACTIONABLE').length },
    { key: 'decisions', label: 'Returned Decision Records', count: decisions.length },
    { key: 'evaluated', label: 'Universe Evaluated', count: statuses.length },
  ]

  return (
    <section aria-labelledby="decisions-title">
      <div className="section-heading"><div><p className="eyebrow">Advisory output</p><h2 id="decisions-title">Opportunities & Decisions</h2></div><div className="heading-help"><span className="muted">Returned results only</span><InfoTooltip label="About opportunity ordering">{HELP_TEXT.opportunitiesOrder}</InfoTooltip></div></div>
      <div className="tab-list" role="tablist" aria-label="Opportunity categories">
        {tabs.map((item) => <button key={item.key} type="button" role="tab" aria-selected={activeTab === item.key} className={activeTab === item.key ? 'tab is-active' : 'tab'} onClick={() => { setTab(item.key); setPage(1) }}>{item.label} <span>{item.count}</span></button>)}
      </div>
      <div className="filter-grid" aria-label="Filter returned results">
        <label><span>Search ticker or company</span><input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1) }} /></label>
        <label><span>Final action</span><select value={finalActionFilter} onChange={(event) => { setFinalActionFilter(event.target.value as typeof finalActionFilter); setPage(1) }}><option value="ALL">All</option><option>BUY</option><option>SELL</option><option>HOLD</option><option>ATTENTION</option><option>EXIT_REQUIRED</option><option>NOT_ACTIONABLE</option></select></label>
        <label><span>Candidate decision</span><select value={candidateDecisionFilter} onChange={(event) => { setCandidateDecisionFilter(event.target.value as typeof candidateDecisionFilter); setPage(1) }}><option value="ALL">All</option><option>BUY</option><option>SELL</option><option>HOLD</option><option>SKIP</option></select></label>
        <label><span>Signal</span><select value={signalFilter} onChange={(event) => { setSignalFilter(event.target.value as typeof signalFilter); setPage(1) }}><option value="ALL">All</option><option>BUY</option><option>SELL</option><option>HOLD</option></select></label>
        <label><span>Sector</span><select value={sectorFilter} onChange={(event) => { setSectorFilter(event.target.value); setPage(1) }}><option value="ALL">All sectors</option>{sectors.map((sector) => <option key={sector}>{sector}</option>)}</select></label>
        <label><span>Data status</span><select value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value as typeof statusFilter); setPage(1) }}><option value="ALL">All statuses</option><option>READY</option><option>NO_ACTION</option><option>COMPANY_NOT_FOUND</option><option>NO_DATA</option><option>STALE_DATA</option><option>INSUFFICIENT_HISTORY</option></select></label>
      </div>
      <p className="muted category-note">Final actions have primary authority. Technical signals are strategy evidence; the evaluated universe also includes names that produced no decision record.</p>
      {activeTab === 'evaluated' ? <CandidateStatuses statuses={filteredStatuses} adminEnabled={adminEnabled} onSyncTicker={onSyncTicker} onDeactivateTicker={onDeactivateTicker} /> : <><p className="ordering-note">{activeTab === 'approved-buy' ? 'Backend recommendation priority · choose any approved opportunity; rank is not required execution order' : 'Backend response order · not a universal recommendation rank'}</p><DecisionTable decisions={visibleDecisions} rankByTicker={rankByTicker} canApplyDecisions={canApplyDecisions} onApplyDecision={onApplyDecision} onPreviewDecision={onPreviewDecision} sizingPolicy={sizingPolicy} appliedActionIds={appliedActionIds} actionPendingId={actionPendingId} emptyTitle={activeTab === 'approved-buy' ? 'No approved BUYs' : undefined} emptyMessage={activeTab === 'approved-buy' ? approvedBuyEmptyMessage : undefined} excludedTickers={excludedTickers} onExcludeTicker={onExcludeTicker} onRestoreTicker={onRestoreTicker} preferencePending={preferencePending} />{filteredDecisions.length > PAGE_SIZE ? <div className="pagination"><button className="button button--secondary button--small" type="button" disabled={safePage === 1} onClick={() => setPage(safePage - 1)}>Previous</button><span>Page {safePage} of {pageCount} · {filteredDecisions.length} rows</span><button className="button button--secondary button--small" type="button" disabled={safePage === pageCount} onClick={() => setPage(safePage + 1)}>Next</button></div> : null}</>}
    </section>
  )
}
