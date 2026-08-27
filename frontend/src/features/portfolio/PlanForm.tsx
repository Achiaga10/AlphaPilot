import { type FormEvent, useState } from 'react'
import { InfoTooltip } from '../../components/InfoTooltip'
import type {
  PlanDraft,
  PortfolioPlanRequest,
  PortfolioPositionInput,
  PortfolioRiskConfig,
  SelectionPolicy,
  StrategyProfile,
  StrategyName,
} from '../../types/portfolio'
import { HELP_TEXT } from './helpText'
import { classificationLabel, sizingLabel } from '../../utils/format'

export interface PlanFormErrors {
  cash?: string
  positions?: string
  asOfDate?: string
}

export function validateDraft(draft: PlanDraft): PlanFormErrors {
  const errors: PlanFormErrors = {}
  if (draft.cash.trim() === '' || !Number.isFinite(Number(draft.cash)) || Number(draft.cash) < 0) {
    errors.cash = 'Cash must be zero or greater.'
  }
  if (!draft.asOfDate) errors.asOfDate = 'Choose a requested analysis date.'
  const seen = new Set<string>()
  for (const position of draft.positions) {
    const ticker = position.ticker.trim().toUpperCase()
    if (!/^[A-Z0-9.-]{1,10}$/.test(ticker)) {
      errors.positions = 'Each position needs a valid ticker.'
      break
    }
    if (seen.has(ticker)) {
      errors.positions = 'Each ticker may appear only once.'
      break
    }
    seen.add(ticker)
    if (!Number.isInteger(position.shares) || position.shares <= 0) {
      errors.positions = 'Shares must be positive whole numbers.'
      break
    }
    if (!Number.isFinite(Number(position.reference_price)) || Number(position.reference_price) <= 0) {
      errors.positions = 'Each position needs a positive reference price.'
      break
    }
  }
  return errors
}

export function buildPlanRequest(
  draft: PlanDraft,
  riskConfig: PortfolioRiskConfig,
): PortfolioPlanRequest {
  const tickers = [...new Set(
    draft.tickerScope
      .split(/[\s,]+/)
      .map((ticker) => ticker.trim().toUpperCase())
      .filter(Boolean),
  )]
  return {
    strategy: draft.strategy,
    selection_policy: draft.selectionPolicy,
    as_of_date: draft.asOfDate,
    tickers: tickers.length > 0 ? tickers : null,
    portfolio: {
      cash: draft.cash,
      positions: draft.positions.map((position) => ({
        ticker: position.ticker.trim().toUpperCase(),
        shares: position.shares,
        reference_price: position.reference_price,
        ...(position.cost_basis ? { cost_basis: position.cost_basis } : {}),
        ...(position.sector ? { sector: position.sector } : {}),
        ...(position.modeled_risk_dollars ? { modeled_risk_dollars: position.modeled_risk_dollars } : {}),
      })),
    },
    risk_config: riskConfig,
  }
}

interface PlanFormProps {
  draft: PlanDraft
  riskConfig: PortfolioRiskConfig
  strategyProfile: StrategyProfile
  isSubmitting: boolean
  onChange: (draft: PlanDraft) => void
  onSubmit: (request: PortfolioPlanRequest) => void
}

export function PlanForm({ draft, riskConfig, strategyProfile, isSubmitting, onChange, onSubmit }: PlanFormProps) {
  const [errors, setErrors] = useState<PlanFormErrors>({})

  function patch<K extends keyof PlanDraft>(field: K, value: PlanDraft[K]) {
    onChange({ ...draft, [field]: value })
  }

  function patchPosition(index: number, value: PortfolioPositionInput) {
    patch('positions', draft.positions.map((item, itemIndex) => (itemIndex === index ? value : item)))
  }

  function addPosition() {
    patch('positions', [
      ...draft.positions,
      { ticker: '', shares: 1, reference_price: '', cost_basis: null },
    ])
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextErrors = validateDraft(draft)
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length === 0) onSubmit(buildPlanRequest(draft, riskConfig))
  }

  return (
    <form className="plan-form" onSubmit={submit} noValidate>
      <section className="panel form-section" aria-labelledby="portfolio-input-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Manual current state</p>
            <h2 id="portfolio-input-title">Portfolio input</h2>
          </div>
          <span className="muted">Not connected to a broker</span>
        </div>
        <div className="form-grid form-grid--two">
          <label>
            <span>Cash (USD)</span>
            <input
              inputMode="decimal"
              value={draft.cash}
              onChange={(event) => patch('cash', event.target.value)}
              aria-invalid={Boolean(errors.cash)}
              aria-describedby={errors.cash ? 'cash-error' : undefined}
            />
            {errors.cash ? <small id="cash-error" className="field-error" role="alert">{errors.cash}</small> : null}
          </label>
          <label>
            <span className="label-with-help">Requested analysis date <InfoTooltip label="About requested analysis date">{HELP_TEXT.requestedDate}</InfoTooltip></span>
            <input
              type="date"
              aria-label="Requested analysis date"
              value={draft.asOfDate}
              onChange={(event) => patch('asOfDate', event.target.value)}
              aria-invalid={Boolean(errors.asOfDate)}
            />
            <small>Backend uses the newest stored SPY date on or before this date.</small>
          </label>
        </div>

        <div className="position-editor">
          <div className="subheading-row">
            <h3>Positions</h3>
            <button className="button button--secondary button--small" type="button" onClick={addPosition}>
              Add position
            </button>
          </div>
          {draft.positions.length === 0 ? <p className="muted">No current positions.</p> : null}
          {draft.positions.map((position, index) => (
            <fieldset className="position-row" key={`position-${index}`}>
              <legend>Position {index + 1}</legend>
              <label>
                <span>Ticker</span>
                <input
                  value={position.ticker}
                  maxLength={10}
                  onChange={(event) => patchPosition(index, { ...position, ticker: event.target.value.toUpperCase() })}
                />
              </label>
              <label>
                <span>Shares</span>
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={position.shares}
                  onChange={(event) => patchPosition(index, { ...position, shares: Number(event.target.value) })}
                />
              </label>
              <label>
                <span>Reference price</span>
                <input
                  inputMode="decimal"
                  value={position.reference_price}
                  onChange={(event) => patchPosition(index, { ...position, reference_price: event.target.value })}
                />
              </label>
              <label>
                <span>Cost basis (optional)</span>
                <input
                  inputMode="decimal"
                  value={position.cost_basis ?? ''}
                  onChange={(event) => patchPosition(index, { ...position, cost_basis: event.target.value || null })}
                />
              </label>
              <button
                className="icon-button"
                type="button"
                aria-label={`Remove ${position.ticker || `position ${index + 1}`}`}
                onClick={() => patch('positions', draft.positions.filter((_, itemIndex) => itemIndex !== index))}
              >
                Remove Draft Position
              </button>
            </fieldset>
          ))}
          {errors.positions ? <p className="field-error" role="alert">{errors.positions}</p> : null}
        </div>
      </section>

      <section className="panel form-section" aria-labelledby="plan-config-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Frozen research choices</p>
            <h2 id="plan-config-title">Plan configuration</h2>
          </div>
          <span className="classification">{classificationLabel(strategyProfile.classification)}</span>
        </div>
        <div className="form-grid form-grid--three">
          <label>
            <span className="label-with-help">Strategy <InfoTooltip label="About strategy choices">{HELP_TEXT.strategy}</InfoTooltip></span>
            <select
              aria-label="Strategy"
              value={draft.strategy}
              onChange={(event) => patch('strategy', event.target.value as StrategyName)}
            >
              <option value="ema20-pullback">EMA20 Pullback</option>
              <option value="micho-150">Micho 150</option>
            </select>
            <small>{draft.strategy === 'ema20-pullback' ? 'HYBRID exit · frozen 2%' : 'Entry mode · BOTH'}</small>
          </label>
          <label>
            <span className="label-with-help">Selection policy <InfoTooltip label="About selection policy">{HELP_TEXT.selection}</InfoTooltip></span>
            <select
              aria-label="Selection policy"
              value={draft.selectionPolicy}
              onChange={(event) => patch('selectionPolicy', event.target.value as SelectionPolicy)}
            >
              <option value="relative-strength-20">Relative strength 20</option>
              <option value="ticker-ascending">Ticker ascending control</option>
            </select>
          </label>
          <div className="profile-fact" aria-label="Backend strategy profile">
            <span className="label-with-help">Backend profile <InfoTooltip label="About backend strategy profile">Sizing and strategy exits are resolved by the versioned backend profile.</InfoTooltip></span>
            <strong>{strategyProfile.display_name} v{strategyProfile.version}</strong>
            <small>{sizingLabel(strategyProfile.sizing_policy)} · {strategyProfile.strategy_exit_description}</small>
          </div>
        </div>
        <p className="inline-note">Default stop: {strategyProfile.protective_stop_default}. Profit management: {strategyProfile.profit_management_default}. Research-only stop candidate: {strategyProfile.research_only_stop_candidate}.</p>
        <label className="full-width-field">
          <span className="label-with-help">Optional ticker scope <InfoTooltip label="About optional ticker scope">{HELP_TEXT.tickerScope}</InfoTooltip></span>
          <input
            aria-label="Optional ticker scope"
            value={draft.tickerScope}
            placeholder="AAPL, MSFT, NVDA — blank uses active S&P 500"
            onChange={(event) => patch('tickerScope', event.target.value)}
          />
          <small>Comma or space separated. Existing positions are always included by the backend.</small>
        </label>
      </section>

      <div className="form-actions">
        <p>AlphaPilot will analyze stored data and return advisory decisions. No orders are sent.</p>
        <button className="button button--primary" type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Generating plan…' : 'Generate Portfolio Plan'}
        </button>
      </div>
    </form>
  )
}
