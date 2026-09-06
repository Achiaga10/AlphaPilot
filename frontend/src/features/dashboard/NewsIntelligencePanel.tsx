import type { ExternalNewsSentiment, NewsArticle, NewsRefreshResult } from '../../types/portfolio'

interface Props {
  articles: NewsArticle[]
  sentiments: ExternalNewsSentiment[]
  loading: boolean
  error: boolean
  refreshing: boolean
  onRefresh: () => void
  refreshResult?: NewsRefreshResult
}

export function NewsIntelligencePanel({ sentiments, articles, loading, error, refreshing, onRefresh, refreshResult }: Props) {
  const tickers = [...new Set([...sentiments.map((item) => item.ticker), ...articles.map((item) => item.ticker)])]
  return <section className="panel news-intelligence" aria-labelledby="news-intelligence-title">
    <div className="section-heading"><div><p className="eyebrow">Persisted evidence · backend-owned policy</p><h2 id="news-intelligence-title">News Intelligence</h2></div><button className="button button--secondary button--small" disabled={refreshing} onClick={onRefresh}>{refreshing ? 'Refreshing…' : 'Refresh open holdings'}</button></div>
    <p className="inline-note">Compact ticker summaries are shown first. Adanos aggregate context, attributable Finnhub articles, and Gemini interpretation remain visibly separate. AI cannot issue BUY or SELL.</p>
    {refreshResult ? <div className="inline-note" aria-label="News coverage status"><strong>Coverage:</strong> {refreshResult.coverage.map(([ticker, status]) => `${ticker} ${status}`).join(' · ')}. Stored articles do not imply current or complete coverage.</div> : null}
    {loading ? <p>Loading persisted news…</p> : null}
    {error ? <p className="inline-note inline-note--warning">News is currently unavailable. Stored portfolio and technical decisions remain available.</p> : null}
    {!loading && !error && tickers.length === 0 ? <p>No persisted news is available for current holdings.</p> : null}
    <div className="news-intelligence__grid">
      {tickers.map((ticker) => {
        const aggregate = sentiments.find((item) => item.ticker === ticker)
        const tickerArticles = articles.filter((item) => item.ticker === ticker)
        const classified = tickerArticles.filter((item) => item.classification?.classification_status === 'CLASSIFIED')
        return <details className="news-card" key={ticker}>
          <summary><span><strong>{ticker}</strong> · {aggregate?.aggregate_effect.replaceAll('_', ' ') ?? 'No aggregate context'}</span><span>{aggregate?.evidence_strength.replaceAll('_', ' ') ?? 'UNAVAILABLE'} · {aggregate?.mentions ?? 0} mentions · {aggregate?.source_count ?? 0} sources · {tickerArticles.length} attributable</span></summary>
          <div className="news-evidence-layer" aria-label={`${ticker} Adanos aggregate evidence`}><h3>Adanos aggregate context</h3>{aggregate ? <><p>Score {Number(aggregate.sentiment_score) >= 0 ? '+' : ''}{aggregate.sentiment_score} · Bullish {aggregate.bullish_pct ?? '—'}% · Bearish {aggregate.bearish_pct ?? '—'}%</p><p>Buzz {aggregate.buzz_score ?? '—'} · Trend {aggregate.trend ?? '—'} · Observed {new Date(aggregate.observed_at).toLocaleString()}</p></> : <p>Unavailable.</p>}</div>
          <div className="news-evidence-layer" aria-label={`${ticker} Finnhub attributable evidence`}><h3>Finnhub attributable articles</h3><p>{tickerArticles.length} stored · {classified.length} classified by targeted Gemini analysis.</p>{tickerArticles.map((article) => <details key={article.id}><summary>{article.headline}</summary><p>{article.source ?? article.provider} · {new Date(article.published_at).toLocaleString()}</p>{article.summary ? <p>{article.summary}</p> : null}{article.classification?.classification_status === 'CLASSIFIED' ? <p><strong>Gemini:</strong> {article.classification.impact} · {article.classification.severity} · {article.classification.event_type}. {article.classification.reason}</p> : <p>Classification {article.classification?.classification_status ?? 'UNAVAILABLE'}.</p>}</details>)}</div>
        </details>
      })}
    </div>
  </section>
}
