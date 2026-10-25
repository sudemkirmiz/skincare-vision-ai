// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Sudem Kırmız
import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Download, Share } from '../icons'
import { api } from '../lib/api'
import { useAppState } from '../lib/app-state'
import type { HistoryRecord } from '../lib/types'
import { Button, Drawer, Spinner, Toggle } from './ui'

/*
 * A shareable "skin journey" image drawn on a canvas in the browser. It carries scores, dates and the
 * routine streak only: never a face photo, and the name only when the user leaves it on.
 */
const W = 1080
const H = 1350
const C = { canvas: '#f4f9f4', surface: '#ffffff', ink: '#24342b', soft: '#3f5046', muted: '#68766d', line: '#ddebde', brand: '#4caf50', deep: '#2f6b45', tint: '#dcefde', blush: '#f0c8be' }
// Same geometry as LogoMark and public/brand/logo-tile.svg.
const DROP = 'M30 10.6C35.4 16.2 46 26.6 46 38.4A16 16 0 0 1 14 38.4C14 26.6 24.6 16.2 30 10.6Z'
const SPARKLE = 'M30 29.6C31.84 36.96 31.84 36.96 39.2 38.8C31.84 40.64 31.84 40.64 30 48C28.16 40.64 28.16 40.64 20.8 38.8C28.16 36.96 28.16 36.96 30 29.6Z'
const SPARKLE_SMALL = 'M50.6 8C51.68 12.32 51.68 12.32 56 13.4C51.68 14.48 51.68 14.48 50.6 18.8C49.52 14.48 49.52 14.48 45.2 13.4C49.52 12.32 49.52 12.32 50.6 8Z'
const SERIF = "'Fraunces Variable', Georgia, serif"
const SANS = "'Inter Variable', system-ui, sans-serif"

interface JourneyData {
  name: string | null
  scores: { date: string; score: number }[]
  analyses: number
  bestStreak: number
}

const date = (value: string) => new Date(value).toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' })

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath()
  ctx.roundRect(x, y, w, h, r)
}

function logo(ctx: CanvasRenderingContext2D, x: number, y: number, size: number) {
  ctx.save()
  ctx.translate(x, y)
  ctx.scale(size / 64, size / 64)
  ctx.fillStyle = '#edf6ee'
  roundRect(ctx, 0, 0, 64, 64, 15)
  ctx.fill()
  ctx.translate(32, 32)
  ctx.scale(0.94, 0.94)
  ctx.translate(-31, -33)
  const drop = new Path2D(DROP)
  ctx.fillStyle = C.brand
  ctx.fill(drop)
  ctx.lineWidth = 4.4
  ctx.lineJoin = 'round'
  ctx.strokeStyle = C.deep
  ctx.stroke(drop)
  ctx.fillStyle = '#ffffff'
  ctx.fill(new Path2D(SPARKLE))
  ctx.fillStyle = C.brand
  ctx.fill(new Path2D(SPARKLE_SMALL))
  ctx.restore()
}

async function drawJourney(canvas: HTMLCanvasElement, data: JourneyData) {
  // Make sure the brand fonts are ready; the canvas would silently fall back otherwise.
  await Promise.all([document.fonts.load(`400 80px ${SERIF}`), document.fonts.load(`600 38px ${SERIF}`), document.fonts.load(`600 32px ${SANS}`)]).catch(() => undefined)
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')!
  ctx.fillStyle = C.canvas
  ctx.fillRect(0, 0, W, H)
  for (const [x, y, r, color] of [[0, 0, 620, 'rgba(165,214,167,0.45)'], [W, 0, 520, 'rgba(240,200,190,0.4)']] as const) {
    const glow = ctx.createRadialGradient(x, y, 0, x, y, r)
    glow.addColorStop(0, color)
    glow.addColorStop(1, 'rgba(244,249,244,0)')
    ctx.fillStyle = glow
    ctx.fillRect(0, 0, W, H)
  }

  logo(ctx, 80, 70, 76)
  ctx.textBaseline = 'alphabetic'
  ctx.fillStyle = C.ink
  ctx.font = `600 38px ${SERIF}`
  ctx.fillText('SkinCare', 174, 108)
  ctx.fillStyle = C.deep
  ctx.font = `600 17px ${SANS}`
  ctx.letterSpacing = '4px'
  ctx.fillText('VİSİON AI', 176, 136)
  ctx.letterSpacing = '0px'

  const first = data.scores[0]
  const last = data.scores[data.scores.length - 1]
  const delta = last.score - first.score
  ctx.textBaseline = 'alphabetic'
  ctx.fillStyle = C.deep
  ctx.font = `600 22px ${SANS}`
  ctx.fillText((data.name ? `${data.name} · cilt yolculuğu` : 'Cilt yolculuğum').toLocaleUpperCase('tr-TR'), 80, 250)
  ctx.fillStyle = C.ink
  ctx.font = `400 76px ${SERIF}`
  const headline = delta > 0 ? `Cilt Skoru ${delta} puan arttı.` : delta === 0 ? 'Cilt Skoru korunuyor.' : 'Yolculuk devam ediyor.'
  ctx.fillText(headline, 80, 340, W - 160)
  ctx.fillStyle = C.muted
  ctx.font = `400 28px ${SANS}`
  ctx.fillText(`${date(first.date)} – ${date(last.date)}`, 80, 395)

  // Score card: before → after.
  ctx.fillStyle = C.surface
  roundRect(ctx, 80, 450, W - 160, 300, 28)
  ctx.fill()
  ctx.strokeStyle = C.line
  ctx.lineWidth = 2
  ctx.stroke()
  const column = (x: number, label: string, value: string, color: string) => {
    ctx.fillStyle = C.muted
    ctx.font = `600 20px ${SANS}`
    ctx.fillText(label.toLocaleUpperCase('tr-TR'), x, 520)
    ctx.fillStyle = color
    ctx.font = `400 150px ${SERIF}`
    ctx.fillText(value, x - 6, 680)
  }
  column(130, 'İlk analiz', String(first.score), C.soft)
  column(420, 'Son analiz', String(last.score), C.ink)
  ctx.fillStyle = delta >= 0 ? C.tint : '#fbefeb'
  roundRect(ctx, 730, 560, 230, 96, 48)
  ctx.fill()
  ctx.fillStyle = delta >= 0 ? C.deep : '#8a4238'
  ctx.font = `600 52px ${SANS}`
  ctx.textAlign = 'center'
  ctx.fillText(`${delta > 0 ? '+' : ''}${delta}`, 845, 627)
  ctx.textAlign = 'left'

  // Sparkline of every scored analysis.
  const top = 820
  const height = 220
  const left = 110
  const width = W - 220
  ctx.strokeStyle = C.line
  ctx.lineWidth = 2
  for (const level of [0, 0.5, 1]) {
    ctx.beginPath()
    ctx.moveTo(left, top + height * level)
    ctx.lineTo(left + width, top + height * level)
    ctx.stroke()
  }
  const values = data.scores.map((item) => item.score)
  const min = Math.max(0, Math.min(...values) - 8)
  const max = Math.min(100, Math.max(...values) + 8)
  const point = (index: number) => [
    left + (data.scores.length === 1 ? width / 2 : (index / (data.scores.length - 1)) * width),
    top + height - ((values[index] - min) / Math.max(1, max - min)) * height,
  ]
  const area = ctx.createLinearGradient(0, top, 0, top + height)
  area.addColorStop(0, 'rgba(76,175,80,0.28)')
  area.addColorStop(1, 'rgba(76,175,80,0)')
  ctx.beginPath()
  values.forEach((_, index) => (index ? ctx.lineTo(...(point(index) as [number, number])) : ctx.moveTo(...(point(index) as [number, number]))))
  ctx.lineTo(point(values.length - 1)[0], top + height)
  ctx.lineTo(point(0)[0], top + height)
  ctx.closePath()
  ctx.fillStyle = area
  ctx.fill()
  ctx.beginPath()
  values.forEach((_, index) => (index ? ctx.lineTo(...(point(index) as [number, number])) : ctx.moveTo(...(point(index) as [number, number]))))
  ctx.strokeStyle = C.brand
  ctx.lineWidth = 6
  ctx.lineJoin = 'round'
  ctx.stroke()
  values.forEach((_, index) => {
    const [x, y] = point(index)
    ctx.beginPath()
    ctx.arc(x, y, index === values.length - 1 ? 13 : 9, 0, Math.PI * 2)
    ctx.fillStyle = C.surface
    ctx.fill()
    ctx.lineWidth = 5
    ctx.strokeStyle = index === values.length - 1 ? C.deep : C.brand
    ctx.stroke()
  })

  // Stat chips.
  const stats = [[`${data.analyses}`, 'analiz'], [`${Math.max(1, Math.round((+new Date(last.date) - +new Date(first.date)) / 86_400_000))}`, 'gün'], [`${data.bestStreak}`, 'gün en uzun rutin serisi']]
  let x = 80
  ctx.font = `600 26px ${SANS}`
  for (const [value, label] of stats) {
    ctx.font = `600 26px ${SANS}`
    const valueWidth = ctx.measureText(value).width
    ctx.font = `400 24px ${SANS}`
    const chip = valueWidth + ctx.measureText(label).width + 60
    ctx.fillStyle = C.surface
    roundRect(ctx, x, 1110, chip, 64, 32)
    ctx.fill()
    ctx.strokeStyle = C.line
    ctx.lineWidth = 2
    ctx.stroke()
    ctx.fillStyle = C.ink
    ctx.font = `600 26px ${SANS}`
    ctx.fillText(value, x + 24, 1151)
    ctx.fillStyle = C.soft
    ctx.font = `400 24px ${SANS}`
    ctx.fillText(label, x + 34 + valueWidth, 1151)
    x += chip + 14
  }

  ctx.fillStyle = C.muted
  ctx.font = `400 20px ${SANS}`
  ctx.fillText('Görsel bakım ön değerlendirmesidir, tıbbi tanı değildir. Bu görsel fotoğraf içermez.', 80, 1270, W - 160)
}

export function JourneyShare({ records }: { records: HistoryRecord[] }) {
  const { profile } = useAppState()
  const [open, setOpen] = useState(false)
  const [withName, setWithName] = useState(true)
  const [image, setImage] = useState<{ url: string; blob: Blob } | null>(null)
  const journal = useQuery({ queryKey: ['journal', profile?.id], queryFn: () => api.journal(profile!.id), enabled: open && !!profile })
  const scores = records.filter((record) => record.overall_score !== null).map((record) => ({ date: record.created_at, score: record.overall_score! }))
  const bestStreak = journal.data?.summary?.routine?.best ?? 0

  useEffect(() => {
    if (!open || scores.length < 2 || journal.isPending) return
    let cancelled = false
    let url = ''
    const canvas = document.createElement('canvas')
    void drawJourney(canvas, { name: withName ? profile?.display_name ?? null : null, scores, analyses: records.length, bestStreak }).then(() =>
      canvas.toBlob((blob) => {
        if (!blob || cancelled) return
        url = URL.createObjectURL(blob)
        setImage({ url, blob })
      }, 'image/png'))
    return () => {
      cancelled = true
      if (url) URL.revokeObjectURL(url)
      setImage(null)
    }
    // scores is derived from records on every render; records identity is the real dependency.
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [open, withName, records, bestStreak, journal.isPending, profile?.display_name])

  if (scores.length < 2) return null
  const file = image ? new File([image.blob], 'cilt-yolculugum.png', { type: 'image/png' }) : null
  const canShare = !!file && typeof navigator.canShare === 'function' && navigator.canShare({ files: [file] })

  return (
    <>
      <Button variant="ghost" onClick={() => setOpen(true)}><Share size={18} /> Yolculuk kartı</Button>
      <Drawer open={open} onClose={() => { setOpen(false); setImage(null) }} title="Cilt yolculuğu kartı">
        <div className="space-y-5">
          <p className="text-sm leading-relaxed text-muted">İlk ve son analiziniz arasındaki değişimi gösteren paylaşılabilir bir görsel. Yüz fotoğrafı içermez.</p>
          <Toggle checked={withName} onChange={setWithName} label="Adım görünsün" hint="Kapalıyken kartta yalnızca “Cilt yolculuğum” yazar." />
          <div className="overflow-hidden rounded-xl border border-line bg-surface-soft">
            {image ? <img src={image.url} alt="Cilt yolculuğu kartı önizlemesi" className="block w-full" /> : <div className="grid aspect-[4/5] place-items-center"><Spinner label="Kart hazırlanıyor…" /></div>}
          </div>
          <div className="flex flex-wrap gap-2">
            {canShare ? <Button onClick={() => void navigator.share({ files: [file!], title: 'Cilt yolculuğum' }).catch(() => undefined)}><Share size={18} /> Paylaş</Button> : null}
            {image ? <a className={canShare ? 'btn-ghost' : 'btn-primary'} href={image.url} download="cilt-yolculugum.png"><Download size={18} /> PNG indir</a> : null}
          </div>
        </div>
      </Drawer>
    </>
  )
}
