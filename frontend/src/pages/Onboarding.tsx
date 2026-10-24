import { useMutation, useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { useState, type ReactNode } from 'react'
import { ArrowLeft, CheckCircle, Info, LogoMark, ShieldSun, Sparkles, UserCircle } from '../icons'
import { ApiError, api } from '../lib/api'
import { useAppState } from '../lib/app-state'
import type { Dict, Profile, ProfileInput } from '../lib/types'
import { Button, Card, Notice, Progress } from '../components/ui'

const OPTIONAL = ['last_name', 'address_form', 'concerns', 'current_actives', 'allergies', 'budget', 'routine_size', 'makeup', 'sun_exposure'] as const
const REQUIRED_COUNT = 7

function draftFrom(profile: Profile | null): ProfileInput {
  if (!profile) {
    return {
      display_name: '', last_name: '', gender: null, address_form: 'siz', consent: false, answered: [],
      skin: { skin_type: undefined, sensitivity: undefined, age_group: undefined, pregnancy: null, concerns: [], allergies: [], current_actives: [], budget: 'mid', routine_size: 'standard', makeup: 'unknown', sun_exposure: 'unknown' },
    }
  }
  return { display_name: profile.display_name, last_name: profile.last_name, gender: profile.gender, address_form: profile.address_form, consent: true, answered: profile.answered, skin: { ...profile.skin } }
}

function Hint({ text }: { text: string }) {
  // Hover (or keyboard focus) shows the explanation without clicking.
  return (
    <span className="group relative inline-flex align-middle">
      <span tabIndex={0} className="ml-1 cursor-help text-muted hover:text-brand-700 focus:text-brand-700" aria-label="Açıklama"><Info size={16} /></span>
      <span role="tooltip" className="pointer-events-none absolute top-6 left-1/2 z-20 hidden w-72 -translate-x-1/2 rounded-xl border border-line bg-surface p-3 text-xs leading-relaxed whitespace-pre-line text-ink normal-case shadow-[var(--shadow-lift)] group-hover:block group-focus-within:block">
        {text.replaceAll('**', '')}
      </span>
    </span>
  )
}

function Field({ label, required, hint, children }: { label: string; required?: boolean; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 flex items-center text-sm font-medium text-ink">
        {label}{required ? <span className="ml-0.5 text-priority">*</span> : null}{hint ? <Hint text={hint} /> : null}
      </span>
      {children}
    </label>
  )
}

function Select({ value, options, onChange, hints, placeholder = 'Seçin' }: { value: string | null | undefined; options: Dict; onChange: (value: string) => void; hints?: Dict; placeholder?: string }) {
  return (
    <select className={clsx('field', !value && 'text-muted')} value={value ?? ''} onChange={(event) => onChange(event.target.value)}>
      <option value="" disabled>{placeholder}</option>
      {Object.entries(options).map(([key, label]) => <option key={key} value={key}>{hints?.[key] ? `${label} · ${hints[key]}` : label}</option>)}
    </select>
  )
}

function Chips({ value, options, onChange }: { value: string[]; options: Dict; onChange: (value: string[]) => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      {Object.entries(options).map(([key, label]) => {
        const active = value.includes(key)
        return (
          <button key={key} type="button" aria-pressed={active} onClick={() => onChange(active ? value.filter((item) => item !== key) : [...value, key])}
            className={clsx('rounded-full border px-3 py-1.5 text-sm transition', active ? 'border-brand-500 bg-brand-500 text-white' : 'border-line-strong bg-surface text-ink hover:border-ink/40')}>
            {label}
          </button>
        )
      })}
    </div>
  )
}

export function Onboarding({ mode }: { mode: 'first' | 'edit' | 'new' }) {
  const { options, profile, closeEditor, refreshProfiles, selectProfile } = useAppState()
  const [step, setStep] = useState<1 | 2>(1)
  const [draft, setDraft] = useState<ProfileInput>(() => draftFrom(mode === 'edit' ? profile : null))
  const [quiz, setQuiz] = useState<Record<string, string | null>>({ t_zone: null, cheeks: null, blotting: null })
  const [errors, setErrors] = useState<string[]>([])
  const answered = new Set(draft.answered)
  const set = (patch: Partial<ProfileInput>) => setDraft((current) => ({ ...current, ...patch }))
  const setSkin = (patch: Partial<ProfileInput['skin']>) => setDraft((current) => ({ ...current, skin: { ...current.skin, ...patch } }))
  const markAnswered = (key: (typeof OPTIONAL)[number], filled: boolean) => {
    const next = new Set(answered)
    if (filled) next.add(key)
    else next.delete(key)
    set({ answered: [...next] })
  }

  const quizResult = useQuery({
    queryKey: ['quiz', quiz],
    queryFn: () => api.quiz(quiz),
    enabled: draft.skin.skin_type === 'unknown' && Object.values(quiz).every(Boolean),
  })
  const pregnancyApplies = draft.gender === 'female' || draft.gender === 'other'

  const save = useMutation({
    mutationFn: async () => {
      const skinType = draft.skin.skin_type === 'unknown' && quizResult.data?.skin_type ? quizResult.data.skin_type : draft.skin.skin_type
      const input: ProfileInput = { ...draft, skin: { ...draft.skin, skin_type: skinType, pregnancy: pregnancyApplies ? draft.skin.pregnancy : 'no' } }
      return mode === 'edit' && profile ? api.updateProfile(profile.id, input) : api.createProfile(input)
    },
    onSuccess: async (saved) => {
      await refreshProfiles()
      selectProfile(saved.id)
      closeEditor()
    },
    onError: (error) => {
      setErrors(error instanceof ApiError ? error.messages : ['Profil kaydedilemedi; lütfen tekrar deneyin.'])
      setStep(1)
    },
  })

  const validateStepOne = () => {
    const missing: string[] = []
    if (draft.display_name.trim().length < 2) missing.push('Adınızı (veya takma adınızı) yazın; en az 2 harf.')
    if (!draft.skin.age_group) missing.push('Yaş aralığınızı seçin.')
    if (!draft.gender) missing.push('Cinsiyetinizi seçin (“Diğer / belirtmek istemiyorum” da seçebilirsiniz).')
    if (!draft.skin.skin_type) missing.push('Cilt tipinizi seçin ya da “Bilmiyorum” deyip kısa testi doldurun.')
    if (!draft.skin.sensitivity) missing.push('Cildinizin hassasiyet durumunu seçin.')
    if (pregnancyApplies && !draft.skin.pregnancy) missing.push('Hamilelik/emzirme sorusunu yanıtlayın (“Belirtmek istemiyorum” da seçebilirsiniz).')
    if (!draft.consent) missing.push('Devam etmek için fotoğraf işleme onayını işaretleyin.')
    setErrors(missing)
    if (!missing.length) setStep(2)
  }

  const share = (REQUIRED_COUNT + draft.answered.length) / (REQUIRED_COUNT + OPTIONAL.length)
  const title = { first: 'Hoş geldiniz', edit: 'Profilinizi düzenleyin', new: 'Yeni profil' }[mode]
  const subtitle = {
    first: 'Size özel analiz ve bakım önerileri için sizi biraz tanıyalım. Bilgileriniz bizde güvenle saklanır; dilediğiniz zaman silebilirsiniz.',
    edit: 'Değişiklikler sonraki analizlerde ve rutininizde hemen kullanılır.',
    new: 'Başka biri için ayrı bir profil ve geçmiş oluşturun.',
  }[mode]

  return (
    <div className="mx-auto max-w-3xl pt-8 pb-16 sm:pt-12">
      <div className="mb-10 flex items-center gap-2.5">
        <LogoMark size={28} className="text-brand-700" />
        <span className="font-display text-[19px] tracking-tight">SkinCare Vision</span>
        <span className="text-[9px] font-semibold tracking-[0.18em] text-brand-600">AI</span>
      </div>
      <div className="mb-8">
        <div className="mb-5 flex max-w-xs gap-1.5" aria-hidden>
          {[1, 2].map((index) => <span key={index} className={clsx('h-1 flex-1 rounded-full', index <= step ? 'bg-brand-500' : 'bg-line')} />)}
        </div>
        <p className="eyebrow">Adım {step} / 2</p>
        <h1 className="mt-3 text-[36px] leading-tight font-normal sm:text-[44px]">{title}</h1>
        <p className="mt-3 max-w-xl text-base leading-relaxed text-ink-soft">{subtitle}</p>
      </div>

      {errors.length ? (
        <div className="mb-5"><Notice tone="error">{errors.map((error) => <div key={error}>• {error}</div>)}</Notice></div>
      ) : null}

      {step === 1 ? (
        <Card className="p-6 sm:p-8">
          <div className="mb-6 flex items-center gap-3 border-b border-line pb-5"><UserCircle className="text-brand-700" /><h2 className="text-xl font-normal">Temel bilgiler</h2><span className="chip ml-auto">zorunlu</span></div>
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Adınız (veya takma adınız)" required hint="Yorumlarda size bu adla hitap edilir. Takma ad da olur.">
              <input className="field" value={draft.display_name} maxLength={40} onChange={(event) => set({ display_name: event.target.value })} placeholder="Örn. Ayşe" />
            </Field>
            <Field label="Yaş aralığınız" required hint="18 yaş altında bazı içerikler önerilmez.">
              <Select value={draft.skin.age_group} options={options.age_groups} onChange={(age_group) => setSkin({ age_group })} />
            </Field>
            <Field label="Cinsiyetiniz" required hint="Yalnızca hamilelik sorusunun size uygun olup olmadığını belirlemek için kullanılır.">
              <Select value={draft.gender} options={options.genders} onChange={(gender) => set({ gender })} />
            </Field>
            {pregnancyApplies ? (
              <Field label="Hamile misiniz veya emziriyor musunuz?" required hint="Bazı içerikler bu dönemde önerilmez. “Belirtmek istemiyorum” seçerseniz ihtiyatlı davranırız.">
                <Select value={draft.skin.pregnancy} options={options.pregnancy} onChange={(pregnancy) => setSkin({ pregnancy })} />
              </Field>
            ) : <div className="hidden sm:block" />}
            <Field label="Cilt tipiniz" required hint={options.skin_type_help}>
              <Select value={draft.skin.skin_type} options={options.skin_types} hints={options.skin_type_hints} onChange={(skin_type) => setSkin({ skin_type })} />
            </Field>
            <Field label="Cildiniz hassas mı?" required hint={options.sensitivity_help}>
              <Select value={draft.skin.sensitivity} options={options.sensitivity} onChange={(sensitivity) => setSkin({ sensitivity })} />
            </Field>
          </div>

          {draft.skin.skin_type === 'unknown' ? (
            <div className="mt-6 rounded-xl border border-line bg-surface-soft p-5">
              <p className="mb-4 flex items-center gap-2 font-display text-lg"><Sparkles size={20} className="text-brand-700" /> Cilt tipinizi birlikte bulalım</p>
              <div className="space-y-4">
                {Object.entries(options.quiz).map(([key, item]) => (
                  <fieldset key={key}>
                    <legend className="mb-2 text-sm font-medium">{item.question}</legend>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(item.options).map(([value, label]) => (
                        <button key={value} type="button" aria-pressed={quiz[key] === value} onClick={() => setQuiz((current) => ({ ...current, [key]: value }))}
                          className={clsx('rounded-full border px-3.5 py-1.5 text-sm transition', quiz[key] === value ? 'border-brand-500 bg-brand-500 text-white' : 'border-line-strong bg-surface hover:border-ink/40')}>
                          {label}
                        </button>
                      ))}
                    </div>
                  </fieldset>
                ))}
              </div>
              {quizResult.data?.label ? (
                <p className="mt-4 flex items-center gap-2 text-sm font-semibold text-brand-700"><CheckCircle size={18} /> Cevaplarınıza göre cildiniz büyük olasılıkla: {quizResult.data.label}</p>
              ) : <p className="mt-4 text-xs text-muted">Üç soruyu da yanıtlarsanız cilt tipinizi tahmin ederiz; yanıtlamazsanız “Bilmiyorum” olarak kalır.</p>}
            </div>
          ) : null}

          <label className="mt-6 flex cursor-pointer gap-3 rounded-xl border border-line bg-surface-soft p-4 text-sm leading-relaxed">
            <input type="checkbox" className="mt-1 size-4 accent-brand-600" checked={draft.consent} onChange={(event) => set({ consent: event.target.checked })} />
            <span><ShieldSun size={18} className="mr-1 inline text-brand-600" />{options.consent_text}<span className="text-priority"> *</span></span>
          </label>

          <div className="mt-6 flex flex-wrap gap-3">
            <Button onClick={validateStepOne}>Devam et</Button>
            {mode !== 'first' ? <Button variant="ghost" onClick={closeEditor}>Vazgeç</Button> : null}
          </div>
        </Card>
      ) : (
        <Card className="p-6 sm:p-8">
          <div className="mb-2 flex items-center gap-3"><Sparkles className="text-brand-700" /><h2 className="text-xl font-normal">Daha isabetli sonuç için</h2><span className="chip ml-auto">isteğe bağlı</span></div>
          <p className="mb-6 border-b border-line pb-5 text-sm text-muted">Bu alanlar isteğe bağlıdır, ancak hepsini doldurursanız rutin, ürün ve yorumlar çok daha isabetli olur.</p>
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Soyadınız" hint="Sadece PDF raporda görünür; yapay zekâ servisine gönderilmez.">
              <input className="field" value={draft.last_name} maxLength={40} onChange={(event) => { set({ last_name: event.target.value }); markAnswered('last_name', Boolean(event.target.value.trim())) }} />
            </Field>
            <Field label="Yapay zekâ yorumlarında hitap">
              <Select value={draft.address_form} options={options.address_forms} onChange={(address_form) => { set({ address_form }); markAnswered('address_form', true) }} />
            </Field>
            <Field label="Makyaj kullanıyor musunuz?">
              <Select value={draft.skin.makeup} options={options.makeup} onChange={(makeup) => { setSkin({ makeup }); markAnswered('makeup', makeup !== 'unknown') }} />
            </Field>
            <Field label="Gün içinde güneşe ne kadar maruz kalıyorsunuz?">
              <Select value={draft.skin.sun_exposure} options={options.sun_exposure} onChange={(sun_exposure) => { setSkin({ sun_exposure }); markAnswered('sun_exposure', sun_exposure !== 'unknown') }} />
            </Field>
            <Field label="Ürün bütçeniz">
              <Select value={draft.skin.budget} options={options.budgets} onChange={(budget) => { setSkin({ budget }); markAnswered('budget', true) }} />
            </Field>
            <Field label="Rutin uzunluğu">
              <Select value={draft.skin.routine_size} options={options.routine_sizes} onChange={(routine_size) => { setSkin({ routine_size }); markAnswered('routine_size', true) }} />
            </Field>
          </div>
          <div className="mt-5 space-y-5">
            <Field label="Hedefleriniz"><Chips value={draft.skin.concerns ?? []} options={options.concerns} onChange={(concerns) => { setSkin({ concerns }); markAnswered('concerns', concerns.length > 0) }} /></Field>
            <Field label="Şu an kullandığınız aktifler"><Chips value={draft.skin.current_actives ?? []} options={options.current_actives} onChange={(current_actives) => { setSkin({ current_actives }); markAnswered('current_actives', current_actives.length > 0) }} /></Field>
            <Field label="Bilinen hassasiyetiniz/alerjiniz"><Chips value={draft.skin.allergies ?? []} options={options.allergies} onChange={(allergies) => { setSkin({ allergies }); markAnswered('allergies', allergies.length > 0) }} /></Field>
          </div>
          <div className="mt-6"><Progress value={share} label="Profiliniz dolu" /></div>
          <div className="mt-6 flex flex-wrap gap-3">
            <Button variant="ghost" onClick={() => setStep(1)}><ArrowLeft size={18} /> Geri</Button>
            <Button onClick={() => save.mutate()} disabled={save.isPending}>{save.isPending ? 'Kaydediliyor…' : 'Kaydet ve başla'}</Button>
          </div>
        </Card>
      )}
    </div>
  )
}
