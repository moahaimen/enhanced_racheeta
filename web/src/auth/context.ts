import { createContext } from 'react'

import type { Account, LoginRequest, RegisterRequest, UpdateMeRequest } from '../api'

export type AuthStatus = 'restoring' | 'anonymous' | 'authenticated'

export interface AuthContextValue {
  status: AuthStatus
  account: Account | null
  /** Non-401 failure during session restoration (e.g. network); session tokens are kept. */
  restoreError: unknown
  login: (payload: LoginRequest) => Promise<Account>
  register: (payload: RegisterRequest) => Promise<Account>
  logout: () => Promise<void>
  /** Re-fetch /me and update the context. */
  refreshAccount: () => Promise<Account>
  updateAccount: (payload: UpdateMeRequest) => Promise<Account>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
