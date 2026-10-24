import { expect, test } from '@playwright/test'

const options = {
  skin_types: { combination: 'Karma' }, skin_type_hints: {}, skin_type_help: '',
  sensitivity: { sometimes: 'Bazen' }, sensitivity_help: '', concerns: { spots: 'Nokta' },
  age_groups: { '18_29': '18-29' }, genders: { female: 'Kadın' }, pregnancy: { no: 'Hayır' },
  allergies: {}, current_actives: {}, budgets: { mid: 'Orta' }, routine_sizes: { standard: 'Standart' },
  makeup: { unknown: 'Belirtmedim' }, sun_exposure: { unknown: 'Belirtmedim' }, address_forms: { siz: 'Siz' },
  consent_text: 'Onay', event_kinds: {}, quiz: {}, providers: ['Gemini'],
  journal: { triggers: {}, symptoms: {}, skin_feel: {}, female_only: [] }, hf_models: [], default_provider: 'Gemini',
  limits: { max_upload_mb: 10, max_views: 3 },
  flags: { history_enabled: true, second_opinion: false, allow_user_api_keys: false },
}

const profile = {
  id: 'p1', display_name: 'Ayşe', last_name: '', full_name: 'Ayşe', gender: 'female', address_form: 'siz',
  consent_at: '2026-10-25T00:00:00', answered: [], completeness: 1,
  skin: { skin_type: 'combination', sensitivity: 'sometimes', age_group: '18_29', pregnancy: 'no', concerns: ['spots'],
    allergies: [], current_actives: [], budget: 'mid', routine_size: 'standard', makeup: 'unknown', sun_exposure: 'unknown' },
}

test('loads a saved profile and exposes the primary analysis flow', async ({ page }) => {
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    const body = path === '/api/options' ? options
      : path === '/api/profiles' ? [profile]
        : path === '/api/health' ? { status: 'ok', providers: { Gemini: { has_key: false, benched: null } } }
          : path === '/api/weather/search' ? [] : {}
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: /Cildinizi/ })).toBeVisible()
  await expect(page.getByText('Merhaba, Ayşe')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Analizi başlat' })).toBeDisabled()
  await expect(page.getByRole('link', { name: 'Geçmiş' })).toBeVisible()
})

test('recovers from access-token protection', async ({ page }) => {
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/options' && route.request().headers().authorization !== 'Bearer secret') {
      await route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'Anahtar gerekli.' }) })
      return
    }
    const body = path === '/api/options' ? options : path === '/api/profiles' ? [profile] : {}
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Erişim anahtarı gerekli' })).toBeVisible()
  await page.getByLabel('Uygulama erişim anahtarı').fill('secret')
  await page.getByRole('button', { name: 'Devam et' }).click()
  await expect(page.getByText('Merhaba, Ayşe')).toBeVisible()
})

test('shows a recoverable profile-load error instead of a null-profile crash', async ({ page }) => {
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/profiles') {
      await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'DB unavailable' }) })
      return
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(path === '/api/options' ? options : {}) })
  })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Profiller yüklenemedi' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Tekrar dene' })).toBeVisible()
})
