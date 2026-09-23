export const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
export const PHONE_RE = /^\+?[0-9]{7,15}$/
export const PASSWORD_MIN_LENGTH = 8

export function isEmail(value: string): boolean {
  return EMAIL_RE.test(value.trim())
}

export function isPhone(value: string): boolean {
  return PHONE_RE.test(value.replace(/[\s-]/g, ''))
}

/** Thrown by submit handlers when client validation fails; not an API error. */
export class ClientValidationError extends Error {
  constructor() {
    super('client validation failed')
    this.name = 'ClientValidationError'
  }
}
