import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router'

import { workspaces as workspacesApi } from '../../api'
import type { OrgRole, OrgSummary, ReservationStatus } from '../../api'
import {
  Alert,
  ApiActionButton,
  AsyncPage,
  Badge,
  Button,
  Container,
  EmptyState,
  FormActions,
  Icon,
  LinkButton,
  PageHeader,
  PageStack,
  SectionCard,
  Select,
  TextField,
} from '../../design-system'
import { toErrorMessage } from '../../hooks/useAsync'
import { useFeatures } from '../../hooks/useFeatures'
import { pickScript } from '../../i18n/localized'
import styles from '../dashboard/Dashboard.module.css'
import { CountGrid } from '../dashboard/widgets'

type Kind = 'facility' | 'company'

/**
 * /workspace/:kind/:id — a facility or business seen by its owner or staff. The server returns 404
 * for an organization the caller has no role in (no enumeration) and checks the capability behind
 * every button again; the buttons shown here only mirror the capabilities the server reported.
 */
export function OrgWorkspacePage() {
  const { t } = useTranslation()
  const params = useParams()
  const kind: Kind = params.kind === 'company' ? 'company' : 'facility'
  const id = params.id ?? ''
  return (
    <Container width="xl">
      <AsyncPage load={(signal) => workspacesApi.getOrgSummary(kind, id, signal)} deps={[kind, id]}>
        {(org, reload) => (
          <>
            <OrgHeader org={org} kind={kind} />
            <PageStack>
              {org.capabilities.length <= 1 ? <Alert kind="info">{t('ws.readOnly')}</Alert> : null}
              <CountGrid counts={org.counts} labelGroup="ws.counts" testPrefix="org-count" />
              {kind === 'facility' ? <FacilityReservations org={org} onChange={reload} /> : <CompanyLinks org={org} />}
              {org.capabilities.includes('members.view') ? <MembersPanel kind={kind} org={org} /> : null}
            </PageStack>
          </>
        )}
      </AsyncPage>
    </Container>
  )
}

function OrgHeader({ org, kind }: { org: OrgSummary; kind: Kind }) {
  const { t, i18n } = useTranslation()
  return (
    <PageHeader
      eyebrow={<><Icon name={kind === 'facility' ? 'hospital' : 'building'} size={16} />{kind === 'facility' ? t('ws.orgTitle') : t('ws.companyTitle')}</>}
      title={pickScript(org.name, i18n.language)}
      description={`${t('ws.role')}: ${t(`ws.roles.${org.role}`)}`}
      actions={<LinkButton to="/workspaces" variant="secondary">{t('nav.workspaces')}</LinkButton>}
    />
  )
}

const NEXT: Partial<Record<ReservationStatus, ReservationStatus[]>> = {
  PENDING: ['CONFIRMED', 'REJECTED'],
  CONFIRMED: ['COMPLETED', 'CANCELLED'],
}

function FacilityReservations({ org, onChange }: { org: OrgSummary; onChange: () => void }) {
  const { t, i18n } = useTranslation()
  const [error, setError] = useState<string | null>(null)
  const canManage = org.capabilities.includes('facility.reservations.manage')
  const { reservationsEnabled: bookingOn } = useFeatures()
  // Booking off: a pending booking can be rejected but no longer accepted (the server agrees).
  const next = (status: ReservationStatus) => (NEXT[status] ?? []).filter((s) => bookingOn || s !== 'CONFIRMED')
  if (!org.capabilities.includes('facility.reservations.view')) return null
  return (
    <SectionCard title={t('ws.reservations')} headingLevel={2}>
      {error ? <Alert kind="error">{error}</Alert> : null}
      <AsyncPage load={(signal) => workspacesApi.listFacilityReservations(org.id, signal)} deps={[org.id]}>
        {(page, reload) =>
          page.results.length === 0 ? (
            <EmptyState icon="calendar" title={t('ws.noReservations')} />
          ) : (
            <ul className={styles.rows} data-testid="facility-reservations">
              {page.results.map((row) => (
                <li key={row.id} className={styles.row}>
                  <div className={styles.rowHead}>
                    <h3 className={styles.rowTitle}>{row.service_title_snapshot}</h3>
                    <Badge tone={row.status === 'PENDING' ? 'warning' : 'neutral'}>{t(`reservationStatus.${row.status}`)}</Badge>
                  </div>
                  <p className={styles.rowMeta}>
                    {row.patient.full_name ? `${row.patient.full_name} · ` : ''}
                    <time dateTime={row.starts_at}>{new Date(row.starts_at).toLocaleString(i18n.language)}</time>
                  </p>
                  {canManage && next(row.status).length > 0 ? (
                    <div className="cluster">
                      {next(row.status).map((status) => (
                        <ApiActionButton
                          key={status}
                          size="sm"
                          variant={status === 'CONFIRMED' || status === 'COMPLETED' ? 'primary' : 'ghost'}
                          action={() => workspacesApi.transitionFacilityReservation(org.id, row.id, status)}
                          onSuccess={() => {
                            setError(null)
                            reload()
                            onChange()
                          }}
                          onError={(e) => setError(toErrorMessage(e))}
                        >
                          {t(`reservationStatus.${status}`)}
                        </ApiActionButton>
                      ))}
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          )
        }
      </AsyncPage>
    </SectionCard>
  )
}

function CompanyLinks({ org }: { org: OrgSummary }) {
  const { t } = useTranslation()
  const q = `?company=${encodeURIComponent(org.id)}`
  return (
    <SectionCard title={t('ws.companyTitle')} headingLevel={2}>
      <div className={styles.links}>
        {org.capabilities.includes('company.orders.view') ? (
          <LinkButton to={`/merchant/orders${q}`} variant="secondary" size="sm">{t('ws.orders')}</LinkButton>
        ) : null}
        {org.capabilities.includes('company.quotes.view') ? (
          <LinkButton to={`/merchant/quotes${q}`} variant="secondary" size="sm">{t('ws.quotes')}</LinkButton>
        ) : null}
      </div>
    </SectionCard>
  )
}

function MembersPanel({ kind, org }: { kind: Kind; org: OrgSummary }) {
  const { t } = useTranslation()
  const canManage = org.capabilities.includes('members.manage')
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<Exclude<OrgRole, 'OWNER'>>('STAFF')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [version, setVersion] = useState(0)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await workspacesApi.addOrgMember(kind, org.id, email.trim(), role)
      setEmail('')
      setVersion((v) => v + 1)
    } catch (e) {
      setError(toErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <SectionCard title={t('ws.members')} headingLevel={2}>
      {error ? <Alert kind="error">{error}</Alert> : null}
      <AsyncPage load={(signal) => workspacesApi.listOrgMembers(kind, org.id, signal)} deps={[kind, org.id, version]}>
        {(members) =>
          members.length === 0 ? (
            <p className="text-secondary">{t('ws.noMembers')}</p>
          ) : (
            <ul className={styles.rows} data-testid="org-members">
              {members.map((member) => (
                <li key={member.id} className={styles.row}>
                  <div className={styles.rowHead}>
                    <strong>{member.full_name}</strong>
                    <Badge tone="brand">{t(`ws.roles.${member.role}`)}</Badge>
                  </div>
                  <p className={`${styles.rowMeta} ltr`}>{member.email}</p>
                  {canManage ? (
                    <ApiActionButton
                      size="sm"
                      variant="ghost"
                      action={() => workspacesApi.endOrgMember(kind, org.id, member.id)}
                      onSuccess={() => setVersion((v) => v + 1)}
                      onError={(e) => setError(toErrorMessage(e))}
                    >
                      {t('ws.endMember')}
                    </ApiActionButton>
                  ) : null}
                </li>
              ))}
            </ul>
          )
        }
      </AsyncPage>
      {canManage ? (
        <form onSubmit={submit} className="stack-sm" data-testid="add-member-form">
          <TextField label={t('ws.memberEmail')} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          <Select label={t('ws.memberRole')} value={role} onChange={(e) => setRole(e.target.value as Exclude<OrgRole, 'OWNER'>)}>
            {(['MANAGER', 'STAFF', 'VIEWER'] as const).map((r) => (
              <option key={r} value={r}>{t(`ws.roles.${r}`)}</option>
            ))}
          </Select>
          <FormActions>
            <Button type="submit" loading={busy}>{t('ws.addMember')}</Button>
          </FormActions>
        </form>
      ) : null}
    </SectionCard>
  )
}
