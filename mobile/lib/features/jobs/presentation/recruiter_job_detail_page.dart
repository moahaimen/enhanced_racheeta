import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/async_action_button.dart';
import '../../../shared/widgets/confirm_dialog.dart';
import '../../../shared/widgets/states.dart';
import '../../auth/application/account_scope.dart';
import '../application/jobs_actions.dart';
import '../application/jobs_providers.dart';
import '../data/job_models.dart';
import 'job_detail_page.dart';
import 'job_labels.dart';
import 'jobs_errors.dart';
import 'recruiter_gate.dart';

class RecruiterJobDetailPage extends ConsumerWidget {
  const RecruiterJobDetailPage({required this.jobId, super.key});
  final String jobId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    return RecruiterGate(
      title: l10n.recruiterJobDetailTitle,
      child: _Detail(jobId: jobId),
    );
  }
}

class _Detail extends ConsumerStatefulWidget {
  const _Detail({required this.jobId});
  final String jobId;

  @override
  ConsumerState<_Detail> createState() => _DetailState();
}

class _DetailState extends ConsumerState<_Detail> {
  String? _message;
  bool _isError = false;
  bool _busy = false;

  /// Messages and the busy flag belong to one account.
  void _resetForAccountChange() => setState(() {
    _message = null;
    _isError = false;
    _busy = false;
  });

  Future<void> _close() async {
    final l10n = AppLocalizations.of(context);
    final accountId = ref.read(accountIdProvider);
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      await closeEmployerJob(ref, widget.jobId);
      if (!mounted || ref.read(accountIdProvider) != accountId) return;
      setState(() {
        _busy = false;
        _message = l10n.jobClosedDone;
        _isError = false;
      });
    } on StaleSessionException {
      // The account changed while this was running: its result is never shown to the new one.
    } on ApiException catch (error) {
      if (!mounted || ref.read(accountIdProvider) != accountId) return;
      setState(() {
        _busy = false;
        _message = jobsErrorMessage(l10n, error, JobsAction.close);
        _isError = true;
      });
      // The backend refused (or the state changed elsewhere): show what is true now.
      ref.invalidate(employerJobDetailProvider);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    ref.listen<String?>(accountIdProvider, (previous, next) {
      if (previous != next) _resetForAccountChange();
    });
    final key = (account: ref.watch(accountIdProvider), value: widget.jobId);
    final detail = ref.watch(employerJobDetailProvider(key));

    // Keyed by account; during a reload the last value stays so the page message survives.
    if (detail.hasValue) return _content(context, detail.requireValue);
    if (detail.hasError && !detail.isLoading) {
      final error = detail.error;
      return AppScaffold(
        title: l10n.recruiterJobDetailTitle,
        scrollable: false,
        body: ErrorView(
          message: error is ApiException
              ? jobsErrorMessage(l10n, error, JobsAction.recruiterLoad)
              : l10n.errorUnknown,
          onRetry: () async => ref.invalidate(employerJobDetailProvider(key)),
        ),
      );
    }
    return AppScaffold(
      title: l10n.recruiterJobDetailTitle,
      body: const LoadingView(),
    );
  }

  Widget _content(BuildContext context, Job job) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    // Closing follows the stored status (a hint); the backend decides.
    final canClose = const {
      'PUBLISHED',
      'PENDING_ADMIN_REVIEW',
      'EXPIRED',
    }.contains(job.status);
    return AppScaffold(
      title: l10n.recruiterJobDetailTitle,
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (_message != null)
            Padding(
              padding: const EdgeInsets.only(bottom: RacheetaSpacing.md),
              child: Semantics(
                liveRegion: true,
                child: Text(
                  _message!,
                  key: const Key('job-message'),
                  style: TextStyle(
                    color: _isError
                        ? theme.colorScheme.error
                        : RacheetaColors.success,
                  ),
                ),
              ),
            ),
          Padding(
            padding: const EdgeInsets.only(bottom: RacheetaSpacing.md),
            child: Wrap(
              spacing: RacheetaSpacing.sm,
              children: [
                Chip(
                  label: Text(jobStatusLabel(l10n, job.status ?? '')),
                  visualDensity: VisualDensity.compact,
                ),
                if (job.applicationsCount != null)
                  Chip(
                    label: Text(
                      '${l10n.recruiterApplicationsCount}: ${job.applicationsCount}',
                    ),
                    visualDensity: VisualDensity.compact,
                  ),
              ],
            ),
          ),
          JobFacts(job: job),
          if (canClose) ...[
            const SizedBox(height: RacheetaSpacing.xl),
            // A request still running for the previous account must not leave this account's
            // button disabled: a new account gets a fresh button.
            KeyedSubtree(
              key: ValueKey(ref.watch(accountIdProvider)),
              child: SecondaryButton(
                key: const Key('job-close'),
                label: l10n.jobClose,
                pendingLabel: l10n.jobClosing,
                icon: Icons.lock_outline,
                confirm: () => showConfirmDialog(
                  context,
                  title: l10n.confirmCloseJobTitle,
                  message: l10n.confirmCloseJobBody,
                  confirmLabel: l10n.jobClose,
                  cancelLabel: l10n.confirmKeepJob,
                ),
                onPressed: _busy ? null : _close,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
