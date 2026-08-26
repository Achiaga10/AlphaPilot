import { Link } from 'react-router-dom'

export function StalePlanWarning({ onRegenerate, message }: { onRegenerate?: () => void; message?: string | null }) {
  return (
    <div className="stale-plan-warning" role="status">
      <div><strong>Displayed plan is stale</strong><span>{message ?? 'Plan inputs changed after this result was generated.'}</span></div>
      {onRegenerate ? <button className="button button--primary button--small" type="button" onClick={onRegenerate}>Regenerate plan</button> : <Link className="button button--primary button--small" to="/portfolio">Review and regenerate</Link>}
    </div>
  )
}
