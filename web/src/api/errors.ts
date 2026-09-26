import type { TFunction } from 'i18next'

import { ApiError } from './client'

/** Localised message for a typed API error (falls back to the server message). */
export function localizeApiError(error: unknown, t: TFunction): string {
  if (!(error instanceof ApiError)) return t('errors.unknown')
  if (error.code === 'network_error') return t('errors.network')
  if (error.code === 'throttled') return t('errors.throttled')
  const key = `apiErrors.${error.code}`
  const translated = t(key, { defaultValue: '' })
  return translated || error.message
}

/** Localised message for the first error code of a field, if it is a known typed code. */
export function localizeFieldError(error: ApiError, field: string, t: TFunction): string | undefined {
  const code = error.codes?.[field]?.[0]
  if (code) {
    const translated = t(`apiErrors.${code}`, { defaultValue: '' })
    if (translated) return translated
  }
  return error.fieldError(field)
}
