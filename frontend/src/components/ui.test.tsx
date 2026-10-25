// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Sudem Kırmız
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Meter, StatusBadge, scoreStatus } from './ui'

describe('scoreStatus', () => {
  it.each([[100, 'İyi'], [75, 'İyi'], [74, 'Orta'], [55, 'Orta'], [54, 'Dikkat'], [35, 'Dikkat'], [34, 'Öncelikli'], [0, 'Öncelikli']])(
    'score %i → %s', (score, label) => expect(scoreStatus(score).label).toBe(label),
  )
})

describe('status display', () => {
  it('shows a word next to the colour', () => {
    render(<StatusBadge score={80} />)
    expect(screen.getByText('İyi')).toBeInTheDocument()
  })

  it('renders an accessible meter', () => {
    render(<Meter value={62} label="Ton eşitliği" />)
    expect(screen.getByText('Ton eşitliği')).toBeInTheDocument()
    expect(screen.getByText('62')).toBeInTheDocument()
  })
})
