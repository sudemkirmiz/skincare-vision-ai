import { useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { Alert, CheckCircle, Edit, LogoMark, Plus, Sliders, Trash } from '../icons'
import { api } from '../lib/api'
import { useAppState } from '../lib/app-state'
import { Button, Drawer, Progress, Toggle } from './ui'
import { CoachLauncher } from './Coach'

const NAV = [
  { to: '/', label: 'Analiz', short: 'Analiz', needsHistory: false },
  { to: '/urun-kontrolu', label: 'Ürünler', short: 'Ürünler', needsHistory: false },
  { to: '/takip', label: 'Günlük Takip', short: 'Takip', needsHistory: true },
  { to: '/gecmis', label: 'Geçmiş', short: 'Geçmiş', needsHistory: true },
]

function initials(name: string) {
  return name.split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toLocaleUpperCase('tr-TR')
}

function AiSettingsDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { options, ai, setAi, providerKeys, setProviderKey } = useAppState()
  const keyName = { Gemini: 'Gemini API anahtarı', 'Hugging Face': 'HF token', Groq: 'Groq API anahtarı' }[ai.provider] ?? 'API anahtarı'
  const health = useQuery({ queryKey: ['health'], queryFn: api.health, enabled: open, refetchInterval: open ? 15000 : false })
  return (
    <Drawer open={open} onClose={onClose} title="Yapay zekâ ayarları">
      <div className="space-y-6">
        <div>
          <label className="label" htmlFor="provider">Yorum sağlayıcısı</label>
          <select id="provider" className="field mt-1.5" value={ai.provider} onChange={(event) => setAi({ provider: event.target.value })}>
            {options.providers.map((provider) => <option key={provider}>{provider}</option>)}
          </select>
          <p className="mt-1.5 text-xs leading-relaxed text-muted">Seçili sağlayıcı hata verirse anahtarı olan diğerleri otomatik denenir. Sunucudaki anahtarlar tarayıcıya gönderilmez.</p>
        </div>
        {ai.provider === 'Hugging Face' ? (
          <div>
            <label className="label" htmlFor="hf-model">Hugging Face modeli</label>
            <select id="hf-model" className="field mt-1.5" value={ai.hfModel} onChange={(event) => setAi({ hfModel: event.target.value })}>
              {options.hf_models.map((model) => <option key={model}>{model}</option>)}
            </select>
          </div>
        ) : null}
        {options.flags.allow_user_api_keys ? (
          <div>
            <label className="label" htmlFor="provider-key">{keyName} (isteğe bağlı)</label>
            <input id="provider-key" type="password" autoComplete="off" className="field mt-1.5" placeholder="Boş bırakırsanız sunucudaki anahtar kullanılır"
              value={providerKeys[ai.provider] ?? ''} onChange={(event) => setProviderKey(ai.provider, event.target.value)} />
            <p className="mt-1.5 text-xs leading-relaxed text-muted">Yalnızca bu sekme açıkken bellekte tutulur; hiçbir yere kaydedilmez.</p>
          </div>
        ) : null}
        <Toggle checked={ai.useVlm} onChange={(useVlm) => setAi({ useVlm })} label="Yapay zekâ yorumu üret" hint="Kapalıyken cilt skoru, bölgeler ve rutin yine hesaplanır." />
        <Toggle
          checked={ai.secondOpinion && ai.useVlm}
          disabled={!ai.useVlm}
          onChange={(secondOpinion) => setAi({ secondOpinion })}
          label="Gemini ile ikinci görüş"
          hint="Noktaları Gemini ayrıca işaretler; yanlış alarmları eler, kaçırılanları ekler. Tek fotoğraflı analizde +1 Gemini çağrısı."
        />
        <div>
          <p className="label mb-2">Sağlayıcı durumu</p>
          <ul className="space-y-2">
            {options.providers.map((provider) => {
              const state = health.data?.providers[provider]
              const ok = state?.has_key && !state.benched
              return (
                <li key={provider} className="flex items-center justify-between rounded-xl border border-line bg-surface px-3 py-2 text-sm">
                  <span className="font-medium">{provider}</span>
                  <span className={clsx('flex items-center gap-1.5 text-xs font-semibold', ok ? 'text-brand-700' : 'text-danger')}>
                    {ok ? <CheckCircle size={16} /> : <Alert size={16} />}
                    {!state ? '…' : !state.has_key ? 'anahtar yok' : state.benched ? `${state.benched.label} (~${Math.max(1, Math.round(state.benched.seconds_left / 60))} dk)` : 'hazır'}
                  </span>
                </li>
              )
            })}
          </ul>
        </div>
      </div>
    </Drawer>
  )
}

function ProfileMenu() {
  const { profile, profiles, selectProfile, openEditor, refreshProfiles } = useAppState()
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const menu = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const onClick = (event: MouseEvent) => !menu.current?.contains(event.target as Node) && setOpen(false)
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [open])
  if (!profile) return null

  const remove = async () => {
    await api.deleteProfile(profile.id)
    setConfirmDelete(false)
    setOpen(false)
    await queryClient.invalidateQueries()
    await refreshProfiles()
  }

  return (
    <div className="relative" ref={menu}>
      <button type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open} aria-haspopup="menu"
        className="flex items-center gap-2 rounded-full py-1 pr-1 pl-1 transition hover:bg-surface sm:pr-3">
        <span className="grid size-8 place-items-center rounded-full bg-brand-500 text-xs font-semibold tracking-wide text-white">{initials(profile.full_name)}</span>
        <span className="hidden text-sm font-medium sm:block">{profile.display_name}</span>
      </button>
      {open ? (
        <div role="menu" className="card absolute right-0 z-40 mt-2 w-72 p-3 shadow-[var(--shadow-lift)]">
          <Progress value={profile.completeness} label="Profil dolu" />
          {profile.completeness < 1 ? <p className="mt-1 text-xs text-muted">Tüm alanları doldurursanız sonuçlar daha isabetli olur.</p> : null}
          <div className="my-3 h-px bg-line" />
          {profiles.length > 1 ? (
            <>
              <p className="label mb-1 px-1">Profil değiştir</p>
              {profiles.map((item) => (
                <button key={item.id} type="button" role="menuitem" onClick={() => { selectProfile(item.id); setOpen(false) }}
                  className={clsx('flex w-full items-center justify-between rounded-xl px-2 py-2 text-left text-sm hover:bg-surface-soft', item.id === profile.id && 'font-semibold text-brand-700')}>
                  {item.full_name}
                  {item.id === profile.id ? <CheckCircle size={16} /> : null}
                </button>
              ))}
              <div className="my-2 h-px bg-line" />
            </>
          ) : null}
          <button type="button" role="menuitem" className="flex w-full items-center gap-2 rounded-xl px-2 py-2 text-sm hover:bg-surface-soft" onClick={() => { openEditor('edit'); setOpen(false) }}>
            <Edit size={18} /> Profili düzenle
          </button>
          <button type="button" role="menuitem" className="flex w-full items-center gap-2 rounded-xl px-2 py-2 text-sm hover:bg-surface-soft" onClick={() => { openEditor('new'); setOpen(false) }}>
            <Plus size={18} /> Yeni profil
          </button>
          {confirmDelete ? (
            <div className="mt-2 rounded-xl border border-blush-300 bg-blush-100 p-3 text-xs text-danger">
              <p>Profil, tüm geçmiş kayıtları ve önizlemeleriyle kalıcı olarak silinecek.</p>
              <div className="mt-2 flex gap-2">
                <Button variant="ghost" className="px-3 py-1.5 text-xs" onClick={() => setConfirmDelete(false)}>Vazgeç</Button>
                <button type="button" className="btn bg-priority px-3 py-1.5 text-xs text-white" onClick={remove}>Kalıcı olarak sil</button>
              </div>
            </div>
          ) : (
            <button type="button" role="menuitem" className="flex w-full items-center gap-2 rounded-xl px-2 py-2 text-sm text-danger hover:bg-blush-100" onClick={() => setConfirmDelete(true)}>
              <Trash size={18} /> Profili sil
            </button>
          )}
        </div>
      ) : null}
    </div>
  )
}

export function Layout({ children }: { children: ReactNode }) {
  const { options } = useAppState()
  const [settingsOpen, setSettingsOpen] = useState(false)
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-line bg-canvas/90 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-3 px-4 sm:gap-6 sm:px-6">
          <NavLink to="/" className="flex shrink-0 items-center gap-2.5 text-ink" aria-label="SkinCare Vision AI ana sayfa">
            <LogoMark size={28} className="text-brand-700" />
            <span className="hidden leading-none md:block">
              <span className="font-display text-[19px] tracking-tight">SkinCare Vision</span>
              <span className="ml-1 align-super text-[9px] font-semibold tracking-[0.18em] text-brand-600">AI</span>
            </span>
          </NavLink>
          <nav className="flex h-full flex-1 justify-center gap-4 sm:gap-8" aria-label="Ana menü">
            {NAV.filter((item) => !item.needsHistory || options.flags.history_enabled).map((item) => (
              <NavLink key={item.to} to={item.to} end={item.to === '/'}
                className={({ isActive }) => clsx('-mb-px flex h-full shrink-0 items-center border-b-2 text-[13px] font-medium transition-colors sm:text-sm',
                  isActive ? 'border-ink text-ink' : 'border-transparent text-muted hover:text-ink')}>
                <span className="sm:hidden">{item.short}</span><span className="hidden sm:inline">{item.label}</span>
              </NavLink>
            ))}
          </nav>
          <div className="flex shrink-0 items-center gap-1">
            <button type="button" onClick={() => setSettingsOpen(true)} aria-label="Yapay zekâ ayarları" title="Yapay zekâ ayarları"
              className="grid size-9 place-items-center rounded-full text-muted transition hover:bg-surface hover:text-ink">
              <Sliders size={20} />
            </button>
            <ProfileMenu />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-12">{children}</main>
      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 pt-6 pb-24 text-xs leading-relaxed text-muted sm:flex-row sm:items-center sm:justify-between sm:px-6 sm:pb-6">
          <p className="flex items-center gap-2"><LogoMark size={16} className="text-brand-600" /> SkinCare Vision AI · görsel bakım ön değerlendirmesi</p>
          <p className="max-w-xl sm:text-right">Tıbbi tanı koymaz. Ağrı, hızlı değişim veya endişe varsa dermatoloğa danışın.</p>
        </div>
      </footer>
      <AiSettingsDrawer open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <CoachLauncher />
    </div>
  )
}
