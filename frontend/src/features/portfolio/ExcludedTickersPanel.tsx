import { useExcludedTickersQuery, useRestoreTickerMutation } from '../../hooks/usePortfolioApi'
import { formatDate } from '../../utils/format'

export function ExcludedTickersPanel({
  portfolioId,
  revision,
  onChanged,
}: {
  portfolioId: string
  revision: number
  onChanged: () => Promise<void>
}) {
  const query = useExcludedTickersQuery(portfolioId)
  const restore = useRestoreTickerMutation(portfolioId)
  const pending = restore.isPending

  async function restoreTicker(ticker: string) {
    await restore.mutateAsync({ ticker, expectedRevision: revision })
    await Promise.all([query.refetch(), onChanged()])
  }

  return <section className="panel" aria-labelledby="excluded-tickers-title">
    <div className="section-heading"><div><p className="eyebrow">Recommendation preferences</p><h2 id="excluded-tickers-title">Excluded tickers</h2></div><span className="badge badge--neutral">{query.data?.length ?? 0}</span></div>
    <p className="muted">Exclusion blocks future BUY recommendations only. It does not delete market data, News, strategy signals, Paper evidence, or trade history. Selling never excludes a ticker automatically.</p>
    {query.isPending ? <p className="muted">Loading exclusions…</p> : null}
    {query.isError ? <p className="inline-note inline-note--warning">Excluded ticker preferences are unavailable.</p> : null}
    {query.data?.length === 0 ? <p className="empty-inline">No tickers are excluded from future plans.</p> : null}
    {query.data?.map((item) => <article className="inline-note" key={item.company_id}>
      <div className="section-heading"><div><strong>{item.ticker}</strong><br /><small>Excluded by you {item.excluded_at ? `on ${formatDate(item.excluded_at)}` : ''}{item.reason ? ` · ${item.reason}` : ''}</small></div><button className="button button--secondary button--small" type="button" disabled={pending} onClick={() => void restoreTicker(item.ticker)}>Return to recommendation pool</button></div>
    </article>)}
  </section>
}
