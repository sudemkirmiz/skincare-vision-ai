// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Sudem Kırmız
import { useCallback, useEffect, useState } from 'react'

export type ThemeChoice = 'system' | 'light' | 'dark'

const KEY = 'scv.theme'
const META = { light: '#f4f9f4', dark: '#0d1510' }
const query = () => window.matchMedia('(prefers-color-scheme: dark)')

function readChoice(): ThemeChoice {
  try {
    const stored = localStorage.getItem(KEY)
    return stored === 'light' || stored === 'dark' ? stored : 'system'
  } catch {
    return 'system'
  }
}

/** Applies the resolved theme to <html data-theme> (the same rule /theme-init.js uses before first paint). */
export function applyTheme(choice: ThemeChoice) {
  const resolved = choice === 'system' ? (query().matches ? 'dark' : 'light') : choice
  document.documentElement.dataset.theme = resolved
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', META[resolved])
  return resolved
}

export function useTheme() {
  const [choice, setChoiceState] = useState<ThemeChoice>(readChoice)

  useEffect(() => {
    applyTheme(choice)
    if (choice !== 'system') return
    // "Sistem" keeps following the OS when it switches at sunset.
    const media = query()
    const onChange = () => applyTheme('system')
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [choice])

  const setChoice = useCallback((next: ThemeChoice) => {
    setChoiceState(next)
    try {
      if (next === 'system') localStorage.removeItem(KEY)
      else localStorage.setItem(KEY, next)
    } catch {
      /* ignore */
    }
  }, [])

  return { choice, setChoice }
}
