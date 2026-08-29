import { type ReactNode, useState } from 'react'
import { EmptyState } from '../../components/AsyncState'
import { InfoTooltip } from '../../components/InfoTooltip'
import { StatusBadge } from '../../components/StatusBadge'
import type {
  PortfolioDecision,
  PortfolioPlanActionResult,
  SizingPolicy,
} from '../../types/portfolio'
import { formatMoney, formatPercent, formatScore, humanizeReason } from '../../utils/format'
import { BuyActionPreviewDialog } from './BuyActionPreviewDialog'
import { HELP_TEXT } from './helpText'
import { METRIC_GLOSSARY } from './metricGlossary'

interface DecisionTableProps {
  decisions: PortfolioDecision[]
  rankByTicker?: Record<string, number | null | undefined>
  canApplyDecisions?: boolean
  onApplyDecision?: (decision: PortfolioDecision, requestedShares?: number) => void | Promise<unknown>
  onPreviewDecision?: (decision: PortfolioDecision, requestedShares?: number) => Promise<PortfolioPlanActionResult | null>
  sizingPolicy?: SizingPolicy
  appliedActionIds?: ReadonlySet<string>
  actionPendingId?: string | null
  emptyTitle?: string
  emptyMessage?: string
}

export function DecisionTable({
  decisions,
  rankByTicker = {},
  canApplyDecisions = false,
  onApplyDecision,
  onPreviewDecision,
  sizingPolicy = 'equal-slot',
  appliedActionIds = new Set<string>(),
  actionPendingId = null,
  emptyTitle = 'No portfolio decisions',
  emptyMessage = 'No actionable or held-position decisions match this view and its current filters.',
}: DecisionTableProps) {
  const [quantities, setQuantities] = useState<Record<string, string>>({})
  const [preview, setPreview] = useState<{ decision: PortfolioDecision; result: PortfolioPlanActionResult } | null>(null)

  async function reviewBuy(decision: PortfolioDecision) {
    const key = decision.action_id ?? decision.ticker
    const shares = Number(quantities[key] ?? decision.proposed_shares)
    if (!Number.isInteger(shares) || shares <= 0) return
    const result = await onPreviewDecision?.(
      decision,
      quantities[key] === undefined ? undefined : shares,
    )
    if (result) setPreview({ decision, result })
  }

  function applySell(decision: PortfolioDecision) {
    const message = `Remove ${decision.ticker} from research portfolio?\n\n${decision.current_shares} shares\nEstimated proceeds: ${formatMoney(decision.estimated_proceeds)}\n\nNo broker order will be sent.`
    if (window.confirm(message)) void onApplyDecision?.(decision, decision.current_shares)
  }

  return (
    <div>
      {decisions.length === 0 ? <EmptyState title={emptyTitle}>{emptyMessage}</EmptyState> : (
        <div className="decision-list">
          {decisions.map((decision) => {
            const applied = decision.action_id !== null && appliedActionIds.has(decision.action_id)
            const pending = decision.action_id !== null && actionPendingId === decision.action_id
            const quantityKey = decision.action_id ?? decision.ticker
            const quantity = quantities[quantityKey] ?? String(decision.proposed_shares)
            const riskApplicable = sizingPolicy !== 'equal-slot' && decision.decision === 'BUY'
            return (
              <article className="decision-card" key={`${decision.ticker}-${decision.decision}`}>
                <div className="decision-card__main">
                  <div className="rank-with-help">
                    <div className="rank" aria-label={rankByTicker[decision.ticker] ? `BUY candidate rank ${rankByTicker[decision.ticker]}` : 'Not ranked'}>{rankByTicker[decision.ticker] ?? '—'}</div>
                    <InfoTooltip label="About candidate rank">This is AlphaPilot&apos;s recommendation priority under the selected ranking policy. You are not required to add positions in this order.</InfoTooltip>
                  </div>
                  <div className="decision-card__identity"><strong>{decision.ticker}</strong><span>{decision.sector}</span></div>
                  <div className="decision-card__badges">
                    <span className="field-label field-label--with-help">Signal <InfoTooltip label="About strategy signal">{METRIC_GLOSSARY.strategySignal}</InfoTooltip></span>
                    <StatusBadge value={decision.signal} label={`Signal ${decision.signal}`} />
                    <span className="field-label field-label--with-help">Decision <InfoTooltip label="About portfolio decision">{METRIC_GLOSSARY.portfolioDecision}</InfoTooltip></span>
                    <StatusBadge value={decision.decision} />
                  </div>
                  <div><span className="field-label field-label--with-help">RS20 score <InfoTooltip label="About RS20 score">{HELP_TEXT.rs20}</InfoTooltip></span><strong>{formatScore(decision.ranking_score)}</strong></div>
                  <div><span className="field-label field-label--with-help">Proposed allocation <InfoTooltip label="About proposed allocation">{METRIC_GLOSSARY.proposedAllocation}</InfoTooltip></span><strong>{formatMoney(decision.target_allocation_dollars)}</strong></div>
                  <div><span className="field-label field-label--with-help">Reason <InfoTooltip label="About decision reason">{METRIC_GLOSSARY.decisionReason}</InfoTooltip></span><strong>{humanizeReason(decision.reason)}</strong></div>
                </div>
                {canApplyDecisions && decision.cash_after_decision !== null && ((decision.decision === 'BUY' && decision.proposed_shares > 0) || (decision.decision === 'SELL' && decision.current_shares > 0)) ? (
                  <div className="decision-action">
                    {decision.decision === 'BUY' ? <>
                      <div className="quantity-choice"><span>AlphaPilot recommendation: <strong>{decision.proposed_shares} shares</strong></span><label><span>Shares to add</span><input aria-label={`Shares to add for ${decision.ticker}`} type="number" min="1" step="1" value={quantity} disabled={applied || pending} onChange={(event) => setQuantities((current) => ({ ...current, [quantityKey]: event.target.value }))} /></label></div>
                      <button className="button button--primary button--small" type="button" disabled={applied || pending || !Number.isInteger(Number(quantity)) || Number(quantity) <= 0} onClick={() => void reviewBuy(decision)}>{applied ? 'Applied' : pending ? 'Validating…' : 'Review Add'}</button>
                    </> : <><p>Research portfolio update only — no broker order is sent.</p><button className="button button--primary button--small" type="button" disabled={applied || pending} onClick={() => applySell(decision)}>{applied ? 'Applied' : pending ? 'Applying…' : 'Apply Sell'}</button></>}
                  </div>
                ) : null}
                <details>
                  <summary>Decision details</summary>
                  <dl className="detail-grid">
                    <Detail label="Candidate rank" help={METRIC_GLOSSARY.candidateRank}>{rankByTicker[decision.ticker] ?? 'Not ranked'}</Detail>
                    <Detail label="Reference price" help={METRIC_GLOSSARY.referencePrice}>{formatMoney(decision.reference_price)}</Detail>
                    <Detail label="ATR14" help={METRIC_GLOSSARY.atr14}>{formatMoney(decision.atr)}</Detail>
                    <Detail label="Modeled stop distance" help={METRIC_GLOSSARY.stopDistance}>{riskValue(riskApplicable, decision.decision, formatMoney(decision.stop_distance))}</Detail>
                    <Detail label="Research stop reference" help={METRIC_GLOSSARY.stopReference}>{riskValue(riskApplicable, decision.decision, formatMoney(decision.modeled_stop_reference_price))}</Detail>
                    <Detail label="Proposed shares" help={METRIC_GLOSSARY.proposedShares}>{decision.proposed_shares}</Detail>
                    <Detail label="Proposed allocation" help={METRIC_GLOSSARY.proposedAllocation}>{formatMoney(decision.target_allocation_dollars)}</Detail>
                    <Detail label="Estimated cash outlay" help={METRIC_GLOSSARY.estimatedOutlay}>{formatMoney(decision.estimated_cash_outlay)}</Detail>
                    <Detail label="Target weight" help={METRIC_GLOSSARY.targetWeight}>{formatPercent(decision.target_weight_pct)}</Detail>
                    <Detail label="Modeled position risk" help={METRIC_GLOSSARY.modeledPositionRisk}>{riskValue(riskApplicable, decision.decision, formatMoney(decision.modeled_position_risk_dollars))}</Detail>
                    <Detail label="Risk budget" help={METRIC_GLOSSARY.riskBudget}>{riskValue(riskApplicable, decision.decision, formatMoney(decision.risk_budget_dollars))}</Detail>
                    <Detail label="Sector" help={METRIC_GLOSSARY.sector}>{decision.sector}</Detail>
                    <Detail label="Sector before" help={METRIC_GLOSSARY.sectorBefore}>{formatPercent(decision.sector_weight_before_pct)}</Detail>
                    <Detail label="Sector after" help={METRIC_GLOSSARY.sectorAfter}>{formatPercent(decision.sector_weight_after_pct)}</Detail>
                    <Detail label="Current shares" help={METRIC_GLOSSARY.currentShares}>{decision.current_shares}</Detail>
                    <Detail label="Estimated proceeds" help={METRIC_GLOSSARY.estimatedProceeds}>{formatMoney(decision.estimated_proceeds)}</Detail>
                    <Detail label="Decision reason" help={METRIC_GLOSSARY.decisionReason}><code>{decision.reason}</code></Detail>
                  </dl>
                  <ExitGuidance decision={decision} riskApplicable={riskApplicable} />
                </details>
              </article>
            )
          })}
        </div>
      )}
      {preview ? <BuyActionPreviewDialog decision={preview.decision} preview={preview.result} pending={actionPendingId === preview.decision.action_id} onCancel={() => setPreview(null)} onConfirm={() => { const shares = preview.result.quantity_semantics === 'USER_QUANTITY_OVERRIDE' ? preview.result.requested_shares : undefined; void Promise.resolve(onApplyDecision?.(preview.decision, shares)).then(() => setPreview(null)) }} /> : null}
    </div>
  )
}

function riskValue(applicable: boolean, decision: string, formatted: string): string {
  if (applicable) return formatted
  return decision === 'BUY' ? 'Not used by Equal-slot' : 'Not applicable'
}

function ExitGuidance({ decision, riskApplicable }: { decision: PortfolioDecision; riskApplicable: boolean }) {
  const context = decision.exit_context
  if (!context) return null
  const state = context.current_exit_state.replaceAll('_', ' ').toLowerCase()
  return (
    <section className="exit-guidance" aria-label={`Exit guidance for ${decision.ticker}`}>
      <div className="section-heading"><div><p className="eyebrow">Stored-data strategy context</p><h3>Exit Guidance</h3></div><span className="muted">Data as of {context.data_as_of_date}</span></div>
      <p><strong>Current exit state:</strong> {state}. This reflects the selected frozen strategy; it is not live monitoring.</p>
      <dl className="detail-grid">
        <Detail label="Strategy exit mode" help="The actual frozen strategy exit configuration used for this analysis.">{context.exit_mode}</Detail>
        <Detail label="Current close" help="Stored close on the analysis date.">{formatMoney(context.reference_close)}</Detail>
        {context.ema20 !== null ? <>
          <Detail label="EMA20" help="The 20-session exponential moving average through the analysis date.">{formatMoney(context.ema20)}</Detail>
          <Detail label="EMA50" help="The 50-session exponential moving average. A close below EMA50 is the HYBRID hard trend exit.">{formatMoney(context.ema50)}</Detail>
          <Detail label="EMA spread" help="EMA20 minus EMA50 as a percentage of EMA50. HYBRID treats a spread of at least 2% as a strong trend.">{formatPercent(context.ema_spread_pct)}</Detail>
          <Detail label="Distance to EMA20" help="Signed close distance from EMA20.">{formatPercent(context.distance_to_ema20_pct)}</Detail>
          <Detail label="Distance to EMA50" help="Signed close distance from the hard EMA50 trend exit reference.">{formatPercent(context.distance_to_ema50_pct)}</Detail>
        </> : null}
        {context.sma150 !== null ? <>
          <Detail label="SMA150" help="The frozen Micho long-term trend reference.">{formatMoney(context.sma150)}</Detail>
          <Detail label="Distance to SMA150" help="Signed close distance from SMA150. Micho exits when close is below SMA150.">{formatPercent(context.distance_to_sma150_pct)}</Detail>
        </> : null}
        <Detail label="Fixed take-profit policy" help="A fixed profit target has not been validated for the current strategy.">None in current strategy</Detail>
        <Detail label="Research ATR reference" help={METRIC_GLOSSARY.stopReference}>{riskValue(riskApplicable, decision.decision, formatMoney(decision.modeled_stop_reference_price))}</Detail>
      </dl>
      <p className="muted">The current strategy attempts to remain in a trend until its strategy exit condition is reached. A fixed profit target has not yet been validated. Any ATR level shown is a research risk reference only—not an active stop order or part of validated exit execution.</p>
    </section>
  )
}

function Detail({ label, help, children }: { label: string; help: string; children: ReactNode }) {
  return <div><dt className="field-label--with-help">{label} <InfoTooltip label={`About ${label}`}>{help}</InfoTooltip></dt><dd>{children}</dd></div>
}
