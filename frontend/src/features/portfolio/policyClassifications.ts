import type { SizingPolicy, StrategyName } from '../../types/portfolio'

export type ResearchClassification = 'PROMISING_RESEARCH_BASELINE' | 'RESEARCH_ONLY'

export const POLICY_CLASSIFICATIONS: Record<
  StrategyName,
  Record<SizingPolicy, ResearchClassification>
> = {
  'ema20-pullback': {
    'equal-slot': 'PROMISING_RESEARCH_BASELINE',
    'atr-risk': 'RESEARCH_ONLY',
    'atr-volatility-normalized': 'RESEARCH_ONLY',
  },
  'micho-150': {
    'equal-slot': 'PROMISING_RESEARCH_BASELINE',
    'atr-risk': 'RESEARCH_ONLY',
    'atr-volatility-normalized': 'PROMISING_RESEARCH_BASELINE',
  },
}
