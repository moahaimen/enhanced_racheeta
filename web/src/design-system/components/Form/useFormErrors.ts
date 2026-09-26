import { useCallback, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError } from '../../../api'
import { localizeApiError, localizeFieldError } from '../../../api/errors'

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
      if (error.code !== 'validation_error') {
        setFormError(localizeApiError(error, t))
        return
      }
      const next: FieldErrors<K> = {}
      let unmatched: string[] = []
      for (const [field, messages] of Object.entries(error.details ?? {})) {
        const first = messages[0]
        if (!first) continue
        if ((fields as readonly string[]).includes(field)) next[field as K] = localizeFieldError(error, field, t) ?? first
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
