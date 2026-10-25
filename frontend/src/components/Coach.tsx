// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Sudem Kırmız
import { useMutation, useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Close, Sparkles } from '../icons'
import { ApiError, api } from '../lib/api'
import { useAppState } from '../lib/app-state'
import type { ChatMessage } from '../lib/types'
import { readLocation } from './WeatherCard'

/** Light formatting for model text: "- " / "• " / "1." lines become a list, ** markers are dropped. */
function Formatted({ text }: { text: string }) {
  const lines = text.replace(/\*\*/g, '').split('\n').map((line) => line.trim()).filter(Boolean)
  return (
    <div className="space-y-1.5">
      {lines.map((line, index) => {
        const bullet = line.match(/^(?:[-•*]|\d+[.)])\s+(.*)$/)
        return bullet
          ? <p key={index} className="flex gap-2"><span className="text-brand-600">•</span><span>{bullet[1]}</span></p>
          : <p key={index}>{line}</p>
      })}
    </div>
  )
}

function CoachPanel({ onClose, messages, setMessages }: { onClose: () => void; messages: ChatMessage[]; setMessages: (next: ChatMessage[]) => void }) {
  const { profile, ai, providerKeys } = useAppState()
  const [draft, setDraft] = useState('')
  const [meta, setMeta] = useState<{ provider: string; remaining: number; filtered: boolean } | null>(null)
  const list = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const suggestions = useQuery({ queryKey: ['coach-suggestions'], queryFn: api.coachSuggestions, staleTime: Infinity })
  const place = readLocation()
  // Same query as the weather card, so it is usually already cached.
  const weather = useQuery({
    queryKey: ['weather', place?.lat, place?.lon, profile?.id],
    queryFn: () => api.weather(place!.lat, place!.lon, profile?.id),
    enabled: !!place, staleTime: 30 * 60_000, retry: false,
  })

  const send = useMutation({
    mutationFn: (history: ChatMessage[]) => api.coach(profile!.id, ai.provider, history,
      weather.data ? { uv_max: weather.data.uv_max, temperature: weather.data.temperature, humidity: weather.data.humidity } : null,
      providerKeys[ai.provider]),
    onSuccess: (result, history) => {
      setMessages([...history, { role: 'assistant', content: result.reply }])
      setMeta({ provider: result.provider, remaining: result.remaining, filtered: result.filtered })
    },
  })

  const submit = (text: string) => {
    const content = text.trim()
    if (!content || send.isPending) return
    const history: ChatMessage[] = [...messages, { role: 'user', content }]
    setMessages(history)
    setDraft('')
    send.mutate(history)
  }

  useEffect(() => { list.current?.scrollTo({ top: list.current.scrollHeight, behavior: 'smooth' }) }, [messages, send.isPending])
  useEffect(() => {
    input.current?.focus()
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-ink/30" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label="Cilt koçu" onClick={(event) => event.stopPropagation()}
        className="flex h-full w-full max-w-md flex-col border-l border-line bg-canvas shadow-[var(--shadow-lift)]">
        <div className="flex items-center justify-between border-b border-line px-5 py-4">
          <div className="flex items-center gap-3">
            <span className="grid size-9 place-items-center rounded-full bg-gradient-to-br from-brand-400 to-brand-600 text-white"><Sparkles size={18} /></span>
            <div>
              <h2 className="text-xl leading-tight font-normal">Cilt koçu</h2>
              <p className="text-xs text-muted">Profilinizi, rutininizi, rafınızı ve günlüğünüzü bilir</p>
            </div>
          </div>
          <button type="button" onClick={onClose} aria-label="Kapat" className="rounded-full p-2 text-muted hover:bg-surface-soft hover:text-ink"><Close /></button>
        </div>

        <div ref={list} className="flex-1 space-y-4 overflow-y-auto px-5 py-5" aria-live="polite">
          {!messages.length ? (
            <div className="space-y-4">
              <p className="text-sm leading-relaxed text-ink-soft">Merhaba {profile?.display_name}! Rutininiz, ürünleriniz veya günlük bakımınız hakkında sorun. Kısa ve size özel yanıt vermeye çalışırım.</p>
              <div className="flex flex-col items-start gap-2">
                {(suggestions.data ?? []).map((question) => (
                  <button key={question} type="button" onClick={() => submit(question)}
                    className="rounded-full border border-line-strong bg-surface px-3.5 py-1.5 text-left text-sm transition hover:border-brand-400">{question}</button>
                ))}
              </div>
            </div>
          ) : null}
          {messages.map((message, index) => (
            <div key={index} className={clsx('flex', message.role === 'user' ? 'justify-end' : 'justify-start')}>
              <div className={clsx('max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed', message.role === 'user'
                ? 'rounded-br-md bg-brand-500 text-white' : 'rounded-bl-md border border-line bg-surface text-ink')}>
                {message.role === 'assistant' ? <Formatted text={message.content} /> : message.content}
              </div>
            </div>
          ))}
          {send.isPending ? (
            <div className="flex gap-1.5 px-2" role="status" aria-label="Yanıt yazılıyor">
              {[0, 1, 2].map((dot) => <span key={dot} className="size-2 animate-bounce rounded-full bg-brand-400" style={{ animationDelay: `${dot * 150}ms` }} />)}
            </div>
          ) : null}
          {send.isError ? (
            <p className="rounded-xl border border-blush-300 bg-blush-100 px-4 py-3 text-sm whitespace-pre-line text-danger">
              {send.error instanceof ApiError ? send.error.messages.join('\n') : 'Yanıt alınamadı; lütfen tekrar deneyin.'}
            </p>
          ) : null}
        </div>

        <form onSubmit={(event: FormEvent) => { event.preventDefault(); submit(draft) }} className="border-t border-line px-5 py-4">
          <div className="flex items-end gap-2">
            <textarea ref={input} rows={2} maxLength={600} value={draft} onChange={(event) => setDraft(event.target.value)} aria-label="Mesajınız"
              onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); submit(draft) } }}
              placeholder="Sorunuzu yazın…" className="field min-h-11 resize-none" />
            <button type="submit" disabled={!draft.trim() || send.isPending} className="btn-primary h-11 shrink-0 px-4">Gönder</button>
          </div>
          <p className="mt-2 text-[11px] leading-relaxed text-muted">
            Tıbbi tavsiye değildir. Sohbet kaydedilmez{meta ? ` · ${meta.provider} · bugün ${meta.remaining} mesaj hakkı kaldı` : ''}.
            {meta?.filtered ? ' Yanıtın bir kısmı güvenlik nedeniyle çıkarıldı.' : ''}
          </p>
        </form>
      </div>
    </div>
  )
}

export function CoachLauncher() {
  const [open, setOpen] = useState(false)
  // Kept here so the conversation survives page changes; never written to storage.
  const [messages, setMessages] = useState<ChatMessage[]>([])
  return (
    <>
      {!open ? (
        <button type="button" onClick={() => setOpen(true)} aria-label="Cilt koçunu aç"
          className="fixed right-4 bottom-4 z-40 flex items-center gap-2 rounded-full bg-gradient-to-br from-brand-400 to-brand-600 px-4 dark:from-[#4caf50] dark:to-[#2e7d32] py-3 text-sm font-medium text-white shadow-[0_12px_30px_rgb(76_175_80/0.35)] transition hover:shadow-[0_16px_36px_rgb(76_175_80/0.45)] sm:right-6 sm:bottom-6">
          <Sparkles size={18} /> Cilt koçu
        </button>
      ) : null}
      {open ? <CoachPanel onClose={() => setOpen(false)} messages={messages} setMessages={setMessages} /> : null}
    </>
  )
}
