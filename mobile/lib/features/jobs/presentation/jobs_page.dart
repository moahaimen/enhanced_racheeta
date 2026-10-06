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
import '../../discovery/application/discovery_providers.dart';
import '../../auth/application/account_scope.dart';
import '../application/jobs_providers.dart';
import '../data/jobs_api.dart';
import 'job_labels.dart';
import 'job_tile.dart';
import 'jobs_errors.dart';

/// Public medical job search: backend text search (`q`), filters and pagination.
class JobsPage extends ConsumerWidget {
  const JobsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final query = ref.watch(jobQueryProvider);
    final results = ref.watch(jobsProvider);
    final controller = ref.read(jobsProvider.notifier);
    return AppScaffold(
      title: l10n.jobsTitle,
      scrollable: false,
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SearchFilterBar(
            scopeKey: ref.watch(accountIdProvider),
            query: query,
            searchLabel: l10n.jobsSearchHint,
            filtersTitle: l10n.jobsFiltersTitle,
            onChanged: ref.read(jobQueryProvider.notifier).update,
            fieldsBuilder: (ref, l10n) {
              final governorates = ref.watch(governoratesProvider);
              final language = Localizations.localeOf(ref.context).languageCode;
              return [
                FilterField(
                  key: JobFilterKeys.profession,
                  label: l10n.filterProfession,
                  options: [
                    for (final code in professionCodes)
                      FilterOption(code, professionLabel(l10n, code)),
                  ],
                ),
                FilterField(
                  key: JobFilterKeys.employmentType,
                  label: l10n.filterEmploymentType,
                  options: [
                    for (final code in employmentTypeCodes)
                      FilterOption(code, employmentTypeLabel(l10n, code)),
                  ],
                ),
                FilterField(
                  key: JobFilterKeys.workMode,
                  label: l10n.filterWorkMode,
                  options: [
                    for (final code in workModeCodes)
                      FilterOption(code, workModeLabel(l10n, code)),
                  ],
                ),
                FilterField(
                  key: JobFilterKeys.governorate,
                  label: l10n.filterGovernorate,
                  failed: governorates.hasError,
                  options: governorates.value
                      ?.map((p) => FilterOption(p.id, p.name(language)))
                      .toList(),
                ),
              ];
            },
          ),
          const SizedBox(height: RacheetaSpacing.md),
          Expanded(
            child: PagedListView(
              state: results,
              onLoadMore: controller.loadMore,
              onReload: controller.reload,
              errorMessage: (l10n, error) =>
                  jobsErrorMessage(l10n, error, JobsAction.browse),
              emptyIcon: Icons.work_outline,
              emptyTitle: l10n.jobsEmptyTitle,
              emptyMessage: l10n.discoverEmptyBody,
              emptyAction: query.isEmpty
                  ? null
                  : SecondaryButton(
                      label: l10n.clearFilters,
                      onPressed: () async => ref
                          .read(jobQueryProvider.notifier)
                          .update(const SearchQuery()),
                    ),
              header: Align(
                alignment: AlignmentDirectional.centerEnd,
                child: TextButton.icon(
                  key: const Key('open-my-applications'),
                  icon: const Icon(Icons.assignment_turned_in_outlined),
                  label: Text(l10n.myApplicationsTitle),
                  onPressed: () => context.push('/jobs/applications'),
                ),
              ),
              itemBuilder: (context, job) => JobTile(
                job: job,
                onTap: () => context.push('/jobs/${job.id}'),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
