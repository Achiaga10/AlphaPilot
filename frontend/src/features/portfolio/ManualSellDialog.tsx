import { type FormEvent, useState } from 'react'
import type { ManualSellRequest, ManualSellResult, PortfolioPositionSummary } from '../../types/portfolio'
import { formatDate, formatMoney } from '../../utils/format'
import { useLatestStoredPriceQuery, useManualSellMutation, useManualSellPreviewMutation } from '../../hooks/usePortfolioApi'
import { usePortfolioWorkspace } from './PortfolioWorkspace'
import { ErrorState, LoadingState } from '../../components/AsyncState'

export function ManualSellDialog({
  position,
  onClose,
}: {
  position: PortfolioPositionSummary
  onClose: () => void
}) {
  const { portfolio, applyManualSellResult } = usePortfolioWorkspace()
  const latest = useLatestStoredPriceQuery(position.ticker)
  const preview = useManualSellPreviewMutation()
  const apply = useManualSellMutation()
  const [shares, setShares] = useState(String(position.shares))
  const [priceOverride, setPriceOverride] = useState('')
  const [priceChanged, setPriceChanged] = useState(false)
  const price = priceChanged ? priceOverride : (latest.data?.price ?? '')

  function request(): ManualSellRequest {
    return {
      portfolio_id: portfolio?.portfolio_id ?? '',
      portfolio_revision: portfolio?.revision ?? -1,
      ticker: position.ticker,
      shares_to_sell: Number(shares),
      execution_price: priceChanged || latest.data?.price === null ? priceOverride || null : null,
    }
  }

  function review(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    preview.mutate(request())
  }

  function confirm() {
    apply.mutate(request(), {
      onSuccess: (result) => {
        if (result.applied) {
          applyManualSellResult(result)
          onClose()
        }
      },
    })
  }

  const invalidShares = !Number.isInteger(Number(shares)) || Number(shares) <= 0 || Number(shares) > position.shares
  const missingPrice = latest.data?.price === null && !price

  return (
    <div className="dialog-backdrop" role="presentation">
      <section className="sell-dialog" role="dialog" aria-modal="true" aria-labelledby="sell-dialog-title">
        <div className="section-heading"><div><p className="eyebrow">Research bookkeeping · no broker order</p><h2 id="sell-dialog-title">Sell Position · {position.ticker}</h2></div><button className="icon-button" type="button" onClick={onClose} aria-label="Close sell position dialog">Close</button></div>
        <dl className="config-grid"><div><dt>Current shares</dt><dd>{position.shares}</dd></div><div><dt>Latest stored completed close</dt><dd>{latest.isPending ? 'Loading…' : formatMoney(latest.data?.price)}</dd></div><div><dt>Data as of</dt><dd>{formatDate(latest.data?.price_date)}</dd></div></dl>
        {latest.isPending ? <LoadingState label="Loading latest stored completed close" /> : null}
        {latest.isError ? <ErrorState error={latest.error} onRetry={() => void latest.refetch()} /> : null}
        {latest.data?.price === null ? <p className="inline-note inline-note--warning">No stored market price is available for this ticker. Enter an execution price manually.</p> : null}
        <form onSubmit={review} className="form-grid form-grid--two">
          <label><span>Shares to sell</span><input aria-label="Shares to sell" type="number" min="1" max={position.shares} step="1" value={shares} onChange={(event) => { setShares(event.target.value); preview.reset() }} />{invalidShares ? <small className="field-error">Enter a whole-share quantity from 1 to {position.shares}.</small> : null}</label>
          <label><span>Execution price</span><input aria-label="Execution price" inputMode="decimal" value={price} onChange={(event) => { setPriceOverride(event.target.value); setPriceChanged(true); preview.reset() }} /><small>{priceChanged ? 'User-provided external fill for bookkeeping.' : 'Defaults to latest stored completed AlphaPilot close; not a live price.'}</small></label>
          <button className="button button--secondary" type="submit" disabled={invalidShares || missingPrice || preview.isPending}>{preview.isPending ? 'Reviewing…' : 'Review Sale'}</button>
        </form>
        {preview.isError ? <ErrorState error={preview.error} onRetry={() => preview.reset()} /> : null}
        {preview.data ? <SellConfirmation result={preview.data} pending={apply.isPending} onCancel={() => preview.reset()} onConfirm={confirm} /> : null}
        {apply.isError ? <ErrorState error={apply.error} onRetry={() => apply.reset()} /> : null}
      </section>
    </div>
  )
}

function SellConfirmation({ result, pending, onCancel, onConfirm }: { result: ManualSellResult; pending: boolean; onCancel: () => void; onConfirm: () => void }) {
  if (result.reason !== 'READY') return <p className="inline-note inline-note--warning">Sale cannot be prepared: {result.reason.replaceAll('_', ' ').toLowerCase()}.</p>
  return <section className="sell-confirmation" aria-label="Manual sale confirmation"><h3>Update research portfolio?</h3><p>Sell {result.shares_sold} shares of {result.ticker} at {formatMoney(result.execution_price)}.</p><dl className="config-grid"><div><dt>Price source</dt><dd>{result.price_source === 'LATEST_STORED_CANDLE' ? 'Latest stored completed AlphaPilot close' : 'User-provided execution price'}</dd></div><div><dt>Data as of</dt><dd>{formatDate(result.price_date)}</dd></div><div><dt>Estimated proceeds</dt><dd>{formatMoney(result.gross_proceeds)}</dd></div><div><dt>Shares remaining</dt><dd>{result.shares_remaining}</dd></div></dl><p className="muted">No broker trade is sent. This manual change makes the existing analysis stale.</p><div className="dialog-actions"><button className="button button--secondary" type="button" onClick={onCancel}>Cancel</button><button className="button button--primary" type="button" disabled={pending} onClick={onConfirm}>{pending ? 'Updating…' : 'Update Research Portfolio'}</button></div></section>
}
