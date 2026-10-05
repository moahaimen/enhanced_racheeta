import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/search/search_query.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/async_action_button.dart';
import '../../../shared/widgets/paged_list.dart';
import '../../../shared/widgets/search_filter_bar.dart';
import '../application/jobs_providers.dart';
import '../data/jobs_api.dart';
import 'job_labels.dart';
import 'job_tile.dart';
import 'jobs_errors.dart';
import 'recruiter_gate.dart';

/// The member's organisation's jobs with the backend's own status; filterable by status.
class RecruiterJobsPage extends ConsumerWidget {
  const RecruiterJobsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    return RecruiterGate(title: l10n.recruiterJobsTitle, child: const _List());
  }
}

class _List extends ConsumerWidget {
  const _List();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final query = ref.watch(employerJobQueryProvider);
    final state = ref.watch(employerJobsProvider);
    final controller = ref.read(employerJobsProvider.notifier);
    return AppScaffold(
      title: l10n.recruiterJobsTitle,
      scrollable: false,
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SearchFilterBar(
            query: query,
            showSearch: false,
            filtersTitle: l10n.recruiterJobsTitle,
            onChanged: ref.read(employerJobQueryProvider.notifier).update,
            fieldsBuilder: (ref, l10n) => [
              FilterField(
                key: JobFilterKeys.status,
                label: l10n.filterJobStatus,
                options: [
                  for (final code in jobStatusCodes)
                    FilterOption(code, jobStatusLabel(l10n, code)),
                ],
              ),
            ],
          ),
          const SizedBox(height: RacheetaSpacing.md),
          Expanded(
            child: PagedListView(
              state: state,
              onLoadMore: controller.loadMore,
              onReload: controller.reload,
              errorMessage: (l10n, error) =>
                  jobsErrorMessage(l10n, error, JobsAction.recruiterLoad),
              emptyIcon: Icons.work_outline,
              emptyTitle: l10n.recruiterJobsEmpty,
              emptyMessage: l10n.recruiterJobsEmptyBody,
              emptyAction: query.isEmpty
                  ? null
                  : SecondaryButton(
                      label: l10n.clearFilters,
                      onPressed: () async => ref
                          .read(employerJobQueryProvider.notifier)
                          .update(const SearchQuery()),
                    ),
              itemBuilder: (context, job) => JobTile(
                job: job,
                badges: [
                  Chip(
                    label: Text(jobStatusLabel(l10n, job.status ?? '')),
                    visualDensity: VisualDensity.compact,
                  ),
                ],
                onTap: () => context.push('/recruiter/jobs/${job.id}'),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
