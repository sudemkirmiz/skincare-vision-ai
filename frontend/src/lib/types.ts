// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Sudem Kırmız
/** Shapes returned by the FastAPI backend (only the fields the UI reads). */

export type Dict = Record<string, string>

export interface Options {
  skin_types: Dict
  skin_type_hints: Dict
  skin_type_help: string
  sensitivity: Dict
  sensitivity_help: string
  concerns: Dict
  age_groups: Dict
  genders: Dict
  pregnancy: Dict
  allergies: Dict
  current_actives: Dict
  budgets: Dict
  routine_sizes: Dict
  makeup: Dict
  sun_exposure: Dict
  address_forms: Dict
  consent_text: string
  event_kinds: Dict
  quiz: Record<string, { question: string; options: Dict }>
  providers: string[]
  journal: { triggers: Dict; symptoms: Dict; skin_feel: Dict; female_only: string[] }
  hf_models: string[]
  default_provider: string
  limits: { max_upload_mb: number; max_views: number }
  flags: { history_enabled: boolean; second_opinion: boolean; allow_user_api_keys: boolean; device_scoped?: boolean }
}

export interface SkinProfile {
  skin_type: string
  sensitivity: string
  age_group: string
  pregnancy: string
  concerns: string[]
  allergies: string[]
  current_actives: string[]
  budget: string
  routine_size: string
  makeup: string
  sun_exposure: string
}

export interface Profile {
  id: string
  display_name: string
  last_name: string
  full_name: string
  gender: string
  address_form: string
  consent_at: string
  answered: string[]
  completeness: number
  skin: SkinProfile
}

export interface ProfileInput {
  display_name: string
  last_name: string
  gender: string | null
  address_form: string
  consent: boolean
  answered: string[]
  skin: Omit<Partial<SkinProfile>, 'pregnancy'> & { pregnancy: string | null }
}

export interface Health {
  status: string
  providers: Record<string, { has_key: boolean; benched: { kind: string; label: string; seconds_left: number } | null }>
}

export interface Region {
  key: string
  name: string
  color: string
  count: number
  density: number | null
  visible: boolean
  area_ratio: number
  view?: number | null
}

export interface SkinMetrics {
  available: boolean
  reason?: string
  overall_score: number
  scores: Record<string, number | null>
  score_labels: Dict
  skin_tone: { ita: number; category: string }
  spot_counts: { yolo: number; colour: number; gemini?: number; total: number }
  regions: Record<string, { name: string; redness: number; tone: number; shine: number }>
  notes: string[]
}

export interface RoutineActive {
  id: string
  name: string
  form: string
  strength: string
  slot: 'am' | 'pm' | 'both'
  frequency: string
  why: string
  cautions: string[]
  already_using: boolean
}

export interface Routine {
  focus: string[]
  actives: RoutineActive[]
  excluded: { name: string; reason: string }[]
  am: { step: string; product: string }[]
  pm: { step: string; product: string }[]
  weekly: { day: string; actives: string[] }[]
  warnings: string[]
  tips: string[]
}

export interface Analysis {
  analysis_id: string
  created_at: string
  face_found: boolean
  original_uri: string
  marked_uri: string | null
  result: {
    image_quality: { status: string; notes: string } | null
    detected_regions: { method: string | null; analysis_region: string | null; face_count?: number; head_pose?: { yaw: number; pitch: number } | null }
    visible_observations: string[]
    care_suggestions: string[]
    disclaimer: string
  }
  skin_metrics: SkinMetrics | null
  region_summary: { regions: Region[]; most_affected_name: string | null; zones: Record<string, { name: string; count: number; density: number | null }> } | null
  vlm_output: { provider: string; model: string; cached?: boolean; quality_score?: number } | null
  vlm_error: string | null
  /** Who wrote the care comment: an AI provider, or the local rule engine when no AI was used. */
  comment_source?: 'ai' | 'local' | null
  vlm_note: string | null
  vlm_attempts?: Record<string, unknown>[]
  skin_findings?: { summary?: { total_detections?: number }; findings?: { confidence?: number }[] } | null
  views?: { original_uri: string; marked_uri: string; yaw: number | null; primary: boolean }[]
  provenance?: Record<string, number>
  routine: Routine
  mismatch_hints: string[]
}

export interface ProductSection {
  title: string
  products: { name: string; brand: string; category: string; price_tier: string; url: string; verdict: string; reasons: string[]; cautions: string[] }[]
  search_links: { name: string; url: string; icon: string }[]
}

export interface ProductVerdict {
  verdict: 'suitable' | 'caution' | 'avoid'
  verdict_label: string
  avoid: string[]
  caution: string[]
  positives: string[]
  routine_notes: string[]
  detected_actives: string[]
  ingredient_count: number
}

export interface HistoryRecord {
  id: string
  created_at: string
  overall_score: number | null
  scores: Record<string, number | null>
  spot_counts: { total?: number }
  regions: Record<string, number | null>
  note: string
  thumbnail_url: string | null
  routine_actives: string[]
}

export interface HistoryResponse {
  records: HistoryRecord[]
  events: { id: string; date: string; kind: string; note: string }[]
  trend: { tarih: string; seri: string; değer: number; id: string }[]
}

export interface Comparison {
  overall_delta: number | null
  scores: { key: string; label: string; before: number | null; after: number | null; delta: number | null; direction: string }[]
  regions: { key: string; name: string; before: number | null; after: number | null; delta: number | null; direction: string }[]
  summary: string[]
  comparability_notes: string[]
}

export interface CaptureCheck {
  guide_available: boolean
  ok: boolean
  face: boolean | null
  message: string
  checks: { key: string; ok: boolean }[]
  /** x, y, w, h as shares of the (unmirrored) frame */
  box: [number, number, number, number] | null
  pose: { yaw: number; pitch: number; roll: number } | null
}

export interface ChangeMap {
  before_uri: string
  after_uri: string
  redness_uri: string
  tone_uri: string
  stats: Record<'redness' | 'tone', { better: number; worse: number }>
  regions: { key: string; name: string; redness_better: number; redness_worse: number; tone_better: number; tone_worse: number }[]
  summary: string[]
  notes: string[]
  alignment_error: number
}

export interface JournalEntry {
  date: string
  am_done: boolean | null
  pm_done: boolean | null
  skin_feel: number | null
  triggers: string[]
  symptoms: string[]
  actives: string[]
  note: string
}

export interface Insight {
  kind: 'trigger' | 'active' | 'routine' | 'score'
  key: string
  tone: 'warn' | 'good' | 'info'
  title: string
  text: string
  evidence: { with_days: number; without_days: number }
}

export interface RoutineStreak {
  /** Days in a row with at least one routine done (yesterday keeps it alive until today is logged). */
  current: number
  best: number
  today_done: boolean
  reached: number
  next: number | null
  week: { date: string; am: boolean; pm: boolean }[]
}

export interface JournalResponse {
  entries: JournalEntry[]
  routine_actives: string[]
  summary: {
    streak: number
    adherence: { days: number; logged: number; am_done: number | null; pm_done: number | null }
    routine: RoutineStreak
    feel: { this_week: number; last_week: number | null; change: number | null } | null
    logged_days: number
    needed_days: number
    insights: Insight[]
    disclaimer: string
  }
}

export interface ShelfItemInput {
  name: string
  category: string
  usage: string
  inci: string
  opened_at: string | null
  pao_months: number | null
}

export interface ShelfItem extends ShelfItemInput {
  id: string
  created_at: string
  category_label: string
  usage_label: string
  expiry: { days_left: number; status: 'ok' | 'soon' | 'expired' } | null
  verdict: ProductVerdict | null
  actives: string[]
  is_sunscreen: boolean
}

export interface ShelfResponse {
  items: ShelfItem[]
  conflicts: string[]
  gaps: string[]
  notes: string[]
  plan: ShelfPlan
  categories: Record<string, string>
  usages: Record<string, string>
}

export interface PlanStep { id: string; name: string; category: string; category_label: string; actives: string[]; tip: string }
export interface ShelfPlan {
  morning: PlanStep[]
  nights: { day: string; theme: 'rest' | 'acid' | 'retinoid' | 'mask'; theme_label: string; steps: PlanStep[] }[]
  as_needed: string[]
  skipped: { name: string; reason: string }[]
  tips: string[]
  active_nights: number
}

export interface Place { name: string; region: string; lat: number; lon: number }

export interface WeatherToday {
  temperature: number | null
  humidity: number | null
  uv_now: number | null
  uv_max: number | null
  temp_max: number | null
  temp_min: number | null
  uv_band: { key: 'low' | 'moderate' | 'high' | 'very_high' | 'extreme'; label: string } | null
  tips: { kind: string; tone: 'warn' | 'info' | 'good'; title: string; text: string }[]
  source: string
}

export interface ChatMessage { role: 'user' | 'assistant'; content: string }
export interface CoachReply { reply: string; provider: string; model: string; filtered: boolean; remaining: number }
