import { useTranslation } from 'react-i18next'

import type { ApplicationStatus, InvitationStatus, JobStatus } from '../../../api'
import { Badge, type BadgeTone } from '../Badge/Badge'

const JOB_TONE: Record<JobStatus, BadgeTone> = {
  DRAFT: 'neutral',
  PENDING_ADMIN_REVIEW: 'warning',
  PUBLISHED: 'success',
  CLOSED: 'neutral',
  EXPIRED: 'neutral',
  REJECTED: 'error',
  SUSPENDED: 'error',
  ARCHIVED: 'neutral',
}
const APPLICATION_TONE: Record<ApplicationStatus, BadgeTone> = {
  SUBMITTED: 'info',
  REVIEWING: 'info',
  SHORTLISTED: 'brand',
  INTERVIEW: 'warning',
  ACCEPTED: 'success',
  REJECTED: 'error',
  WITHDRAWN: 'neutral',
}
const INVITATION_TONE: Record<InvitationStatus, BadgeTone> = {
  PENDING: 'warning',
  ACCEPTED: 'success',
  DECLINED: 'neutral',
  EXPIRED: 'neutral',
  CANCELLED: 'neutral',
}

export function JobStatusBadge({ status }: { status: JobStatus }) {
  const { t } = useTranslation()
  return <Badge tone={JOB_TONE[status]}>{t(`jobStatus.${status}`)}</Badge>
}

export function ApplicationStatusBadge({ status }: { status: ApplicationStatus }) {
  const { t } = useTranslation()
  return <Badge tone={APPLICATION_TONE[status]}>{t(`applicationStatus.${status}`)}</Badge>
}

export function InvitationStatusBadge({ status }: { status: InvitationStatus }) {
  const { t } = useTranslation()
  return <Badge tone={INVITATION_TONE[status]}>{t(`invitationStatus.${status}`)}</Badge>
}
