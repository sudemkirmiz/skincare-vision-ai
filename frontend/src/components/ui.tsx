import clsx from 'clsx'
/* oxlint-disable react/only-export-components -- the UI kit intentionally exports one pure score helper */
import { useEffect, useId, useRef, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { Close, Info, StatusGood, StatusMid, StatusPriority, StatusWatch } from '../icons'

export function Card({ className, children, as: Tag = 'section' }: { className?: string; children: ReactNode; as?: 'section' | 'div' | 'article' }) {
  return <Tag className={clsx('card p-5', className)}>{children}</Tag>
}

export function SectionHeader({ icon, title, subtitle, action }: { icon?: ReactNode; title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="mb-5 flex items-start justify-between gap-4">
      <div className="flex items-start gap-3">
        {icon ? <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-full border border-line bg-surface-soft text-brand-700 [&_svg]:size-[18px]">{icon}</span> : null}
        <div>
          <h2 className="text-xl font-medium text-ink">{title}</h2>
          {subtitle ? <p className="mt-1 max-w-prose text-sm leading-relaxed text-muted">{subtitle}</p> : null}
        </div>
      </div>
      {action}
    </div>
  )
}

export function Button({ variant = 'primary', className, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'ghost' }) {
  return <button type="button" className={clsx(variant === 'primary' ? 'btn-primary' : 'btn-ghost', className)} {...rest} />
}

// Score status: shape + colour + word, never colour alone (same thresholds as the backend).
const STATUS = [
  { min: 75, label: 'İyi', Icon: StatusGood, color: 'text-good' },
  { min: 55, label: 'Orta', Icon: StatusMid, color: 'text-mid' },
  { min: 35, label: 'Dikkat', Icon: StatusWatch, color: 'text-watch' },
  { min: 0, label: 'Öncelikli', Icon: StatusPriority, color: 'text-priority' },
] as const

export function scoreStatus(score: number) {
  return STATUS.find((status) => score >= status.min) ?? STATUS[STATUS.length - 1]
}

export function StatusBadge({ score, className }: { score: number; className?: string }) {
  const { label, Icon, color } = scoreStatus(score)
  return (
    <span className={clsx('inline-flex items-center gap-1 text-sm font-medium text-ink', className)}>
      <Icon size={18} className={color} />
      {label}
    </span>
  )
}

export function Meter({ value, label, hint }: { value: number | null; label: string; hint?: string }) {
  if (value === null) {
    return (
      <div title={hint}>
        <div className="mb-2 flex justify-between text-sm"><span>{label}</span><span className="text-muted">ölçülmedi</span></div>
        <div className="h-1.5 rounded-full bg-line" />
      </div>
    )
  }
  const { color } = scoreStatus(value)
  return (
    <div title={hint}>
      <div className="mb-2 flex items-center justify-between text-sm">
        <span className="text-ink-soft">{label}</span>
        <span className="flex items-center gap-2.5"><span className="font-semibold tabular-nums">{value}</span><StatusBadge score={value} className="w-[5.5rem] text-xs text-muted" /></span>
      </div>
      <div className={clsx('h-1.5 overflow-hidden rounded-full bg-line', color)} role="meter" aria-valuenow={value} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
        <div className="h-full rounded-full bg-current" style={{ width: `${Math.max(2, value)}%` }} />
      </div>
    </div>
  )
}

export function Notice({ tone = 'info', children, icon }: { tone?: 'info' | 'warn' | 'error' | 'success'; children: ReactNode; icon?: ReactNode }) {
  const styles = {
    info: 'border-line bg-surface-soft text-ink-soft',
    warn: 'border-sand-300 bg-sand-100 text-warn-ink',
    error: 'border-blush-300 bg-blush-100 text-danger',
    success: 'border-brand-100 bg-brand-50 text-brand-800',
  }[tone]
  return (
    <div className={clsx('flex gap-2.5 rounded-xl border px-4 py-3 text-sm leading-relaxed', styles)} role={tone === 'error' ? 'alert' : undefined}>
      <span className="mt-0.5 shrink-0">{icon ?? <Info size={18} />}</span>
      <div className="min-w-0 whitespace-pre-line">{children}</div>
    </div>
  )
}

export function Tabs<T extends string>({ tabs, value, onChange, label }: { tabs: { id: T; label: string; icon?: ReactNode }[]; value: T; onChange: (id: T) => void; label: string }) {
  return (
    <div role="tablist" aria-label={label} className="no-scrollbar flex gap-1 overflow-x-auto overflow-y-hidden border-b border-line sm:gap-6">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={tab.id === value}
          onClick={() => onChange(tab.id)}
          className={clsx(
            // On phones all tabs share the row (icons hidden) so none is pushed out of view.
            '-mb-px flex flex-1 shrink-0 items-center justify-center gap-2 border-b-2 px-1 py-3 text-[13px] font-medium whitespace-nowrap transition-colors sm:flex-none sm:text-sm',
            tab.id === value ? 'border-ink text-ink' : 'border-transparent text-muted hover:text-ink',
          )}
        >
          <span className="hidden sm:contents">{tab.icon}</span>
          {tab.label}
        </button>
      ))}
    </div>
  )
}

export function Toggle({ checked, onChange, label, hint, disabled }: { checked: boolean; onChange: (value: boolean) => void; label: string; hint?: string; disabled?: boolean }) {
  const id = useId()
  return (
    <label htmlFor={id} className={clsx('flex cursor-pointer items-start justify-between gap-4', disabled && 'cursor-not-allowed opacity-50')}>
      <span>
        <span className="block text-sm font-medium text-ink">{label}</span>
        {hint ? <span className="block text-xs leading-relaxed text-muted">{hint}</span> : null}
      </span>
      <span className="relative mt-0.5 inline-flex shrink-0">
        <input id={id} type="checkbox" className="peer sr-only" checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} />
        <span className="h-6 w-11 rounded-full bg-line-strong transition peer-checked:bg-brand-500 peer-focus-visible:ring-4 peer-focus-visible:ring-brand-100" />
        <span className="absolute top-0.5 left-0.5 size-5 rounded-full bg-white shadow-sm transition peer-checked:translate-x-5" />
      </span>
    </label>
  )
}

export function Drawer({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  const panel = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    panel.current?.focus()
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-ink/30" onClick={onClose}>
      <div
        ref={panel}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="h-full w-full max-w-md overflow-y-auto border-l border-line bg-canvas p-7 shadow-[var(--shadow-lift)] outline-none"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-7 flex items-center justify-between border-b border-line pb-4">
          <h2 className="text-2xl font-normal">{title}</h2>
          <button type="button" className="rounded-full p-2 text-muted hover:bg-surface-soft hover:text-ink" onClick={onClose} aria-label="Kapat">
            <Close />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

export function Progress({ value, label }: { value: number; label: string }) {
  return (
    <div>
      <div className="mb-1.5 flex justify-between text-xs font-medium text-muted"><span>{label}</span><span>%{Math.round(value * 100)}</span></div>
      <div className="h-1.5 overflow-hidden rounded-full bg-line" role="progressbar" aria-valuenow={Math.round(value * 100)} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
        <div className="h-full rounded-full bg-brand-500 transition-all" style={{ width: `${value * 100}%` }} />
      </div>
    </div>
  )
}

export function EmptyState({ icon, title, children }: { icon: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center rounded-[var(--radius-card)] border border-dashed border-line-strong px-6 py-14 text-center">
      <span className="mb-4 grid size-14 place-items-center rounded-full border border-line bg-surface text-brand-700">{icon}</span>
      <h3 className="text-xl font-normal">{title}</h3>
      {children ? <div className="mt-1.5 max-w-sm text-sm leading-relaxed text-muted">{children}</div> : null}
    </div>
  )
}

export function Spinner({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-muted" role="status">
      <span className="size-4 animate-spin rounded-full border-2 border-line border-t-brand-700" />
      {label}
    </span>
  )
}

/** Thin ring gauge for a 0-100 score; the status word sits beside it, so colour is never the only signal. */
export function ScoreRing({ value, size = 132 }: { value: number | null; size?: number }) {
  const stroke = 6
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const filled = value === null ? 0 : (Math.max(0, Math.min(100, value)) / 100) * circumference
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} role="img" aria-label={value === null ? 'Cilt Skoru ölçülemedi' : `Cilt Skoru 100 üzerinden ${value}`}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--color-line)" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--color-brand-500)" strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={`${filled} ${circumference}`} />
      </svg>
      <span className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-display text-[44px] leading-none tabular-nums">{value ?? '–'}</span>
        <span className="mt-1 text-[11px] text-muted">/ 100</span>
      </span>
    </div>
  )
}
