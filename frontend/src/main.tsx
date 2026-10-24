import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { App } from './App'
import { LogoMark } from './icons'
import { api } from './lib/api'
import { AppStateProvider } from './lib/app-state'
import './index.css'

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 30_000 } } })

function Boot() {
  // Form options and labels come from the backend, so the UI never drifts from the domain code.
  const options = useQuery({ queryKey: ['options'], queryFn: api.options, staleTime: Infinity })
  if (options.isError) {
    return (
      <div className="grid min-h-screen place-items-center p-6 text-center">
        <div className="card max-w-md p-8">
          <h1 className="text-lg font-bold">Sunucuya ulaşılamadı</h1>
          <p className="mt-2 text-sm text-muted">Arka uç (FastAPI) çalışıyor mu? Geliştirmede: <code>uvicorn api.server:app --app-dir src --port 8000</code></p>
        </div>
      </div>
    )
  }
  if (!options.data) {
    return <div className="grid min-h-screen place-items-center text-brand-600"><LogoMark size={48} className="animate-pulse" /></div>
  }
  return (
    <AppStateProvider options={options.data}>
      <App />
    </AppStateProvider>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Boot />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
