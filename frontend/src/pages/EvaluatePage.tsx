import { type FormEvent, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ErrorState, LoadingState } from '../components/AsyncState'
import { InfoTooltip } from '../components/InfoTooltip'
import { MetricCard } from '../components/MetricCard'
import { StatusBadge } from '../components/StatusBadge'
import { buildPlanRequest } from '../features/portfolio/PlanForm'
import { HELP_TEXT } from '../features/portfolio/helpText'
import { usePortfolioWorkspace } from '../features/portfolio/PortfolioWorkspace'
import { usePortfolioPlanMutation, useRiskConfigQuery } from '../hooks/usePortfolioApi'
import type { CandidateStatus, PortfolioDecision, PortfolioPlan } from '../types/portfolio'
import { formatDate, formatMoney, formatScore, humanizeReason, selectionLabel, sizingLabel, strategyLabel } from '../utils/format'

const normalizeTicker = (value: string) => value.trim().toUpperCase()

interface EvaluationSnapshot {
  requestedTicker: string
  plan: PortfolioPlan
  status: CandidateStatus
  decision: PortfolioDecision | undefined
}

function selectEvaluationTarget(plan: PortfolioPlan, requestedTicker: string): EvaluationSnapshot | null {
  const normalizedTarget = normalizeTicker(plan.evaluation_target_ticker ?? '')
  if (normalizedTarget !== requestedTicker) return null
  const matchingStatuses = plan.candidate_statuses.filter(
    (item) => normalizeTicker(item.ticker) === requestedTicker,
  )
  if (matchingStatuses.length !== 1) return null
  const status = matchingStatuses[0]!
  if (status.status !== 'COMPANY_NOT_FOUND' && !status.company_id) return null
  const decision = plan.decisions.find((item) => normalizeTicker(item.ticker) === requestedTicker)
  return { requestedTicker, plan, status, decision }
}

export function EvaluatePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [ticker, setTicker] = useState(searchParams.get('ticker')?.toUpperCase() ?? '')
  const [error, setError] = useState<string | null>(null)
  const [evaluation, setEvaluation] = useState<EvaluationSnapshot | null>(null)
  const [isEvaluating, setIsEvaluating] = useState(false)
  const latestRequestId = useRef(0)
  const { draft } = usePortfolioWorkspace()
  const riskConfig = useRiskConfigQuery()
  const mutation = usePortfolioPlanMutation()

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalized = normalizeTicker(ticker)
    if (!/^[A-Z0-9.-]{1,10}$/.test(normalized)) {
      setError('Enter a valid ticker.')
      return
    }
    if (!riskConfig.data) return
    const requestId = latestRequestId.current + 1
    latestRequestId.current = requestId
    setError(null)
    setIsEvaluating(true)
    setSearchParams({ ticker: normalized })
    try {
      const plan = await mutation.mutateAsync(
        buildPlanRequest({ ...draft, tickerScope: normalized }, riskConfig.data),
      )
      if (latestRequestId.current !== requestId) return
      const target = selectEvaluationTarget(plan, normalized)
      if (!target) {
        console.error('Single-stock evaluation identity mismatch', {
          requestedTicker: normalized,
          returnedTargetTicker: plan.evaluation_target_ticker,
          returnedStatusTickers: plan.candidate_statuses.map((item) => item.ticker),
        })
        setEvaluation(null)
        setError(`AlphaPilot could not match the evaluation response to ${normalized}.`)
        return
      }
      setEvaluation(target)
    } catch (requestError) {
      if (latestRequestId.current !== requestId) return
      setError(requestError instanceof Error ? requestError.message : 'Evaluation failed.')
    } finally {
      if (latestRequestId.current === requestId) setIsEvaluating(false)
    }
  }

  const normalizedDraftTicker = normalizeTicker(ticker)
  const resultIsStale = Boolean(
    evaluation && normalizedDraftTicker && normalizedDraftTicker !== evaluation.requestedTicker,
  )
  const plan = evaluation?.plan
  const status = evaluation?.status
  const decision = evaluation?.decision

  return (
    <div className="page">
      <header className="page-header"><div><p className="eyebrow">Stored-data research</p><h1>Evaluate Stock</h1><p>Ask the backend to evaluate one stored ticker using the current portfolio and frozen research configuration.</p></div></header>
      <form className="panel single-evaluate-form" onSubmit={(event) => void submit(event)} noValidate>
        <label><span className="label-with-help">Ticker <InfoTooltip label="About single-stock evaluation">The backend loads stored company and candle data, then calculates strategy, RS20, ATR, risk, and portfolio decisions. The browser supplies none of those facts.</InfoTooltip></span><input aria-label="Ticker" value={ticker} maxLength={10} placeholder="AAPL" onChange={(event) => setTicker(event.target.value.toUpperCase())} aria-invalid={Boolean(error)} />{error ? <small className="field-error" role="alert">{error}</small> : null}</label>
        <button className="button button--primary" type="submit" disabled={!riskConfig.data}>{isEvaluating ? 'Evaluating…' : 'Evaluate stock'}</button>
      </form>
      {resultIsStale && evaluation ? <p className="notice notice--warning" role="status">Showing previous evaluation for {evaluation.requestedTicker}. Evaluate {normalizedDraftTicker} to update.</p> : null}
      {riskConfig.isPending ? <LoadingState label="Loading research configuration" /> : null}
      {riskConfig.isError ? <ErrorState error={riskConfig.error} onRetry={() => void riskConfig.refetch()} /> : null}
      {isEvaluating ? <LoadingState label="Evaluating stored ticker" /> : null}
      {plan && status ? (
        <div className="page-stack plan-results" aria-live="polite">
          <section className="result-banner"><div><p className="eyebrow">Single-stock result</p><h2>{status.company_name ?? status.ticker}</h2><p>{status.ticker} · {status.sector ?? 'Sector unavailable'}</p></div><StatusBadge value={status.status} /></section>
          <div className="analysis-strip">
            <div><span>Strategy</span><strong>{strategyLabel(plan.strategy)}</strong></div><div><span>Selection</span><strong>{selectionLabel(plan.selection_policy)}</strong></div><div><span>Sizing</span><strong>{sizingLabel(plan.sizing_policy)}</strong></div><div><span>Requested</span><strong>{formatDate(plan.requested_as_of_date)}</strong></div><div><span>Completed analysis session</span><strong>{formatDate(plan.analysis_as_of_date)}</strong></div>
          </div>
          {status.status === 'COMPANY_NOT_FOUND' ? <section className="panel"><h2>Company not found</h2><p>AlphaPilot has no stored company metadata for {status.ticker}. The backend cannot safely infer arbitrary custom-ticker metadata, so no company was fabricated.</p></section> : null}
          {status.status === 'STALE_DATA' || status.status === 'NO_DATA' || status.status === 'INSUFFICIENT_HISTORY' ? <section className="panel"><h2>Evaluation unavailable</h2><p>{humanizeReason(status.reason)}. Stored data date: {formatDate(status.data_as_of_date)}.</p></section> : null}
          {status.status !== 'COMPANY_NOT_FOUND' ? (
            <section className="panel" aria-labelledby="single-result-title"><div className="section-heading"><div><p className="eyebrow">Backend facts</p><h2 id="single-result-title">Signal and portfolio decision</h2></div></div><div className="metric-grid metric-grid--four"><MetricCard label="Strategy signal" value={status.signal ?? 'Not available'} /><MetricCard label="Portfolio decision" value={decision?.decision ?? status.decision ?? 'No decision'} /><MetricCard label="BUY candidate rank" value={String(status.candidate_rank ?? 'Not ranked')} /><MetricCard label="Proposed allocation" value={formatMoney(decision?.target_allocation_dollars)} /><MetricCard label="RS20 score" value={formatScore(decision?.ranking_score ?? status.ranking_score ?? null)} description={HELP_TEXT.rs20} /><MetricCard label="ATR14" value={formatMoney(decision?.atr ?? status.atr)} /><MetricCard label="Data as of" value={formatDate(status.data_as_of_date)} /><MetricCard label="Reason" value={humanizeReason(decision?.reason ?? status.decision_reason ?? status.reason)} /></div>{decision ? <details className="machine-details"><summary>Machine-readable details</summary><code>{decision.reason}</code></details> : null}</section>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
