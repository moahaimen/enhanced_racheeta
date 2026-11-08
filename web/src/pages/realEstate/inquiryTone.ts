import type { InquiryStatus } from '../../api'

/** Badge tone for an inquiry status (shared by the asker's list and the owner inbox). */
export function inquiryTone(status: InquiryStatus) {
  if (status === 'ANSWERED') return 'success' as const
  if (status === 'OPEN') return 'warning' as const
  return 'neutral' as const
}
