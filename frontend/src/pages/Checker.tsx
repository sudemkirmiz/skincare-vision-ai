// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Sudem Kırmız
import { useMutation } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { Alert, CheckCircle, ImageUpload, Info, LabelScan, Leaf, Plus, Sparkles, StatusGood, StatusPriority, StatusWatch } from '../icons'
import { ApiError, api } from '../lib/api'
import { useAppState } from '../lib/app-state'
import type { ProductVerdict, ShelfItemInput } from '../lib/types'
import { ShelfPanel } from '../components/Shelf'
import { Button, Card, Notice, SectionHeader, Tabs } from '../components/ui'
import { DEMO, SAMPLE_INCI } from '../lib/demo'

const VERDICT = {
  suitable: { Icon: StatusGood, color: 'text-good' },
  caution: { Icon: StatusWatch, color: 'text-mid' },
  avoid: { Icon: StatusPriority, color: 'text-priority' },
} as const

function errorText(error: unknown) {
  return error instanceof ApiError ? error.messages.join(' ') : 'İşlem tamamlanamadı; lütfen tekrar deneyin.'
}

function VerdictCard({ verdict, productName, onAdd }: { verdict: ProductVerdict; productName: string; onAdd?: () => void }) {
  const style = VERDICT[verdict.verdict]
  const groups = [
    { title: 'Neden önerilmez', items: verdict.avoid, icon: <StatusPriority size={18} className="text-priority" /> },
    { title: 'Dikkat', items: verdict.caution, icon: <Alert size={18} className="text-mid" /> },
    { title: 'Rutinle uyum', items: verdict.routine_notes, icon: <Info size={18} className="text-brand-600" /> },
    { title: 'Artılar', items: verdict.positives, icon: <CheckCircle size={18} className="text-good" /> },
  ].filter((group) => group.items.length)
  return (
    <div className="card p-6 sm:p-8" aria-live="polite">
      <div className="flex items-center gap-4">
        <style.Icon size={48} className={style.color} />
        <div>
          <p className="label">{productName || 'Ürün'}</p>
          <p className="font-display text-3xl">{verdict.verdict_label}</p>
          <p className="text-xs text-muted">{verdict.ingredient_count} içerik okundu</p>
        </div>
      </div>
      {verdict.detected_actives.length ? (
        <div className="mt-4 flex flex-wrap items-center gap-2 text-sm"><span className="font-semibold">Aktifler:</span>{verdict.detected_actives.map((active) => <span key={active} className="chip">{active}</span>)}</div>
      ) : null}
      <div className="mt-5 grid gap-4 md:grid-cols-2">
        {groups.map((group) => (
          <div key={group.title}>
            <p className="mb-2 flex items-center gap-2 text-sm font-semibold">{group.icon}{group.title}</p>
            <ul className="space-y-1.5 text-sm leading-relaxed">{group.items.map((item) => <li key={item}>• {item}</li>)}</ul>
          </div>
        ))}
      </div>
      <p className="mt-5 text-xs text-muted">Etikette konsantrasyon yazmadığı için yalnızca içerik sırasına bakılır; bu bir ön değerlendirmedir.</p>
      {onAdd ? <div className="mt-5 border-t border-line pt-5"><Button variant="ghost" onClick={onAdd}><Plus size={18} /> Rafıma ekle</Button></div> : null}
    </div>
  )
}

function ProductCheck({ onAddToShelf }: { onAddToShelf?: (item: ShelfItemInput) => void }) {
  const { profile, ai, analysis, providerKeys } = useAppState()
  const [mode, setMode] = useState<'photo' | 'text'>(DEMO ? 'text' : 'photo')
  const [text, setText] = useState('')
  const [productName, setProductName] = useState('')
  const [label, setLabel] = useState<File | null>(null)
  const input = useRef<HTMLInputElement>(null)

  const check = useMutation({ mutationFn: (inci: string) => api.checkProduct(profile!.id, inci, analysis?.analysis_id) })
  const read = useMutation({
    mutationFn: () => api.readLabel(label!, ai.provider, providerKeys[ai.provider]),
    onSuccess: (result) => {
      setText(result.ingredients_text)
      setProductName(result.product_name)
      setMode('text')
      check.mutate(result.ingredients_text)
    },
  })

  return (
    <div className="space-y-6">
      {!analysis ? <Notice icon={<Sparkles size={18} />}>İpucu: Önce bir cilt analizi yaparsanız ürün, kişisel rutininizle çakışma açısından da kontrol edilir.</Notice> : null}

      <Card>
        <div className="mb-5"><Tabs<'photo' | 'text'> label="Giriş yöntemi" value={mode} onChange={setMode} tabs={[
          { id: 'photo', label: 'Etiket fotoğrafı', icon: <ImageUpload size={16} /> },
          { id: 'text', label: 'Listeyi yapıştırın', icon: <LabelScan size={16} /> },
        ]} /></div>
        {mode === 'photo' ? (
          <div className="space-y-4">
            <button type="button" onClick={() => input.current?.click()}
              className="flex w-full flex-col items-center rounded-xl border border-dashed border-line-strong bg-surface-soft/60 px-4 py-10 text-center transition-colors hover:border-brand-400 hover:bg-surface-soft">
              <span className="mb-4 grid size-12 place-items-center rounded-full border border-line bg-surface text-brand-700"><LabelScan size={24} /></span>
              <span className="font-medium">{label ? label.name : 'İçindekiler bölümünün net fotoğrafını seçin'}</span>
              <span className="mt-1 text-xs text-muted">Etiketi yakından ve düz çekin; yazı okunaklı olsun.</span>
            </button>
            <input ref={input} type="file" accept="image/*" className="hidden" onChange={(event) => setLabel(event.target.files?.[0] ?? null)} />
            <Button className="w-full" disabled={!label || read.isPending} onClick={() => read.mutate()}>{read.isPending ? 'Etiket okunuyor…' : 'Etiketi oku ve kontrol et'}</Button>
            {read.isError ? <Notice tone="error">{errorText(read.error)}</Notice> : null}
            <p className="text-xs text-muted">Etiketi seçili yapay zekâ sağlayıcısı ({ai.provider}) okur; okunan liste düzenleyebilmeniz için “Listeyi yapıştırın” sekmesine gelir.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {DEMO ? <button type="button" className="text-sm font-medium text-brand-700 underline-offset-2 hover:underline" onClick={() => setText(SAMPLE_INCI)}>Demo için örnek içerik listesini ekle</button> : null}
            <textarea className="field min-h-36" value={text} onChange={(event) => setText(event.target.value)} placeholder="Aqua, Glycerin, Niacinamide, …" aria-label="İçerik listesi (INCI)" />
            <Button className="w-full" disabled={!text.trim() || check.isPending} onClick={() => check.mutate(text)}>{check.isPending ? 'Kontrol ediliyor…' : 'Kontrol et'}</Button>
          </div>
        )}
      </Card>

      {check.isError ? <Notice tone="error">{errorText(check.error)}</Notice> : null}
      {check.data ? (
        <VerdictCard verdict={check.data} productName={productName} onAdd={onAddToShelf ? () => onAddToShelf({
          name: productName || 'Yeni ürün', category: check.data.positives.some((line) => line.includes('UV filtresi')) ? 'sunscreen' : 'other',
          usage: 'both', inci: text, opened_at: null, pao_months: null,
        }) : undefined} />
      ) : null}

      {!check.data ? (
        <Card>
          <SectionHeader icon={<Leaf />} title="Neye bakıyoruz?" />
          <ul className="grid gap-2 text-sm text-muted sm:grid-cols-2">
            <li>• Aktif içerikler (niasinamid, retinol, asitler…)</li>
            <li>• Parfüm ve koku alerjenleri, uçucu yağlar</li>
            <li>• Listenin başındaki kurutucu alkol</li>
            <li>• Gözenek tıkayabilen bazı yağlar</li>
            <li>• Profilinize göre uygun olmayan içerikler</li>
            <li>• Rutininizle aynı akşam çakışan aktifler</li>
          </ul>
        </Card>
      ) : null}
    </div>
  )
}

type ProductsTab = 'shelf' | 'check'

export function CheckerPage() {
  const { options } = useAppState()
  const shelfEnabled = options.flags.history_enabled
  const [tab, setTab] = useState<ProductsTab>(shelfEnabled ? 'shelf' : 'check')
  const [prefill, setPrefill] = useState<ShelfItemInput | null>(null)
  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <div>
        <p className="eyebrow">Ürünler</p>
        <h1 className="mt-3 text-[34px] leading-tight font-normal sm:text-[42px]">Ürünleriniz cildinize <em className="text-brand-600">uygun mu?</em></h1>
        <p className="mt-3 max-w-2xl text-base leading-relaxed text-ink-soft">Elinizdeki ürünleri rafınıza ekleyin ya da yeni bir ürünün içerik listesini kontrol edin; cildinize ve rutininize uygunluğunu birlikte değerlendirelim.</p>
      </div>
      {shelfEnabled ? (
        <Tabs<ProductsTab> label="Ürünler" value={tab} onChange={setTab} tabs={[{ id: 'shelf', label: 'Rafım' }, { id: 'check', label: 'İçerik kontrolü' }]} />
      ) : null}
      {tab === 'shelf' && shelfEnabled ? (
        <ShelfPanel prefill={prefill} onPrefillUsed={() => setPrefill(null)} />
      ) : (
        <ProductCheck onAddToShelf={shelfEnabled ? (item) => { setPrefill(item); setTab('shelf'); window.scrollTo({ top: 0 }) } : undefined} />
      )}
    </div>
  )
}
