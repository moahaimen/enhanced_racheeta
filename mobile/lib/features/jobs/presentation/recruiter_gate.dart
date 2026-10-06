import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/states.dart';
import '../../auth/application/account_scope.dart';
import '../../explore/dashboard_index_provider.dart';
import '../application/jobs_providers.dart';
import 'jobs_errors.dart';

/// Shows [child] only while the server's dashboard index lists a recruiter dashboard for the
/// signed-in account (membership is not a `/me` capability). Keyed by account, so another
/// account's answer is never used; the backend still authorizes every recruiter call from the
/// membership.
class RecruiterGate extends ConsumerWidget {
  const RecruiterGate({required this.title, required this.child, super.key});
  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final access = ref.watch(recruiterAccessProvider);
    if (access.isLoading && !access.hasValue) {
      return AppScaffold(title: title, body: const LoadingView());
    }
    if (access.hasError && !access.hasValue) {
      final error = access.error;
      return AppScaffold(
        title: title,
        scrollable: false,
        body: ErrorView(
          message: error is ApiException
              ? jobsErrorMessage(l10n, error, JobsAction.recruiterLoad)
              : l10n.errorUnknown,
          onRetry: () async => ref.invalidate(
            dashboardIndexProvider(ref.read(accountIdProvider)),
          ),
        ),
      );
    }
    if (access.value == true) return child;
    return AppScaffold(
      title: title,
      scrollable: false,
      body: EmptyView(icon: Icons.lock_outline, title: l10n.recruiterOnly),
    );
  }
}
