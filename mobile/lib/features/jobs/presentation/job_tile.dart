import 'package:flutter/material.dart';

import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/format/formatters.dart';
import '../../../shared/theme/app_theme.dart';
import '../../discovery/data/discovery_models.dart' show Place;
import '../data/job_models.dart';
import 'job_labels.dart';

/// The salary line, only when the backend marks it visible and carries a bound; never invented.
String? salaryText(AppLocalizations l10n, Job job, String locale) {
  if (!job.salaryVisible) return null;
  final min = job.salaryMin == null
      ? null
      : formatDecimal(job.salaryMin!, locale);
  final max = job.salaryMax == null
      ? null
      : formatDecimal(job.salaryMax!, locale);
  if (min != null && max != null) {
    return l10n.jobSalaryRange(min, max, job.salaryCurrency);
  }
  if (min != null) return l10n.jobSalaryFrom(min, job.salaryCurrency);
  if (max != null) return l10n.jobSalaryUpTo(max, job.salaryCurrency);
  return null;
}

String jobPlace(Place? city, Place? governorate, String languageCode) => [
  city?.name(languageCode),
  governorate?.name(languageCode),
].whereType<String>().where((n) => n.isNotEmpty).join('، ');

class JobTile extends StatelessWidget {
  const JobTile({
    required this.job,
    required this.onTap,
    this.badges = const [],
    super.key,
  });

  final Job job;
  final VoidCallback onTap;
  final List<Widget> badges;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final theme = Theme.of(context);
    final salary = salaryText(l10n, job, locale);
    final place = jobPlace(job.city, job.governorate, locale);
    return Card(
      key: Key('job-${job.id}'),
      margin: const EdgeInsets.only(bottom: RacheetaSpacing.md),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(RacheetaSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(job.title, style: theme.textTheme.titleMedium),
              Text(job.hiringName),
              Text(
                '${professionLabel(l10n, job.profession)} · '
                '${employmentTypeLabel(l10n, job.employmentType)} · '
                '${workModeLabel(l10n, job.workMode)}',
                style: TextStyle(color: theme.colorScheme.primary),
              ),
              if (place.isNotEmpty) Text(place),
              if (salary != null)
                Text(salary, style: theme.textTheme.titleSmall),
              if (job.applicationDeadline != null)
                Text(
                  '${l10n.jobDeadlineLabel}: '
                  '${formatCalendarDate(job.applicationDeadline!, locale)}',
                  style: theme.textTheme.bodySmall,
                ),
              if (job.isFeatured || badges.isNotEmpty) ...[
                const SizedBox(height: RacheetaSpacing.sm),
                Wrap(
                  spacing: RacheetaSpacing.sm,
                  children: [
                    if (job.isFeatured)
                      Chip(
                        label: Text(l10n.jobFeaturedBadge),
                        visualDensity: VisualDensity.compact,
                      ),
                    ...badges,
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
