import type { AdminSyncJob } from '../types/portfolio'
import { formatDate } from '../utils/format'

function stageLabel(value: string | null): string {
  if (!value) return 'Queued'
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function SyncProgress({ job }: { job: AdminSyncJob }) {
  const { progress } = job
  const determinate = progress.total > 0
  const percentage = determinate ? Math.min(progress.attempted / progress.total * 100, 100) : null
  const complete = job.state === 'SUCCEEDED'
  const failed = job.state === 'FAILED'
  const fullInCandlePhase = job.operation === 'FULL_SYNC' && ['benchmark', 'stock_candles', 'complete'].includes(progress.stage ?? '')
  return (
    <section className={`sync-progress sync-progress--${job.state.toLowerCase()}`} aria-labelledby={`sync-${job.job_id}`}>
      <div className="sync-progress__heading"><div><strong id={`sync-${job.job_id}`}>{job.operation.replaceAll('_', ' ')}</strong><span>{job.state}</span></div><span>{percentage === null ? 'Preparing…' : `${Math.round(percentage)}%`}</span></div>
      <div
        className={`progress-track ${determinate ? '' : 'is-indeterminate'}`}
        role="progressbar"
        aria-label={`${job.operation.replaceAll('_', ' ')} progress`}
        aria-valuemin={0}
        aria-valuemax={determinate ? progress.total : undefined}
        aria-valuenow={determinate ? progress.attempted : undefined}
        aria-valuetext={`${stageLabel(progress.stage)}${progress.current_ticker ? `, ${progress.current_ticker}` : ''}`}
      >
        <span style={determinate ? { width: `${percentage}%` } : undefined} />
      </div>
      {job.operation === 'FULL_SYNC' ? <ol className="sync-phases"><li className={fullInCandlePhase || complete ? 'is-complete' : 'is-active'}>Universe {fullInCandlePhase || complete ? 'COMPLETE' : 'IN PROGRESS'}</li><li className={fullInCandlePhase ? 'is-active' : complete ? 'is-complete' : ''}>Candles {complete ? 'COMPLETE' : fullInCandlePhase ? `${progress.attempted} / ${progress.total || 'pending'}` : 'WAITING'}</li></ol> : null}
      <dl className="config-grid"><div><dt>Stage</dt><dd>{stageLabel(progress.stage)}</dd></div><div><dt>Current ticker</dt><dd>{progress.current_ticker ?? '—'}</dd></div><div><dt>Processed</dt><dd>{progress.attempted} / {progress.total || 'pending'}</dd></div><div><dt>Successful / skipped / failed</dt><dd>{progress.synced} / {progress.skipped} / {progress.failed}</dd></div><div><dt>Started</dt><dd>{formatDate(job.started_at)}</dd></div><div><dt>Finished</dt><dd>{formatDate(job.finished_at)}</dd></div><div><dt>Provider / feed</dt><dd>{job.provider ?? '—'}{job.feed ? ` / ${job.feed}` : ''}</dd></div></dl>
      {(job.operation === 'UNIVERSE_SYNC' || job.operation === 'FULL_SYNC') ? <dl className="config-grid"><div><dt>Companies created / updated / unchanged</dt><dd>{job.companies_created} / {job.companies_updated} / {job.companies_unchanged}</dd></div><div><dt>Memberships added / removed</dt><dd>{job.memberships_added} / {job.memberships_removed}</dd></div><div><dt>Active constituents</dt><dd>{job.active_constituents || 'pending'}</dd></div></dl> : null}
      {complete ? <p className="inline-note"><strong>Completed.</strong> The freshness summary will refresh automatically.</p> : null}
      {failed ? <p className="inline-note inline-note--warning"><strong>{job.error_code ?? 'SYNC_FAILED'}</strong> · {job.error}</p> : null}
      {progress.failed_tickers.length > 0 ? <details><summary>Inspect failed tickers ({progress.failed_tickers.length})</summary><p>{progress.failed_tickers.join(', ')}</p></details> : null}
    </section>
  )
}

export function InlineSyncProgress({ label, pending, complete, failed, stages }: { label: string; pending: boolean; complete: boolean; failed: boolean; stages: string[] }) {
  const state = failed ? 'Failed' : complete ? 'Complete' : pending ? 'In progress' : 'Ready'
  return <div className="inline-sync-progress"><div className="sync-progress__heading"><strong>{label}</strong><span>{state}</span></div><div className={`progress-track ${pending ? 'is-indeterminate' : ''}`} role="progressbar" aria-label={`${label} progress`} aria-valuemin={0} aria-valuemax={stages.length} aria-valuenow={complete ? stages.length : failed ? 0 : undefined}><span style={complete ? { width: '100%' } : undefined} /></div><ol className="inline-stages">{stages.map((stage, index) => <li key={stage} className={complete ? 'is-complete' : pending && index === 0 ? 'is-active' : ''}>{stage}{complete ? ' ✓' : ''}</li>)}</ol></div>
}
