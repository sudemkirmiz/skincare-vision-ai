// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Sudem Kırmız
// Runs before first paint (render-blocking in <head>) so a dark-theme visitor never sees a light flash.
// Kept as a file rather than inline because the production CSP only allows same-origin scripts.
;(function () {
  var choice = 'system'
  try {
    choice = localStorage.getItem('scv.theme') || 'system'
  } catch {
    /* storage blocked: follow the system */
  }
  var dark = choice === 'dark' || (choice !== 'light' && window.matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.dataset.theme = dark ? 'dark' : 'light'
})()
