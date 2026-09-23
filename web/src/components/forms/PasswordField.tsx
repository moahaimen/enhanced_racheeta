import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { TextField, type TextFieldProps } from './TextField'

export function PasswordField(props: Omit<TextFieldProps, 'type' | 'trailing'>) {
  const { t } = useTranslation()
  const [visible, setVisible] = useState(false)
  return (
    <TextField
      {...props}
      type={visible ? 'text' : 'password'}
      trailing={
        <button
          type="button"
          className="field__toggle"
          aria-pressed={visible}
          onClick={() => setVisible((v) => !v)}
        >
          {visible ? t('fields.hidePassword') : t('fields.showPassword')}
        </button>
      }
    />
  )
}
