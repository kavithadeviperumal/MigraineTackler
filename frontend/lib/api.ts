import { clearAuth, getAccessToken, getRefreshToken, setTokens } from './auth'

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

// ── Types ─────────────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export interface AuthResponse {
  id: number
  username: string
  token: string
  refresh_token: string
}

export interface LogEntry {
  id: number
  entry_date: string
  migraine_occurred: boolean
  pain_level: number | null
  pain_location: string | null
  duration_hours: number | null
  sleep_hours: number | null
  sleep_quality: number | null
  stress_level: number | null
  stress_source: string | null
  foods: string[] | null
  hydration_oz: number | null
  caffeine_mg: number | null
  medications: string[] | null
  prodrome_symptoms: string[] | null
  relief_methods: string[] | null
  relief_effectiveness: number | null
  menstrual_cycle_day: number | null
  notes: string | null
  city: string | null
}

export interface LogCreatePayload {
  entry_date: string
  migraine_occurred: boolean
  pain_level?: number
  pain_location?: string
  duration_hours?: number
  sleep_hours?: number
  sleep_quality?: number
  stress_level?: number
  stress_source?: string
  foods?: string[]
  hydration_oz?: number
  caffeine_mg?: number
  medications?: string[]
  prodrome_symptoms?: string[]
  relief_methods?: string[]
  relief_effectiveness?: number
  menstrual_cycle_day?: number
  notes?: string
  city?: string
}

export interface LogCreateResponse {
  log: LogEntry
  red_flag: boolean
  red_flag_symptoms: string[]
  moh_alert: boolean
  triptan_days: number
  nsaid_days: number
}

export interface ToxicLoadResponse {
  today_score: number
  carryover_score: number
  rolling_score: number
  threshold: number
  fill_pct: number
  risk_level: 'low' | 'moderate' | 'high' | 'critical'
  breakdown: Record<string, number>
}

export interface UserProfile {
  migraine_duration: string | null
  migraine_frequency: string | null
  migraine_subtype: string | null
  home_city: string | null
  known_food_triggers: string[] | null
  other_triggers: string | null
  typical_bedtime: string | null
  typical_wake_time: string | null
  typical_stress_level: number | null
  job_type: string | null
  typical_hydration_oz: number | null
  typical_caffeine_level: string | null
  hormonal_status: string | null
  cycle_length_days: number | null
  migraines_cluster_period: string | null
  worst_hormonal_phase: string | null
  preventive_medications: string[] | null
  supplements: string[] | null
  acute_medications: string[] | null
  onboarding_complete: boolean
}

export interface AnalyzeState {
  confirmed_triggers: string[]
  suspected_triggers: string[]
  current_root_cause_hypothesis: string | null
  root_cause_evidence: Array<{
    claim: string
    source: string
    source_type: string
  }>
  current_protocol: {
    version: number
    date: string
    active_items: Array<{
      tier: number
      intervention: string
      dose_or_detail: string
      rationale: string
      what_to_log: string
      assessment_weeks: number
    }>
  } | null
  migraine_subtype: string | null
}

export interface NodeError {
  node: string
  step: string
  error: string
  timestamp: string
}

export interface AnalyzeResponse {
  messages: string[]
  moh_alert: boolean
  red_flag: boolean
  node_errors: NodeError[]
}

const NODE_ERROR_MESSAGES: Record<string, Record<string, string>> = {
  research: {
    live_retrieval: 'Live research unavailable — answer based on your personal knowledge base only.',
    kb_retrieval: 'Your personal documents were temporarily unavailable.',
    query_reformulation: 'Search query optimisation failed — results may be less targeted.',
    llm_invoke: 'Research analysis failed — please try again.',
  },
  intake: { llm_invoke: 'Follow-up questions temporarily unavailable — please try again.' },
  pattern: { llm_invoke: 'Pattern analysis failed — please try again.' },
  root_cause: { llm_invoke: 'Root cause analysis failed — please try again.' },
  protocol: { llm_invoke: 'Protocol update failed — your existing plan remains active.' },
  lifestyle_audit: { llm_invoke: 'Lifestyle audit temporarily unavailable — please try again.' },
}

export function getNodeErrorMessage(err: NodeError): string {
  return NODE_ERROR_MESSAGES[err.node]?.[err.step] ?? `${err.node} failed — please try again.`
}

export interface KnowledgeSource {
  id: number
  title: string
  source_type: string
  chunk_count: number
}

// ── Token refresh (singleton) ─────────────────────────────────────────────────

let _refreshing: Promise<boolean> | null = null

async function _tryRefresh(): Promise<boolean> {
  if (_refreshing) return _refreshing
  _refreshing = (async () => {
    const rt = getRefreshToken()
    if (!rt) return false
    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: rt }),
      })
      if (!res.ok) return false
      const data: AuthResponse = await res.json()
      setTokens(data.token, data.refresh_token)
      return true
    } catch {
      return false
    } finally {
      _refreshing = null
    }
  })()
  return _refreshing
}

// ── Core fetch wrapper ────────────────────────────────────────────────────────

async function _fetch<T>(
  method: string,
  path: string,
  opts: {
    body?: unknown
    params?: Record<string, string | number>
    isRetry?: boolean
    isFormData?: boolean
    formData?: FormData
  } = {},
): Promise<T> {
  const url = new URL(`${API_BASE}${path}`)
  if (opts.params) {
    Object.entries(opts.params).forEach(([k, v]) => url.searchParams.set(k, String(v)))
  }

  const token = getAccessToken()
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (!opts.isFormData) headers['Content-Type'] = 'application/json'

  const res = await fetch(url.toString(), {
    method,
    headers,
    body: opts.isFormData
      ? opts.formData
      : opts.body !== undefined
        ? JSON.stringify(opts.body)
        : undefined,
  })

  if (res.status === 401 && !opts.isRetry) {
    const refreshed = await _tryRefresh()
    if (refreshed) {
      return _fetch<T>(method, path, { ...opts, isRetry: true })
    }
    clearAuth()
    window.location.href = '/login'
    throw new ApiError(401, 'Session expired')
  }

  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try {
      const data = await res.json()
      msg = data.detail ?? msg
    } catch {
      msg = (await res.text()) || msg
    }
    throw new ApiError(res.status, msg)
  }

  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export const auth = {
  register: (username: string, password: string) =>
    _fetch<AuthResponse>('POST', '/auth/register', { body: { username, password } }),

  login: (username: string, password: string) =>
    _fetch<AuthResponse>('POST', '/auth/login', { body: { username, password } }),

  logout: (refreshToken: string) =>
    _fetch<void>('POST', '/auth/logout', { body: { refresh_token: refreshToken } }),
}

// ── Logs ──────────────────────────────────────────────────────────────────────

export const logs = {
  create: (payload: LogCreatePayload) =>
    _fetch<LogCreateResponse>('POST', '/logs/', { body: payload }),

  list: (limit = 30) =>
    _fetch<LogEntry[]>('GET', '/logs/', { params: { limit } }),

  get: (id: number) =>
    _fetch<LogEntry>('GET', `/logs/${id}`),

  toxicLoad: (asOf?: string) =>
    _fetch<ToxicLoadResponse>('GET', '/logs/toxic-load', {
      params: asOf ? { as_of: asOf } : undefined,
    }),
}

// ── Profile ───────────────────────────────────────────────────────────────────

export const profile = {
  get: () =>
    _fetch<UserProfile>('GET', '/profile/me'),

  create: (data: Partial<UserProfile>) =>
    _fetch<UserProfile>('POST', '/profile/me', { body: data }),

  update: (data: Partial<UserProfile>) =>
    _fetch<UserProfile>('PATCH', '/profile/me', { body: data }),

  referenceFoods: () =>
    _fetch<{ foods: string[] }>('GET', '/profile/me/reference-foods'),
}

// ── Analyze ───────────────────────────────────────────────────────────────────

export type AnalyzeIntent =
  | 'log_entry'
  | 'lifestyle_audit'
  | 'pattern_review'
  | 'root_cause_review'
  | 'protocol_review'
  | 'research_request'

export const analyze = {
  state: () =>
    _fetch<AnalyzeState>('GET', '/analyze/state/me'),

  run: (intent: AnalyzeIntent, opts?: { logId?: number; message?: string }) =>
    _fetch<AnalyzeResponse>('POST', '/analyze', {
      body: {
        intent,
        ...(opts?.logId != null ? { current_log_id: opts.logId } : {}),
        ...(opts?.message ? { message: opts.message } : {}),
      },
    }),
}

// ── Knowledge ─────────────────────────────────────────────────────────────────

export const knowledge = {
  upload: (file: File, title: string, sourceType = 'doctor_note') => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('title', title)
    fd.append('source_type', sourceType)
    return _fetch<{ status: string; title: string; source_type: string; chunks_stored: number }>(
      'POST',
      '/knowledge/upload',
      { isFormData: true, formData: fd },
    )
  },

  sources: () =>
    _fetch<{ sources: KnowledgeSource[] }>('GET', '/knowledge/sources'),

  deleteSource: (id: number) =>
    _fetch<{ status: string; deleted_chunks: number }>('DELETE', `/knowledge/source/${id}`),
}