import { useContext } from 'react'

import { NotificationsContext, type NotificationsContextValue } from './context'

export function useNotifications(): NotificationsContextValue {
  const value = useContext(NotificationsContext)
  if (!value) throw new Error('useNotifications must be used inside <NotificationsProvider>')
  return value
}
