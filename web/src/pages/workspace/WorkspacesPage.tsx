import { useTranslation } from 'react-i18next'

import { workspaces as workspacesApi } from '../../api'
import type { Workspace } from '../../api'
import {
  AsyncPage,
  Badge,
  Container,
  EmptyState,
  Icon,
  LinkButton,
  PageHeader,
  PageStack,
  SectionCard,
  type IconName,
} from '../../design-system'
import { pickScript } from '../../i18n/localized'

const KIND_ICON: Record<string, IconName> = {
  patient: 'user',
  practitioner: 'stethoscope',
  facility: 'hospital',
  company: 'building',
  property: 'home',
  employer: 'briefcase',
  job_seeker: 'user',
  admin: 'shieldCheck',
}

/**
 * /workspaces — every workspace the SERVER says this account may open (own profile, organizations
 * owned, staff memberships, recruitment, résumé, administration). Nothing here grants access: each
 * workspace page re-checks the role on every request.
 */
export function WorkspacesPage() {
  const { t } = useTranslation()
  return (
    <Container width="xl">
      <PageHeader
        eyebrow={<><Icon name="building" size={16} />{t('nav.workspaces')}</>}
        title={t('ws.switcherTitle')}
        description={t('ws.switcherIntro')}
      />
      <PageStack>
        <AsyncPage load={(signal) => workspacesApi.listWorkspaces(signal)}>
          {(items) =>
            items.length === 0 ? (
              <div className="card-block">
                <EmptyState icon="building" title={t('ws.none')} />
              </div>
            ) : (
              <div className="grid-auto" data-testid="workspace-list">
                {items.map((ws) => (
                  <WorkspaceCard key={`${ws.kind}:${ws.id}`} ws={ws} />
                ))}
              </div>
            )
          }
        </AsyncPage>
      </PageStack>
    </Container>
  )
}

function WorkspaceCard({ ws }: { ws: Workspace }) {
  const { t, i18n } = useTranslation()
  return (
    <SectionCard
      title={pickScript(ws.title, i18n.language)}
      headingLevel={2}
      actions={<Badge tone="brand">{t(`ws.kinds.${ws.kind}`, { defaultValue: ws.kind })}</Badge>}
    >
      <div className="cluster">
        <Icon name={KIND_ICON[ws.kind] ?? 'building'} size={18} />
        {ws.role ? (
          <span className="text-caption">
            {t('ws.role')}: {t(`ws.roles.${ws.role}`, { defaultValue: ws.role })}
          </span>
        ) : null}
        {ws.verification_status ? (
          <Badge tone={ws.verification_status === 'VERIFIED' ? 'success' : 'warning'}>
            {t(`verification.${ws.verification_status}`, { defaultValue: ws.verification_status })}
          </Badge>
        ) : null}
      </div>
      <LinkButton to={ws.path} size="sm">
        {t('ws.open')}
      </LinkButton>
    </SectionCard>
  )
}
