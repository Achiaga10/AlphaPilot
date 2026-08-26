import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { App } from '../App'
import { PortfolioWorkspaceProvider } from '../features/portfolio/PortfolioWorkspace'

export function renderApp(path = '/') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <PortfolioWorkspaceProvider>
          <App />
        </PortfolioWorkspaceProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}
