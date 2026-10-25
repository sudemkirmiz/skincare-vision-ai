// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Sudem Kırmız
import { describe, expect, it } from 'vitest'
import { ApiError } from '../lib/api'
import type { Analysis, HistoryResponse, JournalResponse, Profile } from '../lib/types'
import { DEMO_MESSAGE, demoRequest } from './handler'

const pad = (n: number) => String(n).padStart(2, '0')
const d = new Date()
const today = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`

describe('demo handler', () => {
  it('serves the recorded profile, analysis and history rebased to today', async () => {
    const [profile] = await demoRequest<Profile[]>('/api/profiles')
    const analysis = await demoRequest<Analysis>('/api/analyses', { method: 'POST' })
    expect(analysis.face_found).toBe(true)
    expect(analysis.created_at.startsWith(today)).toBe(true)
    const history = await demoRequest<HistoryResponse>(`/api/profiles/${profile.id}/history`)
    expect(history.records.at(-1)!.created_at.startsWith(today)).toBe(true)
  }, 10_000)

  it('keeps journal ticks in the browser and recomputes the streak', async () => {
    const [profile] = await demoRequest<Profile[]>('/api/profiles')
    const before = await demoRequest<JournalResponse>(`/api/profiles/${profile.id}/journal`)
    const after = await demoRequest<JournalResponse>(`/api/profiles/${profile.id}/journal/${today}`, {
      method: 'PUT', body: JSON.stringify({ am_done: true, pm_done: null, skin_feel: null, triggers: [], symptoms: [], actives: [], note: '' }),
    })
    expect(after.summary.routine.today_done).toBe(true)
    expect(after.summary.routine.current).toBeGreaterThanOrEqual(before.summary.routine.current)
    expect(after.entries.find((entry) => entry.date === today)?.am_done).toBe(true)
  })

  it('refuses work that needs the real models with a clear message', async () => {
    const [profile] = await demoRequest<Profile[]>('/api/profiles')
    await expect(demoRequest(`/api/profiles/${profile.id}/shelf`, { method: 'POST', body: '{}' })).rejects.toEqual(new ApiError(403, [DEMO_MESSAGE]))
    await expect(demoRequest('/api/products/check', { method: 'POST', body: JSON.stringify({ inci_text: 'Aqua' }) })).rejects.toBeInstanceOf(ApiError)
  })
})
