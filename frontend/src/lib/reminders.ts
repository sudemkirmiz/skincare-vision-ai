// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Sudem Kırmız
import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { asset } from './demo'
import type { JournalResponse } from './types'

/*
 * Routine reminders without a push server: the open app (tab or installed PWA, even in the background)
 * checks the clock every half minute and shows a local notification at the chosen time, unless the
 * routine is already ticked for today. Nothing leaves the device.
 */
export type Slot = 'am' | 'pm'
export interface ReminderSettings {
  enabled: boolean
  am: string
  pm: string
}

const KEY = 'scv.reminders'
const FIRED_KEY = 'scv.reminders.fired'
const DEFAULTS: ReminderSettings = { enabled: false, am: '08:30', pm: '21:30' }
const CHECK_MS = 30_000
const LATE_MS = 3 * 60 * 60 * 1000 // a reminder more than 3 h late (laptop was asleep) is skipped, not shown at midnight
const TEXT: Record<Slot, { title: string; body: (streak: number) => string }> = {
  am: { title: 'Sabah rutininizin zamanı', body: (streak) => (streak ? `${streak} günlük serinizi sürdürmek için güne rutininizle başlayın.` : 'Temizleme, nemlendirme ve güneş koruyucu: birkaç dakikanızı alır.') },
  pm: { title: 'Akşam rutininizin zamanı', body: (streak) => (streak ? `Bugünü işaretleyin, ${streak} günlük seriniz devam etsin.` : 'Makyajı ve günün kirini temizleyip akşam bakımınızı yapın.') },
}

export const notificationsSupported = () => typeof window !== 'undefined' && 'Notification' in window

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? { ...fallback, ...JSON.parse(raw) } : fallback
  } catch {
    return fallback
  }
}

function write(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* ignore */
  }
}

const pad = (n: number) => String(n).padStart(2, '0')
export const today = (d = new Date()) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`

function at(time: string, now: Date) {
  const [hours, minutes] = time.split(':').map(Number)
  const slot = new Date(now)
  slot.setHours(hours || 0, minutes || 0, 0, 0)
  return slot
}

/** Which reminders are due right now; pure so it can be tested without timers or notifications. */
export function dueSlots(settings: ReminderSettings, now: Date, fired: { date: string; slots: Slot[] }, done: Record<Slot, boolean>): Slot[] {
  if (!settings.enabled) return []
  const firedToday = fired.date === today(now) ? fired.slots : []
  return (['am', 'pm'] as const).filter((slot) => {
    const elapsed = now.getTime() - at(settings[slot], now).getTime()
    return elapsed >= 0 && elapsed < LATE_MS && !firedToday.includes(slot) && !done[slot]
  })
}

async function show(slot: Slot, streak: number) {
  const { title, body } = TEXT[slot]
  const options: NotificationOptions = { body: body(streak), icon: asset('icons/icon-192.png'), badge: asset('icons/maskable-192.png'), tag: `scv-${slot}`, data: { url: asset('takip') } }
  // Through the service worker when installed (works with the window in the background), plain otherwise.
  const registration = 'serviceWorker' in navigator ? await navigator.serviceWorker.getRegistration() : undefined
  if (registration) await registration.showNotification(title, options)
  else new Notification(title, options).onclick = () => { window.focus(); window.location.assign(asset('takip')) }
}

export function useReminderSettings() {
  const [settings, setState] = useState<ReminderSettings>(() => read(KEY, DEFAULTS))
  const [permission, setPermission] = useState<NotificationPermission | 'unsupported'>(() => (notificationsSupported() ? Notification.permission : 'unsupported'))

  const update = useCallback((patch: Partial<ReminderSettings>) => {
    setState((current) => {
      const next = { ...current, ...patch }
      write(KEY, next)
      return next
    })
  }, [])

  /** Turning reminders on asks for permission first; a refusal leaves them off. */
  const enable = useCallback(async () => {
    if (!notificationsSupported()) return
    const result = Notification.permission === 'default' ? await Notification.requestPermission() : Notification.permission
    setPermission(result)
    update({ enabled: result === 'granted' })
  }, [update])

  return { settings, update, enable, permission }
}

/** Mounted once in the layout: fires due reminders for the active profile. */
export function useReminderScheduler(profileId: string | undefined) {
  const queryClient = useQueryClient()
  useEffect(() => {
    if (!profileId || !notificationsSupported()) return
    let busy = false
    const tick = async () => {
      const settings = read(KEY, DEFAULTS)
      if (busy || !settings.enabled || Notification.permission !== 'granted') return
      const now = new Date()
      const fired = read(FIRED_KEY, { date: '', slots: [] as Slot[] })
      if (!dueSlots(settings, now, fired, { am: false, pm: false }).length) return
      busy = true
      try {
        // Only now ask the server whether today's routine is already ticked.
        const journal = await queryClient.fetchQuery<JournalResponse>({ queryKey: ['journal', profileId], queryFn: () => api.journal(profileId), staleTime: 60_000 })
        const entry = journal.entries?.find((item) => item.date === today(now))
        const due = dueSlots(settings, now, fired, { am: entry?.am_done === true, pm: entry?.pm_done === true })
        const todayFired = fired.date === today(now) ? fired.slots : []
        for (const slot of due) await show(slot, journal.summary?.routine?.current ?? 0)
        // Done slots count as handled too, so the server is not asked again every half minute.
        const handled = (['am', 'pm'] as const).filter((slot) => todayFired.includes(slot) || due.includes(slot) || (slot === 'am' ? entry?.am_done : entry?.pm_done) === true)
        write(FIRED_KEY, { date: today(now), slots: handled })
      } catch {
        /* offline or server down: try again on the next tick */
      } finally {
        busy = false
      }
    }
    void tick()
    const timer = window.setInterval(() => void tick(), CHECK_MS)
    return () => window.clearInterval(timer)
  }, [profileId, queryClient])
}
