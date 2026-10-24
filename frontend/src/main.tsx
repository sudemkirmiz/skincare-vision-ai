import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { StrictMode, useState, type FormEvent } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { App } from './App'
import { LogoMark } from './icons'
import { ApiError, api } from './lib/api'
import { AppStateProvider } from './lib/app-state'
import './index.css'

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 30_000 } } })

export function Boot() {
  const [accessToken, setAccessToken] = useState('')
  // Form options and labels come from the backend, so the UI never drifts from the domain code.
  const options = useQuery({ queryKey: ['options'], queryFn: api.options, staleTime: Infinity })
  if (options.isError) {
    const unauthorized = options.error instanceof ApiError && options.error.status === 401
    return (
      <div className="grid min-h-screen place-items-center p-6 text-center">
        <div className="card max-w-md p-8">
          <h1 className="text-lg font-bold">{unauthorized ? 'Erişim anahtarı gerekli' : 'Sunucuya ulaşılamadı'}</h1>
          {unauthorized ? (
            <form className="mt-4 space-y-3" onSubmit={(event: FormEvent) => { event.preventDefault(); api.setAccessToken(accessToken); void options.refetch() }}>
              <p className="text-sm text-muted">Yöneticinizin verdiği uygulama erişim anahtarını girin. Anahtar yalnızca bu sekmede saklanır.</p>
              <input className="field" type="password" autoComplete="current-password" value={accessToken} onChange={(event) => setAccessToken(event.target.value)} aria-label="Uygulama erişim anahtarı" />
              <button className="btn-primary w-full" type="submit" disabled={!accessToken.trim()}>Devam et</button>
            </form>
          ) : (
            <>
              <p className="mt-2 text-sm text-muted">Arka uç (FastAPI) çalışıyor mu? Geliştirmede: <code>uvicorn api.server:app --app-dir src --port 8000</code></p>
              <button className="btn-ghost mt-4" type="button" onClick={() => void options.refetch()}>Tekrar dene</button>
            </>
          )}
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
