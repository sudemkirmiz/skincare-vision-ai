import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { useState, type ReactNode } from 'react'
import { Alert, Bag, Calendar, CheckCircle, Cleanser, DocumentPdf, Download, ExternalLink, History, Info, Jar, Lightbulb, Moon, Serum, ShieldSun, Sun } from '../icons'
import { api } from '../lib/api'
import { useAppState } from '../lib/app-state'
import type { Analysis, Routine } from '../lib/types'
import { Button, Card, Notice, SectionHeader, Spinner, Toggle } from './ui'

function stepIcon(step: string) {
  if (step === 'Temizleme') return <Cleanser size={20} />
  if (step === 'Nemlendirme') return <Jar size={20} />
  if (step === 'Güneş koruma') return <ShieldSun size={20} />
  return <Serum size={20} />
}

const SLOT = { am: { label: 'Sabah', icon: <Sun size={16} /> }, pm: { label: 'Akşam', icon: <Moon size={16} /> }, both: { label: 'Sabah + Akşam', icon: <Sparkle /> } }
function Sparkle() {
  return <span className="inline-flex"><Sun size={14} /><Moon size={14} /></span>
}

/** Native <details>: keyboard accessible, no state needed, closed by default (details on demand). */
function More({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <details className="group rounded-xl border border-line bg-surface">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm font-semibold text-ink [&::-webkit-details-marker]:hidden">
        <span className="text-brand-600">{icon}</span>{title}
        <span className="ml-auto text-muted transition group-open:rotate-90">›</span>
      </summary>
      <div className="border-t border-line px-4 py-4">{children}</div>
    </details>
  )
}

export function RoutinePanel({ routine }: { routine: Routine }) {
  const { profile, openEditor } = useAppState()
  return (
    <div className="space-y-5">
      <Card>
        <SectionHeader icon={<Serum />} title="Kişisel bakım rutininiz" subtitle="Analiz sonuçlarınız ve cilt profiliniz kullanılarak kural tabanlı oluşturuldu. Marka değil, içerik önerisidir." />
        {profile && profile.completeness < 1 ? (
          <div className="mb-4"><Notice>Profiliniz %{Math.round(profile.completeness * 100)} dolu. <button type="button" className="font-semibold underline" onClick={() => openEditor('edit')}>Profili tamamlarsanız</button> rutin daha isabetli olur.</Notice></div>
        ) : null}
        {routine.warnings.map((warning) => <div key={warning} className="mb-3"><Notice tone="warn" icon={<Alert size={18} />}>{warning}</Notice></div>)}
        {routine.focus.length ? (
          <div className="mb-4 flex flex-wrap items-center gap-2 text-sm"><span className="font-semibold">Odak:</span>{routine.focus.map((item) => <span key={item} className="chip">{item}</span>)}</div>
        ) : null}
        {routine.actives.length ? (
          <div className="grid gap-3 md:grid-cols-2">
            {routine.actives.map((active) => (
              <article key={active.id} className="rounded-xl border border-line bg-surface-soft p-4">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <h3 className="flex items-center gap-2 font-bold"><span className="text-brand-600"><Serum size={20} /></span>{active.name}</h3>
                  <span className="chip">{active.already_using ? 'Zaten kullanıyorsunuz' : <>{SLOT[active.slot].icon}{SLOT[active.slot].label}</>}</span>
                </div>
                <p className="text-xs text-muted">{active.form} · {active.strength}</p>
                <p className="mt-2 text-sm leading-relaxed">{active.why}</p>
                <p className="mt-2 text-sm"><b>Kullanım:</b> {active.frequency}</p>
                {active.cautions.length ? <ul className="mt-2 space-y-1 text-xs text-muted">{active.cautions.map((caution) => <li key={caution}>• {caution}</li>)}</ul> : null}
              </article>
            ))}
          </div>
        ) : <Notice icon={<CheckCircle size={18} />}>Belirgin bir ihtiyaç görünmüyor; temel rutin (temizleme, nemlendirme, güneş koruma) yeterli.</Notice>}
      </Card>

      <div className="grid gap-5 md:grid-cols-2">
        {([['Sabah', <Sun key="s" />, routine.am], ['Akşam', <Moon key="m" />, routine.pm]] as const).map(([title, icon, steps]) => (
          <Card key={title}>
            <SectionHeader icon={icon} title={title} />
            <ol className="space-y-3">
              {steps.map((step, index) => (
                <li key={step.step + index} className="flex gap-3">
                  <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-700">{stepIcon(step.step)}</span>
                  <span className="text-sm leading-relaxed"><b>{index + 1}. {step.step}</b><br /><span className="text-muted">{step.product}</span></span>
                </li>
              ))}
            </ol>
          </Card>
        ))}
      </div>

      <div className="space-y-3">
        <More icon={<Calendar size={18} />} title="Haftalık akşam planını göster">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-7">
            {routine.weekly.map((day) => (
              <div key={day.day} className="rounded-xl border border-line bg-surface-soft p-2.5">
                <p className="text-xs font-bold text-brand-700">{day.day}</p>
                {day.actives.map((active) => <p key={active} className="mt-1 text-[11px] leading-snug">{active}</p>)}
              </div>
            ))}
          </div>
        </More>
        {routine.excluded.length ? (
          <More icon={<Info size={18} />} title="Neden bazı içerikler önerilmedi?">
            <ul className="space-y-1.5 text-sm">{routine.excluded.map((item) => <li key={item.name}><b>{item.name}:</b> {item.reason}</li>)}</ul>
          </More>
        ) : null}
        <More icon={<Lightbulb size={18} />} title="Rutine başlarken">
          <ul className="space-y-1.5 text-sm">{routine.tips.map((tip) => <li key={tip}>• {tip}</li>)}</ul>
        </More>
      </div>
    </div>
  )
}

export function ProductsPanel({ analysis }: { analysis: Analysis }) {
  const { profile } = useAppState()
  const [open, setOpen] = useState(false)
  const products = useQuery({ queryKey: ['products', analysis.analysis_id, profile?.id, profile?.skin], queryFn: () => api.products(analysis.analysis_id, profile!.id), enabled: open && !!profile })
  if (!open) {
    return (
      <Card className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-blush-100 text-blush-500"><Bag /></span>
          <div><p className="font-bold">Ürün önerileri</p><p className="text-sm text-muted">Rutininize uygun ürünleri ve mağaza bağlantılarını görmek ister misiniz?</p></div>
        </div>
        <Button variant="ghost" onClick={() => setOpen(true)}><Bag size={18} /> Ürün önerilerini göster</Button>
      </Card>
    )
  }
  return (
    <Card>
      <SectionHeader icon={<Bag />} title="Ürün önerileri" subtitle="Katalogdaki uygun ürünler ve rutininize göre hazırlanmış mağaza aramaları. Satın almadan önce etiketi Ürünler sayfasındaki içerik kontrolüyle doğrulayabilirsiniz."
        action={<Button variant="ghost" className="px-3 py-1.5 text-xs" onClick={() => setOpen(false)}>Gizle</Button>} />
      {products.isPending ? <Spinner label="Öneriler hazırlanıyor…" /> : null}
      {products.data ? (
        <div className="divide-y divide-line">
          {products.data.sections.map((section) => (
            <div key={section.title} className="flex flex-wrap items-center gap-3 py-3">
              <span className="chip min-w-32 justify-center">{section.title}</span>
              {section.products.length ? (
                <div className="flex-1 space-y-1 text-sm">
                  {section.products.map((product) => (
                    <p key={product.name}><b>{product.brand} · {product.name}</b> <span className="text-muted">{product.reasons.join(' ')}</span>
                      {product.url ? <a className="ml-2 inline-flex items-center gap-1 font-semibold text-brand-700" href={product.url} target="_blank" rel="noopener noreferrer">Ürüne git <ExternalLink size={14} /></a> : null}</p>
                  ))}
                </div>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {section.search_links.map((link) => (
                    <a key={link.name} href={link.url} target="_blank" rel="noopener noreferrer" title={`${link.name} üzerinde ara`}
                      className="inline-flex items-center gap-2 rounded-full border border-line bg-surface py-1 pr-3 pl-1 text-xs font-semibold transition hover:border-brand-300 hover:shadow-sm">
                      {link.icon ? <img src={`/stores/${link.icon}`} alt="" className="size-5 rounded-md" /> : null}{link.name}
                    </a>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      ) : null}
    </Card>
  )
}

export function ReportPanel({ analysis }: { analysis: Analysis }) {
  const { profile, options } = useAppState()
  const queryClient = useQueryClient()
  const [note, setNote] = useState('')
  const [keepThumbnail, setKeepThumbnail] = useState(true)
  const save = useMutation({
    mutationFn: () => api.save(analysis.analysis_id, profile!.id, note, keepThumbnail),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['history'] }),
  })
  if (!profile) return null
  return (
    <div className="grid gap-5 md:grid-cols-2">
      <Card>
        <SectionHeader icon={<DocumentPdf />} title="Raporunuz" subtitle="Skorlar, bölgeler, kişisel rutin ve önceki kayda göre değişimi içeren görselli PDF." />
        <a className="btn-primary w-full" href={api.reportUrl(analysis.analysis_id, profile.id, 'pdf')} download><Download size={18} /> Raporu indir (PDF)</a>
        <details className="mt-4 text-sm">
          <summary className="cursor-pointer font-semibold text-muted">Diğer formatlar</summary>
          <div className="mt-3 flex gap-2">
            <a className="btn-ghost" href={api.reportUrl(analysis.analysis_id, profile.id, 'txt')} download>Metin (TXT)</a>
            <a className="btn-ghost" href={api.reportUrl(analysis.analysis_id, profile.id, 'json')} download>Veri (JSON)</a>
          </div>
        </details>
      </Card>
      {options.flags.history_enabled ? (
        <Card>
          <SectionHeader icon={<History />} title="Geçmişe kaydedin" subtitle="Zaman içindeki değişimi takip etmek için. Orijinal fotoğraf değil, sonuçlar ve küçük bir yüz önizlemesi saklanır." />
          {save.isSuccess ? (
            <Notice tone="success" icon={<CheckCircle size={18} />}>Bu analiz geçmişinize kaydedildi. Geçmiş sekmesinden görebilirsiniz.</Notice>
          ) : (
            <div className="space-y-4">
              <input className="field" value={note} maxLength={500} onChange={(event) => setNote(event.target.value)} placeholder="Not (isteğe bağlı), örn. yeni nemlendiriciye başladım" />
              <Toggle checked={keepThumbnail} onChange={setKeepThumbnail} label="Yüz önizlemesini de kaydet" hint="Önce/sonra karşılaştırması için." />
              {save.isError ? <Notice tone="error">{(save.error as Error).message}</Notice> : null}
              <Button className={clsx('w-full')} onClick={() => save.mutate()} disabled={save.isPending}>{save.isPending ? 'Kaydediliyor…' : 'Geçmişe kaydet'}</Button>
            </div>
          )}
        </Card>
      ) : null}
    </div>
  )
}
