import { useId, type InputHTMLAttributes, type ReactNode } from 'react'

export interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> {
  label: ReactNode
  error?: string | undefined
  hint?: ReactNode
  /** Rendered inside the input wrapper, after the input (e.g. a toggle button). */
  trailing?: ReactNode
}

export function TextField({ label, error, hint, trailing, className = '', ...input }: TextFieldProps) {
  const id = useId()
  const errorId = `${id}-error`
  const hintId = `${id}-hint`
  const describedBy = [error ? errorId : null, hint ? hintId : null].filter(Boolean).join(' ')
  return (
    <div className={`field ${error ? 'field--invalid' : ''} ${className}`.trim()}>
      <label className="field__label" htmlFor={id}>
        {label}
      </label>
      <div className="field__control">
        <input
          id={id}
          className="field__input"
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy || undefined}
          {...input}
        />
        {trailing}
      </div>
      {hint ? (
        <div id={hintId} className="field__hint">
          {hint}
        </div>
      ) : null}
      {error ? (
        <p id={errorId} className="field__error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  )
}
