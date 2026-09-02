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
  return (
    <section className="panel news-intelligence" aria-labelledby="news-intelligence-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Persisted evidence · backend-owned policy</p>
          <h2 id="news-intelligence-title">News Intelligence</h2>
        </div>
        <button className="button button--secondary button--small" disabled={refreshing} onClick={onRefresh}>
          {refreshing ? 'Refreshing…' : 'Refresh open holdings'}
        </button>
      </div>
      <p className="inline-note">AI interprets event impact only. It cannot issue BUY or SELL; AlphaPilot's versioned backend policy owns financial effects.</p>
      {refreshResult ? <div className="inline-note" aria-label="News coverage status"><strong>Coverage:</strong> {refreshResult.coverage.map(([ticker, status]) => `${ticker} ${status}`).join(' · ')}. Stored articles do not imply current or complete coverage.</div> : null}
      {refreshResult ? <div className="inline-note"><strong>Refresh layers:</strong> Adanos {refreshResult.aggregate_returned.length}/{refreshResult.aggregate_requested.length} returned in {refreshResult.aggregate_api_calls} call(s); Gemini targeted attempts {refreshResult.targeted_classification_attempts}.</div> : null}
      {loading ? <p>Loading persisted news…</p> : null}
      {error ? <p className="inline-note inline-note--warning">News is currently unavailable. Stored portfolio and technical decisions remain available.</p> : null}
      {!loading && !error && articles.length === 0 ? <p>No persisted news is available for current holdings.</p> : null}
      <div className="news-evidence-layer" aria-label="External aggregate News sentiment">
        <h3>External News Sentiment — Adanos</h3>
        <p className="inline-note">Aggregate context only. Provider data timestamp is unavailable; observed time is collection time. Adanos cannot directly create BUY, SELL, or EXIT_REQUIRED.</p>
        <div className="news-intelligence__grid">
          {sentiments.map((item) => (
            <article className="news-card" key={item.ticker}>
              <div className="news-card__meta"><strong>{item.ticker}</strong><span>{item.provider}</span><time dateTime={item.observed_at}>{new Date(item.observed_at).toLocaleString()}</time></div>
              <h3>Score {Number(item.sentiment_score) >= 0 ? '+' : ''}{item.sentiment_score}</h3>
              <p>Bullish {item.bullish_pct ?? '—'}% · Bearish {item.bearish_pct ?? '—'}%</p>
              <p>Mentions {item.mentions ?? '—'} · Sources {item.source_count ?? '—'} · Buzz {item.buzz_score ?? '—'} · Trend {item.trend ?? '—'}</p>
              <span className="badge">{item.evidence_strength.replaceAll('_', ' ')}</span>
            </article>
          ))}
        </div>
      </div>
      <div className="news-evidence-layer" aria-label="Attributable News evidence">
        <h3>Attributable News Evidence — Finnhub</h3>
      <div className="news-intelligence__grid">
        {articles.map((article) => {
          const classification = article.classification
          return (
            <article className="news-card" key={article.id}>
              <div className="news-card__meta"><strong>{article.ticker}</strong><span>{article.source ?? article.provider}</span><time dateTime={article.published_at}>{new Date(article.published_at).toLocaleString()}</time></div>
              <h3>{article.canonical_url ? <a href={article.canonical_url} target="_blank" rel="noreferrer">{article.headline}</a> : article.headline}</h3>
              {article.summary ? <p>{article.summary}</p> : null}
              {classification?.classification_status === 'CLASSIFIED' ? (
                <div className="news-card__classification">
                  <span className={`badge badge--${classification.impact?.toLowerCase()}`}>{classification.impact}</span>
                  <span>{classification.event_type?.replaceAll('_', ' ')}</span>
                  <span>{classification.severity} severity</span>
                  <span>{Math.round(Number(classification.confidence) * 100)}% confidence</span>
                  <p>{classification.reason}</p>
                  <small>Targeted Deep AI Analysis — Classified by {classification.classification_provider} · {classification.classification_model} · {classification.classification_version}</small>
                </div>
              ) : <p className="inline-note">Classification: {classification?.classification_status ?? 'UNAVAILABLE'}. No News-driven financial action is inferred.</p>}
            </article>
          )
        })}
      </div>
      </div>
    </section>
  )
}
