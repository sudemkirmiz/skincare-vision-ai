// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Sudem Kırmız
import { describe, expect, it } from 'vitest'
import { dueSlots, today, type ReminderSettings } from './reminders'

const ON: ReminderSettings = { enabled: true, am: '08:30', pm: '21:30' }
const NONE = { date: '', slots: [] }
const NOT_DONE = { am: false, pm: false }
const at = (time: string) => new Date(`2026-10-25T${time}:00`)

describe('dueSlots', () => {
  it('fires at the chosen time, not before', () => {
    expect(dueSlots(ON, at('08:29'), NONE, NOT_DONE)).toEqual([])
    expect(dueSlots(ON, at('08:30'), NONE, NOT_DONE)).toEqual(['am'])
    expect(dueSlots(ON, at('21:45'), NONE, NOT_DONE)).toEqual(['pm'])
  })

  it('skips a routine already ticked today and a reminder already shown', () => {
    expect(dueSlots(ON, at('21:45'), NONE, { am: false, pm: true })).toEqual([])
    expect(dueSlots(ON, at('21:45'), { date: today(at('21:45')), slots: ['pm'] }, NOT_DONE)).toEqual([])
    // Yesterday's log does not silence today.
    expect(dueSlots(ON, at('21:45'), { date: '2026-10-24', slots: ['pm'] }, NOT_DONE)).toEqual(['pm'])
  })

  it('drops reminders that are hours late and does nothing when off', () => {
    expect(dueSlots(ON, at('12:00'), NONE, NOT_DONE)).toEqual([])
    expect(dueSlots({ ...ON, enabled: false }, at('08:31'), NONE, NOT_DONE)).toEqual([])
  })
})
