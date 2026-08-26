import { useState } from 'react'
import { PortfolioAllocationDonut } from './PortfolioAllocationDonut'
import { PositionsTable } from './PositionsTable'
import { ManualSellDialog } from './ManualSellDialog'
import type { PortfolioPositionSummary } from '../../types/portfolio'
import { usePortfolioWorkspace } from './PortfolioWorkspace'

export function ResearchPortfolioPanel() {
  const { draftSummary } = usePortfolioWorkspace()
  const [selling, setSelling] = useState<PortfolioPositionSummary | null>(null)
  if (!draftSummary) return <section className="panel"><p className="muted">Research Portfolio Draft summary is unavailable until the backend validates the current inputs.</p></section>
  return (
    <div className="page-stack research-portfolio-panel">
      <PortfolioAllocationDonut summary={draftSummary} />
      <PositionsTable positions={draftSummary.positions} onSellPosition={setSelling} />
      {selling ? <ManualSellDialog position={selling} onClose={() => setSelling(null)} /> : null}
    </div>
  )
}
