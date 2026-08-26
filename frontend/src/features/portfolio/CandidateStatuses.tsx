import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { InfoTooltip } from '../../components/InfoTooltip'
import { StatusBadge } from '../../components/StatusBadge'
import type { CandidateDataStatus, CandidateStatus } from '../../types/portfolio'
import { formatDate, humanizeReason } from '../../utils/format'
import { HELP_TEXT } from './helpText'

const PAGE_SIZE = 25
const STATUS_ORDER: CandidateDataStatus[] = [
  'READY',
  'NO_ACTION',
  'COMPANY_NOT_FOUND',
  'NO_DATA',
  'STALE_DATA',
  'INSUFFICIENT_HISTORY',
]

export function CandidateStatuses({ statuses, adminEnabled = false, onSyncTicker, onDeactivateTicker }: { statuses: CandidateStatus[]; adminEnabled?: boolean; onSyncTicker?: (ticker: string) => void; onDeactivateTicker?: (ticker: string) => void }) {
  const [page, setPage] = useState(1)
  const sorted = useMemo(
    () => [...statuses].sort((left, right) => left.ticker.localeCompare(right.ticker)),
    [statuses],
  )
  const pageCount = Math.max(Math.ceil(sorted.length / PAGE_SIZE), 1)
  const safePage = Math.min(page, pageCount)
  const visible = sorted.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE)

  const counts = Object.fromEntries(
    STATUS_ORDER.map((status) => [status, statuses.filter((item) => item.status === status).length]),
  ) as Record<CandidateDataStatus, number>

  return (
    <div className="universe-evaluation">
      <div className="subheading-row">
        <h3>Universe Evaluation</h3>
        <span className="muted">View all {statuses.length} returned tickers</span>
      </div>
      <div className="status-counts" aria-label="Universe evaluation status counts">
        {STATUS_ORDER.map((status) => (
          <div key={status}><span>{humanizeReason(status)}</span><strong>{counts[status]}</strong></div>
        ))}
      </div>
      <div className="subheading-row universe-ordering">
        <span className="badge badge--neutral">Sorted A-Z</span>
        <InfoTooltip label="About universe evaluation ordering">{HELP_TEXT.universeOrder}</InfoTooltip>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Ticker</th><th scope="col">Company</th><th scope="col">Sector</th>
              <th scope="col">Data status</th><th scope="col">Data as of</th><th scope="col">Signal</th>
              <th scope="col">Decision</th><th scope="col">Rank</th><th scope="col">Reason</th>
              <th scope="col"><span className="visually-hidden">Action</span></th>
            </tr>
          </thead>
          <tbody>
            {visible.map((item) => (
              <tr key={item.ticker}>
                <th scope="row">{item.ticker}</th>
                <td>{item.company_name ?? '—'}</td><td>{item.sector ?? '—'}</td>
                <td><StatusBadge value={item.status} /></td><td>{formatDate(item.data_as_of_date)}</td>
                <td>{item.signal ?? '—'}</td><td>{item.decision ?? '—'}</td>
                <td>{item.candidate_rank ?? '—'}</td>
                <td>{humanizeReason(item.decision_reason ?? item.reason)}</td>
                <td><div className="table-actions"><Link className="table-action" to={`/evaluate?ticker=${encodeURIComponent(item.ticker)}`}>Evaluate</Link>{adminEnabled ? <button className="table-action table-action--button" type="button" onClick={() => onSyncTicker?.(item.ticker)}>Sync data</button> : null}{adminEnabled && item.is_custom_tracked ? <button className="table-action table-action--button table-action--danger" type="button" onClick={() => onDeactivateTicker?.(item.ticker)}>Deactivate tracking</button> : null}</div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {sorted.length > PAGE_SIZE ? (
        <div className="pagination" aria-label="Universe evaluation pages">
          <button className="button button--secondary button--small" type="button" disabled={safePage === 1} onClick={() => setPage(safePage - 1)}>Previous</button>
          <span>Page {safePage} of {pageCount} · {sorted.length} returned rows</span>
          <button className="button button--secondary button--small" type="button" disabled={safePage === pageCount} onClick={() => setPage(safePage + 1)}>Next</button>
        </div>
      ) : null}
    </div>
  )
}
