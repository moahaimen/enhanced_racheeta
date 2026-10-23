import { jobs as jobsApi } from '../../api'
import { useAuth } from '../../auth/useAuth'
import { useAsyncData } from '../../hooks/useAsync'
import { entitled } from '../employer/entitlements'

export interface TalentTarget {
  to: string
  state?: { from: string }
}

/**
 * Where the homepage "find talent / hire" calls to action lead — never to a page the visitor cannot use.
 *
 * - anonymous: through login, then the employer workspace;
 * - signed in: the employer workspace (`/employer`), which onboards an account without an
 *   organisation and offers talent search only to an eligible one;
 * - signed in AND the existing employer endpoints say the caller may recruit (OWNER/RECRUITER of a
 *   verified, active organisation whose plan has `talent.search`): straight to talent search.
 *
 * The decision reuses the same endpoints and the same `entitled()` rule the workspace uses; the
 * backend still authorises every request, this only chooses between two valid pages.
 */
export function useTalentTarget(): TalentTarget {
  const { status } = useAuth()
  const eligible = useAsyncData<boolean>(
    async (signal) => {
      if (status !== 'authenticated') return false
      try {
        const employer = await jobsApi.getMyEmployer(signal)
        const canWrite = employer?.my_role === 'OWNER' || employer?.my_role === 'RECRUITER'
        if (!employer || !canWrite || employer.verification_status !== 'VERIFIED' || employer.recruitment_status !== 'ACTIVE') return false
        return entitled(await jobsApi.getEmployerBilling(signal), 'talent.search')
      } catch {
        return false // no organisation (404), no permission, or a failed request: use the workspace
      }
    },
    [status],
  )
  if (status !== 'authenticated') return { to: '/login', state: { from: '/employer' } }
  return { to: eligible.data === true ? '/employer/talent' : '/employer' }
}
