import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { App } from './App'
import { PortfolioWorkspaceProvider } from './features/portfolio/PortfolioWorkspace'
import './styles.css'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
})

const root = document.getElementById('root')
if (!root) throw new Error('AlphaPilot root element was not found')

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <PortfolioWorkspaceProvider>
          <App />
        </PortfolioWorkspaceProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
