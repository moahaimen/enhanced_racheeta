import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../auth/application/account_scope.dart';
import '../data/job_models.dart';
import 'jobs_providers.dart';

void invalidateMyApplications(WidgetRef ref) =>
    ref.invalidate(myApplicationsProvider);

/// After closing a job the organisation's list, opened details and the recruiter dashboard are
/// reloaded from the backend.
void invalidateEmployerJobs(WidgetRef ref) {
  ref
    ..invalidate(employerJobsProvider)
    ..invalidate(employerJobDetailProvider)
    ..invalidate(recruiterDashboardProvider);
}

/// `POST /jobs/{id}/apply`: exactly one request, for the initiating account only (see
/// `runAsAccount`); the backend decides (already applied, closed, deadline, profile, limits).
Future<JobApplication> applyToJob(
  WidgetRef ref, {
  required String jobId,
  required String coverText,
}) => runAsAccount(
  ref,
  () => ref.read(jobsApiProvider).apply(jobId, coverText: coverText),
  () => invalidateMyApplications(ref),
);

/// `POST /jobs/me/applications/{id}/withdraw`.
Future<JobApplication> withdrawApplication(WidgetRef ref, String id) =>
    runAsAccount(
      ref,
      () => ref.read(jobsApiProvider).withdraw(id),
      () => invalidateMyApplications(ref),
    );

/// `POST /jobs/employer/jobs/{id}/close`.
Future<Job> closeEmployerJob(WidgetRef ref, String id) => runAsAccount(
  ref,
  () => ref.read(jobsApiProvider).closeJob(id),
  () => invalidateEmployerJobs(ref),
);
