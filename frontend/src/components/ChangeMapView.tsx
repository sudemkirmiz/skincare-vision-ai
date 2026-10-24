import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { ChevronRight, StatusGood, StatusPriority } from '../icons'
import { ApiError, api } from '../lib/api'
import { Notice, Spinner, Tabs } from './ui'

type Mode = 'slider' | 'redness' | 'tone'

const LEGEND = {
  redness: { better: 'Kızarıklık azaldı', worse: 'Kızarıklık arttı' },
  tone: { better: 'Leke açıldı', worse: 'Leke koyulaştı' },
}

/** Drag a divider across the aligned photos: "before" on the left, "after" on the right. */
function WipeSlider({ before, after }: { before: string; after: string }) {
  const [position, setPosition] = useState(50)
  return (
    <div className="relative mx-auto aspect-square w-full max-w-md overflow-hidden rounded-xl border border-line bg-surface-soft select-none">
      <img src={after} alt="Sonra (hizalanmış)" className="absolute inset-0 h-full w-full object-cover" />
      <img src={before} alt="Önce" className="absolute inset-0 h-full w-full object-cover" style={{ clipPath: `inset(0 ${100 - position}% 0 0)` }} />
      <div className="pointer-events-none absolute inset-y-0 w-0.5 bg-white shadow-[0_0_0_1px_rgb(0_0_0/0.15)]" style={{ left: `${position}%` }}>
        <span className="absolute top-1/2 left-1/2 flex size-8 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-white text-ink shadow"><ChevronRight size={12} className="rotate-180" /><ChevronRight size={12} /></span>
      </div>
      <span className="absolute top-3 left-3 rounded-full bg-black/55 px-2.5 py-1 text-[11px] font-medium text-white">Önce</span>
      <span className="absolute top-3 right-3 rounded-full bg-black/55 px-2.5 py-1 text-[11px] font-medium text-white">Sonra</span>
      <input type="range" min={0} max={100} value={position} onChange={(event) => setPosition(Number(event.target.value))}
        aria-label="Önce ve sonra arasında kaydırın" className="absolute inset-0 h-full w-full cursor-ew-resize opacity-0" />
    </div>
  )
}

export function ChangeMapView({ profileId, before, after }: { profileId: string; before: string; after: string }) {
  const [mode, setMode] = useState<Mode>('slider')
  const map = useQuery({ queryKey: ['change-map', profileId, before, after], queryFn: () => api.compareMap(profileId, before, after), retry: false, staleTime: Infinity })

  if (map.isPending) return <Spinner label="Yüzler hizalanıyor…" />
  if (map.isError) return <Notice tone="warn">{map.error instanceof ApiError ? map.error.messages.join(' ') : 'Fark haritası oluşturulamadı.'}</Notice>
  const data = map.data

  return (
    <div className="space-y-4">
      <Tabs<Mode> label="Görünüm" value={mode} onChange={setMode} tabs={[
        { id: 'slider', label: 'Önce / sonra' },
        { id: 'redness', label: 'Kızarıklık' },
        { id: 'tone', label: 'Leke' },
      ]} />
      {mode === 'slider' ? (
        <>
          <WipeSlider before={data.before_uri} after={data.after_uri} />
          <p className="text-center text-xs text-muted">İkinci fotoğraf, yüz noktalarına göre ilkinin üzerine hizalandı.</p>
        </>
      ) : (
        <div className="grid items-center gap-5 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <img src={mode === 'redness' ? data.redness_uri : data.tone_uri} alt={mode === 'redness' ? 'Kızarıklık değişim haritası' : 'Leke değişim haritası'}
            className="mx-auto aspect-square w-full max-w-md rounded-xl border border-line object-cover" />
          <div className="space-y-4">
            <ul className="space-y-3 text-sm">
              <li className="flex items-center justify-between gap-3">
                <span className="flex items-center gap-2"><span className="size-3 rounded-sm bg-good" /><StatusGood size={16} className="text-good" />{LEGEND[mode].better}</span>
                <span className="font-semibold tabular-nums">%{data.stats[mode].better}</span>
              </li>
              <li className="flex items-center justify-between gap-3">
                <span className="flex items-center gap-2"><span className="size-3 rounded-sm bg-priority" /><StatusPriority size={16} className="text-priority" />{LEGEND[mode].worse}</span>
                <span className="font-semibold tabular-nums">%{data.stats[mode].worse}</span>
              </li>
            </ul>
            <p className="text-xs leading-relaxed text-muted">Yüzdeler, iki fotoğrafta da görünen cilt alanına göredir. Boyanmamış alanlarda belirgin bir değişim yok.</p>
            <table className="w-full text-sm">
              <thead className="text-xs text-muted"><tr><th className="text-left font-medium">Bölge</th><th className="font-medium">Azaldı</th><th className="font-medium">Arttı</th></tr></thead>
              <tbody>{data.regions.map((region) => (
                <tr key={region.key} className="border-t border-line text-center">
                  <td className="py-1.5 text-left">{region.name}</td>
                  <td className="tabular-nums">%{mode === 'redness' ? region.redness_better : region.tone_better}</td>
                  <td className="tabular-nums">%{mode === 'redness' ? region.redness_worse : region.tone_worse}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </div>
      )}
      <ul className="space-y-1 text-sm text-ink-soft">{data.summary.map((line) => <li key={line}>• {line}</li>)}</ul>
      <ul className="space-y-1 text-xs text-muted">{data.notes.map((note) => <li key={note}>• {note}</li>)}</ul>
    </div>
  )
}
