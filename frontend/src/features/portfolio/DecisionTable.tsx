import { type ReactNode, useState } from 'react'
import { EmptyState } from '../../components/AsyncState'
import { InfoTooltip } from '../../components/InfoTooltip'
import { StatusBadge } from '../../components/StatusBadge'
import type {
  PortfolioDecision,
  PortfolioPlanActionResult,
  SizingPolicy,
} from '../../types/portfolio'
import { isFinalApprovedBuy, isFinalApprovedSell } from '../../utils/decisionSemantics'
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
  excludedTickers?: ReadonlySet<string>
  onExcludeTicker?: (ticker: string) => void
  onRestoreTicker?: (ticker: string) => void
  preferencePending?: boolean
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
  excludedTickers = new Set<string>(),
  onExcludeTicker,
  onRestoreTicker,
  preferencePending = false,
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
            const excluded = excludedTickers.has(decision.ticker)
            const approvedBuy = isFinalApprovedBuy(decision)
            const approvedSell = isFinalApprovedSell(decision)
            const terminalReason = decision.terminal_reason ?? decision.reason
            const allocationLabel = approvedBuy ? 'Approved allocation' : 'Candidate allocation'
            const finalActionLabel = approvedBuy
              ? 'APPROVED BUY'
              : decision.final_action.replaceAll('_', ' ')
            return (
              <article className="decision-card" key={`${decision.ticker}-${decision.decision}`}>
                <div className="decision-card__main">
                  <div className="rank-with-help">
                    <div className="rank" aria-label={rankByTicker[decision.ticker] ? `BUY candidate rank ${rankByTicker[decision.ticker]}` : 'Not ranked'}>{rankByTicker[decision.ticker] ?? '—'}</div>
                    <InfoTooltip label="About candidate rank">This is AlphaPilot&apos;s recommendation priority under the selected ranking policy. You are not required to add positions in this order.</InfoTooltip>
                  </div>
                  <div className="decision-card__identity"><strong>{decision.ticker}</strong><span>{decision.sector}</span></div>
                  <div className="decision-card__badges">
                    <span className="field-label field-label--with-help">Final status <InfoTooltip label="About final status">The authoritative user-facing action after every hard gate.</InfoTooltip></span>
                    <StatusBadge value={decision.final_action} label={`Final action ${finalActionLabel}`} />
                    <span className="field-label field-label--with-help">Technical signal <InfoTooltip label="About strategy signal">{METRIC_GLOSSARY.strategySignal}</InfoTooltip></span>
                    <StatusBadge value={decision.signal} label={`Signal ${decision.signal}`} />
                    <span className="field-label field-label--with-help">Candidate decision <InfoTooltip label="About candidate decision">{`${METRIC_GLOSSARY.portfolioDecision} This is intermediate and is not approval to act.`}</InfoTooltip></span>
                    <StatusBadge value={decision.decision} />
                  </div>
                  <div><span className="field-label field-label--with-help">RS20 score <InfoTooltip label="About RS20 score">{HELP_TEXT.rs20}</InfoTooltip></span><strong>{formatScore(decision.ranking_score)}</strong></div>
                  <div><span className="field-label field-label--with-help">{allocationLabel} <InfoTooltip label={`About ${allocationLabel.toLowerCase()}`}>{METRIC_GLOSSARY.proposedAllocation}</InfoTooltip></span><strong>{formatMoney(decision.target_allocation_dollars)}</strong></div>
                  <div><span className="field-label field-label--with-help">Terminal reason <InfoTooltip label="About terminal reason">The first authoritative hard gate that determines the final action.</InfoTooltip></span><strong>{humanizeReason(terminalReason)}</strong></div>
                </div>
                {terminalReason === 'LOSS_CONTROL_UNAVAILABLE' ? <p className="inline-note"><strong>LOSS CONTROL</strong><br />No approved numeric loss-control policy<br /><strong>Status: NOT ACTIONABLE</strong></p> : null}
                {approvedBuy && decision.manual_stop_required ? <p className="inline-note inline-note--warning"><strong>MANUAL STOP REQUIRED</strong><br />No system stop — set and manage the protective stop manually.</p> : null}
                {excluded ? <p className="inline-note">Excluded by you. Technical and historical evidence remains available.</p> : null}
                {onExcludeTicker || onRestoreTicker ? <div className="table-actions">
                  {excluded ? <button className="button button--secondary button--small" type="button" disabled={preferencePending} onClick={() => onRestoreTicker?.(decision.ticker)}>Return to recommendation pool</button> : <button className="button button--secondary button--small" type="button" disabled={preferencePending} onClick={() => onExcludeTicker?.(decision.ticker)}>Exclude from future plans</button>}
                </div> : null}
                {canApplyDecisions && decision.cash_after_decision !== null && ((approvedBuy && decision.proposed_shares > 0) || (approvedSell && decision.current_shares > 0)) ? (
                  <div className="decision-action">
                    {approvedBuy ? <>
                      <div className="quantity-choice"><span>AlphaPilot research allocation: <strong>{decision.proposed_shares} shares</strong><small>{decision.manual_stop_required ? 'Manual stop required · no system stop' : decision.execution_readiness === 'ACTIONABLE' ? 'System loss-control evidence approved' : 'Research only · no approved protective stop'}</small></span><label><span>Shares to add</span><input aria-label={`Shares to add for ${decision.ticker}`} type="number" min="1" step="1" value={quantity} disabled={applied || pending} onChange={(event) => setQuantities((current) => ({ ...current, [quantityKey]: event.target.value }))} /></label></div>
                      <button className="button button--primary button--small" type="button" disabled={applied || pending || !Number.isInteger(Number(quantity)) || Number(quantity) <= 0} onClick={() => void reviewBuy(decision)}>{applied ? 'Applied' : pending ? 'Validating…' : 'Review Add'}</button>
                    </> : <><p>Research portfolio update only — no broker order is sent.</p><button className="button button--primary button--small" type="button" disabled={applied || pending} onClick={() => applySell(decision)}>{applied ? 'Applied' : pending ? 'Applying…' : 'Apply Sell'}</button></>}
                  </div>
                ) : null}
                <details>
                  <summary>Decision details</summary>
                  <dl className="detail-grid">
                    <Detail label="Technical signal" help="The frozen strategy output; it does not itself authorize a portfolio action."><StatusBadge value={decision.signal} /></Detail>
                    <Detail label="Portfolio candidate decision" help="The intermediate allocation-stage outcome before final safety checks. News context has no approval authority."><StatusBadge value={decision.base_decision ?? decision.decision} /></Detail>
                    <Detail label="Allocation-stage outcome" help="Intermediate sizing/allocation evidence, preserved separately from final actionability.">{allocationOutcome(decision)}</Detail>
                    <Detail label={decision.news_advisory_only ? 'News advisory context' : 'News effect'} help="Persisted News assessment. When marked advisory-only by the backend, it cannot change the final action, allocation or terminal reason.">{decision.news_advisory_only ? <p>Advisory only — does not approve, block or change this decision.</p> : null}<code>{decision.news_effect ?? 'NO_EFFECT'}</code></Detail>
                    <Detail label="News coverage" help="Current provider and classifier readiness is separate from stored article history."><code>{decision.news_coverage ?? 'NEVER_REFRESHED'}</code></Detail>
                    <Detail label="Final AlphaPilot action" help="The single authoritative action after all hard gates."><StatusBadge value={decision.final_action} label={finalActionLabel} /></Detail>
                    <Detail label="Terminal reason" help="The first authoritative blocker, or approval reason for a final actionable decision."><code>{terminalReason}</code></Detail>
                    <Detail label="News reason" help="The stored assessment reason; the AI classifier never supplies a trade action.">{decision.news_reason ?? (decision.news_advisory_only ? 'Optional News context not evaluated' : 'No News-driven change')}</Detail>
                    <Detail label="News policy" help="The deterministic server policy version that produced the News effect."><code>{decision.news_policy_version ?? 'Not applicable'}</code></Detail>
                    <Detail label="Supporting News" help="Persisted article identifiers supporting the News assessment.">{decision.supporting_news_article_ids?.length ? decision.supporting_news_article_ids.join(', ') : 'None'}</Detail>
                    <Detail label="Candidate rank" help={METRIC_GLOSSARY.candidateRank}>{rankByTicker[decision.ticker] ?? 'Not ranked'}</Detail>
                    <Detail label="Reference price" help={METRIC_GLOSSARY.referencePrice}>{formatMoney(decision.reference_price)}</Detail>
                    {decision.entry_safety ? <>
                      <Detail label="EMA20 entry safety" help="Fresh backend-owned entry geometry; ranking and News cannot override a block."><StatusBadge value={decision.entry_safety.status} /> · <code>{decision.entry_safety.reason}</code></Detail>
                      <Detail label="Entry validation price" help="Authoritative price selected by the backend for current entry revalidation.">{formatMoney(decision.entry_safety.entry_price)} · {decision.entry_safety.entry_price_source ?? 'Unavailable'}</Detail>
                      <Detail label="EMA20 entry anchor" help="The fixed completed signal-session EMA20 anchor; the current price does not move this reference.">{formatMoney(decision.entry_safety.ema20)} · {decision.entry_safety.ema20_source}</Detail>
                      <Detail label="Distance from EMA20" help="Calculated by the backend from the authoritative entry price and fixed EMA20 anchor.">{formatMoney(decision.entry_safety.distance_to_ema20)} / {formatPercent(decision.entry_safety.distance_to_ema20_pct)}</Detail>
                      <Detail label="Entry evidence time" help="Price timestamp and completed EMA anchor date used by the safety policy.">{decision.entry_safety.entry_price_timestamp ? new Date(decision.entry_safety.entry_price_timestamp).toLocaleString() : 'Unavailable'} · EMA as of {decision.entry_safety.ema20_as_of ?? 'Unavailable'}</Detail>
                    </> : null}
                    <Detail label="ATR14" help={METRIC_GLOSSARY.atr14}>{formatMoney(decision.atr)}</Detail>
                    <Detail label="Modeled stop distance" help={METRIC_GLOSSARY.stopDistance}>{riskValue(riskApplicable, decision.decision, formatMoney(decision.stop_distance))}</Detail>
                    <Detail label="Research stop reference" help={METRIC_GLOSSARY.stopReference}>{riskValue(riskApplicable, decision.decision, formatMoney(decision.modeled_stop_reference_price))}</Detail>
                    <Detail label="Proposed shares" help={METRIC_GLOSSARY.proposedShares}>{decision.proposed_shares}</Detail>
                    <Detail label={allocationLabel} help={METRIC_GLOSSARY.proposedAllocation}>{formatMoney(decision.target_allocation_dollars)}</Detail>
                    <Detail label="Estimated cash outlay" help={METRIC_GLOSSARY.estimatedOutlay}>{formatMoney(decision.estimated_cash_outlay)}</Detail>
                    <Detail label="Target weight" help={METRIC_GLOSSARY.targetWeight}>{formatPercent(decision.target_weight_pct)}</Detail>
                    <Detail label="Modeled position risk" help={METRIC_GLOSSARY.modeledPositionRisk}>{riskValue(riskApplicable, decision.decision, formatMoney(decision.modeled_position_risk_dollars))}</Detail>
                    <Detail label="Risk budget" help={METRIC_GLOSSARY.riskBudget}>{riskValue(riskApplicable, decision.decision, formatMoney(decision.risk_budget_dollars))}</Detail>
                    <Detail label="Sector" help={METRIC_GLOSSARY.sector}>{decision.sector}</Detail>
                    <Detail label="Sector before" help={METRIC_GLOSSARY.sectorBefore}>{formatPercent(decision.sector_weight_before_pct)}</Detail>
                    <Detail label="Sector after" help={METRIC_GLOSSARY.sectorAfter}>{formatPercent(decision.sector_weight_after_pct)}</Detail>
                    <Detail label="Current shares" help={METRIC_GLOSSARY.currentShares}>{decision.current_shares}</Detail>
                    <Detail label="Estimated proceeds" help={METRIC_GLOSSARY.estimatedProceeds}>{formatMoney(decision.estimated_proceeds)}</Detail>
                    <Detail label="Candidate reason" help="Intermediate allocation-stage reason; it is not the final actionability reason.">{allocationOutcome(decision)}</Detail>
                    <Detail label="Execution readiness" help="Micho requires approved system loss control. EMA20 may be approved under the explicit user-managed manual-stop policy after every other hard gate passes.">{decision.execution_readiness ?? 'RESEARCH_ONLY'} · <code>{decision.execution_readiness_reason ?? 'NO_APPROVED_LOSS_CONTROL_POLICY'}</code></Detail>
                    <Detail label="Loss-control source" help="Whether an approved system policy supplies the boundary or the EMA20 stop must be chosen and managed by the user."><code>{decision.loss_control_source ?? 'NONE'}</code></Detail>
                    {decision.loss_control_active ? <Detail label="Loss-control boundary" help="Backend-owned numeric strategy boundary and exact trigger semantics.">{decision.loss_control_policy} · {formatMoney(decision.loss_control_boundary_price)} · {decision.loss_control_trigger} · broker stop: {decision.loss_control_broker_stop_order ? 'YES' : 'NONE'}</Detail> : decision.manual_stop_required ? <Detail label="Loss control" help="AlphaPilot has not generated a protective boundary. The user is responsible for choosing and placing it.">MANUAL STOP REQUIRED · No system stop — set manually</Detail> : <Detail label="Loss control" help="No approved system or user-managed loss-control mode applies to this decision.">No approved numeric loss-control policy</Detail>}
                    <Detail label="Approved protective stop" help="Null means AlphaPilot generated no automatic protective-stop price; research references are not substituted.">{decision.approved_protective_stop_price === null || decision.approved_protective_stop_price === undefined ? decision.manual_stop_required ? 'No system stop — set manually' : 'None · research only' : formatMoney(decision.approved_protective_stop_price)}</Detail>
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

function allocationOutcome(decision: PortfolioDecision): string {
  const reason = decision.allocation_reason ?? decision.reason
  if (reason === 'BUY_APPROVED') {
    return isFinalApprovedBuy(decision)
      ? 'Approved allocation'
      : 'Candidate allocation proposed (intermediate)'
  }
  return humanizeReason(reason)
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
