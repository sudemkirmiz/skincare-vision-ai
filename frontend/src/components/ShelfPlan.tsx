// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Sudem Kırmız
import clsx from 'clsx'
import { useState, type ReactNode } from 'react'
import { Drop, Info, Jar, Layers, Leaf, Moon, Serum, Sun } from '../icons'
import type { PlanStep, ShelfPlan } from '../lib/types'
import { Card, Notice, SectionHeader } from './ui'

const THEME: Record<ShelfPlan['nights'][number]['theme'], { icon: ReactNode; chip: string }> = {
  retinoid: { icon: <Serum size={14} />, chip: 'border-blush-300 bg-blush-100 text-danger' },
  acid: { icon: <Drop size={14} />, chip: 'border-sand-300 bg-sand-100 text-warn-ink' },
  mask: { icon: <Jar size={14} />, chip: 'border-line-strong bg-surface-soft text-ink-soft' },
  rest: { icon: <Leaf size={14} />, chip: 'border-brand-200 bg-brand-50 text-brand-700' },
}

function Steps({ steps, empty }: { steps: PlanStep[]; empty: string }) {
  if (!steps.length) return <p className="text-sm text-muted">{empty}</p>
  return (
    <ol className="space-y-3">
      {steps.map((step, index) => (
        <li key={step.id} className="grid grid-cols-[1.75rem_1fr] gap-3">
          <span className="grid size-7 place-items-center rounded-full bg-brand-500 text-xs font-semibold text-white tabular-nums">{index + 1}</span>
          <div className="min-w-0">
            <p className="text-sm font-medium">{step.name}
              <span className="ml-2 text-xs font-normal text-muted">{step.category_label}{step.actives.length ? ` · ${step.actives.join(', ')}` : ''}</span>
            </p>
            {step.tip ? <p className="mt-0.5 text-xs leading-relaxed text-muted">{step.tip}</p> : null}
          </div>
        </li>
      ))}
    </ol>
  )
}

/** The shelf turned into a routine: application order and a 7-night active cycle. */
export function ShelfPlanCard({ plan }: { plan: ShelfPlan }) {
  const [night, setNight] = useState(() => (new Date().getDay() + 6) % 7)
  const selected = plan.nights[night]
  return (
    <Card className="p-6 sm:p-7">
      <SectionHeader icon={<Layers />} title="Raf rutinim"
        subtitle={`Rafınızdaki ürünlerle uygulama sırası ve haftalık akşam takvimi${plan.active_nights ? `: haftada ${plan.active_nights} aktif gece, aradaki geceler onarım için` : ''}.`} />
      <div className="grid gap-8 lg:grid-cols-2">
        <div>
          <p className="label mb-3 flex items-center gap-1.5"><Sun size={16} className="text-brand-600" /> Her sabah</p>
          <Steps steps={plan.morning} empty="Sabah kullanım olarak işaretli ürün yok." />
        </div>
        <div>
          <p className="label mb-3 flex items-center gap-1.5"><Moon size={16} className="text-brand-600" /> Akşam · hafta planı</p>
          <div className="no-scrollbar -mx-1 mb-4 flex gap-1.5 overflow-x-auto px-1 pb-1" role="tablist" aria-label="Gece">
            {plan.nights.map((item, index) => (
              <button key={item.day} type="button" role="tab" aria-selected={index === night} onClick={() => setNight(index)} title={item.theme_label}
                className={clsx('flex shrink-0 flex-col items-center gap-1 rounded-xl border px-2.5 py-1.5 text-xs transition',
                  index === night ? 'border-ink bg-surface font-semibold text-ink' : 'border-line bg-surface-soft text-muted hover:border-ink/40')}>
                {item.day}
                <span className={clsx('grid size-6 place-items-center rounded-full border', THEME[item.theme].chip)}>{THEME[item.theme].icon}</span>
              </button>
            ))}
          </div>
          <p className={clsx('mb-3 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium', THEME[selected.theme].chip)}>
            {THEME[selected.theme].icon}{selected.theme_label}
          </p>
          <Steps steps={selected.steps} empty="Akşam kullanım olarak işaretli ürün yok." />
        </div>
      </div>
      {plan.tips.length || plan.skipped.length || plan.as_needed.length ? (
        <div className="mt-6 space-y-2 border-t border-line pt-5">
          {plan.tips.map((tip) => <Notice key={tip} icon={<Info size={18} />}>{tip}</Notice>)}
          {plan.skipped.length ? <p className="text-xs text-muted">Plana alınmadı: {plan.skipped.map((item) => `${item.name} (${item.reason.toLocaleLowerCase('tr-TR')})`).join(', ')}.</p> : null}
          {plan.as_needed.length ? <p className="text-xs text-muted">Gerektikçe: {plan.as_needed.join(', ')}.</p> : null}
        </div>
      ) : null}
    </Card>
  )
}
