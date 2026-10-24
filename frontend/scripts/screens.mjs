/**
 * Visual review helper: drives the app in headless Chromium and saves screenshots.
 * Needs a throwaway backend (API_TARGET) + `vite --port 5174`. Usage: node scripts/screens.mjs <step>
 */
import { chromium } from '@playwright/test'
import { resolve } from 'node:path'

const BASE = process.env.APP_URL ?? 'http://localhost:5174'
const OUT = '../outputs/screens'
const step = process.argv[2] ?? 'onboarding'

// The camera step feeds a still face as a fake webcam (outputs/fake-cam.y4m) and auto-grants permission.
const browser = await chromium.launch(step === 'camera' ? {
  args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', `--use-file-for-fake-video-capture=${resolve('../outputs/fake-cam.y4m')}`],
} : {})
const shoot = async (page, name) => page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true })

async function fillOnboarding(page) {
  await page.getByPlaceholder('Örn. Ayşe').fill('Ayşe')
  const selects = page.locator('select')
  await selects.nth(0).selectOption('18_29')
  await selects.nth(1).selectOption('female')
  await page.locator('select').nth(2).selectOption('no')
  await page.locator('select').nth(3).selectOption('combination')
  await page.locator('select').nth(4).selectOption('sometimes')
  await page.getByRole('checkbox').check()
}

try {
  for (const [label, viewport] of [['desktop', { width: 1280, height: 900 }], ['mobile', { width: 390, height: 844 }]]) {
    const page = await browser.newPage({ viewport })
    // Screenshots must never spend VLM quota: AI comments and the second opinion start disabled.
    await page.addInitScript(() => localStorage.setItem('scv.aiSettings', JSON.stringify({ provider: 'Gemini', useVlm: false, secondOpinion: false })))
    await page.goto(BASE)
    await page.waitForSelector('h1')
    if (step === 'onboarding') {
      await shoot(page, `onboarding-${label}`)
      if (label === 'desktop') {
        await page.getByRole('button', { name: 'Devam et' }).click()
        await shoot(page, 'onboarding-errors')
        await fillOnboarding(page)
        await page.locator('select').nth(3).selectOption('unknown')
        await page.getByRole('button', { name: 'Parlak / yağlı' }).first().click()
        await shoot(page, 'onboarding-quiz')
        await page.locator('select').nth(3).selectOption('combination')
        await page.getByRole('button', { name: 'Devam et' }).click()
        await shoot(page, 'onboarding-step2')
        await page.getByRole('button', { name: 'Kaydet ve başla' }).click()
        await page.waitForSelector('text=Analiz')
        await shoot(page, 'home')
      }
    } else if (step === 'analyze') {
      await page.locator('input[type=file]').setInputFiles(['../samples/01_frontal_lying.png'])
      await page.getByRole('button', { name: 'Analizi başlat' }).click()
      await page.getByRole('tab', { name: 'Özet' }).waitFor({ timeout: 90_000 })
      await shoot(page, `analyze-summary-${label}`)
      if (label === 'desktop') {
        for (const [tab, name] of [['Detaylı Analiz', 'detail'], ['Rutin', 'routine'], ['Rapor', 'report']]) {
          await page.getByRole('tab', { name: tab }).click()
          await page.waitForTimeout(300)
          if (name === 'routine') {
            await page.getByText('Haftalık akşam planını göster').click()
            await page.getByRole('button', { name: 'Ürün önerilerini göster' }).click()
            await page.waitForSelector('img[src^="/stores/"]')
          }
          await shoot(page, `analyze-${name}`)
        }
      }
    } else if (step === 'history' && label === 'desktop') {
      for (const sample of ['03_studio_frontal.png', '01_frontal_lying.png']) {
        await page.goto(BASE)
        await page.locator('input[type=file]').setInputFiles([`../samples/${sample}`])
        await page.getByRole('button', { name: 'Analizi başlat' }).click()
        await page.getByRole('tab', { name: 'Rapor' }).click({ timeout: 90_000 })
        await page.getByRole('button', { name: 'Geçmişe kaydet' }).click()
        await page.waitForSelector('text=geçmişinize kaydedildi')
      }
      await page.getByRole('link', { name: 'Geçmiş' }).click()
      await page.getByPlaceholder('Not, örn. azelaik aside başladım').fill('azelaik aside başladım')
      await page.getByRole('button', { name: 'Ekle' }).click()
      await page.waitForSelector('text=Önce / sonra')
      await page.waitForTimeout(1500)
      await shoot(page, 'history')
    } else if (step === 'checker' && label === 'desktop') {
      await page.getByRole('link', { name: 'Ürünler' }).click()
      await page.getByRole('tab', { name: 'İçerik kontrolü' }).click()
      await page.getByRole('tab', { name: 'Listeyi yapıştırın' }).click()
      await page.getByLabel('İçerik listesi (INCI)').fill('Aqua, Glycerin, Retinol, Niacinamide, Parfum, Linalool, Phenoxyethanol')
      await page.getByRole('button', { name: 'Kontrol et' }).click()
      await page.waitForSelector('text=içerik okundu')
      await shoot(page, 'checker')
    } else if (step === 'camera') {
      await page.getByRole('button', { name: 'Kamerayla rehberli çekim' }).click()
      await page.waitForSelector('video')
      await page.waitForTimeout(1500)
      await shoot(page, `camera-live-${label}`)
      await page.getByRole('button', { name: 'Bu fotoğraflarla devam et' }).waitFor({ timeout: 20_000 })
      await shoot(page, `camera-review-${label}`)
      if (label === 'desktop') {
        await page.getByRole('button', { name: 'Bu fotoğraflarla devam et' }).click()
        await page.waitForTimeout(800)
        await shoot(page, 'camera-done')
      }
    } else if (step === 'changemap') {
      await page.goto(BASE + '/gecmis')
      await page.getByRole('tab', { name: 'Önce / sonra' }).waitFor({ timeout: 30_000 })
      const section = page.locator('section', { hasText: 'Önce / sonra' })
      await section.screenshot({ path: `${OUT}/changemap-slider-${label}.png` })
      await page.getByRole('tab', { name: 'Kızarıklık' }).click()
      await section.screenshot({ path: `${OUT}/changemap-redness-${label}.png` })
    } else if (step === 'tracking') {
      await page.goto(BASE + '/takip')
      await page.getByText('Günlük kayıt').waitFor()
      await page.getByRole('button', { name: 'Yaptım' }).first().click()
      await page.getByRole('radio', { name: /İyi/ }).first().click()
      await page.getByRole('button', { name: 'Stresli gün' }).click()
      await page.getByRole('button', { name: 'Kaydet' }).click()
      await page.getByText('Kaydedildi').waitFor()
      await shoot(page, `tracking-${label}`)
    } else if (step === 'shelf') {
      await page.goto(BASE + '/urun-kontrolu')
      if (label === 'desktop') {
        for (const [name, category, usage, inci] of [
          ['Gece serumu', 'serum', 'pm', 'Aqua, Glycerin, Retinol, Tocopherol'],
          ['Arındırıcı tonik', 'exfoliant', 'pm', 'Aqua, Glycolic Acid, Glycerin, Parfum'],
          ['Nemlendirici krem', 'moisturizer', 'both', 'Aqua, Glycerin, Ceramide NP, Niacinamide, Squalane'],
        ]) {
          await page.getByRole('button', { name: 'Ürün ekle' }).click()
          await page.getByPlaceholder('Örn. Nemlendirici krem').fill(name)
          await page.locator('select').nth(0).selectOption(category)
          await page.locator('select').nth(1).selectOption(usage)
          await page.getByPlaceholder('Aqua, Glycerin, Niacinamide, …').fill(inci)
          if (name === 'Nemlendirici krem') {
            await page.locator('input[type=date]').fill('2025-11-20')
            await page.locator('select').nth(2).selectOption('12')
          }
          await page.getByRole('button', { name: 'Rafa ekle' }).click()
          await page.getByText(name).first().waitFor()
        }
      }
      await page.getByText('Gece serumu').first().waitFor()
      await shoot(page, `shelf-${label}`)
    } else if (step === 'weather') {
      if (label === 'desktop') {
        await page.getByPlaceholder('veya şehir arayın, örn. İzmir').fill('İstanbul')
        await page.getByRole('button', { name: 'Ara' }).click()
        await page.getByRole('button', { name: /İstanbul/ }).first().click()
      } else {
        await page.evaluate(() => localStorage.setItem('scv.location', JSON.stringify({ name: 'İstanbul', region: '', lat: 41, lon: 28.9 })))
        await page.reload()
      }
      await page.getByText('En yüksek UV').waitFor({ timeout: 20_000 })
      await page.locator('section', { hasText: 'Bugünün cilt hava durumu' }).screenshot({ path: `${OUT}/weather-${label}.png` })
    } else if (step === 'coach' || step === 'coach-live') {
      await page.getByRole('button', { name: 'Cilt koçunu aç' }).click()
      await page.getByText('Rafımdaki ürünleri birlikte kullanabilir miyim?').waitFor()
      await shoot(page, `coach-empty-${label}`)
      if (step === 'coach-live' && label === 'desktop') {
        // One real model call: the only live VLM request of this check.
        await page.getByText('Rafımdaki ürünleri birlikte kullanabilir miyim?').click()
        await page.getByText(/mesaj hakkı kaldı|Yanıt alınamadı|yanıt veremiyor/).waitFor({ timeout: 120_000 })
        await shoot(page, 'coach-reply')
      }
    } else if (step.startsWith('view:') && label === 'desktop') {
      // Look at an existing page without creating data, e.g. view:/gecmis
      await page.goto(BASE + step.slice(5))
      await page.waitForTimeout(2000)
      await shoot(page, 'view' + step.slice(5).replaceAll('/', '-'))
    } else if (label === 'desktop') {
      await shoot(page, `${step}-${label}`)
    }
    await page.close()
  }
} finally {
  await browser.close()
}
