import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'

import type { TalentCard as TalentCardData } from '../../../api'
import { useLocalizedName } from '../../../i18n/localized'
import { Icon } from '../../icons'
import { Avatar } from '../Avatar/Avatar'
import { Badge } from '../Badge/Badge'
import { Card } from '../Card/Card'
import styles from './TalentCard.module.css'

/** Employer-facing candidate card: professional facts only, never identity or contact data. */
export function TalentCard({ candidate, to }: { candidate: TalentCardData; to?: string }) {
  const { t } = useTranslation()
  const name = useLocalizedName()
  const href = to ?? `/employer/talent/${candidate.id}`
  return (
    <Card as="article" interactive className={styles.card}>
      <div className={styles.top}>
        <Avatar name={candidate.professional_title} size="md" fallback={<Icon name="user" size={22} />} />
        <div className={styles.identity}>
          <h3 className={styles.title}>
            <Link to={href}>{candidate.professional_title}</Link>
          </h3>
          <div className={styles.meta}>
            <Badge tone="brand">{t(`professions.${candidate.profession}`)}</Badge>
            {candidate.general_specialty ? <Badge tone="outline">{name(candidate.general_specialty)}</Badge> : null}
            <Badge tone="outline">{t(`degrees.${candidate.degree}`)}</Badge>
          </div>
        </div>
      </div>
      <div className={styles.facts}>
        <span>
          <Icon name="briefcase" size={14} />
          {t('talent.experienceYears', { count: candidate.years_of_experience })}
        </span>
        <span>
          <Icon name="mapPin" size={14} />
          {name(candidate.governorate)}
          {candidate.city ? ` — ${name(candidate.city)}` : ''}
        </span>
        <span>
          <Icon name="clock" size={14} />
          {t(`availabilities.${candidate.availability}`)}
        </span>
      </div>
      {candidate.skills.length > 0 ? (
        <ul className={styles.chips} aria-label={t('talent.skills')}>
          {candidate.skills.slice(0, 4).map((s) => (
            <li key={s}>
              <Badge tone="outline">{s}</Badge>
            </li>
          ))}
          {candidate.skills.length > 4 ? (
            <li>
              <Badge tone="outline">+{candidate.skills.length - 4}</Badge>
            </li>
          ) : null}
        </ul>
      ) : null}
    </Card>
  )
}
