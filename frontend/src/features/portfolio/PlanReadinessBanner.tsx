import { Link } from 'react-router-dom'
import type { PortfolioPlanReadiness } from '../../types/portfolio'
import { formatDate, humanizeReason } from '../../utils/format'

export function PlanReadinessBanner({ readiness }: { readiness: PortfolioPlanReadiness }) {
  const excluded = readiness.stale_tickers
    + readiness.no_data_tickers
    + readiness.insufficient_history_tickers
    + readiness.company_not_found_tickers
  const isBlocked = readiness.status === 'DATA_NOT_READY'
  const title = isBlocked
    ? 'Data refresh required'
    : readiness.status === 'PARTIAL_DATA'
      ? 'Partial analysis coverage'
      : readiness.status === 'NO_ACTION'
        ? 'Analysis complete · no actionable decision'
        : 'Analysis data ready'
  const explanation = isBlocked
    ? `No normal strategy evaluation was available. ${readiness.stale_tickers} ticker datasets were stale and ${readiness.no_data_tickers} had no stored data.`
    : readiness.status === 'PARTIAL_DATA'
      ? `${excluded} requested tickers were excluded or lacked sufficient history; eligible tickers were still evaluated.`
      : readiness.final_approved_buys === 0
        ? `No approved BUY opportunities were produced from ${readiness.evaluated_tickers} normally evaluated tickers.`
        : `${readiness.final_approved_buys} final actionable BUY decisions were produced from ${readiness.evaluated_tickers} normally evaluated tickers.`

  return (
    <section className={`readiness-banner readiness-banner--${readiness.status.toLowerCase()}`} aria-labelledby="readiness-title">
      <div>
        <p className="eyebrow">Plan readiness</p>
        <h2 id="readiness-title">{title}</h2>
        <p>{explanation}</p>
        <p className="muted">Latest returned ticker data: {formatDate(readiness.latest_ticker_data_date)}</p>
      </div>
      <dl className="readiness-counts">
        <div><dt>Analysis coverage</dt><dd>{readiness.evaluated_tickers} / {readiness.requested_tickers} eligible</dd></div>
        <div><dt>Fresh / stale / no data</dt><dd>{readiness.fresh_tickers} / {readiness.stale_tickers} / {readiness.no_data_tickers}</dd></div>
        <div><dt>Technical BUY / final actionable BUY</dt><dd>{readiness.technical_buy_signals} / {readiness.final_approved_buys}</dd></div>
        <div><dt>User-excluded BUY signals</dt><dd>{readiness.user_excluded_buys}</dd></div>
      </dl>
      {(isBlocked || readiness.status === 'PARTIAL_DATA') ? <Link className="button button--secondary button--small" to="/admin/data">Go to Data Management</Link> : null}
      {readiness.buy_funnel.technical_buy_signals > 0 ? (
        <section aria-labelledby="buy-funnel-title">
          <h3 id="buy-funnel-title">BUY funnel</h3>
          <p className="inline-note">
            {readiness.buy_funnel.news_advisory_only
              ? <>{readiness.buy_funnel.technical_buy_signals} technical BUY signals · {readiness.buy_funnel.rejected_before_news} stopped by deterministic hard gates · {readiness.buy_funnel.final_approved_buys} final actionable BUYs. News is optional advisory context, not an approval gate.</>
              : <>{readiness.buy_funnel.technical_buy_signals} technical BUY signals · {readiness.buy_funnel.rejected_before_news} stopped before News · {readiness.buy_funnel.reached_news} reached News · {readiness.buy_funnel.final_approved_buys} final actionable BUYs.</>}
          </p>
          <div className="disclosure-list">
            {readiness.buy_funnel.groups.map((group) => (
              <details key={group.stage}>
                <summary>{humanizeReason(group.stage)}: {group.count}</summary>
                <p>{group.tickers.join(', ')}</p>
              </details>
            ))}
          </div>
        </section>
      ) : null}
      {Object.keys(readiness.buy_rejections_by_reason).length > 0 ? (
        <details><summary>BUY constraint outcomes</summary><ul>{Object.entries(readiness.buy_rejections_by_reason).map(([reason, count]) => <li key={reason}>{humanizeReason(reason)}: {count}</li>)}</ul></details>
      ) : null}
    </section>
  )
}
