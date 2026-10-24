import clsx from 'clsx'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Camera, CheckCircle, Close, FaceScan, Plus } from '../icons'
import { api } from '../lib/api'
import type { CaptureCheck } from '../lib/types'
import { Button } from './ui'

type Target = 'front' | 'side'
interface Shot { file: File; url: string; target: Target; yaw: number | null }

/** Consecutive good preview frames before the photo is taken automatically (~1.5 s). */
const READY_STREAK = 3
const CHECK_INTERVAL_MS = 450
const PREVIEW_WIDTH = 360
// Face guide oval (rx 98, ry 132 around 150,190), drawn from the top clockwise so progress starts at 12 o'clock.
const OVAL = 'M150 58 A98 132 0 1 1 150 322 A98 132 0 1 1 150 58'

export function cameraSupported() {
  return typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia && window.isSecureContext
}

function cameraError(error: unknown) {
  const name = error instanceof DOMException ? error.name : ''
  if (name === 'NotAllowedError') return 'Kamera izni verilmedi. Adres çubuğundaki kamera simgesinden izin verip tekrar deneyin.'
  if (name === 'NotFoundError' || name === 'OverconstrainedError') return 'Kullanılabilir bir kamera bulunamadı.'
  if (name === 'NotReadableError') return 'Kamera başka bir uygulama tarafından kullanılıyor olabilir.'
  return 'Kamera açılamadı; fotoğraf yükleyerek devam edebilirsiniz.'
}

function grab(video: HTMLVideoElement, width: number, quality: number): Promise<Blob | null> {
  const scale = width / video.videoWidth
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(video.videoWidth * scale)
  canvas.height = Math.round(video.videoHeight * scale)
  canvas.getContext('2d')!.drawImage(video, 0, 0, canvas.width, canvas.height)
  return new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', quality))
}

export function CameraCapture({ maxShots, onClose, onDone }: { maxShots: number; onClose: () => void; onDone: (files: File[]) => void }) {
  const video = useRef<HTMLVideoElement>(null)
  const [stream, setStream] = useState<MediaStream | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [shots, setShots] = useState<Shot[]>([])
  const [target, setTarget] = useState<Target | null>('front')
  const [guide, setGuide] = useState<CaptureCheck | null>(null)
  const [streak, setStreak] = useState(0)
  const [flash, setFlash] = useState(false)
  // Read inside the guidance loop without restarting it on every update.
  const lastYaw = useRef<number | null>(null)
  const shotsRef = useRef<Shot[]>([])
  useEffect(() => { shotsRef.current = shots }, [shots])

  // Open the front camera once; stop every track when the dialog closes.
  useEffect(() => {
    let active: MediaStream | null = null
    let cancelled = false
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: 'user', width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false })
      .then((media) => {
        if (cancelled) return media.getTracks().forEach((track) => track.stop())
        active = media
        setStream(media)
      })
      .catch((reason) => setError(cameraError(reason)))
    return () => {
      cancelled = true
      active?.getTracks().forEach((track) => track.stop())
    }
  }, [])

  useEffect(() => {
    if (video.current && stream) video.current.srcObject = stream
  }, [stream, target])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const sideSign = (() => {
    const yaw = shots.find((shot) => shot.target === 'side')?.yaw
    return yaw ? Math.sign(yaw) : 0
  })()

  const capture = useCallback(async () => {
    const element = video.current
    if (!element || !target || !element.videoWidth) return
    const blob = await grab(element, element.videoWidth, 0.92)
    if (!blob) return
    const index = shots.length + 1
    const file = new File([blob], `kamera-${index}-${target === 'front' ? 'onden' : 'yandan'}.jpg`, { type: 'image/jpeg' })
    setFlash(true)
    setTimeout(() => setFlash(false), 180)
    setShots((current) => [...current, { file, url: URL.createObjectURL(blob), target, yaw: lastYaw.current }])
    setTarget(null)
    setStreak(0)
    setGuide(null)
  }, [shots.length, target])
  const captureRef = useRef(capture)
  useEffect(() => { captureRef.current = capture }, [capture])

  // Live guidance: one small frame in flight at a time; never stored on the server.
  useEffect(() => {
    if (!stream || !target) return
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    let streakNow = 0
    const tick = async () => {
      const element = video.current
      if (element?.videoWidth) {
        try {
          const blob = await grab(element, PREVIEW_WIDTH, 0.7)
          if (blob) {
            const result = await api.captureCheck(blob, target, target === 'side' ? sideSign : 0, controller.signal)
            // Without the face model only lighting is known, so the user takes the photo.
            streakNow = result.ok && result.guide_available ? streakNow + 1 : 0
            lastYaw.current = result.pose?.yaw ?? null
            setGuide(result)
            setStreak(streakNow)
            if (streakNow >= READY_STREAK) return captureRef.current()
          }
        } catch {
          if (controller.signal.aborted) return
        }
      }
      timer = setTimeout(tick, CHECK_INTERVAL_MS)
    }
    timer = setTimeout(tick, 600)
    return () => {
      controller.abort()
      clearTimeout(timer)
    }
  }, [stream, target, sideSign])

  // Object URLs are released only when the dialog closes; the review grid still shows them.
  useEffect(() => () => shotsRef.current.forEach((shot) => URL.revokeObjectURL(shot.url)), [])

  const ready = guide?.ok && guide.guide_available
  const progress = Math.min(1, streak / READY_STREAK)
  const finish = () => onDone(shots.map((shot) => shot.file))
  const title = target === 'front' ? 'Önden fotoğraf' : target === 'side' ? 'Yan açı' : 'Fotoğraflarınız'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/70 sm:p-6" role="dialog" aria-modal="true" aria-label="Kamerayla çekim">
      <div className="flex h-full w-full flex-col overflow-hidden bg-[#0f1612] text-white sm:h-auto sm:max-w-xl sm:rounded-[var(--radius-card)]">
        <div className="flex items-center justify-between px-5 py-4">
          <div>
            <p className="text-[11px] font-semibold tracking-[0.14em] text-brand-300 uppercase">Rehberli çekim · {Math.min(shots.length + (target ? 1 : 0), maxShots)} / {maxShots}</p>
            <h2 className="mt-1 text-xl font-normal">{title}</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Kapat" className="rounded-full p-2 text-white/70 hover:bg-white/10 hover:text-white"><Close /></button>
        </div>

        {error ? (
          <div className="m-5 rounded-xl bg-white/10 p-5 text-sm leading-relaxed">{error}</div>
        ) : target ? (
          <div className="relative flex-1 bg-black sm:flex-none">
            <video ref={video} autoPlay playsInline muted className="h-full max-h-[68vh] w-full -scale-x-100 object-cover sm:aspect-[3/4]" />
            {!stream ? <p className="absolute inset-0 grid place-items-center text-sm text-white/70">Kamera açılıyor…</p> : null}
            <svg viewBox="0 0 300 400" preserveAspectRatio="xMidYMid slice" className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden>
              {/* A very wide stroke dims everything outside the oval. */}
              <ellipse cx="150" cy="190" rx="398" ry="432" fill="none" stroke="rgb(0 0 0 / 0.45)" strokeWidth="600" />
              <path d={OVAL} fill="none" stroke={ready ? '#66b26f' : 'rgb(255 255 255 / 0.75)'} strokeWidth="2.5" strokeDasharray={ready ? undefined : '6 6'} />
              {progress > 0 ? (
                <path d={OVAL} fill="none" stroke="#4caf50" strokeWidth="5" strokeLinecap="round" pathLength={100} strokeDasharray={`${progress * 100} 100`} />
              ) : null}
            </svg>
            {flash ? <div className="absolute inset-0 bg-white/80" /> : null}
            <div className="absolute inset-x-0 bottom-0 p-4">
              <p className={clsx('mx-auto w-fit max-w-full rounded-full px-4 py-2 text-center text-sm font-medium backdrop-blur', ready ? 'bg-brand-500/90 text-white' : 'bg-black/60 text-white')} aria-live="polite">
                {guide?.message ?? (target === 'side' ? 'Başınızı yavaşça bir yana çevirin.' : 'Yüzünüzü oval çerçevenin içine getirin.')}
              </p>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-3 p-5">
            {shots.map((shot) => (
              <figure key={shot.url}>
                <img src={shot.url} alt={shot.target === 'front' ? 'Önden fotoğraf' : 'Yan açı'} className="aspect-[3/4] w-full rounded-lg object-cover" />
                <figcaption className="mt-1.5 flex items-center gap-1 text-xs text-white/70"><CheckCircle size={14} className="text-brand-300" />{shot.target === 'front' ? 'Önden' : 'Yandan'}</figcaption>
              </figure>
            ))}
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
          {error ? (
            <Button variant="ghost" className="ml-auto border-white/30 text-white hover:border-white/60 hover:bg-white/10" onClick={onClose}>Fotoğraf yükleyerek devam et</Button>
          ) : target ? (
            <>
              <p className="max-w-[16rem] text-xs leading-relaxed text-white/60">Her şey uygun olduğunda fotoğraf kendiliğinden çekilir. Görüntü kaydedilmez; yalnızca anlık kontrol edilir.</p>
              <Button onClick={capture} disabled={!stream} className="bg-none bg-white text-ink shadow-none hover:bg-white/90"><Camera size={18} /> Şimdi çek</Button>
            </>
          ) : (
            <>
              {shots.length < maxShots ? (
                <Button variant="ghost" className="border-white/30 text-white hover:border-white/60 hover:bg-white/10" onClick={() => setTarget('side')}><Plus size={18} /> Yan açı ekle</Button>
              ) : <span />}
              <Button onClick={finish}><FaceScan size={18} /> Bu fotoğraflarla devam et</Button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
