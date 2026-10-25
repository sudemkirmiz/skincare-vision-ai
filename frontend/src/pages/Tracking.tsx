// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Sudem Kırmız
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { useState } from 'react'
import { Alert, Calendar, CheckCircle, Info, Lightbulb, Moon, Sun, TrendUp } from '../icons'
import { ApiError, api } from '../lib/api'
import { useAppState } from '../lib/app-state'
import type { Insight, JournalEntry, JournalResponse } from '../lib/types'
import { Button, Card, Notice, Progress, SectionHeader, Spinner } from '../components/ui'
import { WeatherCard } from '../components/WeatherCard'
import { TodayCard } from '../components/TodayCard'

const EDIT_DAYS = 7
const CALENDAR_DAYS = 28
const WEEKDAYS = ['Paz', 'Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt']
// Skin feel 1-5 on a light status scale; the number is always printed too, so colour is never the only signal.
const FEEL_BG: Record<number, string> = { 1: 'bg-feel-1', 2: 'bg-feel-2', 3: 'bg-feel-3', 4: 'bg-feel-4', 5: 'bg-feel-5' }

const pad = (n: number) => String(n).padStart(2, '0')
const iso = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
function daysAgo(n: number) {
  const d = new Date()
  d.setHours(12, 0, 0, 0)
  d.setDate(d.getDate() - n)
  return d
}
const blank = (date: string): JournalEntry => ({ date, am_done: null, pm_done: null, skin_feel: null, triggers: [], symptoms: [], actives: [], note: '' })

function dayLabel(date: string) {
  const today = iso(daysAgo(0))
  if (date === today) return 'Bugün'
  if (date === iso(daysAgo(1))) return 'Dün'
  const d = new Date(`${date}T12:00:00`)
  return `${WEEKDAYS[d.getDay()]} ${d.getDate()}`
}

function ChipGroup({ options, value, onChange }: { options: [string, string][]; value: string[]; onChange: (next: string[]) => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map(([key, label]) => {
        const active = value.includes(key)
        return (
          <button key={key} type="button" aria-pressed={active} onClick={() => onChange(active ? value.filter((item) => item !== key) : [...value, key])}
            className={clsx('rounded-full border px-3 py-1.5 text-sm transition', active ? 'border-brand-500 bg-brand-500 text-white' : 'border-line-strong bg-surface text-ink hover:border-brand-400')}>
            {label}
          </button>
        )
      })}
    </div>
  )
}

function DoneToggle({ icon, label, value, onChange }: { icon: React.ReactNode; label: string; value: boolean | null; onChange: (value: boolean | null) => void }) {
  return (
    <div className="rounded-xl border border-line bg-surface-soft/60 p-3">
      <p className="mb-2.5 flex items-center gap-2 text-sm font-medium"><span className="text-brand-600">{icon}</span>{label}</p>
      <div className="grid grid-cols-2 gap-1.5" role="group" aria-label={label}>
        {([[true, 'Yaptım'], [false, 'Atladım']] as const).map(([option, text]) => (
          <button key={text} type="button" aria-pressed={value === option} onClick={() => onChange(value === option ? null : option)}
            className={clsx('rounded-lg border px-2 py-1.5 text-sm transition', value === option
              ? option ? 'border-brand-500 bg-brand-500 text-white' : 'border-ink/60 bg-ink/80 text-canvas'
              : 'border-line-strong bg-surface hover:border-brand-400')}>
            {text}
          </button>
        ))}
      </div>
    </div>
  )
}

function CheckIn({ data, day, setDay }: { data: JournalResponse; day: string; setDay: (day: string) => void }) {
  const { options, profile } = useAppState()
  const queryClient = useQueryClient()
  const stored = data.entries.find((entry) => entry.date === day)
  const [draft, setDraft] = useState<JournalEntry>(stored ?? blank(day))
  const [saved, setSaved] = useState(false)
  const set = (patch: Partial<JournalEntry>) => { setDraft((current) => ({ ...current, ...patch })); setSaved(false) }

  const save = useMutation({
    mutationFn: () => api.saveJournal(profile!.id, draft),
    onSuccess: (result) => { queryClient.setQueryData(['journal', profile!.id], result); setSaved(true) },
  })
  const remove = useMutation({
    mutationFn: () => api.deleteJournal(profile!.id, day),
    onSuccess: (result) => { queryClient.setQueryData(['journal', profile!.id], result); setDraft(blank(day)) },
  })

  const triggers = Object.entries(options.journal.triggers).filter(([key]) => profile?.gender === 'female' || !options.journal.female_only.includes(key))
  // Evening actives: the saved routine's actives plus anything logged before.
  const activeOptions = [...new Set([...data.routine_actives, ...data.entries.flatMap((entry) => entry.actives), ...draft.actives])]

  return (
    <Card className="p-6 sm:p-7">
      <SectionHeader icon={<Calendar />} title="Günlük kayıt" subtitle="Bir dakikanızı alır. Düzenli kayıt, cildinizi neyin etkilediğini görmenizi sağlar." />
      <div className="no-scrollbar -mx-1 mb-6 flex gap-1.5 overflow-x-auto px-1 pb-1" role="tablist" aria-label="Gün">
        {Array.from({ length: EDIT_DAYS }, (_, index) => iso(daysAgo(index))).map((date) => {
          const logged = data.entries.some((entry) => entry.date === date)
          return (
            <button key={date} type="button" role="tab" aria-selected={date === day} onClick={() => setDay(date)}
              className={clsx('flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition', date === day ? 'border-ink bg-ink text-canvas' : 'border-line-strong bg-surface hover:border-ink/40')}>
              {logged ? <CheckCircle size={14} className={date === day ? 'text-brand-300' : 'text-brand-600'} /> : null}{dayLabel(date)}
            </button>
          )
        })}
      </div>

      <div className="space-y-6">
        <div className="grid gap-3 sm:grid-cols-2">
          <DoneToggle icon={<Sun size={18} />} label="Sabah rutini" value={draft.am_done} onChange={(am_done) => set({ am_done })} />
          <DoneToggle icon={<Moon size={18} />} label="Akşam rutini" value={draft.pm_done} onChange={(pm_done) => set({ pm_done })} />
        </div>
        {draft.pm_done && activeOptions.length ? (
          <div>
            <p className="label mb-2">Bu akşam kullandığınız aktifler</p>
            <ChipGroup options={activeOptions.map((active) => [active, active])} value={draft.actives} onChange={(actives) => set({ actives })} />
          </div>
        ) : null}

        <div>
          <p className="label mb-2">Cildiniz {day === iso(daysAgo(0)) ? 'bugün' : 'o gün'} nasıldı?</p>
          <div className="grid grid-cols-5 gap-1.5" role="radiogroup" aria-label="Cilt hissi">
            {Object.entries(options.journal.skin_feel).map(([value, label]) => {
              const score = Number(value)
              const active = draft.skin_feel === score
              return (
                <button key={value} type="button" role="radio" aria-checked={active} onClick={() => set({ skin_feel: active ? null : score })}
                  className={clsx('flex flex-col items-center rounded-xl border px-1 py-2.5 transition', active ? 'border-brand-500 bg-brand-50 ring-2 ring-brand-200' : 'border-line bg-surface hover:border-brand-300')}>
                  <span className={clsx('grid size-8 place-items-center rounded-full text-sm font-semibold', FEEL_BG[score])}>{score}</span>
                  <span className="mt-1.5 text-center text-[11px] leading-tight text-ink-soft">{label}</span>
                </button>
              )
            })}
          </div>
        </div>

        <div>
          <p className="label mb-2">{day === iso(daysAgo(0)) ? 'Bugün' : 'O gün'} neler oldu?</p>
          <ChipGroup options={triggers} value={draft.triggers} onChange={(next) => set({ triggers: next })} />
        </div>
        <div>
          <p className="label mb-2">Fark ettiğiniz belirtiler</p>
          <ChipGroup options={Object.entries(options.journal.symptoms)} value={draft.symptoms} onChange={(symptoms) => set({ symptoms })} />
        </div>
        <input className="field" maxLength={200} value={draft.note} onChange={(event) => set({ note: event.target.value })} placeholder="Not (isteğe bağlı), örn. yeni güneş kremine başladım" aria-label="Not" />

        {save.isError ? <Notice tone="error">{save.error instanceof ApiError ? save.error.messages.join(' ') : 'Kaydedilemedi.'}</Notice> : null}
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={() => save.mutate()} disabled={save.isPending}>{save.isPending ? 'Kaydediliyor…' : 'Kaydet'}</Button>
          {saved ? <span className="flex items-center gap-1.5 text-sm text-brand-700"><CheckCircle size={16} /> Kaydedildi</span> : null}
          {stored ? <button type="button" className="ml-auto text-sm text-muted underline-offset-2 hover:text-danger hover:underline" onClick={() => remove.mutate()}>Bu günün kaydını sil</button> : null}
        </div>
      </div>
    </Card>
  )
}

function Stats({ data }: { data: JournalResponse }) {
  const { streak, adherence, feel } = data.summary
  const tiles: [string, string, string][] = [
    ['Kayıt serisi', `${streak}`, streak === 1 ? 'gün' : 'gün üst üste kayıt'],
    ['Sabah rutini', adherence.am_done === null ? '–' : `%${adherence.am_done}`, `son ${adherence.days} günde`],
    ['Akşam rutini', adherence.pm_done === null ? '–' : `%${adherence.pm_done}`, `son ${adherence.days} günde`],
    ['Cilt hissi', feel ? `${feel.this_week}` : '–', feel?.change ? `geçen haftaya göre ${feel.change > 0 ? '+' : ''}${feel.change}` : 'bu hafta, 5 üzerinden'],
  ]
  return (
    <div className="grid grid-cols-2 gap-3">
      {tiles.map(([label, value, note]) => (
        <Card key={label} className="p-4">
          <p className="label">{label}</p>
          <p className="mt-2 font-display text-3xl leading-none tabular-nums">{value}</p>
          <p className="mt-1.5 text-xs text-muted">{note}</p>
        </Card>
      ))}
    </div>
  )
}

function MonthGrid({ data, day, setDay }: { data: JournalResponse; day: string; setDay: (day: string) => void }) {
  const byDate = Object.fromEntries(data.entries.map((entry) => [entry.date, entry]))
  // Start on a Monday so columns are weekdays.
  const first = daysAgo(CALENDAR_DAYS - 1)
  const offset = (first.getDay() + 6) % 7
  const cells = Array.from({ length: offset + CALENDAR_DAYS }, (_, index) => (index < offset ? null : iso(daysAgo(CALENDAR_DAYS - 1 - (index - offset)))))
  const editable = new Set(Array.from({ length: EDIT_DAYS }, (_, index) => iso(daysAgo(index))))
  return (
    <Card>
      <SectionHeader icon={<TrendUp />} title="Son 4 hafta" />
      <div className="grid grid-cols-7 gap-1.5 text-center">
        {['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz'].map((name) => <span key={name} className="text-[11px] text-muted">{name}</span>)}
        {cells.map((date, index) => {
          if (!date) return <span key={`gap-${index}`} />
          const entry = byDate[date]
          const label = `${dayLabel(date)}: ${entry ? `cilt hissi ${entry.skin_feel ?? '–'}, sabah ${entry.am_done ? 'yapıldı' : 'yok'}, akşam ${entry.pm_done ? 'yapıldı' : 'yok'}` : 'kayıt yok'}`
          return (
            <button key={date} type="button" title={label} aria-label={label} disabled={!editable.has(date)} onClick={() => setDay(date)}
              className={clsx('relative aspect-square rounded-lg border text-xs transition disabled:cursor-default',
                entry?.skin_feel ? FEEL_BG[entry.skin_feel] : 'bg-surface-soft',
                date === day ? 'border-ink' : 'border-transparent', editable.has(date) && 'hover:border-ink/40')}>
              <span className="absolute top-1 left-1.5 text-[10px] text-ink-soft">{Number(date.slice(8))}</span>
              {entry?.skin_feel ? <span className="font-semibold">{entry.skin_feel}</span> : null}
              <span className="absolute inset-x-0 bottom-1 flex justify-center gap-0.5">
                {entry?.am_done ? <span className="size-1.5 rounded-full bg-[#eda100]" /> : null}
                {entry?.pm_done ? <span className="size-1.5 rounded-full bg-[#2a78d6]" /> : null}
              </span>
            </button>
          )
        })}
      </div>
      <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1.5 text-[11px] text-muted">
        <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-[#eda100]" />Sabah rutini</span>
        <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-[#2a78d6]" />Akşam rutini</span>
        <span>Kutudaki sayı: cilt hissi (1 çok kötü – 5 çok iyi)</span>
      </div>
    </Card>
  )
}

function InsightCard({ insight }: { insight: Insight }) {
  const good = insight.tone === 'good'
  return (
    <li className="flex gap-3 border-t border-line py-4 first:border-t-0 first:pt-0">
      <span className={clsx('mt-0.5 shrink-0', good ? 'text-good' : insight.tone === 'warn' ? 'text-mid' : 'text-brand-600')}>
        {good ? <CheckCircle size={20} /> : insight.tone === 'warn' ? <Alert size={20} /> : <Info size={20} />}
      </span>
      <div>
        <p className="font-medium">{insight.title}</p>
        <p className="mt-1 text-sm leading-relaxed text-ink-soft">{insight.text}</p>
        {insight.evidence.without_days ? <p className="mt-1.5 text-xs text-muted">Dayanak: {insight.evidence.with_days} gün ile {insight.evidence.without_days} gün karşılaştırıldı.</p> : null}
      </div>
    </li>
  )
}

function Insights({ data }: { data: JournalResponse }) {
  const { insights, needed_days: needed, logged_days: logged, disclaimer } = data.summary
  return (
    <Card>
      <SectionHeader icon={<Lightbulb />} title="Size özel içgörüler" subtitle="Kayıtlarınızdaki günler karşılaştırılarak bulunur." />
      {needed > 0 ? (
        <div className="space-y-3">
          <Progress value={logged / (logged + needed)} label={`İçgörüler için ${logged + needed} günlük kayıt gerekiyor`} />
          <p className="text-sm text-muted">{needed} gün daha kayıt eklediğinizde, uyku, stres veya kullandığınız aktiflerle cildiniz arasındaki ilişkileri burada göstereceğiz.</p>
        </div>
      ) : insights.length ? (
        <ul>{insights.map((insight) => <InsightCard key={`${insight.kind}-${insight.key}-${insight.title}`} insight={insight} />)}</ul>
      ) : (
        <p className="text-sm text-muted">Şimdilik belirgin bir ilişki görünmüyor. Kayıt eklemeye devam edin; tetikleyicileri işaretlediğiniz günler arttıkça sonuçlar netleşir.</p>
      )}
      <p className="mt-5 text-xs leading-relaxed text-muted">{disclaimer}</p>
    </Card>
  )
}

export function TrackingPage() {
  const { profile } = useAppState()
  const [day, setDay] = useState(() => iso(daysAgo(0)))
  const journal = useQuery({ queryKey: ['journal', profile?.id], queryFn: () => api.journal(profile!.id), enabled: !!profile })
  if (!profile) return null
  return (
    <div className="space-y-8">
      <div>
        <p className="eyebrow">Günlük takip</p>
        <h1 className="mt-3 text-[34px] leading-tight font-normal sm:text-[42px]">{profile.display_name}, cildiniz <em className="text-brand-600">bugün</em> nasıl?</h1>
        <p className="mt-3 max-w-2xl text-base leading-relaxed text-ink-soft">Rutininizi ve gününüzü kısaca işaretleyin. Birkaç hafta sonra hangi alışkanlıkların cildinizi etkilediğini birlikte görelim.</p>
      </div>
      {journal.isPending ? <Spinner label="Kayıtlar yükleniyor…" /> : null}
      {journal.isError ? <Notice tone="error">Kayıtlar yüklenemedi.</Notice> : null}
      {journal.data ? (
        <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:items-start">
          <CheckIn key={day} data={journal.data} day={day} setDay={setDay} />
          <div className="space-y-6">
            <TodayCard quickTick={false} />
            <Stats data={journal.data} />
            <WeatherCard />
            <MonthGrid data={journal.data} day={day} setDay={setDay} />
          </div>
          <div className="lg:col-span-2"><Insights data={journal.data} /></div>
        </div>
      ) : null}
    </div>
  )
}
