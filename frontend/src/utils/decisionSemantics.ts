import type { PortfolioDecision } from '../types/portfolio'

export function isFinalApprovedBuy(decision: PortfolioDecision): boolean {
  return decision.final_action === 'BUY' && decision.is_final_actionable
}

export function isFinalApprovedSell(decision: PortfolioDecision): boolean {
  return (
    (decision.final_action === 'SELL' || decision.final_action === 'EXIT_REQUIRED')
    && decision.is_final_actionable
  )
}
