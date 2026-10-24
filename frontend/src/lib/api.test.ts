import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api } from './api'

function mockFetch(status: number, body: unknown) {
  const response = new Response(typeof body === 'string' ? body : JSON.stringify(body), { status })
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(response)
}

afterEach(() => vi.restoreAllMocks())

describe('api error handling', () => {
  it('passes the backend message through', async () => {
    mockFetch(404, { detail: 'Profil bulunamadı.' })
    await expect(api.profiles()).rejects.toMatchObject({ status: 404, messages: ['Profil bulunamadı.'] })
  })

  it('keeps every validation error from the analysis endpoint', async () => {
    mockFetch(400, { detail: { errors: ['Dosya çok büyük.', 'Desteklenmeyen biçim.'] } })
    const error = await api.profiles().catch((e) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error.messages).toEqual(['Dosya çok büyük.', 'Desteklenmeyen biçim.'])
  })

  it('falls back to a generic Turkish message for non-JSON bodies', async () => {
    mockFetch(502, '<html>Bad gateway</html>')
    await expect(api.profiles()).rejects.toMatchObject({ messages: ['Beklenmeyen bir hata oluştu; lütfen tekrar deneyin.'] })
  })
})

describe('api requests', () => {
  it('sends no key header unless the user typed one', async () => {
    const spy = mockFetch(200, {})
    await api.analyze({ profileId: 'p1', files: [new File(['x'], 'a.png', { type: 'image/png' })], provider: 'Gemini', useVlm: false, secondOpinion: false })
    const [url, init] = spy.mock.calls[0]
    expect(url).toBe('/api/analyses')
    expect(JSON.stringify(init?.headers ?? {})).not.toMatch(/key/i)
    const form = init?.body as FormData
    expect(form.get('profile_id')).toBe('p1')
    expect(form.getAll('files')).toHaveLength(1)
    expect(form.get('hf_model')).toBeNull()
  })

  it('sends a typed key and the HF model choice', async () => {
    const spy = mockFetch(200, {})
    await api.analyze({ profileId: 'p1', files: [new File(['x'], 'a.png')], provider: 'Hugging Face', useVlm: true, secondOpinion: false, hfModel: 'org/model', providerKey: ' hf_abc ' })
    const [, init] = spy.mock.calls[0]
    expect(init?.headers).toEqual({ 'X-Provider-Key': 'hf_abc' })
    expect((init!.body as FormData).get('hf_model')).toBe('org/model')
  })

  it('adds the optional app access token without exposing it in request bodies', async () => {
    api.setAccessToken(' app-secret ')
    const spy = mockFetch(200, [])
    await api.profiles()
    const headers = new Headers(spy.mock.calls[0][1]?.headers)
    expect(headers.get('Authorization')).toBe('Bearer app-secret')
    api.setAccessToken('')
  })
})
