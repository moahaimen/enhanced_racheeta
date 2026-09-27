import type { JobListParams } from '../../api'

export const JOB_FILTER_KEYS = ['q', 'profession', 'specialty', 'governorate', 'city', 'degree', 'min_experience', 'max_experience', 'employment_type', 'work_mode', 'shift_type', 'salary_available'] as const
export type JobFilterKey = (typeof JOB_FILTER_KEYS)[number]

export function readJobFilters(params: URLSearchParams): JobListParams & { page: number } {
  const out: Record<string, string> = {}
  for (const key of JOB_FILTER_KEYS) {
    const value = params.get(key)
    if (value) out[key] = value
  }
  return { ...(out as JobListParams), page: Math.max(1, Number(params.get('page') ?? '1') || 1) }
}

export function writeJobFilters(next: Record<string, string | number | undefined>): URLSearchParams {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(next)) {
    if (value === undefined || value === '' || (key === 'page' && Number(value) === 1)) continue
    params.set(key, String(value))
  }
  return params
}
