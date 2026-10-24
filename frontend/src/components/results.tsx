import type { ReactNode } from 'react'
import { Alert, CheckCircle, FaceScan, Info, Lightbulb, Sparkles } from '../icons'
import type { Analysis } from '../lib/types'
import { Card, Meter, Notice, ScoreRing, SectionHeader, StatusBadge } from './ui'

const SCORE_HELP: Record<string, string> = {
  spots: 'Model, renk analizi ve (açıksa) Gemini ile bulunan nokta sayısına göre. Az nokta = yüksek skor.',
  redness: 'Cildin genel ve bölgesel kızarıklığına göre; ışık sapması göz akı referansıyla düzeltilir.',
  tone: 'Işık etkisi ayıklandıktan sonra kalan açık/koyu ton farklılıklarına göre.',
  texture: 'İnce ölçekli pürüzlülüğe göre. Fotoğraf çözünürlüğünden etkilenir.',
  shine: 'Yansıma/parlama noktalarının kapladığı alana göre. Işık kaynağından etkilenir.',
}

export function totalSpots(analysis: Analysis) {
  return analysis.skin_metrics?.available ? analysis.skin_metrics.spot_counts.total : 0
}

export function ResultHero({ analysis }: { analysis: Analysis }) {
  const metrics = analysis.skin_metrics
  const quality = analysis.result.image_quality
  const score = metrics?.available ? metrics.overall_score : null
  const facts: [string, ReactNode][] = []
  if (analysis.region_summary?.most_affected_name) facts.push(['En yoğun bölge', analysis.region_summary.most_affected_name])
  facts.push(['Nokta görünümü', `${totalSpots(analysis)} adet`])
  if (analysis.routine.focus.length) facts.push(['Bakım odağı', analysis.routine.focus.slice(0, 2).join(' · ')])
  const quote = analysis.result.visible_observations[0]
  return (
    <section className="card overflow-hidden">
      <div className="grid lg:grid-cols-[240px_minmax(0,1fr)]">
        {analysis.marked_uri ? (
          <img src={analysis.marked_uri} alt="İşaretlenmiş yüz fotoğrafı" className="hidden h-full max-h-80 w-full bg-surface-soft object-cover lg:block" />
        ) : null}
        <div className="grid gap-8 p-6 sm:p-8 md:grid-cols-[auto_minmax(0,1fr)] md:items-center">
          <div className="flex items-center gap-5">
            <ScoreRing value={score} />
            <div>
              <p className="label">Cilt Skoru</p>
              {score !== null ? <StatusBadge score={score} className="mt-1.5 text-base" /> : <p className="mt-1.5 text-sm text-muted">ölçülemedi</p>}
              {quality?.status === 'needs_review' ? <p className="mt-2 flex items-center gap-1.5 text-xs text-warn-ink"><Alert size={14} /> Fotoğraf kalitesi ideal değil</p> : null}
            </div>
          </div>
          <div className="md:border-l md:border-line md:pl-8">
            <dl className="divide-y divide-line">
              {facts.map(([term, value]) => (
                <div key={term} className="flex items-baseline justify-between gap-4 py-2.5 first:pt-0">
                  <dt className="text-sm text-muted">{term}</dt>
                  <dd className="text-right text-sm font-medium text-ink">{value}</dd>
                </div>
              ))}
            </dl>
            {quote ? <blockquote className="mt-4 font-display text-[17px] leading-relaxed text-ink-soft italic">“{quote}”</blockquote> : null}
          </div>
        </div>
      </div>
    </section>
  )
}

function viewLabel(yaw: number | null) {
  if (yaw === null || Math.abs(yaw) < 12) return 'Önden'
  return yaw > 0 ? 'Sağa dönük' : 'Sola dönük'
}

export function PhotosCard({ analysis }: { analysis: Analysis }) {
  const views = analysis.views ?? []
  const regionNames = Object.fromEntries((analysis.region_summary?.regions ?? []).map((region) => [region.key, region.name]))
  const measured: Record<number, string[]> = {}
  Object.entries(analysis.provenance ?? {}).forEach(([key, index]) => (measured[index] ??= []).push(regionNames[key] ?? key))
  return (
    <Card>
      <SectionHeader icon={<FaceScan />} title="Görseller" subtitle="Renkli çizgiler yüz bölgeleri; kutular model bulguları, mor halkalar renk analizi, mavi halkalar Gemini ikinci görüşü." />
      <div className="grid gap-4 sm:grid-cols-2">
        {[['Yüklenen', analysis.original_uri], ['İşaretlenen', analysis.marked_uri]].map(([label, uri]) => (
          <figure key={label}>
            <figcaption className="label mb-2">{label}</figcaption>
            {uri ? <img src={uri ?? undefined} alt={`${label} fotoğraf`} className="aspect-square w-full rounded-xl border border-line bg-surface-soft object-contain" /> : null}
          </figure>
        ))}
      </div>
      {views.length > 1 ? (
        <div className="mt-6">
          <p className="mb-2 text-sm font-semibold">Açılar <span className="font-normal text-muted">· her bölge en iyi göründüğü fotoğraftan ölçüldü</span></p>
          <div className="grid grid-cols-3 gap-3">
            {views.map((view, index) => (
              <figure key={index} className="rounded-xl border border-line bg-surface-soft p-2">
                <img src={view.marked_uri} alt={viewLabel(view.yaw)} className="aspect-[3/4] w-full rounded-xl object-cover" />
                <figcaption className="mt-2 text-xs"><b>{viewLabel(view.yaw)}</b>{view.primary ? ' · ana fotoğraf' : ''}<br /><span className="text-muted">{(measured[index] ?? []).join(', ') || '–'}</span></figcaption>
              </figure>
            ))}
          </div>
        </div>
      ) : null}
    </Card>
  )
}

export function AiComment({ analysis }: { analysis: Analysis }) {
  const { visible_observations: observations, care_suggestions: suggestions } = analysis.result
  // Turning the comment off is a choice, not an error: show it as neutral information.
  const disabledByUser = analysis.vlm_error?.includes('ayarlarda kapalı') ?? false
  return (
    <Card>
      <SectionHeader icon={<Sparkles />} title="Bakım odaklı yorum" subtitle={analysis.vlm_output ? `Kaynak: ${analysis.vlm_output.provider} · ${analysis.vlm_output.model}` : undefined} />
      <div className="space-y-3">
        {analysis.vlm_note ? <Notice>{analysis.vlm_note}</Notice> : null}
        {analysis.vlm_output?.cached ? <Notice>Bu fotoğraf için az önce üretilen yorum tekrar kullanıldı (kota tasarrufu).</Notice> : null}
        {analysis.vlm_error && disabledByUser ? (
          <Notice>Yapay zekâ yorumu ayarlarda kapalı. Açmak için üst menüdeki ayarlar düğmesini kullanın; cilt skoru ve rutininiz yine hesaplandı.</Notice>
        ) : analysis.vlm_error ? (
          <Notice tone="warn" icon={<Alert size={18} />}>{`Yapay zekâ yorumu üretilemedi.\n${analysis.vlm_error}`}</Notice>
        ) : null}
      </div>
      {observations.length || suggestions.length ? (
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {([['Gözlemler', observations], ['Öneriler', suggestions]] as const).map(([title, items]) => (
            <div key={title}>
              <p className="label mb-1">{title}</p>
              <ul className="divide-y divide-line">
                {items.map((item) => <li key={item} className="py-3 text-sm leading-relaxed text-ink-soft">{item}</li>)}
              </ul>
            </div>
          ))}
        </div>
      ) : null}
      <p className="mt-5 rounded-xl bg-sand-100 px-4 py-3 text-xs leading-relaxed text-warn-ink">{analysis.result.disclaimer}</p>
    </Card>
  )
}

export function ScoreDetails({ analysis }: { analysis: Analysis }) {
  const metrics = analysis.skin_metrics
  if (!metrics?.available) return <Notice tone="warn">{metrics?.reason ?? 'Cilt metrikleri bu fotoğraf için hesaplanamadı.'}</Notice>
  const counts = metrics.spot_counts
  return (
    <Card>
      <SectionHeader icon={<Sparkles />} title="Cilt Skoru ayrıntıları" subtitle="Görüntü işleme ile ölçülen görsel indekslerdir (yüksek = daha iyi). Işık ve kameradan etkilenir; tıbbi ölçüm değildir." />
      <div className="grid gap-x-8 gap-y-5">
        {Object.entries(metrics.scores).map(([key, value]) => <Meter key={key} value={value} label={metrics.score_labels[key]} hint={SCORE_HELP[key]} />)}
      </div>
      <div className="mt-5 flex flex-wrap gap-2">
        <span className="chip">Cilt tonu: {metrics.skin_tone.category} (ITA {metrics.skin_tone.ita}°)</span>
        <span className="chip">Nokta: {counts.yolo} model + {counts.colour} renk analizi{counts.gemini ? ` + ${counts.gemini} Gemini` : ''}</span>
      </div>
      {metrics.notes.length ? <div className="mt-4 space-y-2">{metrics.notes.map((note) => <Notice key={note}>{note}</Notice>)}</div> : null}
      {Object.keys(metrics.regions ?? {}).length ? (
        <details className="mt-4 text-sm">
          <summary className="cursor-pointer font-semibold text-muted">Bölge bazlı metrikler</summary>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-muted"><tr><th className="py-1.5 pr-3">Bölge</th><th className="pr-3">{metrics.score_labels.redness}</th><th className="pr-3">{metrics.score_labels.tone}</th><th>{metrics.score_labels.shine}</th></tr></thead>
              <tbody>{Object.entries(metrics.regions).map(([key, region]) => (
                <tr key={key} className="border-t border-line"><td className="py-1.5 pr-3 font-medium">{region.name}</td><td className="pr-3">{region.redness}</td><td className="pr-3">{region.tone}</td><td>{region.shine}</td></tr>
              ))}</tbody>
            </table>
          </div>
        </details>
      ) : null}
    </Card>
  )
}

export function RegionCard({ analysis }: { analysis: Analysis }) {
  const summary = analysis.region_summary
  if (!summary) return null
  const max = Math.max(1, ...summary.regions.map((region) => region.density ?? 0))
  const pose = analysis.result.detected_regions.head_pose
  return (
    <Card>
      <SectionHeader icon={<FaceScan />} title="Bölgesel dağılım" subtitle="Göz, kaş ve dudaklar hariç; sol/sağ görsele göredir. Yoğunluk, bölge alanına oranlanmış nokta sayısıdır." />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {summary.regions.map((region) => (
          <div key={region.key} className="rounded-xl border border-line bg-surface-soft p-3">
            <p className="flex items-center gap-1.5 text-xs font-semibold text-muted"><span className="size-2.5 rounded-full" style={{ background: region.color }} />{region.name}</p>
            {region.visible ? (
              <>
                <p className="mt-1 text-2xl font-bold">{region.count}</p>
                <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-line/70"><div className="h-full rounded-full" style={{ width: `${(100 * (region.density ?? 0)) / max}%`, background: region.color }} /></div>
                <p className="mt-1 text-[11px] text-muted">yoğunluk {region.density}</p>
              </>
            ) : <p className="mt-1 text-sm text-muted">kadrajda görünmüyor</p>}
          </div>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap gap-2 text-sm">
        {summary.most_affected_name ? <span className="chip">En yoğun: {summary.most_affected_name}</span> : null}
        {Object.values(summary.zones).map((zone) => <span key={zone.name} className="chip bg-surface-soft text-ink">{zone.name}: {zone.count}</span>)}
        {pose ? <span className="chip bg-surface-soft text-ink">Baş açısı: yana {Math.abs(pose.yaw).toFixed(0)}°, yukarı/aşağı {Math.abs(pose.pitch).toFixed(0)}°</span> : null}
      </div>
    </Card>
  )
}

export function TechnicalDetails({ analysis }: { analysis: Analysis }) {
  const findings = analysis.skin_findings?.findings ?? []
  const confidences = findings.map((finding) => finding.confidence).filter((value): value is number => typeof value === 'number')
  const average = confidences.length ? (confidences.reduce((sum, value) => sum + value, 0) / confidences.length).toFixed(2) : '–'
  const rows: [string, string][] = [
    ['Yüz bulma yöntemi', analysis.result.detected_regions.method ?? '–'],
    ['Model bulgusu', String(analysis.skin_findings?.summary?.total_detections ?? findings.length)],
    ['Ortalama model güveni', average],
    ['Yorum kaynağı', analysis.vlm_output ? `${analysis.vlm_output.provider} · ${analysis.vlm_output.model}` : 'üretilmedi'],
  ]
  return (
    <details className="card p-5 text-sm">
      <summary className="cursor-pointer font-semibold text-muted">Teknik ayrıntılar</summary>
      <dl className="mt-4 grid gap-x-6 gap-y-2 sm:grid-cols-2">
        {rows.map(([term, value]) => <div key={term} className="flex justify-between gap-4 border-b border-line py-1.5"><dt className="text-muted">{term}</dt><dd className="font-semibold">{value}</dd></div>)}
      </dl>
      {analysis.vlm_attempts?.length ? (
        <>
          <p className="label mt-4 mb-2">Sağlayıcı denemeleri</p>
          <pre className="max-h-64 overflow-auto rounded-xl bg-surface-soft p-3 text-[11px] leading-relaxed">{JSON.stringify(analysis.vlm_attempts, null, 2)}</pre>
        </>
      ) : null}
    </details>
  )
}

export function QualityCard({ analysis }: { analysis: Analysis }) {
  const quality = analysis.result.image_quality
  if (!quality) return null
  const good = quality.status === 'good'
  return (
    <Notice tone={good ? 'success' : 'warn'} icon={good ? <CheckCircle size={18} /> : <Lightbulb size={18} />}>
      <b>Fotoğraf kalitesi: {good ? 'Uygun' : 'Kontrol gerekli'}.</b> {quality.notes}
    </Notice>
  )
}

export function MismatchHints({ analysis }: { analysis: Analysis }) {
  if (!analysis.mismatch_hints.length) return null
  return <div className="space-y-2">{analysis.mismatch_hints.map((hint) => <Notice key={hint} tone="warn" icon={<Info size={18} />}>{hint}</Notice>)}</div>
}
