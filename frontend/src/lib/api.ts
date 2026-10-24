import type { Analysis, CaptureCheck, ChangeMap, Comparison, Health, HistoryResponse, JournalEntry, JournalResponse, ChatMessage, CoachReply, Place, ShelfItemInput, ShelfResponse, WeatherToday, Options, Profile, ProfileInput, ProductSection, ProductVerdict, Routine } from './types'

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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
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
  health: () => request<Health>('/api/health'),
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
    `/api/analyses/${analysisId}/report.${extension}?profile_id=${encodeURIComponent(profileId)}`,
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
  exportUrl: (profileId: string, extension: 'json' | 'csv') => `/api/profiles/${profileId}/history/export.${extension}`,

  checkProduct: (profileId: string, inciText: string, analysisId?: string) =>
    request<ProductVerdict>('/api/products/check', json('POST', { profile_id: profileId, inci_text: inciText, analysis_id: analysisId ?? null })),
  readLabel: (file: File, provider: string, providerKey?: string) => {
    const form = new FormData()
    form.append('file', file)
    form.append('provider', provider)
    return request<{ ingredients_text: string; product_name: string }>('/api/products/read-label', { method: 'POST', body: form, headers: keyHeader(providerKey) })
  },
}
