// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Sudem Kırmız
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Bell, CheckCircle, Flame, Moon, Sun } from '../icons'
import { api } from '../lib/api'
import { useAppState } from '../lib/app-state'
import { today, useReminderSettings, type Slot } from '../lib/reminders'
import type { JournalEntry, JournalResponse, RoutineStreak } from '../lib/types'
import { Notice, Toggle } from './ui'

const MILESTONES = [3, 7, 14, 30, 60, 100]
const WEEKDAY = ['Pz', 'Pt', 'Sa', 'Ça', 'Pe', 'Cu', 'Ct']
const blank = (date: string): JournalEntry => ({ date, am_done: null, pm_done: null, skin_feel: null, triggers: [], symptoms: [], actives: [], note: '' })

function WeekStrip({ week }: { week: RoutineStreak['week'] }) {
  return (
    <ol className="grid grid-cols-7 gap-1.5" aria-label="Son 7 gün">
      {week.map((day, index) => {
        const weekday = WEEKDAY[new Date(`${day.date}T12:00:00`).getDay()]
        const label = `${index === 6 ? 'Bugün' : weekday}: sabah ${day.am ? 'yapıldı' : 'yok'}, akşam ${day.pm ? 'yapıldı' : 'yok'}`
        return (
          <li key={day.date} className="flex flex-col items-center gap-1" title={label} aria-label={label}>
            {/* Two halves of a pill: top = morning, bottom = evening; empty halves stay outlined. */}
            <span className={clsx('flex h-9 w-full max-w-7 flex-col overflow-hidden rounded-full border', index === 6 ? 'border-brand-500' : 'border-line-strong')}>
              <span className={clsx('flex-1', day.am && 'bg-brand-300')} />
              <span className={clsx('flex-1', day.pm && 'bg-brand-500')} />
            </span>
            <span className={clsx('text-[10px]', index === 6 ? 'font-semibold text-ink' : 'text-muted')}>{index === 6 ? 'Bugün' : weekday}</span>
          </li>
        )
      })}
    </ol>
  )
}

function Milestones({ best }: { best: number }) {
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Seri rozetleri">
      {MILESTONES.map((step) => {
        const earned = best >= step
        return (
          <li key={step} title={earned ? `${step} günlük seri rozeti kazanıldı` : `${step} günlük seriye ulaşınca açılır`}
            className={clsx('flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold tabular-nums',
              earned ? 'border-brand-300 bg-brand-50 text-brand-700' : 'border-dashed border-line-strong text-muted')}>
            <Flame size={12} className={earned ? 'text-brand-500' : 'opacity-50'} />{step}
          </li>
        )
      })}
    </ul>
  )
}

function ReminderPanel() {
  const { settings, update, enable, permission } = useReminderSettings()
  if (permission === 'unsupported') return <p className="text-xs text-muted">Bu tarayıcı bildirimleri desteklemiyor.</p>
  return (
    <div className="space-y-3 rounded-xl border border-line bg-surface-soft/60 p-3">
      <Toggle checked={settings.enabled && permission === 'granted'} disabled={permission === 'denied'}
        onChange={(on) => (on ? void enable() : update({ enabled: false }))}
        label="Rutin hatırlatıcısı" hint="Rutini o gün işaretlediyseniz hatırlatma gelmez." />
      {permission === 'denied' ? <Notice tone="warn">Bildirim izni kapalı. Tarayıcının site ayarlarından bu siteye bildirim izni verip yeniden deneyin.</Notice> : null}
      <div className="grid grid-cols-2 gap-2">
        {([['am', 'Sabah', Sun], ['pm', 'Akşam', Moon]] as const).map(([slot, label, Icon]) => (
          <label key={slot} className="block">
            <span className="label flex items-center gap-1"><Icon size={14} />{label}</span>
            <input type="time" className="field mt-1 py-1.5" value={settings[slot as Slot]} onChange={(event) => update({ [slot]: event.target.value })} />
          </label>
        ))}
      </div>
      <p className="text-[11px] leading-relaxed text-muted">Hatırlatmalar cihazınızda oluşturulur; uygulama bir sekmede açıkken ya da ana ekrana eklenmiş uygulama arka planda çalışırken gelir.</p>
    </div>
  )
}

/** Home-screen habit card: today's routine in one tap, the streak and its badges, reminders. */
export function TodayCard({ quickTick = true }: { quickTick?: boolean }) {
  const { profile } = useAppState()
  const queryClient = useQueryClient()
  const [reminders, setReminders] = useState(false)
  const journal = useQuery({ queryKey: ['journal', profile?.id], queryFn: () => api.journal(profile!.id), enabled: !!profile })
  const save = useMutation({
    mutationFn: (entry: JournalEntry) => api.saveJournal(profile!.id, entry),
    onSuccess: (result) => queryClient.setQueryData<JournalResponse>(['journal', profile!.id], result),
  })
  // A habit card is never worth breaking the home page: render nothing when the journal is unavailable.
  const streak = journal.data?.summary?.routine
  if (!profile || !journal.data?.entries || !streak) return null
  const date = today()
  const entry = journal.data.entries.find((item) => item.date === date) ?? blank(date)
  const tick = (slot: Slot) => save.mutate({ ...entry, [`${slot}_done`]: entry[`${slot}_done`] === true ? null : true })
  const toNext = streak.next ? streak.next - streak.current : 0
  const justReached = streak.today_done && streak.reached > 0 && streak.current === streak.reached

  return (
    <section className="card p-5" aria-label="Bugünkü rutin">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className={clsx('grid size-12 place-items-center rounded-2xl', streak.current ? 'bg-gradient-to-br from-brand-400 to-brand-600 text-white dark:from-[#4caf50] dark:to-[#2e7d32]' : 'border border-line bg-surface-soft text-muted')}>
            <Flame size={26} />
          </span>
          <div>
            <p className="font-display text-[28px] leading-none tabular-nums">{streak.current}<span className="ml-1.5 font-sans text-sm text-muted">gün seri</span></p>
            <p className="mt-1 text-xs text-muted">
              {streak.next ? `${streak.next} günlük rozete ${toNext} gün` : 'Tüm rozetler sizde'}{streak.best > streak.current ? ` · en iyi ${streak.best}` : ''}
            </p>
          </div>
        </div>
        <button type="button" onClick={() => setReminders((open) => !open)} aria-expanded={reminders} aria-label="Hatırlatıcı ayarları" title="Hatırlatıcı ayarları"
          className={clsx('grid size-9 place-items-center rounded-full transition hover:bg-surface-soft', reminders ? 'text-brand-600' : 'text-muted hover:text-ink')}>
          <Bell size={20} />
        </button>
      </div>

      {justReached ? <div className="mt-4"><Notice tone="success" icon={<CheckCircle size={18} />}>Tebrikler! {streak.reached} günlük seri rozetini kazandınız. Düzenli bakım, sonuçları görmenin en kısa yolu.</Notice></div> : null}
      {!streak.today_done && streak.current > 0 ? <p className="mt-4 text-sm text-ink-soft">Serinizi korumak için bugünkü rutininizi işaretlemeyi unutmayın.</p> : null}

      {quickTick ? (
        <div className="mt-4 grid grid-cols-2 gap-2">
          {([['am', 'Sabah', Sun], ['pm', 'Akşam', Moon]] as const).map(([slot, label, Icon]) => {
            const done = entry[`${slot}_done`] === true
            return (
              <button key={slot} type="button" aria-pressed={done} disabled={save.isPending} onClick={() => tick(slot)}
                className={clsx('flex items-center justify-center gap-2 rounded-xl border px-3 py-2.5 text-sm font-medium transition disabled:opacity-60',
                  done ? 'border-brand-500 bg-brand-500 text-white' : 'border-line-strong bg-surface hover:border-brand-400')}>
                {done ? <CheckCircle size={18} /> : <Icon size={18} />}{label} {done ? 'tamam' : 'rutini'}
              </button>
            )
          })}
        </div>
      ) : null}
      {save.isError ? <p className="mt-2 text-xs text-danger">Kaydedilemedi; bağlantınızı kontrol edin.</p> : null}

      <div className="mt-5 space-y-4">
        <WeekStrip week={streak.week} />
        <Milestones best={streak.best} />
        {reminders ? <ReminderPanel /> : null}
      </div>
      {quickTick ? <Link to="/takip" className="mt-4 inline-block text-sm font-medium text-brand-700 underline-offset-2 hover:underline">Cilt hissini ve tetikleyicileri kaydedin →</Link> : null}
    </section>
  )
}
