import type { PortfolioDecision, PortfolioPlanActionResult } from '../../types/portfolio'
import { formatMoney, formatPercent, humanizeReason } from '../../utils/format'

export function BuyActionPreviewDialog({
  decision,
  preview,
  pending,
  onCancel,
  onConfirm,
}: {
  decision: PortfolioDecision
  preview: PortfolioPlanActionResult
  pending: boolean
  onCancel: () => void
  onConfirm: () => void
}) {
  const override = preview.quantity_semantics === 'USER_QUANTITY_OVERRIDE'
  const larger = preview.requested_shares > preview.recommended_shares
  return (
    <div className="dialog-backdrop" role="presentation">
      <section className="sell-dialog" role="dialog" aria-modal="true" aria-labelledby="buy-preview-title">
        <div className="section-heading">
          <div><p className="eyebrow">Backend-validated preview · no broker order</p><h2 id="buy-preview-title">Add {decision.ticker} to Research Portfolio</h2></div>
          <button className="icon-button" type="button" onClick={onCancel} aria-label="Close buy preview">Close</button>
        </div>
        {override ? <p className="inline-note inline-note--warning" role="status">User quantity override. {larger ? 'This position is larger than AlphaPilot’s sizing recommendation.' : 'This position is smaller than AlphaPilot’s sizing recommendation.'}</p> : null}
        <dl className="config-grid action-preview-grid">
          <div><dt>AlphaPilot recommendation</dt><dd>{preview.recommended_shares} shares</dd></div>
          <div><dt>Recommended allocation</dt><dd>{formatMoney(preview.recommended_allocation_dollars)}</dd></div>
          <div><dt>Your selection</dt><dd>{preview.requested_shares} shares</dd></div>
          <div><dt>Selected allocation</dt><dd>{formatMoney(preview.requested_allocation_dollars)}</dd></div>
          <div><dt>Selected weight</dt><dd>{formatPercent(preview.resulting_position_weight_pct)}</dd></div>
          <div><dt>Current cash</dt><dd>{formatMoney(preview.cash_before)}</dd></div>
          <div><dt>Cash after</dt><dd>{formatMoney(preview.cash_after)}</dd></div>
          <div><dt>Sector after</dt><dd>{formatPercent(preview.sector_weight_after_pct)}</dd></div>
        </dl>
        {preview.validation_status === 'REJECTED' ? (
          <p className="inline-note inline-note--warning" role="alert">Rejected by current draft validation: <code>{preview.reason}</code> ({humanizeReason(preview.reason)}).</p>
        ) : (
          <p className="muted">Validated against the current research draft, including cash, whole shares, position count, position weight, sector concentration, and policy-applicable reserve and modeled-risk constraints.</p>
        )}
        <div className="dialog-actions">
          <button className="button button--secondary" type="button" onClick={onCancel}>Cancel</button>
          <button className="button button--primary" type="button" disabled={pending || preview.validation_status !== 'VALID'} onClick={onConfirm}>{pending ? 'Updating…' : 'Add to Research Portfolio'}</button>
        </div>
      </section>
    </div>
  )
}
