import type { ReactNode } from 'react'
import { ApiError } from '../api/client'

export function LoadingState({ label }: { label: string }) {
  return (
    <div className="state-card" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <div>
        <strong>{label}</strong>
        <p>Using stored AlphaPilot data. This may take a moment.</p>
      </div>
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const apiError = error instanceof ApiError ? error : null
  const message = apiError?.message ?? 'AlphaPilot could not complete this request.'
  return (
    <div className="state-card state-card--error" role="alert">
      <div>
        <strong>{message}</strong>
        {apiError?.status === 422 && apiError.validationIssues.length > 0 ? (
          <ul>
            {apiError.validationIssues.map((issue, index) => (
              <li key={`${issue.loc?.join('.') ?? 'request'}-${index}`}>
                {issue.loc?.join(' › ')}: {issue.msg ?? 'Invalid value'}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
      {onRetry ? (
        <button className="button button--secondary" type="button" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="empty-state">
      <span aria-hidden="true">◇</span>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  )
}
