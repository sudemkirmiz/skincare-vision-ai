// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Sudem Kırmız
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { useState, type ReactNode } from 'react'
import { Alert, Bag, Cleanser, Drop, Edit, Info, Jar, Plus, Serum, ShieldSun, StatusGood, StatusPriority, StatusWatch, Trash } from '../icons'
import { ApiError, api } from '../lib/api'
import { useAppState } from '../lib/app-state'
import type { ShelfItem, ShelfItemInput, ShelfResponse } from '../lib/types'
import { Button, Card, EmptyState, Notice, Spinner } from './ui'
import { ShelfPlanCard } from './ShelfPlan'

const CATEGORY_ICON: Record<string, ReactNode> = {
  cleanser: <Cleanser size={22} />, moisturizer: <Jar size={22} />, sunscreen: <ShieldSun size={22} />,
  serum: <Serum size={22} />, exfoliant: <Drop size={22} />, other: <Bag size={22} />,
}
const VERDICT = {
  suitable: { Icon: StatusGood, color: 'text-good' },
  caution: { Icon: StatusWatch, color: 'text-mid' },
  avoid: { Icon: StatusPriority, color: 'text-priority' },
} as const
const PAO = [3, 6, 9, 12, 18, 24, 36]
const EMPTY: ShelfItemInput = { name: '', category: 'moisturizer', usage: 'both', inci: '', opened_at: null, pao_months: null }

function expiryText(item: ShelfItem) {
  if (!item.expiry) return null
  const { days_left: days, status } = item.expiry
  if (status === 'expired') return { tone: 'text-priority', text: 'Açıldıktan sonraki kullanım süresi doldu' }
  if (status === 'soon') return { tone: 'text-mid', text: `Kullanım süresinin bitmesine ${days} gün kaldı` }
  return { tone: 'text-muted', text: `Açıldıktan sonra yaklaşık ${Math.round(days / 30)} ay daha kullanılabilir` }
}

function ItemForm({ data, initial, onCancel, onSaved, editingId }: {
  data: ShelfResponse; initial: ShelfItemInput; editingId?: string; onCancel: () => void; onSaved: (result: ShelfResponse) => void
}) {
  const { profile } = useAppState()
  const [draft, setDraft] = useState(initial)
  // Local date (toISOString would be UTC and allow tomorrow in the evening hours).
  const [today] = useState(() => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` })
  const set = (patch: Partial<ShelfItemInput>) => setDraft((current) => ({ ...current, ...patch }))
  const save = useMutation({
    mutationFn: () => (editingId ? api.updateShelfItem(profile!.id, editingId, draft) : api.addShelfItem(profile!.id, draft)),
    onSuccess: onSaved,
  })
  return (
    <Card className="p-6">
      <h3 className="mb-5 text-xl font-normal">{editingId ? 'Ürünü düzenleyin' : 'Rafınıza ürün ekleyin'}</h3>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="text-sm font-medium sm:col-span-2">Ürün adı
          <input className="field mt-1.5" maxLength={80} value={draft.name} onChange={(event) => set({ name: event.target.value })} placeholder="Örn. Nemlendirici krem" />
        </label>
        <label className="text-sm font-medium">Tür
          <select className="field mt-1.5" value={draft.category} onChange={(event) => set({ category: event.target.value })}>
            {Object.entries(data.categories).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select>
        </label>
        <label className="text-sm font-medium">Ne zaman kullanıyorsunuz?
          <select className="field mt-1.5" value={draft.usage} onChange={(event) => set({ usage: event.target.value })}>
            {Object.entries(data.usages).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select>
        </label>
        <label className="text-sm font-medium sm:col-span-2">İçerik listesi (isteğe bağlı)
          <textarea className="field mt-1.5 min-h-24" maxLength={8000} value={draft.inci} onChange={(event) => set({ inci: event.target.value })} placeholder="Aqua, Glycerin, Niacinamide, …" />
          <span className="mt-1 block text-xs font-normal text-muted">Eklerseniz ürün profilinize göre kontrol edilir ve diğer ürünlerle çakışmaları bulunur.</span>
        </label>
        <label className="text-sm font-medium">Açtığınız tarih (isteğe bağlı)
          <input type="date" className="field mt-1.5" value={draft.opened_at ?? ''} max={today} onChange={(event) => set({ opened_at: event.target.value || null })} />
        </label>
        <label className="text-sm font-medium">Açıldıktan sonra kullanım süresi
          <select className="field mt-1.5" value={draft.pao_months ?? ''} onChange={(event) => set({ pao_months: event.target.value ? Number(event.target.value) : null })}>
            <option value="">Bilmiyorum</option>
            {PAO.map((months) => <option key={months} value={months}>{months} ay ({months}M)</option>)}
          </select>
          <span className="mt-1 block text-xs font-normal text-muted">Ambalajdaki açık kavanoz simgesinde yazar.</span>
        </label>
      </div>
      {save.isError ? <div className="mt-4"><Notice tone="error">{save.error instanceof ApiError ? save.error.messages.join(' ') : 'Kaydedilemedi.'}</Notice></div> : null}
      <div className="mt-6 flex gap-3">
        <Button onClick={() => save.mutate()} disabled={!draft.name.trim() || save.isPending}>{save.isPending ? 'Kaydediliyor…' : editingId ? 'Değişiklikleri kaydet' : 'Rafa ekle'}</Button>
        <Button variant="ghost" onClick={onCancel}>Vazgeç</Button>
      </div>
    </Card>
  )
}

function ItemCard({ item, onEdit, onDelete }: { item: ShelfItem; onEdit: () => void; onDelete: () => void }) {
  const verdict = item.verdict ? VERDICT[item.verdict.verdict] : null
  const expiry = expiryText(item)
  return (
    <Card className="flex flex-col p-5">
      <div className="flex items-start gap-3">
        <span className="grid size-11 shrink-0 place-items-center rounded-full border border-line bg-surface-soft text-brand-600">{CATEGORY_ICON[item.category]}</span>
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium" title={item.name}>{item.name}</p>
          <p className="text-xs text-muted">{item.category_label} · {item.usage_label}</p>
        </div>
        <button type="button" onClick={onEdit} aria-label={`${item.name} düzenle`} className="rounded-full p-1.5 text-muted hover:bg-surface-soft hover:text-ink"><Edit size={18} /></button>
        <button type="button" onClick={onDelete} aria-label={`${item.name} sil`} className="rounded-full p-1.5 text-muted hover:bg-blush-100 hover:text-danger"><Trash size={18} /></button>
      </div>
      <div className="mt-4 space-y-2 text-sm">
        {item.verdict && verdict ? (
          <p className="flex items-center gap-1.5 font-medium"><verdict.Icon size={18} className={verdict.color} />{item.verdict.verdict_label}</p>
        ) : <p className="text-xs text-muted">İçerik listesi eklenmedi; uygunluk kontrol edilmedi.</p>}
        {item.verdict?.avoid.length ? <p className="text-xs leading-relaxed text-danger">{item.verdict.avoid[0]}</p> : null}
        {item.verdict && !item.verdict.avoid.length && item.verdict.caution.length ? <p className="text-xs leading-relaxed text-warn-ink">{item.verdict.caution[0]}</p> : null}
        {item.verdict?.detected_actives.length ? (
          <div className="flex flex-wrap gap-1.5">{item.verdict.detected_actives.map((active) => <span key={active} className="chip">{active}</span>)}</div>
        ) : null}
        {expiry ? <p className={clsx('text-xs', expiry.tone)}>{expiry.text}</p> : null}
      </div>
    </Card>
  )
}

export function ShelfPanel({ prefill, onPrefillUsed }: { prefill: ShelfItemInput | null; onPrefillUsed: () => void }) {
  const { profile } = useAppState()
  const queryClient = useQueryClient()
  const shelf = useQuery({ queryKey: ['shelf', profile?.id], queryFn: () => api.shelf(profile!.id), enabled: !!profile })
  const [editing, setEditing] = useState<{ id?: string; initial: ShelfItemInput } | null>(null)
  const form = editing ?? (prefill ? { initial: prefill } : null)
  const update = (result: ShelfResponse) => { queryClient.setQueryData(['shelf', profile!.id], result); setEditing(null); onPrefillUsed() }
  const remove = useMutation({ mutationFn: (id: string) => api.deleteShelfItem(profile!.id, id), onSuccess: update })

  if (shelf.isPending) return <Spinner label="Rafınız yükleniyor…" />
  if (shelf.isError || !shelf.data) return <Notice tone="error">Raf yüklenemedi.</Notice>
  const data = shelf.data

  return (
    <div className="space-y-6">
      {form ? (
        <ItemForm key={form.id ?? 'new'} data={data} initial={form.initial} editingId={form.id} onSaved={update} onCancel={() => { setEditing(null); onPrefillUsed() }} />
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted">{data.items.length ? `${data.items.length} ürün` : 'Rafınız henüz boş.'}</p>
          <Button onClick={() => setEditing({ initial: EMPTY })}><Plus size={18} /> Ürün ekle</Button>
        </div>
      )}

      {data.notes.length || data.conflicts.length || data.gaps.length ? (
        <div className="space-y-2">
          {data.notes.map((note) => <Notice key={note} tone="error" icon={<Alert size={18} />}>{note}</Notice>)}
          {data.conflicts.map((line) => <Notice key={line} tone="warn" icon={<Alert size={18} />}>{line}</Notice>)}
          {data.gaps.map((line) => <Notice key={line} icon={<Info size={18} />}>{line}</Notice>)}
        </div>
      ) : null}

      {data.items.length ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.items.map((item) => (
            <ItemCard key={item.id} item={item} onDelete={() => remove.mutate(item.id)}
              onEdit={() => setEditing({ id: item.id, initial: { name: item.name, category: item.category, usage: item.usage, inci: item.inci, opened_at: item.opened_at, pao_months: item.pao_months } })} />
          ))}
        </div>
      ) : null}
      {data.items.length ? <ShelfPlanCard plan={data.plan} /> : !form ? (
        <EmptyState icon={<Jar size={28} />} title="Elinizdeki ürünleri ekleyin">Temizleyici, nemlendirici, güneş kremi ve serumlarınızı ekleyin; aynı akşam kullanılmaması gerekenleri, eksik adımları ve son kullanma sürelerini birlikte takip edelim.</EmptyState>
      ) : null}
    </div>
  )
}
