// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Sudem Kırmız
import type { Analysis, CaptureCheck, ChangeMap, Comparison, Health, HistoryResponse, JournalEntry, JournalResponse, ChatMessage, CoachReply, Place, ShelfItemInput, ShelfResponse, WeatherToday, Options, Profile, ProfileInput, ProductSection, ProductVerdict, Routine } from './types'
import { DEMO, asset } from './demo'

/** Error with the backend's Turkish message(s), ready to show to the user. */
export class ApiError extends Error {
  status: number
  messages: string[]
  constructor(status: number, messages: string[]) {
    super(messages.join(' '))
    this.status = status
    this.messages = messages
  }
}

const secure = () => (location.protocol === 'https:' ? '; Secure' : '')

/**
 * A random key that identifies this browser. When the server keeps profiles per device (a link shared with
 * friends), each browser only sees the profiles it created. Sent as a header and as a SameSite cookie, so
 * images and downloads (thumbnails, PDF, exports) carry it too. Only its hash is stored on the server.
 */
// getRandomValues also works on plain-http LAN addresses, where crypto.randomUUID is unavailable.
const randomKey = () => Array.from(crypto.getRandomValues(new Uint8Array(24)), (byte) => byte.toString(16).padStart(2, '0')).join('')

function deviceKey(): string {
  let key = ''
  try {
    key = localStorage.getItem('scv.device') ?? ''
    if (!/^[A-Za-z0-9_-]{32,128}$/.test(key)) {
      key = randomKey()
      localStorage.setItem('scv.device', key)
    }
  } catch {
    key = key || randomKey()
  }
  document.cookie = `scv_device=${key}; Path=/; Max-Age=315360000; SameSite=Strict${secure()}`
  try {
    // Restore the token cookie for a tab that already holds the token (e.g. after a browser restart).
    const token = sessionStorage.getItem('scv.accessToken') ?? localStorage.getItem('scv.accessToken')
    if (token) document.cookie = `scv_token=${encodeURIComponent(token)}; Path=/; SameSite=Strict${secure()}`
  } catch { /* storage may be unavailable */ }
  return key
}
const DEVICE = typeof window === 'undefined' ? '' : deviceKey()

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // The Pages demo answers in the browser; the module (and its recorded data) is only loaded in that build.
  // Inline env check (not DEMO) so the bundler drops the import from the regular build entirely.
  if (import.meta.env.VITE_DEMO === '1') return (await import('../demo/handler')).demoRequest<T>(path, init)
  let token = ''
  try { token = sessionStorage.getItem('scv.accessToken') ?? localStorage.getItem('scv.accessToken') ?? '' } catch { /* storage may be unavailable */ }
  const headers = new Headers(init?.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (DEVICE) headers.set('X-Device-Key', DEVICE)
  const requestInit = { ...init, headers }
  const response = await fetch(path, requestInit)
  if (!response.ok) {
    let messages = ['Beklenmeyen bir hata oluştu; lütfen tekrar deneyin.']
    try {
      const body = await response.json()
      const detail = body?.detail
      if (typeof detail === 'string') messages = [detail]
      else if (Array.isArray(detail?.errors)) messages = detail.errors
      else if (Array.isArray(detail)) messages = detail.map((d: { msg?: string }) => d.msg ?? 'Geçersiz alan')
    } catch {
      /* non-JSON error body: keep the generic message */
    }
    throw new ApiError(response.status, messages)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

const keyHeader = (key?: string): HeadersInit => (key?.trim() ? { 'X-Provider-Key': key.trim() } : {})

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export interface AnalyzeOptions {
  profileId: string
  files: File[]
  provider: string
  useVlm: boolean
  secondOpinion: boolean
  hfModel?: string
  /** Typed by the user in this tab; only sent when the server allows personal keys. */
  providerKey?: string
}

export const api = {
  /** `remember` (invite links on a personal phone) keeps the token across browser restarts. */
  setAccessToken: (token: string, remember = false) => {
    try {
      if (token.trim()) (remember ? localStorage : sessionStorage).setItem('scv.accessToken', token.trim())
      else {
        sessionStorage.removeItem('scv.accessToken')
        localStorage.removeItem('scv.accessToken')
      }
    } catch { /* storage may be unavailable */ }
    // Session cookie for <img>/download links, which cannot send the Authorization header.
    document.cookie = token.trim()
      ? `scv_token=${encodeURIComponent(token.trim())}; Path=/; SameSite=Strict${secure()}`
      : 'scv_token=; Path=/; Max-Age=0; SameSite=Strict'
  },
  health: () => request<Health>('/api/status'),
  options: () => request<Options>('/api/options'),
  quiz: (answers: Record<string, string | null>) => request<{ skin_type: string | null; label: string | null }>('/api/quiz/skin-type', json('POST', answers)),

  profiles: () => request<Profile[]>('/api/profiles'),
  createProfile: (input: ProfileInput) => request<Profile>('/api/profiles', json('POST', input)),
  updateProfile: (id: string, input: ProfileInput) => request<Profile>(`/api/profiles/${id}`, json('PUT', input)),
  touchProfile: (id: string) => request<void>(`/api/profiles/${id}/touch`, { method: 'POST' }),
  deleteProfile: (id: string) => request<void>(`/api/profiles/${id}`, { method: 'DELETE' }),

  analyze: ({ profileId, files, provider, useVlm, secondOpinion, hfModel, providerKey }: AnalyzeOptions) => {
    const form = new FormData()
    files.forEach((file) => form.append('files', file))
    form.append('profile_id', profileId)
    form.append('provider', provider)
    form.append('use_vlm', String(useVlm))
    form.append('second_opinion', String(secondOpinion))
    if (provider === 'Hugging Face' && hfModel) form.append('hf_model', hfModel)
    return request<Analysis>('/api/analyses', { method: 'POST', body: form, headers: keyHeader(providerKey) })
  },
  routine: (analysisId: string, profileId: string) => request<Routine>(`/api/analyses/${analysisId}/routine?profile_id=${profileId}`),
  products: (analysisId: string, profileId: string) =>
    request<{ sections: ProductSection[]; catalog_errors: string[] }>(`/api/analyses/${analysisId}/products?profile_id=${profileId}`),
  reportUrl: (analysisId: string, profileId: string, extension: 'pdf' | 'txt' | 'json') =>
    DEMO ? asset('demo/report.pdf') : `/api/analyses/${analysisId}/report.${extension}?profile_id=${encodeURIComponent(profileId)}`,
  save: (analysisId: string, profileId: string, note: string, keepThumbnail: boolean) =>
    request<{ saved: boolean }>(`/api/analyses/${analysisId}/save`, json('POST', { profile_id: profileId, note, keep_thumbnail: keepThumbnail })),

  history: (profileId: string) => request<HistoryResponse>(`/api/profiles/${profileId}/history`),
  compare: (profileId: string, before: string, after: string) =>
    request<Comparison>(`/api/profiles/${profileId}/compare?before=${before}&after=${after}`),
  journal: (profileId: string) => request<JournalResponse>(`/api/profiles/${profileId}/journal`),
  saveJournal: (profileId: string, entry: JournalEntry) =>
    request<JournalResponse>(`/api/profiles/${profileId}/journal/${entry.date}`, json('PUT', { ...entry, date: undefined })),
  deleteJournal: (profileId: string, day: string) => request<JournalResponse>(`/api/profiles/${profileId}/journal/${day}`, { method: 'DELETE' }),
  shelf: (profileId: string) => request<ShelfResponse>(`/api/profiles/${profileId}/shelf`),
  addShelfItem: (profileId: string, item: ShelfItemInput) => request<ShelfResponse>(`/api/profiles/${profileId}/shelf`, json('POST', item)),
  updateShelfItem: (profileId: string, id: string, item: ShelfItemInput) => request<ShelfResponse>(`/api/profiles/${profileId}/shelf/${id}`, json('PUT', item)),
  deleteShelfItem: (profileId: string, id: string) => request<ShelfResponse>(`/api/profiles/${profileId}/shelf/${id}`, { method: 'DELETE' }),
  weatherSearch: (query: string) => request<Place[]>(`/api/weather/search?q=${encodeURIComponent(query)}`),
  weather: (lat: number, lon: number, profileId?: string) =>
    request<WeatherToday>(`/api/weather?lat=${lat}&lon=${lon}${profileId ? `&profile_id=${profileId}` : ''}`),
  coachSuggestions: () => request<string[]>('/api/coach/suggestions'),
  coach: (profileId: string, provider: string, messages: ChatMessage[], weather: { uv_max: number | null; temperature: number | null; humidity: number | null } | null, providerKey?: string) =>
    request<CoachReply>('/api/coach', { ...json('POST', { profile_id: profileId, provider, messages, weather }), headers: { 'Content-Type': 'application/json', ...keyHeader(providerKey) } }),
  compareMap: (profileId: string, before: string, after: string) =>
    request<ChangeMap>(`/api/profiles/${profileId}/compare/map?before=${before}&after=${after}`),
  captureCheck: (frame: Blob, target: 'front' | 'side', avoidSign: number, signal?: AbortSignal) => {
    const form = new FormData()
    form.append('frame', frame, 'frame.jpg')
    form.append('target', target)
    form.append('avoid_sign', String(avoidSign))
    return request<CaptureCheck>('/api/capture/check', { method: 'POST', body: form, signal })
  },
  deleteRecord: (recordId: string) => request<void>(`/api/history/${recordId}`, { method: 'DELETE' }),
  deleteHistory: (profileId: string) => request<{ deleted: number }>(`/api/profiles/${profileId}/history`, { method: 'DELETE' }),
  addEvent: (profileId: string, kind: string, date: string, note: string) =>
    request<{ id: string }>(`/api/profiles/${profileId}/events`, json('POST', { kind, date, note })),
  deleteEvent: (eventId: string) => request<void>(`/api/events/${eventId}`, { method: 'DELETE' }),
  exportUrl: (profileId: string, extension: 'json' | 'csv') => (DEMO ? asset(`demo/export.${extension}`) : `/api/profiles/${profileId}/history/export.${extension}`),

  checkProduct: (profileId: string, inciText: string, analysisId?: string) =>
    request<ProductVerdict>('/api/products/check', json('POST', { profile_id: profileId, inci_text: inciText, analysis_id: analysisId ?? null })),
  readLabel: (file: File, provider: string, providerKey?: string) => {
    const form = new FormData()
    form.append('file', file)
    form.append('provider', provider)
    return request<{ ingredients_text: string; product_name: string }>('/api/products/read-label', { method: 'POST', body: form, headers: keyHeader(providerKey) })
  },
}
