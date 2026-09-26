import type { JobCard as JobCardData } from '../../../api'

export function formatSalary(job: Pick<JobCardData, 'salary_min' | 'salary_max' | 'salary_currency'>, language: string): string | null {
  if (job.salary_min === null && job.salary_max === null) return null
  const fmt = (v: string) => Number(v).toLocaleString(language)
  if (job.salary_min !== null && job.salary_max !== null) return `${fmt(job.salary_min)} – ${fmt(job.salary_max)} ${job.salary_currency}`
  return `${fmt((job.salary_min ?? job.salary_max) as string)} ${job.salary_currency}`
}
