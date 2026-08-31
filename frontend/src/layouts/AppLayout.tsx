import { NavLink, Outlet } from 'react-router-dom'
import alphaPilotLogo from '../assets/images/alphapilot-logo.png'
import { StatusBadge } from '../components/StatusBadge'
import { useAdminCapabilityQuery, useHealthQuery } from '../hooks/usePortfolioApi'
import { FloatingCopilot } from '../features/copilot/FloatingCopilot'

export function AppLayout() {
  const health = useHealthQuery()
  const adminCapability = useAdminCapabilityQuery()
  const connectionLabel = health.isPending
    ? 'Checking backend'
    : health.isSuccess
      ? 'Backend connected'
      : 'Backend unavailable'
  const connectionValue = health.isSuccess ? 'ok' : health.isPending ? 'HOLD' : 'NO_DATA'

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <aside className="sidebar">
        <div className="brand">
          <img className="brand__logo" src={alphaPilotLogo} alt="AlphaPilot" />
          <span className="brand__subtitle">Daily Portfolio Manager</span>
        </div>
        <nav aria-label="Primary navigation">
          <NavLink to="/" end>Dashboard</NavLink>
          <NavLink to="/portfolio">Portfolio plan</NavLink>
          <NavLink to="/evaluate">Evaluate stock</NavLink>
          <NavLink to="/settings">Research settings</NavLink>
          <NavLink to="/admin/data">Data Management {adminCapability.data && !adminCapability.data.enabled ? <span className="nav-lock">Locked</span> : null}</NavLink>
        </nav>
        <div className="sidebar__status">
          <StatusBadge value={connectionValue} label={connectionLabel} />
          <p>Stored market data · advisory output</p>
        </div>
      </aside>
      <div className="app-content">
        <header className="topbar">
          <div>
            <span className="research-dot" aria-hidden="true" />
            Research environment
          </div>
          <span>Not connected to live trading</span>
        </header>
        <main id="main-content" tabIndex={-1}>
          <Outlet />
        </main>
        <footer>
          AlphaPilot outputs are research/advisory decisions. Current models are not live-trading validated.
        </footer>
      </div>
      <FloatingCopilot />
    </div>
  )
}
