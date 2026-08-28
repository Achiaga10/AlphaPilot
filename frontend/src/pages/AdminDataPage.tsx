import { type FormEvent, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ErrorState, LoadingState } from '../components/AsyncState'
import { InfoTooltip } from '../components/InfoTooltip'
import { MetricCard } from '../components/MetricCard'
import { InlineSyncProgress, SyncProgress } from '../components/SyncProgress'
import {
  useAddCustomTickerMutation,
  useAdminCandleSyncMutation,
  useAdminCapabilityQuery,
  useAdminDataSummaryQuery,
  useAdminFullSyncMutation,
  useAdminSyncJobQuery,
  useAdminTickerSyncMutation,
  useAdminUniverseSyncMutation,
  useCustomTickersQuery,
  useDeactivateCustomTickerMutation,
} from '../hooks/usePortfolioApi'
import type { AdminDataSummary, AdminFullSyncRequest, AdminSyncJob } from '../types/portfolio'
import { formatDate } from '../utils/format'
import { usePortfolioWorkspace } from '../features/portfolio/PortfolioWorkspace'

function dateOffset(days: number): string {
  const value = new Date()
  value.setDate(value.getDate() + days)
  return value.toISOString().slice(0, 10)
}

export function AdminDataPage() {
  const { refreshPortfolio } = usePortfolioWorkspace()
  const capability = useAdminCapabilityQuery()
  const enabled = capability.data?.enabled === true
  const summary = useAdminDataSummaryQuery(true)
  const customTickers = useCustomTickersQuery(enabled)
  const tickerSync = useAdminTickerSyncMutation()
  const addCustom = useAddCustomTickerMutation()
  const deactivateCustom = useDeactivateCustomTickerMutation()
  const universeSync = useAdminUniverseSyncMutation()
  const candleSync = useAdminCandleSyncMutation()
  const fullSync = useAdminFullSyncMutation()
  const [ticker, setTicker] = useState('')
  const [customTicker, setCustomTicker] = useState('')
  const [startDate, setStartDate] = useState(dateOffset(-400))
  const [endDate, setEndDate] = useState(dateOffset(0))
  const [jobId, setJobId] = useState<string | null>(null)
  const jobQuery = useAdminSyncJobQuery(jobId)
  const latestStarted = universeSync.data?.job ?? candleSync.data?.job ?? fullSync.data?.job
  const job = jobQuery.data ?? latestStarted ?? summary.data?.latest_sync_job
  const running = job?.state === 'QUEUED' || job?.state === 'RUNNING'
  const starting = universeSync.isPending || candleSync.isPending || fullSync.isPending
  const request: AdminFullSyncRequest = { start_date: startDate, end_date: endDate, batch_size: 100 }

  function observe(result: { job: AdminSyncJob }) { setJobId(result.job.job_id) }
  function refreshCustom() { void customTickers.refetch(); void summary.refetch(); void refreshPortfolio() }
  function submitTicker(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    tickerSync.mutate({ ticker: ticker.trim().toUpperCase(), start_date: startDate, end_date: endDate }, { onSuccess: refreshCustom })
  }
  function submitCustom(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    addCustom.mutate({ ticker: customTicker.trim().toUpperCase(), start_date: startDate, end_date: endDate }, { onSuccess: refreshCustom })
  }

  useEffect(() => {
    if (job?.state === 'SUCCEEDED' || job?.state === 'FAILED') {
      void summary.refetch()
      void customTickers.refetch()
      if (job.state === 'SUCCEEDED' && (job.operation === 'MARKET_CANDLES_SYNC' || job.operation === 'FULL_SYNC')) void refreshPortfolio()
    }
  }, [customTickers, job?.operation, job?.state, refreshPortfolio, summary])

  return (
    <div className="page">
      <header className="page-header"><div><p className="eyebrow">Development operations</p><h1>Data Management</h1><p>Inspect stored research data and run explicitly gated synchronization workflows.</p></div></header>
      {capability.isPending ? <LoadingState label="Checking research admin availability" /> : null}
      {capability.isError ? <ErrorState error={capability.error} onRetry={() => void capability.refetch()} /> : null}
      {capability.data && !enabled ? <section className="panel"><h2>Research admin tools are disabled by backend configuration</h2><p>For a local development environment, set <code>ADMIN_TOOLS_ENABLED=true</code> and restart the backend.</p><p className="inline-note inline-note--warning">Visibility is not authorization. All data-management write endpoints remain blocked while disabled.</p></section> : null}
      {summary.isPending ? <LoadingState label="Loading stored-data freshness" /> : null}
      {summary.isError ? <ErrorState error={summary.error} onRetry={() => void summary.refetch()} /> : null}
      {summary.data ? <DataSummary summary={summary.data} /> : null}

      {enabled ? <div className="page-stack">
        <p className="inline-note inline-note--warning" role="status">Research admin tools are enabled. This configuration gate is not authentication. Actions can call external data providers.</p>
        <section className="panel">
          <div className="section-heading"><div><p className="eyebrow">Custom coverage</p><h2>Custom Tracked Tickers</h2></div></div>
          <p>Add a valid company independently of S&amp;P 500 membership. Metadata discovery and storage happen in the backend.</p>
          <form className="admin-sync-form" onSubmit={submitCustom}>
            <label><span>Ticker</span><input aria-label="Custom ticker" value={customTicker} maxLength={10} pattern="[A-Za-z0-9.-]+" required onChange={(event) => setCustomTicker(event.target.value.toUpperCase())} /></label>
            <label><span>History start</span><input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label>
            <label><span>History end</span><input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label>
            <button className="button button--primary" type="submit" disabled={addCustom.isPending}>{addCustom.isPending ? 'Adding & syncing…' : 'Add & Sync'}</button>
          </form>
          {addCustom.isError ? <ErrorState error={addCustom.error} onRetry={() => addCustom.reset()} /> : null}
          {(addCustom.isPending || addCustom.data || addCustom.isError) ? <InlineSyncProgress label={customTicker || addCustom.data?.ticker || 'Custom ticker'} pending={addCustom.isPending} complete={Boolean(addCustom.data && !['SYMBOL_NOT_FOUND', 'METADATA_PROVIDER_FAILED', 'TRACKED_CANDLE_SYNC_FAILED'].includes(addCustom.data.state))} failed={addCustom.isError || Boolean(addCustom.data && ['SYMBOL_NOT_FOUND', 'METADATA_PROVIDER_FAILED', 'TRACKED_CANDLE_SYNC_FAILED'].includes(addCustom.data.state))} stages={['Ticker validation', 'Metadata', 'Company persistence', 'Historical candles']} /> : null}
          {addCustom.data ? <p className={`inline-note ${['SYMBOL_NOT_FOUND', 'METADATA_PROVIDER_FAILED', 'TRACKED_CANDLE_SYNC_FAILED'].includes(addCustom.data.state) ? 'inline-note--warning' : ''}`}><strong>{addCustom.data.ticker}: {addCustom.data.state}</strong> · {addCustom.data.message} · Tracked: {addCustom.data.is_custom_tracked ? 'Yes' : 'No'} · S&amp;P 500: {addCustom.data.is_sp500_member ? 'Yes' : 'No'} · Candles: {addCustom.data.stored_candle_count}</p> : null}
          {customTickers.isPending ? <LoadingState label="Loading custom tracked tickers" /> : null}
          {customTickers.data?.length ? <div className="table-scroll"><table><thead><tr><th>Ticker</th><th>Company</th><th>Exchange</th><th>Sector</th><th>Tracking</th><th>Latest candle</th><th>Actions</th></tr></thead><tbody>{customTickers.data.map((item) => <tr key={item.ticker}><th>{item.ticker}</th><td>{item.company_name}</td><td>{item.exchange}</td><td>{item.sector ?? 'Sector unavailable'}</td><td>{item.is_custom_tracked ? 'Active custom' : 'Inactive'}{item.is_sp500_member ? ' · S&P managed' : ''}</td><td>{formatDate(item.latest_candle_date)}</td><td><div className="table-actions"><Link className="table-action" to={`/evaluate?ticker=${encodeURIComponent(item.ticker)}`}>Evaluate</Link><button className="table-action table-action--button" type="button" onClick={() => tickerSync.mutate({ ticker: item.ticker, start_date: startDate, end_date: endDate }, { onSuccess: refreshCustom })}>Sync Candles</button>{item.is_custom_tracked && !item.is_sp500_member ? <button className="table-action table-action--button table-action--danger" type="button" onClick={() => deactivateCustom.mutate(item.ticker, { onSuccess: refreshCustom })}>Deactivate Tracking</button> : null}</div></td></tr>)}</tbody></table></div> : <p className="muted">No custom tracked tickers are stored.</p>}
        </section>

        <section className="panel">
          <div className="section-heading"><div><p className="eyebrow">Independent operations</p><h2>Universe and Market Data</h2></div></div>
          <p>Universe Sync refreshes constituent metadata and membership without downloading candles. Market Candles Sync updates SPY, current constituents, and active custom tickers.</p>
          <div className="provider-strip"><span>Market provider: <strong>{capability.data?.market_data_provider ?? summary.data?.market_data_provider ?? 'Alpaca'}</strong></span><span>Configured feed: <strong>{capability.data?.market_data_feed ?? summary.data?.market_data_feed ?? 'unknown'}</strong> <InfoTooltip label="About the configured market-data feed">The backend sends this exact configured Alpaca feed. It never silently falls back from SIP to IEX; a feed entitlement failure is reported safely.</InfoTooltip></span></div>
          <div className="admin-action-grid"><button className="button button--primary" type="button" disabled={running || starting} onClick={() => universeSync.mutate(request, { onSuccess: observe })}>Sync S&amp;P 500 Universe</button><button className="button button--primary" type="button" disabled={running || starting} onClick={() => candleSync.mutate(request, { onSuccess: observe })}>Sync Market Candles</button><button className="button button--secondary" type="button" disabled={running || starting} onClick={() => fullSync.mutate(request, { onSuccess: observe })}>Full Sync</button></div>
          {running ? <p className="inline-note" role="status">Sync already running. Conflicting actions are disabled; current progress is shown below.</p> : null}
          {(universeSync.isError || candleSync.isError || fullSync.isError) ? <ErrorState error={(universeSync.error ?? candleSync.error ?? fullSync.error)!} /> : null}
          {job ? <><SyncProgress job={job} />{job.state === 'SUCCEEDED' && (job.operation === 'MARKET_CANDLES_SYNC' || job.operation === 'FULL_SYNC') ? <p><Link className="button button--primary button--small" to="/portfolio">Return to Portfolio Plan</Link></p> : null}</> : <p className="muted">No process-local sync job has been observed in this backend session.</p>}
        </section>

        <section className="panel"><div className="section-heading"><div><p className="eyebrow">Known company maintenance</p><h2>Sync One Stored Ticker</h2></div></div><form className="admin-sync-form" onSubmit={submitTicker}><label><span>Ticker</span><input value={ticker} maxLength={10} required onChange={(event) => setTicker(event.target.value.toUpperCase())} /></label><button className="button button--secondary" type="submit" disabled={tickerSync.isPending}>{tickerSync.isPending ? 'Syncing…' : 'Sync stored ticker candles'}</button></form>{(tickerSync.isPending || tickerSync.data || tickerSync.isError) ? <InlineSyncProgress label={ticker || tickerSync.data?.ticker || 'Stored ticker'} pending={tickerSync.isPending} complete={tickerSync.data?.state === 'SYNCED'} failed={tickerSync.isError || tickerSync.data?.state === 'FAILED'} stages={['Queued', 'Candle request', 'Persisting', 'Complete']} /> : null}{tickerSync.data ? <p className="inline-note"><strong>{tickerSync.data.ticker}: {tickerSync.data.state}</strong> · {tickerSync.data.message}</p> : null}</section>
      </div> : null}
    </div>
  )
}

function DataSummary({ summary }: { summary: AdminDataSummary }) {
  return <section className={`panel ${summary.stale_tracked_ticker_count > 0 || summary.no_data_tracked_ticker_count > 0 ? 'data-health--warning' : ''}`}><div className="section-heading"><div><p className="eyebrow">Stored completed daily data · not live</p><h2>Data freshness</h2></div></div><div className="metric-grid"><MetricCard label="Total Company records" value={String(summary.active_company_count)} /><MetricCard label="Current active S&P 500" value={String(summary.active_sp500_count)} /><MetricCard label="Active custom tracked" value={String(summary.active_custom_tracked_count)} /><MetricCard label="Latest stored completed SPY session" value={formatDate(summary.latest_spy_date)} /><MetricCard label="Fresh tracked tickers" value={String(summary.fresh_tracked_ticker_count)} /><MetricCard label="Stale tracked tickers" value={String(summary.stale_tracked_ticker_count)} /><MetricCard label="No-data tickers" value={String(summary.no_data_tracked_ticker_count)} /><MetricCard label="Oldest tracked completed close" value={formatDate(summary.earliest_active_stock_latest_date)} /><MetricCard label="Newest tracked completed close" value={formatDate(summary.latest_active_stock_latest_date)} /><MetricCard label="Last universe sync" value={formatDate(summary.last_universe_sync_at)} /><MetricCard label="Last candle sync" value={formatDate(summary.last_candle_sync_at)} /></div></section>
}
