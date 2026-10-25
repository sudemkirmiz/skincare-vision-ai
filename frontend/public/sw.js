// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Sudem Kırmız
/*
 * SkinCare Vision AI service worker: makes the app installable and lets the shell open offline.
 *
 * Privacy rule: only the public app shell is cached. /api/* (photos, analyses, journal, profiles) is never
 * stored here, so health data never lingers in a cache and results are never shown stale.
 */
const VERSION = 'scv-v1'
const SHELL = ['/', '/manifest.webmanifest', '/favicon.svg', '/theme-init.js', '/icons/icon-192.png', '/icons/icon-512.png']

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(VERSION).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()))
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== VERSION).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  )
})

async function networkFirst(request) {
  const cache = await caches.open(VERSION)
  try {
    const response = await fetch(request)
    if (response.ok) cache.put('/', response.clone())
    return response
  } catch {
    return (await cache.match('/')) ?? Response.error()
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(VERSION)
  const hit = await cache.match(request)
  if (hit) return hit
  const response = await fetch(request)
  if (response.ok) cache.put(request, response.clone())
  return response
}

self.addEventListener('fetch', (event) => {
  const { request } = event
  const url = new URL(request.url)
  if (request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return
  // Every route is the same SPA shell: always try the network so a new release shows up at once.
  if (request.mode === 'navigate') return event.respondWith(networkFirst(request))
  // Build output is content-hashed, so a cached copy is always the right one.
  if (url.pathname.startsWith('/assets/') || url.pathname.startsWith('/icons/')) return event.respondWith(cacheFirst(request))
})

// Routine reminders are shown by the page through registration.showNotification; a tap opens the journal.
self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const target = new URL(event.notification.data?.url ?? '/takip', self.location.origin).href
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windows) => {
      const open = windows.find((client) => new URL(client.url).origin === self.location.origin)
      if (open) return open.focus().then(() => open.navigate(target))
      return self.clients.openWindow(target)
    }),
  )
})
