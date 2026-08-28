import { type FormEvent, useState } from 'react'
import {
  useCashAdjustmentMutation,
  useExternalPositionMutation,
  usePositionReconciliationMutation,
} from '../../hooks/usePortfolioApi'
import type { ResearchPortfolio } from '../../types/portfolio'

export function ManageResearchPortfolio({ portfolio, onChanged }: {
  portfolio: ResearchPortfolio
  onChanged: () => void
}) {
  const [open, setOpen] = useState(false)
  const [positionId, setPositionId] = useState(portfolio.positions[0]?.position_id ?? '')
  const cash = useCashAdjustmentMutation(portfolio.portfolio_id)
  const external = useExternalPositionMutation(portfolio.portfolio_id)
  const reconcile = usePositionReconciliationMutation(portfolio.portfolio_id, positionId)
  const completed = () => { onChanged(); setOpen(false) }
  const text = (data: FormData, name: string) => {
    const value = data.get(name)
    return typeof value === 'string' ? value : ''
  }
  function adjust(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const data = new FormData(event.currentTarget); cash.mutate({ expected_revision: portfolio.revision, delta: text(data, 'delta'), reason: text(data, 'reason') }, { onSuccess: completed }) }
  function addExternal(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const data = new FormData(event.currentTarget); external.mutate({ expected_revision: portfolio.revision, ticker: text(data, 'ticker').toUpperCase(), quantity: Number(text(data, 'quantity')), average_cost: text(data, 'average_cost'), entry_trading_day: text(data, 'entry_date') || null, reason: text(data, 'reason') }, { onSuccess: completed }) }
  function correct(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const data = new FormData(event.currentTarget); reconcile.mutate({ expected_revision: portfolio.revision, quantity: Number(text(data, 'quantity')), average_cost: text(data, 'average_cost'), entry_trading_day: text(data, 'entry_date') || null, reason: text(data, 'reason') }, { onSuccess: completed }) }
  return <section className="panel"><div className="section-heading"><div><p className="eyebrow">Audited backend mutations</p><h2>Manage Portfolio</h2></div><button className="button button--secondary button--small" type="button" onClick={() => setOpen(!open)}>{open ? 'Close' : 'Manage'}</button></div><p>Adjust cash, import an externally opened holding, or reconcile a stored position. Successful actions increment revision and invalidate older plans.</p>{open ? <div className="admin-action-grid">
    <form onSubmit={adjust}><h3>Adjust Cash</h3><label><span>Signed delta</span><input name="delta" type="number" step="0.01" required /></label><label><span>Reason</span><input name="reason" required /></label><button className="button button--primary button--small" disabled={cash.isPending}>Apply adjustment</button></form>
    <form onSubmit={addExternal}><h3>Add External Position</h3><label><span>Ticker</span><input name="ticker" required maxLength={10} /></label><label><span>Whole shares</span><input name="quantity" type="number" min="1" required /></label><label><span>Average cost</span><input name="average_cost" type="number" min="0.0001" step="0.0001" required /></label><label><span>Entry date (optional)</span><input name="entry_date" type="date" /></label><label><span>Reason</span><input name="reason" required /></label><button className="button button--primary button--small" disabled={external.isPending}>Import position</button></form>
    <form onSubmit={correct}><h3>Reconcile Existing Position</h3><label><span>Position</span><select value={positionId} onChange={(event) => setPositionId(event.target.value)}>{portfolio.positions.map((item) => <option key={item.position_id} value={item.position_id}>{item.ticker}</option>)}</select></label><label><span>Correct whole shares</span><input name="quantity" type="number" min="1" required /></label><label><span>Correct average cost</span><input name="average_cost" type="number" min="0.0001" step="0.0001" required /></label><label><span>Entry date (optional)</span><input name="entry_date" type="date" /></label><label><span>Reason</span><input name="reason" required /></label><button className="button button--primary button--small" disabled={reconcile.isPending || !positionId}>Reconcile position</button></form>
  </div> : null}{cash.isError || external.isError || reconcile.isError ? <p role="alert" className="inline-note inline-note--warning">The reconciliation was rejected. Refresh authoritative portfolio state and verify the values.</p> : null}</section>
}
