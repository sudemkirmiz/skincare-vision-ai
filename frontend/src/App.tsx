// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Sudem Kırmız
import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { useAppState } from './lib/app-state'
import { AnalyzePage } from './pages/Analyze'
import { CheckerPage } from './pages/Checker'
import { Onboarding } from './pages/Onboarding'
import { Spinner } from './components/ui'

// The charting library is only needed on the history page; load it on demand.
const HistoryPage = lazy(() => import('./pages/History').then((module) => ({ default: module.HistoryPage })))
const TrackingPage = lazy(() => import('./pages/Tracking').then((module) => ({ default: module.TrackingPage })))

export function App() {
  const { editor, options } = useAppState()
  if (editor) {
    return (
      <div className="min-h-screen px-4 sm:px-6">
        <Onboarding key={editor} mode={editor} />
      </div>
    )
  }
  return (
    <Layout>
      <Suspense fallback={<div className="grid place-items-center py-24"><Spinner label="Sayfa yükleniyor…" /></div>}>
      <Routes>
        <Route path="/" element={<AnalyzePage />} />
        <Route path="/urun-kontrolu" element={<CheckerPage />} />
        {options.flags.history_enabled ? <Route path="/gecmis" element={<HistoryPage />} /> : null}
        {options.flags.history_enabled ? <Route path="/takip" element={<TrackingPage />} /> : null}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </Suspense>
    </Layout>
  )
}
