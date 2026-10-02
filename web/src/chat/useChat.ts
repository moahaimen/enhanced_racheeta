import { useContext } from 'react'

import { ChatContext } from './context'

export function useChat() {
  const value = useContext(ChatContext)
  if (value === null) throw new Error('useChat must be used inside ChatProvider')
  return value
}
