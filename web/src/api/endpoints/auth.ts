import { apiRequest } from '../client'
import { tokenStore } from '../tokens'
import type {
  Account,
  DetailResponse,
  EmailVerificationConfirmRequest,
  LoginRequest,
  PasswordResetConfirmRequest,
  PasswordResetRequest,
  RegisterRequest,
  RegisterResponse,
  TokenPair,
  UpdateMeRequest,
} from '../types'

export async function register(payload: RegisterRequest): Promise<RegisterResponse> {
  const result = await apiRequest<RegisterResponse>('/api/v1/auth/register', {
    method: 'POST',
    body: payload,
    auth: false,
  })
  tokenStore.set(result.tokens)
  return result
}

export async function login(payload: LoginRequest): Promise<TokenPair> {
  const tokens = await apiRequest<TokenPair>('/api/v1/auth/login', {
    method: 'POST',
    body: payload,
    auth: false,
  })
  tokenStore.set(tokens)
  return tokens
}

export async function logout(): Promise<void> {
  const refresh = tokenStore.getRefresh()
  tokenStore.clear()
  if (!refresh) return
  try {
    await apiRequest<void>('/api/v1/auth/logout', { method: 'POST', body: { refresh }, auth: false })
  } catch {
    /* token already invalid or server unreachable: local session is cleared regardless */
  }
}

export function getMe(signal?: AbortSignal): Promise<Account> {
  return apiRequest<Account>('/api/v1/me', { signal })
}

export function updateMe(payload: UpdateMeRequest): Promise<Account> {
  return apiRequest<Account>('/api/v1/me', { method: 'PATCH', body: payload })
}

export function requestPasswordReset(payload: PasswordResetRequest): Promise<DetailResponse> {
  return apiRequest<DetailResponse>('/api/v1/auth/password-reset/request', {
    method: 'POST',
    body: payload,
    auth: false,
  })
}

export function confirmPasswordReset(payload: PasswordResetConfirmRequest): Promise<DetailResponse> {
  return apiRequest<DetailResponse>('/api/v1/auth/password-reset/confirm', {
    method: 'POST',
    body: payload,
    auth: false,
  })
}

export function requestEmailVerification(): Promise<DetailResponse> {
  return apiRequest<DetailResponse>('/api/v1/auth/email-verification/request', { method: 'POST' })
}

export function confirmEmailVerification(
  payload: EmailVerificationConfirmRequest,
): Promise<DetailResponse> {
  return apiRequest<DetailResponse>('/api/v1/auth/email-verification/confirm', {
    method: 'POST',
    body: payload,
    auth: false,
  })
}
