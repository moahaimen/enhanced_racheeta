import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_exception.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/format/labels.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/async_action_button.dart';
import '../../../shared/widgets/states.dart';
import '../../auth/application/account_scope.dart';
import '../application/jobs_providers.dart';
import '../data/job_models.dart';
import 'job_labels.dart';
import 'jobs_errors.dart';
import 'recruiter_gate.dart';

/// The recruiter's home: the backend's own counts for the member's organisation. Application and
/// interview figures appear only when the backend returns them (it withholds them for accounts
/// without the right, and says why).
class RecruiterWorkspacePage extends ConsumerWidget {
  const RecruiterWorkspacePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    return RecruiterGate(
      title: l10n.recruiterWorkspaceTitle,
      child: const _Dashboard(),
    );
  }
}

class _Dashboard extends ConsumerWidget {
  const _Dashboard();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final provider = recruiterDashboardProvider(ref.watch(accountIdProvider));
    final dashboard = ref.watch(provider);

    // Keyed by account: a value here always belongs to the signed-in account.
    if (dashboard.isLoading && !dashboard.hasValue) {
      return AppScaffold(
        title: l10n.recruiterWorkspaceTitle,
        body: const LoadingView(),
      );
    }
    if (dashboard.hasError && !dashboard.hasValue) {
      final error = dashboard.error;
      return AppScaffold(
        title: l10n.recruiterWorkspaceTitle,
        scrollable: false,
        body: ErrorView(
          message: error is ApiException
              ? jobsErrorMessage(l10n, error, JobsAction.recruiterLoad)
              : l10n.errorUnknown,
          onRetry: () async => ref.invalidate(provider),
        ),
      );
    }
    final data = dashboard.requireValue;
    return AppScaffold(
      title: l10n.recruiterWorkspaceTitle,
      scrollable: false,
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(provider);
          try {
            await ref.read(provider.future);
          } on Object {
            // the error view reports it
          }
        },
        child: ListView(
          children: [
            _Organization(data: data),
            const SizedBox(height: RacheetaSpacing.lg),
            _Jobs(data: data),
            const SizedBox(height: RacheetaSpacing.lg),
            _Applications(data: data),
            const SizedBox(height: RacheetaSpacing.lg),
            _Seats(data: data),
            const SizedBox(height: RacheetaSpacing.lg),
            PrimaryButton(
              key: const Key('open-recruiter-jobs'),
              label: l10n.recruiterOpenJobs,
              icon: Icons.work_outline,
              onPressed: () async => context.push('/recruiter/jobs'),
            ),
          ],
        ),
      ),
    );
  }
}

Widget _stat(BuildContext context, String label, String value) => Padding(
  padding: const EdgeInsets.symmetric(vertical: RacheetaSpacing.xs),
  child: Row(
    children: [
      Expanded(child: Text(label)),
      Text(value, style: Theme.of(context).textTheme.titleSmall),
    ],
  ),
);

Widget _section(
  BuildContext context,
  Key key,
  String title,
  List<Widget> children,
) => Card(
  key: key,
  child: Padding(
    padding: const EdgeInsets.all(RacheetaSpacing.lg),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Semantics(
          header: true,
          child: Text(title, style: Theme.of(context).textTheme.titleMedium),
        ),
        const SizedBox(height: RacheetaSpacing.sm),
        ...children,
      ],
    ),
  ),
);

class _Organization extends StatelessWidget {
  const _Organization({required this.data});
  final RecruiterDashboard data;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return _section(
      context,
      const Key('recruiter-organization'),
      data.organizationName,
      [
        _stat(context, l10n.recruiterMyRole, data.myRole),
        _stat(
          context,
          l10n.dashboardVerification,
          verificationLabel(l10n, data.verificationStatus),
        ),
        _stat(context, l10n.recruiterRecruitmentStatus, data.recruitmentStatus),
        Text(
          data.canRecruit
              ? l10n.recruiterCanRecruit
              : l10n.recruiterCannotRecruit,
        ),
      ],
    );
  }
}

class _Jobs extends StatelessWidget {
  const _Jobs({required this.data});
  final RecruiterDashboard data;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return _section(
      context,
      const Key('recruiter-jobs'),
      l10n.recruiterJobsHeading,
      [
        _stat(context, l10n.dashboardTotal, '${data.jobsTotal}'),
        _stat(context, l10n.recruiterOpenNow, '${data.jobsOpenNow}'),
        const Divider(),
        for (final entry in data.jobsByStatus.entries)
          _stat(context, jobStatusLabel(l10n, entry.key), '${entry.value}'),
      ],
    );
  }
}

class _Applications extends StatelessWidget {
  const _Applications({required this.data});
  final RecruiterDashboard data;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    if (!data.hasApplicationFigures) {
      return _section(
        context,
        const Key('recruiter-applications'),
        l10n.recruiterApplicationsHeading,
        [Text(l10n.recruiterApplicationsWithheld)],
      );
    }
    return _section(
      context,
      const Key('recruiter-applications'),
      l10n.recruiterApplicationsHeading,
      [
        _stat(context, l10n.dashboardTotal, '${data.applicationsTotal}'),
        _stat(
          context,
          l10n.recruiterAwaitingReview,
          '${data.applicationsAwaitingReview}',
        ),
        _stat(
          context,
          l10n.recruiterLast7Days,
          '${data.applicationsLast7Days}',
        ),
        if (data.interviewsTotal != null)
          _stat(
            context,
            l10n.recruiterInterviewsHeading,
            '${data.interviewsTotal}',
          ),
      ],
    );
  }
}

class _Seats extends StatelessWidget {
  const _Seats({required this.data});
  final RecruiterDashboard data;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return _section(
      context,
      const Key('recruiter-seats'),
      l10n.recruiterSeatsHeading,
      [
        _stat(context, l10n.recruiterSeatsActive, '${data.seatsActive}'),
        if (data.seatsLimit != null)
          _stat(context, l10n.recruiterSeatsLimit, '${data.seatsLimit}'),
      ],
    );
  }
}
