import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/time/time_providers.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/format/formatters.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/async_action_button.dart';
import '../../../shared/widgets/confirm_dialog.dart';
import '../../../shared/widgets/paged_list.dart';
import '../../auth/application/account_scope.dart';
import '../application/jobs_actions.dart';
import '../application/jobs_providers.dart';
import '../data/job_models.dart';
import 'job_labels.dart';
import 'jobs_errors.dart';

/// The signed-in seeker's own applications (the profile snapshot, interviews and history are not
/// shown). Withdrawing is confirmed, one request per tap, and never shown to another account.
class MyApplicationsPage extends ConsumerStatefulWidget {
  const MyApplicationsPage({super.key});

  @override
  ConsumerState<MyApplicationsPage> createState() => _MyApplicationsPageState();
}

class _MyApplicationsPageState extends ConsumerState<MyApplicationsPage> {
  String? _message;
  bool _isError = false;

  void _resetForAccountChange() => setState(() => _message = null);

  Future<void> _withdraw(JobApplication application) async {
    final l10n = AppLocalizations.of(context);
    final accountId = ref.read(accountIdProvider);
    setState(() => _message = null);
    try {
      await withdrawApplication(ref, application.id);
      if (!mounted || ref.read(accountIdProvider) != accountId) return;
      setState(() {
        _message = l10n.applicationWithdrawn;
        _isError = false;
      });
    } on StaleSessionException {
      // The account changed while this was running: nothing to show.
    } on ApiException catch (error) {
      if (!mounted || ref.read(accountIdProvider) != accountId) return;
      setState(() {
        _message = jobsErrorMessage(l10n, error, JobsAction.withdraw);
        _isError = true;
      });
      // The backend refused (or the state changed elsewhere): show what is true now.
      ref.invalidate(myApplicationsProvider);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final theme = Theme.of(context);
    ref.listen<String?>(accountIdProvider, (previous, next) {
      if (previous != next) _resetForAccountChange();
    });
    final wallClock = ref.watch(wallClockProvider);
    final state = ref.watch(myApplicationsProvider);
    final controller = ref.read(myApplicationsProvider.notifier);
    return AppScaffold(
      title: l10n.myApplicationsTitle,
      scrollable: false,
      body: PagedListView(
        state: state,
        onLoadMore: controller.loadMore,
        onReload: controller.reload,
        errorMessage: (l10n, error) =>
            jobsErrorMessage(l10n, error, JobsAction.browse),
        emptyIcon: Icons.assignment_outlined,
        emptyTitle: l10n.myApplicationsEmpty,
        emptyMessage: l10n.myApplicationsEmptyBody,
        showCount: false,
        header: _message == null
            ? null
            : Padding(
                padding: const EdgeInsets.only(bottom: RacheetaSpacing.md),
                child: Semantics(
                  liveRegion: true,
                  child: Text(
                    _message!,
                    key: const Key('applications-message'),
                    style: TextStyle(
                      color: _isError
                          ? theme.colorScheme.error
                          : RacheetaColors.success,
                    ),
                  ),
                ),
              ),
        itemBuilder: (context, application) => Card(
          key: Key('application-${application.id}'),
          margin: const EdgeInsets.only(bottom: RacheetaSpacing.md),
          child: Padding(
            padding: const EdgeInsets.all(RacheetaSpacing.lg),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                InkWell(
                  onTap: () => context.push('/jobs/${application.job.id}'),
                  child: Text(
                    application.job.title,
                    style: theme.textTheme.titleMedium,
                  ),
                ),
                Text(application.job.hiringName),
                const SizedBox(height: RacheetaSpacing.xs),
                Text(
                  applicationStatusLabel(l10n, application.status),
                  key: Key('status-${application.id}'),
                  style: TextStyle(color: theme.colorScheme.primary),
                ),
                Text(
                  l10n.applicationSubmittedOn(
                    formatDate(application.submittedAt, wallClock, locale),
                  ),
                  style: theme.textTheme.bodySmall,
                ),
                if (application.canWithdraw) ...[
                  const SizedBox(height: RacheetaSpacing.sm),
                  SecondaryButton(
                    key: Key('withdraw-${application.id}'),
                    label: l10n.applicationWithdraw,
                    pendingLabel: l10n.applicationWithdrawing,
                    icon: Icons.undo,
                    confirm: () => showConfirmDialog(
                      context,
                      title: l10n.confirmWithdrawTitle,
                      message: l10n.confirmWithdrawBody,
                      confirmLabel: l10n.applicationWithdraw,
                      cancelLabel: l10n.confirmKeepApplication,
                    ),
                    onPressed: () => _withdraw(application),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
