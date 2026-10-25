// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Sudem Kırmız
/*
 * The demo "backend": answers /api/* in the browser from responses recorded by scripts/build_demo_fixtures.py.
 * Only loaded in the VITE_DEMO build. Nothing is uploaded anywhere; the journal ticks a visitor makes are kept
 * in this browser only. Anything that would need the real models (a new photo, a new product, the coach)
 * answers with a clear "demo" message instead of made-up results.
 */
import { ApiError } from '../lib/api'
import type { Analysis, JournalEntry, JournalResponse, RoutineStreak } from '../lib/types'
import raw from './fixtures.json'

type Fixtures = {
  captured_on: string
  profile_id: string
  get: Record<string, unknown>
  analysis: Analysis
  compare: Record<string, unknown>
  compare_map: Record<string, unknown>
  product_check: { inci: string; verdict: unknown }
  weather?: unknown
}

const DAY = 86_400_000
const JOURNAL_KEY = 'scv.demo.journal'
export const DEMO_MESSAGE = 'Bu işlem canlı demoda kapalı. Kendi fotoğrafınız, ürünleriniz ve tüm özellikler için uygulamayı kendi bilgisayarınızda çalıştırın.'
const MILESTONES = [3, 7, 14, 30, 60, 100]

const pad = (n: number) => String(n).padStart(2, '0')
const iso = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
const noon = (value: string) => new Date(`${value.slice(0, 10)}T12:00:00`)
const daysBetween = (a: string, b: string) => Math.round((+noon(b) - +noon(a)) / DAY)

/** Moves every ISO date in the recorded data forward, so the sample weeks always end today. */
function rebase<T>(value: T, days: number): T {
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(value)) {
    const shifted = new Date(+noon(value) + days * DAY)
    return (iso(shifted) + value.slice(10)) as T
  }
  if (Array.isArray(value)) return value.map((item) => rebase(item, days)) as T
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, rebase(item, days)])) as T
  return value
}

const today = iso(new Date())
const data = rebase(raw as unknown as Fixtures, daysBetween((raw as unknown as Fixtures).captured_on, today))
const pid = data.profile_id
const recordedJournal = data.get[`/api/profiles/${pid}/journal`] as JournalResponse

function readJournal(): JournalEntry[] {
  try {
    const stored = localStorage.getItem(JOURNAL_KEY)
    if (stored) return JSON.parse(stored) as JournalEntry[]
  } catch {
    /* storage blocked: start from the sample */
  }
  return recordedJournal.entries
}

let journal = readJournal()
const saveJournal = () => {
  try {
    localStorage.setItem(JOURNAL_KEY, JSON.stringify(journal))
  } catch {
    /* ignore */
  }
}

// Same rules as src/history/insights.py, for the parts a visitor can change with a tap.
function routineStreak(entries: JournalEntry[]): RoutineStreak {
  const done = new Set(entries.filter((entry) => entry.am_done || entry.pm_done).map((entry) => entry.date))
  const back = (date: string, n: number) => iso(new Date(+noon(date) - n * DAY))
  let cursor = done.has(today) ? today : back(today, 1)
  let current = 0
  while (done.has(cursor)) {
    current += 1
    cursor = back(cursor, 1)
  }
  let best = 0
  let run = 0
  let previous = ''
  for (const date of [...done].sort()) {
    run = previous && daysBetween(previous, date) === 1 ? run + 1 : 1
    best = Math.max(best, run)
    previous = date
  }
  const byDate = Object.fromEntries(entries.map((entry) => [entry.date, entry]))
  const week = Array.from({ length: 7 }, (_, index) => {
    const date = back(today, 6 - index)
    return { date, am: byDate[date]?.am_done === true, pm: byDate[date]?.pm_done === true }
  })
  return {
    current, best, today_done: done.has(today), week,
    reached: Math.max(0, ...MILESTONES.filter((step) => current >= step)),
    next: MILESTONES.find((step) => step > current) ?? null,
  }
}

function journalResponse(): JournalResponse {
  const logged = new Set(journal.map((entry) => entry.date))
  let cursor = logged.has(today) ? today : iso(new Date(+noon(today) - DAY))
  let streak = 0
  while (logged.has(cursor)) {
    streak += 1
    cursor = iso(new Date(+noon(cursor) - DAY))
  }
  const recent = journal.filter((entry) => daysBetween(entry.date, today) < 14)
  const share = (key: 'am_done' | 'pm_done') => {
    const answered = recent.filter((entry) => entry[key] !== null)
    return answered.length ? Math.round((100 * answered.filter((entry) => entry[key]).length) / answered.length) : null
  }
  const summary = recordedJournal.summary
  return {
    entries: [...journal].sort((a, b) => a.date.localeCompare(b.date)),
    routine_actives: recordedJournal.routine_actives,
    summary: {
      ...summary, streak, routine: routineStreak(journal),
      adherence: { days: 14, logged: recent.length, am_done: share('am_done'), pm_done: share('pm_done') },
      logged_days: journal.length, needed_days: Math.max(0, 7 - journal.length),
    },
  }
}

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))
const closed = () => new ApiError(403, [DEMO_MESSAGE])

export async function demoRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? 'GET').toUpperCase()
  const url = new URL(path, 'https://demo.local')
  const route = url.pathname
  await wait(method === 'GET' ? 120 : 250)

  if (method === 'GET') {
    if (route === '/api/status' || route === '/api/health') return data.get['/api/status'] as T
    if (route === '/api/weather') {
      if (data.weather) return data.weather as T
      throw closed()
    }
    if (route.endsWith('/journal')) return journalResponse() as T
    if (route.endsWith('/compare') || route.endsWith('/compare/map')) {
      const before = url.searchParams.get('before') ?? ''
      const after = url.searchParams.get('after') ?? ''
      const table = route.endsWith('/map') ? data.compare_map : data.compare
      const hit = table[`${before}|${after}`] ?? table[`${after}|${before}`]
      if (hit) return hit as T
      throw new ApiError(422, ['Canlı demoda fark haritası yalnızca ilk ve son kayıt için hazırlandı.'])
    }
    // The recorded GETs keep their query string (routine and products are per profile).
    const key = Object.keys(data.get).find((candidate) => candidate === route + url.search || candidate === route || candidate.split('?')[0] === route)
    if (key) return data.get[key] as T
    throw closed()
  }

  if (route === '/api/analyses' && method === 'POST') {
    await wait(2600) // long enough to see the three analysis steps
    return { ...data.analysis, created_at: `${today} ${pad(new Date().getHours())}:${pad(new Date().getMinutes())}` } as T
  }
  if (route.endsWith('/touch')) return undefined as T
  if (route.endsWith('/save')) return { saved: true, record_id: data.analysis.analysis_id } as T
  if (route === '/api/products/check') {
    const body = JSON.parse(String(init?.body ?? '{}')) as { inci_text?: string }
    if (body.inci_text?.trim() === data.product_check.inci) return data.product_check.verdict as T
    throw new ApiError(403, ['Canlı demoda yalnızca örnek içerik listesi kontrol edilebilir. Kendi ürünleriniz için uygulamayı yerelde çalıştırın.'])
  }
  const day = route.match(/\/journal\/(\d{4}-\d{2}-\d{2})$/)?.[1]
  if (day && method === 'PUT') {
    const entry = { ...(JSON.parse(String(init?.body ?? '{}')) as Omit<JournalEntry, 'date'>), date: day }
    journal = [...journal.filter((item) => item.date !== day), entry]
    saveJournal()
    return journalResponse() as T
  }
  if (day && method === 'DELETE') {
    journal = journal.filter((item) => item.date !== day)
    saveJournal()
    return journalResponse() as T
  }
  throw closed()
}
