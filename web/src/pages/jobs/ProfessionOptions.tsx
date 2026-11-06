import { useTranslation } from 'react-i18next'

import { PROFESSION_GROUPS } from '../../api/jobs.types'

/** Profession <option>s grouped like the backend's PROFESSION_GROUPS (healthcare first). */
export function ProfessionOptions() {
  const { t } = useTranslation()
  return (
    <>
      {PROFESSION_GROUPS.map(([group, list]) => (
        <optgroup key={group} label={t(`professionGroups.${group}`)}>
          {list.map((p) => (
            <option key={p} value={p}>
              {t(`professions.${p}`)}
            </option>
          ))}
        </optgroup>
      ))}
    </>
  )
}
