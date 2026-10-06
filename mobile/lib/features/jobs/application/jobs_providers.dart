import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/page.dart';
import '../../../core/paging/paged_notifier.dart';
import '../../../shared/search/search_query.dart';
import '../../auth/application/account_scope.dart';
import '../../auth/application/providers.dart';
import '../../explore/dashboard_index_provider.dart';
import '../data/job_models.dart';
import '../data/jobs_api.dart';
import '../provider_capability.dart';

final Provider<JobsApi> jobsApiProvider = Provider<JobsApi>(
  (ref) => JobsApi(ref.watch(apiClientProvider)),
);

/// The job search form (text + filters); reset when the account changes.
class JobQueryController extends Notifier<SearchQuery> {
  @override
  SearchQuery build() {
    ref.watch(accountIdProvider);
    return const SearchQuery();
  }

  void update(SearchQuery next) => state = next;
}

final jobQueryProvider = NotifierProvider<JobQueryController, SearchQuery>(
  JobQueryController.new,
  retry: noRetry,
);

/// Public job search results. Rebuilt (epoch bumped, requests cancelled, late responses dropped)
/// when the query or the account changes, so an older query's answer never replaces the current
/// one and page N of one query is never appended to another.
class JobsController extends PagedNotifier<Job> {
  late SearchQuery _query;

  @override
  PagedState<Job> build() {
    ref.watch(accountIdProvider);
    _query = ref.watch(jobQueryProvider);
    return start();
  }

  @override
  Future<Page<Job>> fetchPage(int page, CancelToken token) => ref
      .read(jobsApiProvider)
      .jobs(
        _query,
        page: page,
        pageSize: PagedNotifier.pageSize,
        cancelToken: token,
      );
}

final jobsProvider = NotifierProvider<JobsController, PagedState<Job>>(
  JobsController.new,
  retry: noRetry,
);

/// One public job (public data, disposed with the screen).
final jobDetailProvider = FutureProvider.autoDispose.family<Job, String>((
  ref,
  id,
) {
  final token = CancelToken();
  ref.onDispose(() => token.cancel('disposed'));
  return ref.watch(jobsApiProvider).job(id, cancelToken: token);
}, retry: noRetry);

/// The signed-in job seeker's own applications. Rebuilt on an account change and invalidated after
/// applying or withdrawing.
class MyApplicationsController extends PagedNotifier<JobApplication> {
  @override
  PagedState<JobApplication> build() {
    ref.watch(accountIdProvider);
    return start();
  }

  @override
  Future<Page<JobApplication>> fetchPage(int page, CancelToken token) => ref
      .read(jobsApiProvider)
      .myApplications(
        page: page,
        pageSize: PagedNotifier.pageSize,
        cancelToken: token,
      );
}

final myApplicationsProvider =
    NotifierProvider<MyApplicationsController, PagedState<JobApplication>>(
      MyApplicationsController.new,
      retry: noRetry,
    );

/// Whether the server lists a recruiter dashboard for this account (membership, not a `/me`
/// capability). Keyed by account via [dashboardIndexProvider].
final recruiterAccessProvider = Provider.autoDispose<AsyncValue<bool>>((ref) {
  final index = ref.watch(dashboardIndexProvider(ref.watch(accountIdProvider)));
  return index.whenData((keys) => keys.contains(recruiterDashboardKey));
});

final recruiterDashboardProvider = FutureProvider.autoDispose
    .family<RecruiterDashboard, String?>((ref, accountId) {
      final token = CancelToken();
      ref.onDispose(() => token.cancel('disposed'));
      return ref.watch(jobsApiProvider).recruiterDashboard(cancelToken: token);
    }, retry: noRetry);

/// The status filter of the organisation's jobs; reset when the account changes.
class EmployerJobQueryController extends Notifier<SearchQuery> {
  @override
  SearchQuery build() {
    ref.watch(accountIdProvider);
    return const SearchQuery();
  }

  void update(SearchQuery next) => state = next;
}

final employerJobQueryProvider =
    NotifierProvider<EmployerJobQueryController, SearchQuery>(
      EmployerJobQueryController.new,
      retry: noRetry,
    );

/// The member's organisation's jobs (the backend scopes them to the membership).
class EmployerJobsController extends PagedNotifier<Job> {
  late SearchQuery _query;

  @override
  PagedState<Job> build() {
    ref.watch(accountIdProvider);
    _query = ref.watch(employerJobQueryProvider);
    return start();
  }

  @override
  Future<Page<Job>> fetchPage(int page, CancelToken token) => ref
      .read(jobsApiProvider)
      .employerJobs(
        _query,
        page: page,
        pageSize: PagedNotifier.pageSize,
        cancelToken: token,
      );
}

final employerJobsProvider =
    NotifierProvider<EmployerJobsController, PagedState<Job>>(
      EmployerJobsController.new,
      retry: noRetry,
    );

final employerJobDetailProvider = FutureProvider.autoDispose
    .family<Job, AccountScoped<String>>((ref, key) {
      final token = CancelToken();
      ref.onDispose(() => token.cancel('disposed'));
      return ref
          .watch(jobsApiProvider)
          .employerJob(key.value, cancelToken: token);
    }, retry: noRetry);
