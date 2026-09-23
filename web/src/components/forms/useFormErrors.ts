import { useCallback, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../../api'

export type FieldErrors<K extends string> = Partial<Record<K, string>>

/**
 * Field + form-level error state shared by every form. `applyApiError`
 * maps the backend envelope's `details` onto known fields; anything else
 * becomes the form-level message.
 */
export function useFormErrors<K extends string>(fields: readonly K[]) {
  const { t } = useTranslation()
  const [fieldErrors, setFieldErrors] = useState<FieldErrors<K>>({})
  const [formError, setFormError] = useState<string | null>(null)

  const clear = useCallback(() => {
    setFieldErrors({})
    setFormError(null)
  }, [])

  const applyApiError = useCallback(
    (error: unknown, fallback?: string) => {
      if (!(error instanceof ApiError)) {
        setFormError(t('errors.unknown'))
        return
      }
      if (error.code === 'network_error') {
        setFormError(t('errors.network'))
        return
      }
      if (error.code === 'throttled') {
        setFormError(t('errors.throttled'))
        return
      }
      const next: FieldErrors<K> = {}
      let unmatched: string[] = []
      for (const [field, messages] of Object.entries(error.details ?? {})) {
        const first = messages[0]
        if (!first) continue
        if ((fields as readonly string[]).includes(field)) next[field as K] = first
        else unmatched = unmatched.concat(messages)
      }
      setFieldErrors(next)
      if (unmatched.length > 0) setFormError(unmatched.join(' '))
      else if (Object.keys(next).length === 0) setFormError(fallback ?? error.message)
      else setFormError(null)
    },
    [fields, t],
  )

  return { fieldErrors, setFieldErrors, formError, setFormError, clear, applyApiError }
}
