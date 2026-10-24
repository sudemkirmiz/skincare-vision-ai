import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { api } from './api'
import type { Analysis, Options, Profile } from './types'

export interface AiSettings {
  provider: string
  useVlm: boolean
  secondOpinion: boolean
  hfModel: string
}

interface AppState {
  options: Options
  profiles: Profile[]
  profile: Profile | null
  selectProfile: (id: string) => void
  refreshProfiles: () => Promise<void>
  editor: 'first' | 'edit' | 'new' | null
  openEditor: (mode: 'edit' | 'new') => void
  closeEditor: () => void
  ai: AiSettings
  setAi: (settings: Partial<AiSettings>) => void
  /** Personal API keys live in memory only: never written to browser storage. */
  providerKeys: Record<string, string>
  setProviderKey: (provider: string, key: string) => void
  analysis: Analysis | null
  setAnalysis: (analysis: Analysis | null) => void
}

const Context = createContext<AppState | null>(null)
const ACTIVE_KEY = 'scv.activeProfile'
const AI_KEY = 'scv.aiSettings'

// Browser storage is a convenience only; it can be blocked (private mode), so every access is guarded.
function readStorage<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? { ...fallback, ...JSON.parse(raw) } : fallback
  } catch {
    return fallback
  }
}

function writeStorage(key: string, value: unknown) {
  try {
    localStorage.setItem(key, typeof value === 'string' ? value : JSON.stringify(value))
  } catch {
    /* ignore */
  }
}

export function AppStateProvider({ options, children }: { options: Options; children: ReactNode }) {
  const queryClient = useQueryClient()
  const profilesQuery = useQuery({ queryKey: ['profiles'], queryFn: api.profiles })
  const profiles = useMemo(() => profilesQuery.data ?? [], [profilesQuery.data])
  const [activeId, setActiveId] = useState<string | null>(() => {
    try {
      return localStorage.getItem(ACTIVE_KEY)
    } catch {
      return null
    }
  })
  const [editorMode, setEditorMode] = useState<'edit' | 'new' | null>(null)
  const [ai, setAiState] = useState<AiSettings>(() => {
    const stored = readStorage(AI_KEY, { provider: options.default_provider, useVlm: true, secondOpinion: options.flags.second_opinion, hfModel: options.hf_models[0] ?? '' })
    // Stored choices can go stale when the server's lists change.
    return {
      ...stored,
      provider: options.providers.includes(stored.provider) ? stored.provider : options.default_provider,
      hfModel: options.hf_models.includes(stored.hfModel) ? stored.hfModel : options.hf_models[0] ?? '',
    }
  })
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [providerKeys, setProviderKeys] = useState<Record<string, string>>({})
  const setProviderKey = useCallback((provider: string, key: string) => setProviderKeys((keys) => ({ ...keys, [provider]: key })), [])

  // Derived, not synced: falls back to the most recently used profile when the stored id is gone.
  const profile = profiles.find((p) => p.id === activeId) ?? profiles[0] ?? null

  const selectProfile = useCallback((id: string) => {
    setActiveId(id)
    writeStorage(ACTIVE_KEY, id)
    setAnalysis(null)
    api.touchProfile(id).catch(() => undefined)
  }, [])

  const refreshProfiles = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ['profiles'] })
  }, [queryClient])

  const setAi = useCallback((settings: Partial<AiSettings>) => {
    setAiState((current) => {
      const next = { ...current, ...settings }
      writeStorage(AI_KEY, next)
      return next
    })
  }, [])

  const value: AppState = {
    options,
    profiles,
    profile,
    selectProfile,
    refreshProfiles,
    editor: profilesQuery.isSuccess && profiles.length === 0 ? 'first' : editorMode,
    openEditor: setEditorMode,
    closeEditor: () => setEditorMode(null),
    ai,
    setAi,
    providerKeys,
    setProviderKey,
    analysis,
    setAnalysis,
  }

  if (profilesQuery.isPending) return null
  return <Context.Provider value={value}>{children}</Context.Provider>
}

export function useAppState(): AppState {
  const state = useContext(Context)
  if (!state) throw new Error('useAppState outside AppStateProvider')
  return state
}
