import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './layouts/AppLayout'
import { DashboardPage } from './pages/DashboardPage'
import { PortfolioPage } from './pages/PortfolioPage'
import { SettingsPage } from './pages/SettingsPage'
import { EvaluatePage } from './pages/EvaluatePage'
import { AdminDataPage } from './pages/AdminDataPage'

export function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="portfolio" element={<PortfolioPage />} />
        <Route path="evaluate" element={<EvaluatePage />} />
        <Route path="admin/data" element={<AdminDataPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
