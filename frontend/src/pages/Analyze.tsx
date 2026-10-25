// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Sudem Kırmız
import { useMutation, useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Camera, Close, DocumentPdf, FaceScan, ImageUpload, Plus, ShieldSun, Sparkles, Sun } from '../icons'
import { ApiError, api } from '../lib/api'
import { useAppState } from '../lib/app-state'
import { DEMO, asset } from '../lib/demo'
import { AiComment, MismatchHints, PhotosCard, QualityCard, RegionCard, ResultHero, ScoreDetails, TechnicalDetails } from '../components/results'
import { ProductsPanel, ReportPanel, RoutinePanel } from '../components/plan'
import { CameraCapture, cameraSupported } from '../components/CameraCapture'
import { WeatherCard } from '../components/WeatherCard'
import { TodayCard } from '../components/TodayCard'
import { Button, EmptyState, Notice, Tabs } from '../components/ui'

type Tab = 'summary' | 'detail' | 'routine' | 'report'
const STEPS = ['Yüz haritası çıkarılıyor', 'Noktalar ve bölgeler ölçülüyor', 'Yapay zekâ yorumluyor']
const HOW = [
  { title: 'Fotoğraf', text: 'Önden net bir fotoğraf yükleyin; isterseniz sağa ve sola dönük iki açı ekleyin.' },
  { title: 'Ölçüm', text: 'Yüz bölgeleri ayrılır; nokta, kızarıklık, ton, doku ve parlama ölçülür.' },
  { title: 'Rutin', text: 'Profilinize göre sabah ve akşam rutini, ürün önerileri ve PDF rapor hazırlanır.' },
]
const TIPS = [
  { icon: <Sun size={16} />, text: 'Doğal, yumuşak ışık' },
  { icon: <Camera size={16} />, text: 'Sabit ve net kadraj' },
  { icon: <FaceScan size={16} />, text: 'Önden, yüz tam görünür' },
  { icon: <Sparkles size={16} />, text: 'Makyajsız, filtresiz' },
]

const pad = (n: number) => String(n).padStart(2, '0')
function stamp(value: string) {
  const d = new Date(value)
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} · ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function UploadCard({ files, setFiles, onAnalyze, busy }: { files: File[]; setFiles: (files: File[]) => void; onAnalyze: () => void; busy: boolean }) {
  const { options } = useAppState()
  const input = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [camera, setCamera] = useState(false)
  const previews = useMemo(() => files.map((file) => URL.createObjectURL(file)), [files])
  useEffect(() => () => previews.forEach((url) => URL.revokeObjectURL(url)), [previews])

  const add = (incoming: FileList | null) => {
    if (!incoming) return
    const accepted = [...incoming].filter((file) => file.type.startsWith('image/'))
    const tooBig = accepted.find((file) => file.size > options.limits.max_upload_mb * 1024 * 1024)
    if (tooBig) return setError(`${tooBig.name}: en fazla ${options.limits.max_upload_mb} MB yükleyebilirsiniz.`)
    const next = [...files, ...accepted].slice(0, options.limits.max_views)
    setError(files.length + accepted.length > options.limits.max_views ? `En fazla ${options.limits.max_views} fotoğraf kullanılır.` : null)
    setFiles(next)
  }

  return (
    <div className="card p-5 sm:p-6">
      <div
        role="button"
        tabIndex={0}
        onClick={() => input.current?.click()}
        onKeyDown={(event) => (event.key === 'Enter' || event.key === ' ') && input.current?.click()}
        onDragOver={(event) => { event.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => { event.preventDefault(); setDragging(false); add(event.dataTransfer.files) }}
        className={clsx('flex cursor-pointer flex-col items-center rounded-xl border border-dashed px-4 py-10 text-center transition-colors',
          dragging ? 'border-brand-500 bg-brand-50' : 'border-line-strong bg-surface-soft/60 hover:border-brand-400 hover:bg-surface-soft')}
      >
        <span className="mb-4 grid size-12 place-items-center rounded-full border border-line bg-surface text-brand-700"><ImageUpload size={24} /></span>
        <p className="font-medium">Fotoğraf seçin veya buraya bırakın</p>
        <p className="mt-1 text-xs text-muted">1–3 fotoğraf · JPG, PNG, WEBP · en fazla {options.limits.max_upload_mb} MB</p>
        <input ref={input} type="file" accept="image/jpeg,image/png,image/webp,image/bmp" multiple className="hidden" onChange={(event) => { add(event.target.files); event.target.value = '' }} />
      </div>
      {cameraSupported() && files.length < options.limits.max_views ? (
        <>
          <div className="my-4 flex items-center gap-3 text-xs text-muted"><span className="h-px flex-1 bg-line" />veya<span className="h-px flex-1 bg-line" /></div>
          <Button variant="ghost" className="w-full" onClick={() => setCamera(true)}><Camera size={18} /> Kamerayla rehberli çekim</Button>
        </>
      ) : null}
      {camera ? (
        <CameraCapture maxShots={options.limits.max_views - files.length} onClose={() => setCamera(false)}
          onDone={(taken) => { setFiles([...files, ...taken].slice(0, options.limits.max_views)); setCamera(false) }} />
      ) : null}
      {previews.length ? (
        <div className="mt-4 grid grid-cols-3 gap-3">
          {previews.map((url, index) => (
            <div key={url} className="relative">
              <img src={url} alt={`Fotoğraf ${index + 1}`} className="aspect-[3/4] w-full rounded-lg border border-line object-cover" />
              <button type="button" aria-label="Fotoğrafı kaldır" onClick={() => setFiles(files.filter((_, i) => i !== index))}
                className="absolute top-1.5 right-1.5 grid size-7 place-items-center rounded-full bg-white/95 text-[#24342b] shadow-sm hover:bg-white"><Close size={14} /></button>
            </div>
          ))}
        </div>
      ) : null}
      {files.length > 1 ? <p className="mt-3 text-xs text-muted">Fotoğrafların aynı kişiye ait olduğundan emin olun; her bölge en iyi göründüğü açıdan ölçülür.</p> : null}
      {error ? <div className="mt-3"><Notice tone="warn">{error}</Notice></div> : null}
      <Button className="mt-5 w-full py-3" onClick={onAnalyze} disabled={!files.length || busy}>
        {busy ? 'Analiz ediliyor…' : <><FaceScan size={18} /> Analizi başlat</>}
      </Button>
      <ul className="mt-5 grid grid-cols-2 gap-x-4 gap-y-2.5 border-t border-line pt-5">
        {TIPS.map((tip) => <li key={tip.text} className="flex items-center gap-2 text-xs text-ink-soft"><span className="text-brand-600">{tip.icon}</span>{tip.text}</li>)}
      </ul>
    </div>
  )
}

/** Demo build: the recorded sample photo is the only one that can be analysed, so say so instead of taking uploads. */
function DemoUpload({ onAnalyze }: { onAnalyze: () => void }) {
  return (
    <div className="card p-5 sm:p-6">
      <div className="flex gap-4">
        <img src={asset('demo/sample.jpg')} alt="Örnek fotoğraf (yapay zekâ ile üretilmiş portre)" className="aspect-[3/4] w-28 shrink-0 rounded-xl border border-line object-cover" />
        <div>
          <p className="eyebrow">Canlı demo</p>
          <p className="mt-2 font-medium">Örnek fotoğrafla deneyin</p>
          <p className="mt-1 text-sm leading-relaxed text-muted">Demoda kendi fotoğrafınız yüklenmez; analiz, gerçek modellerle önceden işlenmiş bu örnek portre üzerinden gösterilir.</p>
        </div>
      </div>
      <Button className="mt-5 w-full py-3" onClick={onAnalyze}><FaceScan size={18} /> Örnek fotoğrafı analiz et</Button>
      <ul className="mt-5 grid grid-cols-2 gap-x-4 gap-y-2.5 border-t border-line pt-5">
        {TIPS.map((tip) => <li key={tip.text} className="flex items-center gap-2 text-xs text-ink-soft"><span className="text-brand-600">{tip.icon}</span>{tip.text}</li>)}
      </ul>
    </div>
  )
}

function Analyzing() {
  const [step, setStep] = useState(0)
  useEffect(() => {
    const timer = setInterval(() => setStep((current) => Math.min(current + 1, STEPS.length - 1)), 2200)
    return () => clearInterval(timer)
  }, [])
  return (
    <div className="card p-8" role="status" aria-live="polite">
      <div className="mb-6 flex items-center gap-3">
        <span className="size-5 animate-spin rounded-full border-2 border-line border-t-brand-700" />
        <p className="font-display text-xl">Analiz ediliyor</p>
      </div>
      <ol className="space-y-3">
        {STEPS.map((label, index) => (
          <li key={label} className={clsx('flex items-center gap-3 text-sm transition-colors', index === step ? 'font-medium text-ink' : index < step ? 'text-muted' : 'text-muted/60')}>
            <span className={clsx('grid size-6 place-items-center rounded-full border text-[11px] tabular-nums', index < step ? 'border-brand-500 bg-brand-500 text-white' : index === step ? 'border-ink text-ink' : 'border-line')}>{index + 1}</span>
            {label}
          </li>
        ))}
      </ol>
    </div>
  )
}

function Welcome({ children }: { children: React.ReactNode }) {
  const { profile, options } = useAppState()
  return (
    <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,440px)] lg:items-start lg:gap-16">
      <div className="pt-2">
        <p className="eyebrow">Merhaba, {profile?.display_name}</p>
        <h1 className="mt-4 text-[40px] leading-[1.08] font-normal sm:text-[56px]">
          Cildinizi <em className="text-brand-600">yakından</em> tanıyın.
        </h1>
        <p className="mt-5 max-w-lg text-base leading-relaxed text-ink-soft">
          Yüz bölgelerinizi ayırır, görünür noktaları ve kızarıklığı ölçer, size özel bir bakım rutini hazırlarız. Birkaç saniye sürer.
        </p>
        <ol className="mt-10 max-w-lg border-t border-line">
          {HOW.map((item, index) => (
            <li key={item.title} className="grid grid-cols-[3rem_1fr] gap-2 border-b border-line py-4">
              <span className="font-display text-lg text-brand-600 tabular-nums">0{index + 1}</span>
              <span>
                <span className="block text-sm font-medium">{item.title}</span>
                <span className="mt-0.5 block text-sm leading-relaxed text-muted">{item.text}</span>
              </span>
            </li>
          ))}
        </ol>
        <p className="mt-6 flex max-w-lg items-start gap-2 text-xs leading-relaxed text-muted">
          <ShieldSun size={16} className="mt-0.5 shrink-0 text-brand-600" />
          Fotoğrafınız analizden sonra saklanmaz. Bu bir tıbbi teşhis değildir; ağrı, hızlı değişim veya endişe varsa dermatoloğa danışın.
        </p>
      </div>
      <div className="space-y-6">{children}{options.flags.history_enabled ? <TodayCard /> : null}<WeatherCard /></div>
    </div>
  )
}

export function AnalyzePage() {
  const { profile, ai, analysis, setAnalysis, providerKeys } = useAppState()
  const [files, setFiles] = useState<File[]>([])
  const [tab, setTab] = useState<Tab>('summary')
  const run = useMutation({
    mutationFn: () => api.analyze({ profileId: profile!.id, files, provider: ai.provider, useVlm: ai.useVlm, secondOpinion: ai.secondOpinion && files.length === 1, hfModel: ai.hfModel, providerKey: providerKeys[ai.provider] }),
    onSuccess: (result) => { setAnalysis(result); setTab('summary'); window.scrollTo({ top: 0 }) },
  })
  // The routine follows the current profile: editing the profile updates it without re-analysing.
  const routine = useQuery({
    queryKey: ['routine', analysis?.analysis_id, profile?.id, JSON.stringify(profile?.skin)],
    queryFn: () => api.routine(analysis!.analysis_id, profile!.id),
    enabled: !!analysis && !!profile,
    placeholderData: analysis?.routine,
  })
  const current = analysis && routine.data ? { ...analysis, routine: routine.data } : analysis
  const startOver = () => { setAnalysis(null); setFiles([]); run.reset() }

  if (run.isPending || !current) {
    return (
      <Welcome>
        {run.isPending ? <Analyzing /> : DEMO ? <DemoUpload onAnalyze={() => run.mutate()} /> : <UploadCard files={files} setFiles={setFiles} onAnalyze={() => run.mutate()} busy={false} />}
        {run.isError ? <div className="mt-4"><Notice tone="error">{run.error instanceof ApiError ? run.error.messages.join('\n') : 'Analiz çalıştırılamadı; lütfen tekrar deneyin.'}</Notice></div> : null}
      </Welcome>
    )
  }

  if (!current.face_found) {
    return (
      <div className="mx-auto max-w-xl space-y-6">
        <EmptyState icon={<FaceScan size={28} />} title="Yüz algılanamadı">{current.vlm_error}</EmptyState>
        <div className="text-center"><Button onClick={startOver}><Plus size={18} /> Başka bir fotoğraf deneyin</Button></div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="eyebrow">Analiz sonucu · {stamp(current.created_at)}</p>
          <h1 className="mt-3 text-[34px] leading-tight font-normal sm:text-[42px]">{profile?.display_name}, cilt raporunuz</h1>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={startOver}><Plus size={18} /> Yeni analiz</Button>
          {profile ? <a className="btn-primary" href={api.reportUrl(current.analysis_id, profile.id, 'pdf')}><DocumentPdf size={18} /> PDF rapor</a> : null}
        </div>
      </div>

      <ResultHero analysis={current} />

      <div className="space-y-6">
        <Tabs<Tab> label="Sonuç bölümleri" value={tab} onChange={setTab} tabs={[
          { id: 'summary', label: 'Özet' },
          { id: 'detail', label: 'Detaylı Analiz' },
          { id: 'routine', label: 'Rutin' },
          { id: 'report', label: 'Rapor' },
        ]} />
        {tab === 'summary' ? (
          <div className="space-y-6">
            <MismatchHints analysis={current} />
            <div className="grid gap-6 lg:grid-cols-[minmax(0,6fr)_minmax(0,5fr)]">
              <AiComment analysis={current} />
              <PhotosCard analysis={current} />
            </div>
          </div>
        ) : null}
        {tab === 'detail' ? (
          <div className="space-y-6">
            <QualityCard analysis={current} />
            <div className="grid gap-6 lg:grid-cols-2">
              <ScoreDetails analysis={current} />
              <RegionCard analysis={current} />
            </div>
            <TechnicalDetails analysis={current} />
          </div>
        ) : null}
        {tab === 'routine' ? <div className="space-y-6"><RoutinePanel routine={current.routine} /><ProductsPanel analysis={current} /></div> : null}
        {tab === 'report' ? <ReportPanel analysis={current} /> : null}
      </div>
    </div>
  )
}
