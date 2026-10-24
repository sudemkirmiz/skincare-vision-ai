import { useMutation, useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { useState, type FormEvent, type ReactNode } from 'react'
import { Alert, Drop, Pin, ShieldSun, Sun } from '../icons'
import { ApiError, api } from '../lib/api'
import { useAppState } from '../lib/app-state'
import type { Place } from '../lib/types'
import { Button, Card, Notice, Spinner } from './ui'

const LOCATION_KEY = 'scv.location'
// WHO UV index colours; the band word is always shown next to them.
const UV_COLOR = { low: '#3ea72d', moderate: '#e3c800', high: '#f18b00', very_high: '#e53210', extreme: '#b567a4' } as const
const TIP_ICON: Record<string, ReactNode> = {
  uv: <Sun size={18} />, actives: <Alert size={18} />, humidity: <Drop size={18} />, temperature: <ShieldSun size={18} />,
}

// The location is a per-browser convenience: it is never stored on the server.
export function readLocation(): Place | null {
  try {
    const raw = localStorage.getItem(LOCATION_KEY)
    return raw ? (JSON.parse(raw) as Place) : null
  } catch {
    return null
  }
}

function writeLocation(place: Place | null) {
  try {
    if (place) localStorage.setItem(LOCATION_KEY, JSON.stringify(place))
    else localStorage.removeItem(LOCATION_KEY)
  } catch {
    /* ignore */
  }
}

const round = (value: number) => Math.round(value * 10) / 10

function LocationPicker({ onPick }: { onPick: (place: Place) => void }) {
  const [query, setQuery] = useState('')
  const [geoError, setGeoError] = useState<string | null>(null)
  const [locating, setLocating] = useState(false)
  const search = useMutation({ mutationFn: (text: string) => api.weatherSearch(text) })
  const submit = (event: FormEvent) => { event.preventDefault(); if (query.trim().length >= 2) search.mutate(query) }
  const locate = () => {
    if (!navigator.geolocation) return setGeoError('Tarayıcınız konum paylaşımını desteklemiyor; şehir arayın.')
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      (position) => { setLocating(false); onPick({ name: 'Konumunuz', region: '', lat: round(position.coords.latitude), lon: round(position.coords.longitude) }) },
      () => { setLocating(false); setGeoError('Konum izni verilmedi; şehrinizi arayabilirsiniz.') },
      { maximumAge: 3_600_000, timeout: 10_000 },
    )
  }
  return (
    <div className="space-y-3">
      <Button variant="ghost" className="w-full" onClick={locate} disabled={locating}><Pin size={18} /> {locating ? 'Konum alınıyor…' : 'Konumumu kullan'}</Button>
      <form onSubmit={submit} className="flex gap-2">
        <input className="field" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="veya şehir arayın, örn. İzmir" aria-label="Şehir" maxLength={60} />
        <Button type="submit" variant="ghost" disabled={query.trim().length < 2 || search.isPending}>Ara</Button>
      </form>
      {geoError ? <p className="text-xs text-warn-ink">{geoError}</p> : null}
      {search.isError ? <p className="text-xs text-danger">{search.error instanceof ApiError ? search.error.messages.join(' ') : 'Arama yapılamadı.'}</p> : null}
      {search.data ? (
        search.data.length ? (
          <ul className="divide-y divide-line rounded-xl border border-line">
            {search.data.map((place) => (
              <li key={`${place.lat},${place.lon},${place.name}`}>
                <button type="button" className="w-full px-3 py-2 text-left text-sm hover:bg-surface-soft" onClick={() => onPick(place)}>
                  <span className="font-medium">{place.name}</span>{place.region ? <span className="text-muted"> · {place.region}</span> : null}
                </button>
              </li>
            ))}
          </ul>
        ) : <p className="text-xs text-muted">Sonuç bulunamadı.</p>
      ) : null}
      <p className="text-[11px] leading-relaxed text-muted">Hava durumu için yalnızca yaklaşık konum (~10 km) Open-Meteo'ya gönderilir; konumunuz bu tarayıcıda kalır.</p>
    </div>
  )
}

export function WeatherCard() {
  const { profile } = useAppState()
  const [place, setPlace] = useState<Place | null>(readLocation)
  const [picking, setPicking] = useState(false)
  const weather = useQuery({
    queryKey: ['weather', place?.lat, place?.lon, profile?.id],
    queryFn: () => api.weather(place!.lat, place!.lon, profile?.id),
    enabled: !!place,
    staleTime: 30 * 60_000,
    retry: false,
  })
  const pick = (next: Place) => { writeLocation(next); setPlace(next); setPicking(false) }
  const data = weather.data

  return (
    <Card>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-medium">Bugünün cilt hava durumu</h2>
          {place && !picking ? <p className="mt-0.5 flex items-center gap-1 text-sm text-muted"><Pin size={14} />{place.name}</p> : null}
        </div>
        {place && !picking ? <button type="button" className="text-sm text-brand-700 underline-offset-2 hover:underline" onClick={() => setPicking(true)}>Değiştir</button> : null}
      </div>
      {!place || picking ? (
        <>
          {!place ? <p className="mb-4 text-sm leading-relaxed text-ink-soft">UV, sıcaklık ve neme göre bugün cildiniz için neye dikkat etmeniz gerektiğini gösterelim.</p> : null}
          <LocationPicker onPick={pick} />
          {picking ? <button type="button" className="mt-3 text-sm text-muted hover:text-ink" onClick={() => setPicking(false)}>Vazgeç</button> : null}
        </>
      ) : weather.isPending ? <Spinner label="Hava durumu alınıyor…" /> : weather.isError ? (
        <Notice tone="warn">{weather.error instanceof ApiError ? weather.error.messages.join(' ') : 'Hava durumu alınamadı.'}</Notice>
      ) : data ? (
        <div className="space-y-4">
          <div className="flex items-center gap-5">
            {data.uv_max !== null && data.uv_band ? (
              <div className="flex items-center gap-3">
                <span className="grid size-14 place-items-center rounded-full font-display text-2xl text-white" style={{ background: UV_COLOR[data.uv_band.key] }}>{Math.round(data.uv_max)}</span>
                <div><p className="label">En yüksek UV</p><p className="text-sm font-medium">{data.uv_band.label}</p></div>
              </div>
            ) : null}
            <dl className="ml-auto grid grid-cols-2 gap-x-5 gap-y-0.5 text-sm">
              <dt className="text-muted">Sıcaklık</dt><dd className="text-right font-medium tabular-nums">{data.temperature === null ? '–' : `${Math.round(data.temperature)}°`}</dd>
              <dt className="text-muted">Nem</dt><dd className="text-right font-medium tabular-nums">{data.humidity === null ? '–' : `%${Math.round(data.humidity)}`}</dd>
            </dl>
          </div>
          <ul className="divide-y divide-line border-t border-line">
            {data.tips.map((tip) => (
              <li key={tip.kind + tip.title} className="flex gap-3 py-3">
                <span className={clsx('mt-0.5 shrink-0', tip.tone === 'warn' ? 'text-mid' : tip.tone === 'good' ? 'text-good' : 'text-brand-600')}>{TIP_ICON[tip.kind] ?? <Sun size={18} />}</span>
                <p className="text-sm leading-relaxed"><span className="font-medium">{tip.title}.</span> <span className="text-ink-soft">{tip.text}</span></p>
              </li>
            ))}
          </ul>
          <p className="text-[11px] text-muted">Kaynak: {data.source}</p>
        </div>
      ) : null}
    </Card>
  )
}
