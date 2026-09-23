import { useCallback, type ButtonHTMLAttributes, type MouseEvent, type ReactNode } from 'react'

import { useAsyncAction } from '../hooks/useAsync'
import { Spinner } from './Spinner'

export interface ApiActionButtonProps<Result>
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'onClick' | 'onError'> {
  /** The backend call. The button is disabled and shows a spinner until it settles. */
  action: () => Promise<Result>
  onSuccess?: (result: Result) => void
  onError?: (error: unknown) => void
  /** Optional text shown next to the spinner while pending. */
  pendingLabel?: ReactNode
  children: ReactNode
}

/**
 * The mandatory pattern for every button that talks to the backend:
 * disabled while running, circular progress shown, duplicate clicks ignored,
 * state restored on success or error.
 */
export function ApiActionButton<Result>({
  action,
  onSuccess,
  onError,
  pendingLabel,
  children,
  disabled,
  className = '',
  type = 'button',
  ...rest
}: ApiActionButtonProps<Result>) {
  const { run, pending } = useAsyncAction(action)

  const handleClick = useCallback(
    async (event: MouseEvent<HTMLButtonElement>) => {
      // As a submit button we own the submission: never let the browser post the form.
      if (type === 'submit') event.preventDefault()
      let result: Result | undefined
      try {
        result = await run()
      } catch (error) {
        onError?.(error)
        return
      }
      if (result !== undefined) onSuccess?.(result)
    },
    [run, type, onSuccess, onError],
  )

  return (
    <button
      {...rest}
      type={type}
      className={`btn ${className}`.trim()}
      disabled={disabled || pending}
      aria-busy={pending}
      onClick={handleClick}
    >
      {pending ? (
        <>
          <Spinner size="sm" />
          <span className="btn__label btn__label--pending">{pendingLabel ?? children}</span>
        </>
      ) : (
        <span className="btn__label">{children}</span>
      )}
    </button>
  )
}
