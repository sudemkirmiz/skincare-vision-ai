import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Calendar, Download, History as HistoryIcon, Plus, StatusGood, StatusMid, StatusPriority, Trash, TrendUp } from '../icons'
import { api } from '../lib/api'
import { useAppState } from '../lib/app-state'
import type { HistoryRecord } from '../lib/types'
import { Button, Card, EmptyState, Notice, SectionHeader, Spinner } from '../components/ui'
import { ChangeMapView } from '../components/ChangeMapView'

// Reference categorical palette, light mode, fixed order (validated for colour-vision deficiency).
const SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4']
const SCORE_KEYS = [['spots', 'Nokta yoğunluğu'], ['redness', 'Kızarıklık dengesi'], ['tone', 'Ton eşitliği'], ['texture', 'Doku pürüzsüzlüğü'], ['shine', 'Parlama kontrolü']] as const
const GRID = '#e8eee8'
// Single-measure charts use the brand ink; the categorical palette is kept for the five sub-scores.
const BRAND = '#3e8e47'
const AXIS = { fontSize: 11, fill: '#68766d' }
// Manual dd.MM: locale data differs between browsers (some render 24/10 for tr-TR).
const pad = (n: number) => String(n).padStart(2, '0')
const day = (value: number | string) => { const d = new Date(value); return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}` }
const localToday = () => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` }
const clock = (value: number) => { const d = new Date(value); return `${pad(d.getHours())}:${pad(d.getMinutes())}` }
const stamp = (value: string) => new Date(value).toLocaleString('tr-TR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
const DIRECTION = {
  better: { icon: <StatusGood size={16} className="text-good" />, word: 'iyileşti' },
  worse: { icon: <StatusPriority size={16} className="text-priority" />, word: 'geriledi' },
  same: { icon: <StatusMid size={16} className="text-mid" />, word: 'benzer' },
  unknown: { icon: null, word: '–' },
} as Record<string, { icon: React.ReactNode; word: string }>

function Charts({ records, events }: { records: HistoryRecord[]; events: { id: string; date: string; kind: string; note: string }[] }) {
  const { options } = useAppState()
  const rows = records.filter((record) => record.overall_score !== null).map((record) => ({
    t: new Date(record.created_at).getTime(),
    overall: record.overall_score,
    // Distinct key: "spots" is also the spot-density *score* below and would overwrite the count.
    spotTotal: record.spot_counts.total ?? null,
    ...Object.fromEntries(SCORE_KEYS.map(([key]) => [key, record.scores[key] ?? null])),
  }))
  rows.sort((a, b) => a.t - b.t)
  // One evenly spaced slot per analysis: a time scale collapses several photos taken on the same day.
  const dayCount: Record<string, number> = {}
  rows.forEach((row) => { dayCount[day(row.t)] = (dayCount[day(row.t)] ?? 0) + 1 })
  const seen: Record<string, number> = {}
  const data = rows.map((row) => {
    const base = dayCount[day(row.t)] > 1 ? `${day(row.t)} ${clock(row.t)}` : day(row.t)
    seen[base] = (seen[base] ?? 0) + 1
    return { ...row, x: seen[base] > 1 ? `${base} (${seen[base]})` : base }
  })
  if (data.length < 2) {
    return <Notice icon={<TrendUp size={18} />}>Trend grafikleri için en az iki kayıtlı analiz gerekiyor. Benzer ışık ve açıyla düzenli fotoğraf çekip kaydedin.</Notice>
  }
  const xAxis = <XAxis dataKey="x" padding={{ left: 24, right: 24 }} tick={AXIS} axisLine={{ stroke: GRID }} tickLine={false} />
  // An event marks the first analysis taken on or after its day (events have a date, not a time).
  const markers = events.flatMap((event) => {
    const start = new Date(event.date).setHours(0, 0, 0, 0)
    const row = data.find((item) => item.t >= start)
    return row ? [{ event, x: row.x }] : []
  }).map(({ event, x }) => (
    <ReferenceLine key={event.id} x={x} stroke="#9aa8a0" strokeDasharray="4 4"
      label={{ value: options.event_kinds[event.kind] ?? event.kind, position: 'insideTopLeft', fill: '#52514e', fontSize: 11 }} />
  ))
  const tooltip = <Tooltip labelFormatter={(_, payload) => (payload?.[0]?.payload ? stamp(new Date(payload[0].payload.t).toISOString()) : '')} contentStyle={{ borderRadius: 14, border: '1px solid #ddebde', fontSize: 12 }} />
  return (
    <div className="space-y-5">
      <Card>
        <SectionHeader icon={<TrendUp />} title="Cilt Skoru zaman içinde" subtitle="Kesikli çizgiler rutin olaylarıdır; noktaların üzerine gelin." />
        <div className="h-56">
          <ResponsiveContainer>
            <LineChart data={data} margin={{ top: 16, right: 36, bottom: 0, left: -18 }}>
              <CartesianGrid vertical={false} stroke={GRID} />{xAxis}
              <YAxis domain={[0, 100]} tick={AXIS} axisLine={false} tickLine={false} />{tooltip}{markers}
              <Line type="monotone" dataKey="overall" name="Genel skor" stroke={BRAND} strokeWidth={2.5} dot={{ r: 4, strokeWidth: 2, fill: '#fff' }} activeDot={{ r: 6 }} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>
      <Card>
        <SectionHeader icon={<TrendUp />} title="Alt skorlar" subtitle="Yüksek = daha iyi." />
        <div className="h-72">
          <ResponsiveContainer>
            <LineChart data={data} margin={{ top: 16, right: 36, bottom: 0, left: -18 }}>
              <CartesianGrid vertical={false} stroke={GRID} />{xAxis}
              <YAxis domain={[0, 100]} tick={AXIS} axisLine={false} tickLine={false} />{tooltip}{markers}
              {/* itemSorter null keeps the validated colour order instead of sorting alphabetically. */}
              <Legend iconType="plainline" itemSorter={null} wrapperStyle={{ fontSize: 12 }} />
              {SCORE_KEYS.map(([key, label], index) => (
                <Line key={key} type="monotone" dataKey={key} name={label} stroke={SERIES[index]} strokeWidth={2} dot={{ r: 3.5, strokeWidth: 2, fill: '#fff' }} connectNulls isAnimationActive={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>
      <Card>
        <SectionHeader icon={<TrendUp />} title="Toplam nokta sayısı" />
        <div className="h-44">
          <ResponsiveContainer>
            <BarChart data={data} margin={{ top: 8, right: 36, bottom: 0, left: -18 }}>
              <CartesianGrid vertical={false} stroke={GRID} />{xAxis}
              <YAxis allowDecimals={false} tick={AXIS} axisLine={false} tickLine={false} />{tooltip}
              <Bar dataKey="spotTotal" name="Toplam nokta" fill={BRAND} radius={[4, 4, 0, 0]} maxBarSize={18} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer font-semibold text-muted">Tablo görünümü</summary>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-muted"><tr><th className="py-1.5 pr-3">Tarih</th><th className="pr-3">Genel</th>{SCORE_KEYS.map(([key, label]) => <th key={key} className="pr-3">{label}</th>)}<th>Nokta</th></tr></thead>
              <tbody>{data.map((row) => (
                <tr key={row.t} className="border-t border-line"><td className="py-1.5 pr-3">{stamp(new Date(row.t).toISOString())}</td><td className="pr-3 font-semibold">{row.overall}</td>
                  {SCORE_KEYS.map(([key]) => <td key={key} className="pr-3">{(row as Record<string, unknown>)[key] as number ?? '–'}</td>)}<td>{row.spotTotal ?? '–'}</td></tr>
              ))}</tbody>
            </table>
          </div>
        </details>
      </Card>
    </div>
  )
}

function Compare({ profileId, records }: { profileId: string; records: HistoryRecord[] }) {
  const [before, setBefore] = useState(records[0]?.id)
  const [after, setAfter] = useState(records[records.length - 1]?.id)
  const comparison = useQuery({ queryKey: ['compare', profileId, before, after], queryFn: () => api.compare(profileId, before!, after!), enabled: !!before && !!after && before !== after })
  const byId = Object.fromEntries(records.map((record) => [record.id, record]))
  const option = (record: HistoryRecord) => `${stamp(record.created_at)} · skor ${record.overall_score ?? '–'}${record.note ? ` · ${record.note.slice(0, 20)}` : ''}`
  const ordered = [byId[before!], byId[after!]].filter(Boolean).sort((a, b) => a.created_at.localeCompare(b.created_at))
  return (
    <Card>
      <SectionHeader icon={<HistoryIcon />} title="Önce / sonra" />
      <div className="grid gap-3 sm:grid-cols-2">
        {[['Önce', before, setBefore], ['Sonra', after, setAfter]].map(([label, value, set]) => (
          <label key={label as string} className="text-sm font-semibold">{label as string}
            <select className="field mt-1.5" value={value as string} onChange={(event) => (set as (id: string) => void)(event.target.value)}>
              {records.map((record) => <option key={record.id} value={record.id}>{option(record)}</option>)}
            </select>
          </label>
        ))}
      </div>
      {before === after ? <p className="mt-3 text-sm text-muted">Karşılaştırmak için iki farklı kayıt seçin.</p> : null}
      {comparison.isPending && before !== after ? <div className="mt-4"><Spinner label="Karşılaştırılıyor…" /></div> : null}
      {comparison.data && before !== after ? (
        <div className="mt-5 space-y-5">
          {ordered.length === 2 && ordered.every((record) => record.thumbnail_url) ? (
            <ChangeMapView profileId={profileId} before={ordered[0].id} after={ordered[1].id} />
          ) : (
          <div className="grid grid-cols-2 gap-3">
            {ordered.map((record, index) => (
              <figure key={record.id} className="rounded-xl border border-line bg-surface-soft p-2">
                {record.thumbnail_url ? <img src={record.thumbnail_url} alt={index ? 'Sonra' : 'Önce'} className="aspect-square w-full rounded-xl object-cover" /> : <div className="grid aspect-square place-items-center rounded-xl text-xs text-muted">Önizleme kaydedilmemiş</div>}
                <figcaption className="mt-2 text-xs"><b>{index ? 'Sonra' : 'Önce'}</b> · {stamp(record.created_at)}</figcaption>
              </figure>
            ))}
          </div>
          )}
          <ul className="space-y-1.5 rounded-xl bg-brand-50/60 p-4 text-sm">{comparison.data.summary.map((line) => <li key={line}>• {line}</li>)}</ul>
          <div className="grid gap-4 md:grid-cols-2">
            {[['Alt skorlar', comparison.data.scores.map((item) => ({ ...item, name: item.label }))], ['Bölgelerdeki nokta', comparison.data.regions.filter((item) => item.before !== null || item.after !== null)]].map(([title, rows]) => (
              <div key={title as string}>
                <p className="label mb-2">{title as string}</p>
                <table className="w-full text-sm">
                  <thead className="text-xs text-muted"><tr><th className="text-left font-semibold" /><th>Önce</th><th>Sonra</th><th>Fark</th><th /></tr></thead>
                  <tbody>{(rows as { name: string; before: number | null; after: number | null; delta: number | null; direction: string }[]).map((row) => (
                    <tr key={row.name} className="border-t border-line text-center">
                      <td className="py-1.5 text-left">{row.name}</td><td>{row.before ?? '–'}</td><td>{row.after ?? '–'}</td>
                      <td>{row.delta === null ? '–' : row.delta > 0 ? `+${row.delta}` : row.delta}</td>
                      <td><span className="inline-flex items-center gap-1 text-xs">{DIRECTION[row.direction]?.icon}{DIRECTION[row.direction]?.word}</span></td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            ))}
          </div>
          <ul className="space-y-1 text-xs text-muted">{comparison.data.comparability_notes.map((note) => <li key={note}>• {note}</li>)}</ul>
        </div>
      ) : null}
    </Card>
  )
}

export function HistoryPage() {
  const { profile, options } = useAppState()
  const queryClient = useQueryClient()
  const history = useQuery({ queryKey: ['history', profile?.id], queryFn: () => api.history(profile!.id), enabled: !!profile })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['history'] })
  const [event, setEvent] = useState(() => ({ kind: 'routine_start', date: localToday(), note: '' }))
  const [confirmAll, setConfirmAll] = useState(false)
  const addEvent = useMutation({ mutationFn: () => api.addEvent(profile!.id, event.kind, event.date, event.note), onSuccess: () => { setEvent((e) => ({ ...e, note: '' })); refresh() } })
  const removeRecord = useMutation({ mutationFn: api.deleteRecord, onSuccess: refresh })
  const removeEvent = useMutation({ mutationFn: api.deleteEvent, onSuccess: refresh })
  const removeAll = useMutation({ mutationFn: () => api.deleteHistory(profile!.id), onSuccess: () => { setConfirmAll(false); refresh() } })
  const records = useMemo(() => history.data?.records ?? [], [history.data])
  if (!profile) return null
  const scored = records.filter((record) => record.overall_score !== null)
  const delta = scored.length > 1 ? scored[scored.length - 1].overall_score! - scored[0].overall_score! : null

  return (
    <div className="space-y-6">
      <div>
        <p className="eyebrow">Geçmiş ve Takip</p>
        <h1 className="mt-3 text-[34px] leading-tight font-normal sm:text-[42px]">{profile.display_name}, cildiniz zaman içinde</h1>
        <p className="mt-3 max-w-2xl text-base leading-relaxed text-ink-soft">Kayıtlarınız bizde güvenle saklanır: sonuçlar ve küçük bir yüz önizlemesi. Yüklediğiniz orijinal fotoğraf saklanmaz; kayıtlarınızı dilediğiniz zaman silebilirsiniz.</p>
      </div>
      {history.isPending ? <Spinner label="Geçmiş yükleniyor…" /> : null}
      {history.data && !records.length ? (
        <EmptyState icon={<HistoryIcon size={34} />} title="Henüz kayıt yok">Analiz sonrası “Rapor” sekmesinden “Geçmişe kaydet”e basın. Takip için 1-2 haftada bir, benzer ışık ve açıyla fotoğraf önerilir.</EmptyState>
      ) : null}
      {records.length ? (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            {[['Kayıt sayısı', records.length, ''], ['Son skor', scored.at(-1)?.overall_score ?? '–', scored.at(-1) ? stamp(scored.at(-1)!.created_at) : ''], ['İlk kayıttan beri', delta === null ? '–' : delta > 0 ? `+${delta}` : delta, 'genel skor farkı']].map(([label, value, note]) => (
              <Card key={label as string} className="p-5"><p className="label">{label}</p><p className="mt-2 font-display text-4xl leading-none tabular-nums">{value}</p><p className="mt-2 text-xs text-muted">{note}</p></Card>
            ))}
          </div>
          <Charts records={records} events={history.data?.events ?? []} />
          {records.length > 1 ? <Compare key={records.length} profileId={profile.id} records={records} /> : null}
        </>
      ) : null}

      <Card>
        <SectionHeader icon={<Calendar />} title="Rutin olayları" subtitle="Örneğin yeni bir ürüne başladığınız gün; grafiklerde işaretlenir." />
        <div className="grid gap-3 sm:grid-cols-[1fr_auto_2fr_auto]">
          <select className="field" value={event.kind} onChange={(e) => setEvent({ ...event, kind: e.target.value })} aria-label="Olay türü">
            {Object.entries(options.event_kinds).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select>
          <input type="date" className="field" value={event.date} onChange={(e) => setEvent({ ...event, date: e.target.value })} aria-label="Tarih" />
          <input className="field" value={event.note} maxLength={200} onChange={(e) => setEvent({ ...event, note: e.target.value })} placeholder="Not, örn. azelaik aside başladım" aria-label="Not" />
          <Button onClick={() => addEvent.mutate()} disabled={addEvent.isPending}><Plus size={18} /> Ekle</Button>
        </div>
        {history.data?.events.length ? (
          <ul className="mt-4 divide-y divide-line text-sm">
            {history.data.events.map((item) => (
              <li key={item.id} className="flex items-center justify-between py-2">
                <span>{new Date(item.date).toLocaleDateString('tr-TR')} · <b>{options.event_kinds[item.kind]}</b> {item.note}</span>
                <button type="button" className="rounded-full p-1.5 text-muted hover:bg-blush-100 hover:text-priority" aria-label="Olayı sil" onClick={() => removeEvent.mutate(item.id)}><Trash size={18} /></button>
              </li>
            ))}
          </ul>
        ) : null}
      </Card>

      <Card>
        <SectionHeader icon={<Download />} title="Kayıtlarınızı yönetin" />
        <div className="flex flex-wrap gap-3">
          <a className="btn-ghost" href={api.exportUrl(profile.id, 'json')} download><Download size={18} /> JSON indir</a>
          <a className="btn-ghost" href={api.exportUrl(profile.id, 'csv')} download><Download size={18} /> CSV indir</a>
        </div>
        {records.length ? (
          <ul className="mt-5 divide-y divide-line text-sm">
            {[...records].reverse().map((record) => (
              <li key={record.id} className="flex items-center justify-between gap-3 py-2">
                <span className="flex items-center gap-3">
                  {record.thumbnail_url ? <img src={record.thumbnail_url} alt="" className="size-10 rounded-lg object-cover" /> : <span className="size-10 rounded-lg bg-surface-soft" />}
                  <span>{stamp(record.created_at)} · skor <b>{record.overall_score ?? '–'}</b>{record.note ? <span className="text-muted"> · {record.note}</span> : null}</span>
                </span>
                <button type="button" className="rounded-full p-1.5 text-muted hover:bg-blush-100 hover:text-priority" aria-label="Kaydı sil" onClick={() => removeRecord.mutate(record.id)}><Trash size={18} /></button>
              </li>
            ))}
          </ul>
        ) : null}
        {records.length ? (
          confirmAll ? (
            <div className="mt-4"><Notice tone="error">
              Tüm kayıtlar ve önizlemeler kalıcı olarak silinecek.
              <div className="mt-2 flex gap-2"><Button variant="ghost" onClick={() => setConfirmAll(false)}>Vazgeç</Button><button type="button" className="btn bg-priority text-white" onClick={() => removeAll.mutate()}>Kalıcı olarak sil</button></div>
            </Notice></div>
          ) : <button type="button" className="mt-4 text-sm font-semibold text-danger hover:underline" onClick={() => setConfirmAll(true)}>Tüm kayıtlarımı sil</button>
        ) : null}
      </Card>
    </div>
  )
}
