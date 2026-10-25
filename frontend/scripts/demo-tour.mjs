// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Sudem Kırmız
/**
 * README media from the static demo: a recorded tour (for the GIF) and the screenshots.
 *
 *   npm run build:demo   (with VITE_BASE=/skincare-vision-ai/)
 *   npx vite preview --mode demo --outDir dist-demo --port 4180
 *   node scripts/demo-tour.mjs video   → ../outputs/demo/frames/ (crisp screencast frames), then: python scripts/make_demo_animation.py
 *   node scripts/demo-tour.mjs shots   → ../screenshots/*.png
 */
import { chromium } from '@playwright/test'
import { mkdirSync, rmSync, writeFileSync } from 'node:fs'

const BASE = process.env.DEMO_URL ?? 'http://localhost:4180/skincare-vision-ai'
const mode = process.argv[2] ?? 'video'
const SIZE = { width: 1280, height: 800 }

// Playwright videos have no pointer; draw one so viewers can follow the clicks.
const CURSOR = () => {
  const dot = document.createElement('div')
  dot.style.cssText = 'position:fixed;z-index:2147483647;left:0;top:0;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;' +
    'background:rgba(47,107,69,.35);border:2px solid #2f6b45;pointer-events:none;transition:transform .12s'
  addEventListener('mousemove', (event) => { dot.style.left = `${event.clientX}px`; dot.style.top = `${event.clientY}px` }, true)
  addEventListener('mousedown', () => { dot.style.transform = 'scale(.7)' }, true)
  addEventListener('mouseup', () => { dot.style.transform = '' }, true)
  addEventListener('DOMContentLoaded', () => document.body.append(dot))
}

const pause = (page, ms) => page.waitForTimeout(ms)

async function click(page, locator) {
  await locator.scrollIntoViewIfNeeded()
  const box = await locator.boundingBox()
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 18 })
  await pause(page, 180)
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2)
}

async function scroll(page, distance, ms = 1400) {
  const steps = Math.round(ms / 35)
  for (let i = 0; i < steps; i += 1) {
    await page.mouse.wheel(0, distance / steps)
    await pause(page, 35)
  }
}

const FRAMES = '../outputs/demo/frames'

async function video() {
  rmSync(FRAMES, { recursive: true, force: true })
  mkdirSync(FRAMES, { recursive: true })
  const browser = await chromium.launch()
  const context = await browser.newContext({ viewport: SIZE, colorScheme: 'light' })
  await context.addInitScript(CURSOR)
  const page = await context.newPage()
  // Chrome's screencast hands over each painted frame as a near-lossless JPEG with its timestamp. Playwright's own
  // video re-encodes at a low bitrate, which is what made the earlier GIF blurry.
  const cdp = await context.newCDPSession(page)
  const timings = []
  cdp.on('Page.screencastFrame', ({ data, metadata, sessionId }) => {
    const name = `${String(timings.length).padStart(5, '0')}.jpg`
    writeFileSync(`${FRAMES}/${name}`, Buffer.from(data, 'base64'))
    timings.push({ name, t: metadata.timestamp })
    void cdp.send('Page.screencastFrameAck', { sessionId }).catch(() => undefined)
  })
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 95, maxWidth: SIZE.width, maxHeight: SIZE.height, everyNthFrame: 1 })
  const tab = (name) => page.getByRole('tab', { name, exact: true })
  const nav = (name) => page.getByRole('link', { name, exact: true })
  const expand = async (title) => {
    await click(page, page.locator('summary', { hasText: title }).first())
    await pause(page, 700)
  }
  const top = () => page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }))

  // 1. Analiz: welcome and today's habit card.
  await page.goto(`${BASE}/`)
  await page.getByRole('button', { name: 'Örnek fotoğrafı analiz et' }).waitFor()
  await page.mouse.move(640, 400)
  await pause(page, 1200)
  await click(page, page.getByRole('button', { name: /Akşam rutini/ }))
  await pause(page, 900)
  await scroll(page, -700, 400)

  //    Analysis, then every result tab in order: Özet → Detaylı Analiz → Rutin → Rapor.
  await click(page, page.getByRole('button', { name: 'Örnek fotoğrafı analiz et' }))
  await page.getByRole('heading', { name: /cilt raporunuz/ }).waitFor({ timeout: 15000 })
  await pause(page, 1500)
  await scroll(page, 560, 1100)                    // Özet: care comment and photos
  await pause(page, 1500)
  await click(page, tab('Detaylı Analiz'))
  await pause(page, 900)
  await scroll(page, 420, 900)
  await expand('Bölge bazlı metrikler')
  await expand('Teknik ayrıntılar')
  await scroll(page, 360, 700)
  await pause(page, 900)
  await top()
  await pause(page, 600)
  await click(page, tab('Rutin'))
  await pause(page, 900)
  await scroll(page, 700, 1300)
  await expand('Haftalık akşam planını göster')
  await expand('Rutine başlarken')
  await click(page, page.getByRole('button', { name: /Ürün önerilerini göster/ }))
  await pause(page, 900)
  await scroll(page, 500, 900)
  await pause(page, 800)
  await top()
  await pause(page, 600)
  await click(page, tab('Rapor'))
  await pause(page, 900)
  await expand('Diğer formatlar')
  await pause(page, 900)

  // 2. Ürünler: Rafım (plan, every night in order) → İçerik kontrolü (Etiket fotoğrafı → Listeyi yapıştırın).
  await click(page, nav('Ürünler'))
  await page.getByRole('heading', { name: 'Raf rutinim' }).waitFor()
  await pause(page, 900)
  await scroll(page, 760, 1300)
  await pause(page, 500)
  for (const day of ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz']) {
    await click(page, tab(day))
    await pause(page, 450)
  }
  await top()
  await pause(page, 600)
  await click(page, tab('İçerik kontrolü'))
  await pause(page, 900)
  await click(page, tab('Etiket fotoğrafı'))
  await pause(page, 1000)
  await click(page, tab('Listeyi yapıştırın'))
  await pause(page, 500)
  await click(page, page.getByText('Demo için örnek içerik listesini ekle'))
  await pause(page, 500)
  await click(page, page.getByRole('button', { name: 'Kontrol et' }))
  await page.getByText('Dikkatli kullanın').waitFor()
  await pause(page, 500)
  await scroll(page, 520, 1000)
  await pause(page, 1100)

  // 3. Günlük Takip: the whole page.
  await click(page, nav('Günlük Takip'))
  await page.getByText('Günlük kayıt').waitFor()
  await pause(page, 1200)
  await scroll(page, 900, 1600)
  await pause(page, 700)
  await scroll(page, 900, 1400)
  await pause(page, 900)

  // 4. Geçmiş: charts → Önce / sonra → Kızarıklık → Leke → records → journey card.
  await click(page, nav('Geçmiş'))
  await page.getByText('Cilt Skoru zaman içinde').waitFor()
  await pause(page, 1200)
  await scroll(page, 1300, 1800)
  await pause(page, 500)
  const compare = tab('Önce / sonra')
  await compare.scrollIntoViewIfNeeded()
  await scroll(page, 260, 400)
  await pause(page, 600)
  const slider = page.getByRole('slider').first()
  if (await slider.count()) {
    const box = await slider.boundingBox()
    if (box) {
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 12 })
      await page.mouse.down()
      await page.mouse.move(box.x + box.width * 0.2, box.y + box.height / 2, { steps: 20 })
      await page.mouse.move(box.x + box.width * 0.8, box.y + box.height / 2, { steps: 30 })
      await page.mouse.up()
    }
  }
  await pause(page, 700)
  await click(page, tab('Kızarıklık'))
  await pause(page, 1300)
  await click(page, tab('Leke'))
  await pause(page, 1300)
  await scroll(page, 1100, 1600)
  await pause(page, 900)
  await top()
  await pause(page, 700)
  await click(page, page.getByRole('button', { name: /Yolculuk kartı/ }))
  await page.getByAltText('Cilt yolculuğu kartı önizlemesi').waitFor()
  await pause(page, 2000)
  await page.keyboard.press('Escape')
  await pause(page, 500)

  // 5. Header, left to right: theme (Sistem → Açık → Koyu) → AI settings → skincare coach, ending in dark mode.
  await click(page, nav('Analiz'))
  await pause(page, 700)
  for (let i = 0; i < 2; i += 1) {
    await click(page, page.getByRole('button', { name: /\(değiştir:/ }))
    await pause(page, 400)
  }
  await pause(page, 900)
  await click(page, page.getByRole('button', { name: 'Yapay zekâ ayarları' }))
  await pause(page, 1800)
  await page.keyboard.press('Escape')
  await pause(page, 400)
  await click(page, page.getByRole('button', { name: 'Cilt koçunu aç' }))
  await pause(page, 1800)
  await page.keyboard.press('Escape')
  await pause(page, 600)
  await scroll(page, 500, 900)
  await pause(page, 1200)

  await cdp.send('Page.stopScreencast')
  writeFileSync(`${FRAMES}/timings.json`, JSON.stringify(timings))
  await context.close()
  await browser.close()
  console.log(`frames: ${timings.length} in ${FRAMES}`)
}

async function shots() {
  const browser = await chromium.launch()
  const shoot = async (page, name, options = {}) => {
    if (options.fullPage) {
      // A sticky header would be painted wherever the page was scrolled to; pin it to the top for full-page shots.
      await page.addStyleTag({ content: 'header{position:static!important}' })
      await page.evaluate(() => window.scrollTo(0, 0))
      await pause(page, 250)
    }
    await page.screenshot({ path: `../screenshots/${name}.png`, ...options })
  }
  const desktop = async (scheme) => {
    const context = await browser.newContext({ viewport: { width: 1280, height: 860 }, colorScheme: scheme, deviceScaleFactor: 1.25 })
    return [context, await context.newPage()]
  }

  let [context, page] = await desktop('light')
  await page.goto(`${BASE}/`)
  await page.getByRole('button', { name: 'Örnek fotoğrafı analiz et' }).click()
  await page.getByRole('heading', { name: /cilt raporunuz/ }).waitFor({ timeout: 15000 })
  await pause(page, 600)
  await shoot(page, 'analiz-sonucu', { fullPage: true })
  await page.getByRole('tab', { name: 'Detaylı Analiz' }).click()
  await pause(page, 600)
  await shoot(page, 'detayli-analiz', { fullPage: true })
  await page.getByRole('tab', { name: 'Rutin' }).click()
  await pause(page, 600)
  await shoot(page, 'rutin', { fullPage: true })
  await page.getByRole('link', { name: 'Ürünler' }).click()
  await page.getByRole('heading', { name: 'Raf rutinim' }).waitFor()
  await page.getByRole('tab', { name: 'Per', exact: true }).click()
  await shoot(page, 'raf-rutinim', { fullPage: true })
  await page.getByRole('tab', { name: 'İçerik kontrolü' }).click()
  await page.getByText('Demo için örnek içerik listesini ekle').click()
  await page.getByRole('button', { name: 'Kontrol et' }).click()
  await pause(page, 900)
  await shoot(page, 'icerik-kontrolu', { fullPage: true })
  await page.getByRole('link', { name: 'Günlük Takip' }).click()
  await page.getByText('Günlük kayıt').waitFor()
  await pause(page, 500)
  await shoot(page, 'gunluk-takip', { fullPage: true })
  await page.getByRole('link', { name: 'Geçmiş' }).click()
  await page.getByText('Cilt Skoru zaman içinde').waitFor()
  await pause(page, 1200)
  await shoot(page, 'gecmis', { fullPage: true })
  await page.getByRole('button', { name: /Yolculuk kartı/ }).click()
  const card = page.getByAltText('Cilt yolculuğu kartı önizlemesi')
  await card.waitFor()
  // The page's CSP (connect-src 'self') blocks fetch() of blob: URLs, so copy the rendered image through a canvas.
  const dataUrl = await card.evaluate(async (img) => {
    await img.decode()
    const canvas = Object.assign(document.createElement('canvas'), { width: img.naturalWidth, height: img.naturalHeight })
    canvas.getContext('2d').drawImage(img, 0, 0)
    return canvas.toDataURL('image/png')
  })
  writeFileSync('../screenshots/yolculuk-karti.png', Buffer.from(dataUrl.split(',')[1], 'base64'))
  await page.keyboard.press('Escape')
  // Skincare coach panel with its suggested questions (answers need a real provider, so none is sent).
  await page.getByRole('button', { name: 'Cilt koçunu aç' }).click()
  await page.getByRole('dialog', { name: 'Cilt koçu' }).waitFor()
  await pause(page, 600)
  await shoot(page, 'cilt-kocu')
  await page.keyboard.press('Escape')
  await page.getByRole('dialog', { name: 'Cilt koçu' }).waitFor({ state: 'hidden' }).catch(() => undefined)
  // Profile editor (opens without saving anything).
  await page.getByRole('button', { name: /Helin/ }).click()
  await page.getByRole('menuitem', { name: 'Profili düzenle' }).click()
  await pause(page, 600)
  await shoot(page, 'profil', { fullPage: true })
  await context.close()

  ;[context, page] = await desktop('dark')
  await page.goto(`${BASE}/`)
  await page.getByRole('button', { name: 'Örnek fotoğrafı analiz et' }).waitFor()
  await pause(page, 500)
  await shoot(page, 'koyu-tema')
  await context.close()

  for (const [name, path] of [['mobil-analiz', '/'], ['mobil-takip', '/takip']]) {
    const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, colorScheme: 'dark', isMobile: true, hasTouch: true })
    const tab = await mobile.newPage()
    await tab.goto(`${BASE}${path}`)
    if (path === '/') {
      await tab.getByRole('button', { name: 'Örnek fotoğrafı analiz et' }).click()
      await tab.getByRole('heading', { name: /cilt raporunuz/ }).waitFor({ timeout: 15000 })
    } else {
      await tab.getByText('Günlük kayıt').waitFor()
    }
    await pause(tab, 600)
    await tab.screenshot({ path: `../screenshots/${name}.png` })
    await mobile.close()
  }
  await browser.close()
  console.log('screenshots written to ../screenshots')
}

await (mode === 'shots' ? shots() : video())
