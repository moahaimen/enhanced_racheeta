import { useCallback, type MouseEvent, type ReactNode } from 'react'

import { DUPLICATE_CALL, useAsyncAction } from '../../../hooks/useAsync'
import { Button, type ButtonProps } from './Button'

export interface ApiActionButtonProps<Result>
  extends Omit<ButtonProps, 'onClick' | 'onError' | 'loading' | 'loadingLabel'> {
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
 * disabled while running, circular progress shown, stable dimensions,
 * duplicate clicks ignored, state restored on success or error.
 * As `type="submit"` it owns the form submission (Enter key works, native
 * submission is suppressed).
 */
export function ApiActionButton<Result>({
  action,
  onSuccess,
  onError,
  pendingLabel,
  children,
  type = 'button',
  ...rest
}: ApiActionButtonProps<Result>) {
  const { run, pending } = useAsyncAction(action)

  const handleClick = useCallback(
    async (event: MouseEvent<HTMLButtonElement>) => {
      if (type === 'submit') event.preventDefault()
      let result: Result | typeof DUPLICATE_CALL
      try {
        result = await run()
      } catch (error) {
        onError?.(error)
        return
      }
      if (result === DUPLICATE_CALL) return // the click was ignored while another call was pending
      onSuccess?.(result) // including `undefined` results (a DELETE / 204 is still a success)
    },
    [run, type, onSuccess, onError],
  )

  return (
    <Button {...rest} type={type} loading={pending} loadingLabel={pendingLabel} onClick={handleClick}>
      {children}
    </Button>
  )
}
