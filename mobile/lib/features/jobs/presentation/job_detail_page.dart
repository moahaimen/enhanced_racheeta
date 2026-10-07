import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_exception.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/format/formatters.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/async_action_button.dart';
import '../../../shared/widgets/states.dart';
import '../../auth/application/account_scope.dart';
import '../application/jobs_actions.dart';
import '../application/jobs_providers.dart';
import '../data/job_models.dart';
import 'job_labels.dart';
import 'job_tile.dart';
import 'jobs_errors.dart';
import '../../../shared/widgets/selectable_value.dart';

/// Longest cover note the backend accepts (`ApplyRequest.cover_text`, maxLength 2000).
const int maxCoverTextLength = 2000;

/// One public job exactly as the API exposes it, plus the INTERNAL application form (the API has
/// no external apply URL, so nothing here opens an external link).
class JobDetailPage extends ConsumerWidget {
  const JobDetailPage({required this.jobId, super.key});
  final String jobId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final detail = ref.watch(jobDetailProvider(jobId));
    return detail.when(
      loading: () =>
          AppScaffold(title: l10n.jobDetailTitle, body: const LoadingView()),
      error: (error, _) => AppScaffold(
        title: l10n.jobDetailTitle,
        scrollable: false,
        body: ErrorView(
          message: error is ApiException
              ? jobsErrorMessage(l10n, error, JobsAction.browse)
              : l10n.errorUnknown,
          onRetry: () async => ref.invalidate(jobDetailProvider(jobId)),
        ),
      ),
      data: (job) => _JobDetail(job: job),
    );
  }
}

/// The job card shared with the recruiter's own detail.
class JobFacts extends StatelessWidget {
  const JobFacts({required this.job, super.key});
  final Job job;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final theme = Theme.of(context);
    final salary = salaryText(l10n, job, locale);
    final place = jobPlace(job.city, job.governorate, locale);
    Widget row(String label, String value) => Padding(
      padding: const EdgeInsets.only(bottom: RacheetaSpacing.sm),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          SelectableValue(value),
        ],
      ),
    );
    Widget text(String label, String? value) => value == null || value.isEmpty
        ? const SizedBox.shrink()
        : Card(
            child: Padding(
              padding: const EdgeInsets.all(RacheetaSpacing.lg),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Semantics(
                    header: true,
                    child: Text(label, style: theme.textTheme.titleMedium),
                  ),
                  const SizedBox(height: RacheetaSpacing.sm),
                  SelectableValue(value),
                ],
              ),
            ),
          );
    final specialty = job.generalSpecialty?.name(locale) ?? '';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(RacheetaSpacing.lg),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Semantics(
                  header: true,
                  child: Text(job.title, style: theme.textTheme.headlineSmall),
                ),
                const SizedBox(height: RacheetaSpacing.xs),
                Text(
                  job.hiringEmployer != null ||
                          job.hiringOrganizationName.isNotEmpty
                      ? '${job.employer.name} · ${l10n.jobOnBehalfOf(job.hiringName)}'
                      : job.employer.name,
                ),
                const SizedBox(height: RacheetaSpacing.sm),
                Text(
                  '${professionLabel(l10n, job.profession)} · '
                  '${employmentTypeLabel(l10n, job.employmentType)} · '
                  '${workModeLabel(l10n, job.workMode)}',
                  style: TextStyle(color: theme.colorScheme.primary),
                ),
                if (salary != null) ...[
                  const SizedBox(height: RacheetaSpacing.sm),
                  Text(
                    salary,
                    key: const Key('job-salary'),
                    style: theme.textTheme.titleMedium,
                  ),
                ],
              ],
            ),
          ),
        ),
        const SizedBox(height: RacheetaSpacing.lg),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(RacheetaSpacing.lg),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (place.isNotEmpty) row(l10n.detailLocation, place),
                if (job.workplaceText != null && job.workplaceText!.isNotEmpty)
                  row(l10n.jobWorkplaceLabel, job.workplaceText!),
                if (specialty.isNotEmpty)
                  row(l10n.jobSpecialtyLabel, specialty),
                if (job.detailedSpecialty.isNotEmpty)
                  row(l10n.jobSpecialtyLabel, job.detailedSpecialty),
                if (job.shiftType.isNotEmpty)
                  row(l10n.jobShiftLabel, shiftTypeLabel(l10n, job.shiftType)),
                if (job.minimumDegree.isNotEmpty)
                  row(
                    l10n.jobDegreeLabel,
                    degreeLabel(l10n, job.minimumDegree),
                  ),
                row(
                  l10n.jobExperienceLabel,
                  l10n.jobExperienceYears(job.minimumExperienceYears),
                ),
                if (job.numberOfOpenings != null)
                  row(l10n.jobOpeningsLabel, '${job.numberOfOpenings}'),
                if (job.applicationDeadline != null)
                  row(
                    l10n.jobDeadlineLabel,
                    formatCalendarDate(job.applicationDeadline!, locale),
                  ),
              ],
            ),
          ),
        ),
        if ((job.description ?? '').isNotEmpty) ...[
          const SizedBox(height: RacheetaSpacing.lg),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(RacheetaSpacing.lg),
              child: SelectableValue(job.description!),
            ),
          ),
        ],
        if ((job.responsibilities ?? '').isNotEmpty) ...[
          const SizedBox(height: RacheetaSpacing.lg),
          text(l10n.jobResponsibilitiesLabel, job.responsibilities),
        ],
        if ((job.requirements ?? '').isNotEmpty) ...[
          const SizedBox(height: RacheetaSpacing.lg),
          text(l10n.jobRequirementsLabel, job.requirements),
        ],
      ],
    );
  }
}

class _JobDetail extends ConsumerStatefulWidget {
  const _JobDetail({required this.job});
  final Job job;

  @override
  ConsumerState<_JobDetail> createState() => _JobDetailState();
}

class _JobDetailState extends ConsumerState<_JobDetail> {
  final TextEditingController _cover = TextEditingController();
  String? _message;
  bool _isError = false;
  bool _applied = false;
  String? _coverError;

  @override
  void dispose() {
    _cover.dispose();
    super.dispose();
  }

  /// The note, the messages and "I applied" belong to one account: on logout or an account switch
  /// they are discarded even though this page stays on screen.
  void _resetForAccountChange() {
    _cover.clear();
    setState(() {
      _message = null;
      _isError = false;
      _applied = false;
      _coverError = null;
    });
  }

  Future<void> _apply() async {
    final l10n = AppLocalizations.of(context);
    if (_cover.text.trim().length > maxCoverTextLength) {
      setState(() => _coverError = l10n.applyCoverTooLong(maxCoverTextLength));
      return;
    }
    final accountId = ref.read(accountIdProvider);
    setState(() {
      _coverError = null;
      _message = null;
    });
    try {
      await applyToJob(ref, jobId: widget.job.id, coverText: _cover.text);
      if (!mounted || ref.read(accountIdProvider) != accountId) return;
      setState(() {
        _applied = true;
        _message = l10n.applySent;
        _isError = false;
      });
    } on StaleSessionException {
      // The account changed while this was running: its result is never shown to the new one.
    } on ApiException catch (error) {
      if (!mounted || ref.read(accountIdProvider) != accountId) return;
      setState(() {
        _message = jobsErrorMessage(l10n, error, JobsAction.apply);
        _isError = true;
        // The backend says the seeker already applied: there is nothing left to send.
        if (error.code == 'already_applied') _applied = true;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    ref.listen<String?>(accountIdProvider, (previous, next) {
      if (previous != next) _resetForAccountChange();
    });
    final job = widget.job;
    final open = job.isOpen ?? true;
    return AppScaffold(
      title: l10n.jobDetailTitle,
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          JobFacts(job: job),
          const SizedBox(height: RacheetaSpacing.xl),
          if (!open)
            Text(l10n.jobClosedNotice, key: const Key('job-closed'))
          else ...[
            Semantics(
              header: true,
              child: Text(l10n.applyTitle, style: theme.textTheme.titleMedium),
            ),
            const SizedBox(height: RacheetaSpacing.sm),
            if (_message != null)
              Padding(
                padding: const EdgeInsets.only(bottom: RacheetaSpacing.md),
                child: Semantics(
                  liveRegion: true,
                  child: Text(
                    _message!,
                    key: const Key('apply-message'),
                    style: TextStyle(
                      color: _isError
                          ? theme.colorScheme.error
                          : RacheetaColors.success,
                    ),
                  ),
                ),
              ),
            if (!_applied) ...[
              TextField(
                key: const Key('apply-cover'),
                controller: _cover,
                minLines: 3,
                maxLines: 6,
                keyboardType: TextInputType.multiline,
                decoration: InputDecoration(
                  labelText: l10n.applyCoverText,
                  errorText: _coverError,
                  errorMaxLines: 3,
                ),
              ),
              const SizedBox(height: RacheetaSpacing.md),
              // A request still running for the previous account must not leave B's button
              // disabled: a new account gets a fresh button.
              KeyedSubtree(
                key: ValueKey(ref.watch(accountIdProvider)),
                child: PrimaryButton(
                  key: const Key('apply-submit'),
                  label: l10n.applyAction,
                  pendingLabel: l10n.applyPending,
                  icon: Icons.send,
                  onPressed: _apply,
                ),
              ),
            ] else
              SecondaryButton(
                key: const Key('apply-view-mine'),
                label: l10n.applyViewMine,
                onPressed: () async => context.push('/jobs/applications'),
              ),
          ],
        ],
      ),
    );
  }
}
