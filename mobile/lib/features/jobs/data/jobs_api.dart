import 'package:dio/dio.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/page.dart';
import '../../../shared/search/search_query.dart';
import 'job_models.dart';

/// The `GET /jobs` filter parameters the app sends (all documented).
abstract final class JobFilterKeys {
  static const profession = 'profession';
  static const employmentType = 'employment_type';
  static const workMode = 'work_mode';
  static const governorate = 'governorate';
  static const status = 'status';
}

/// Public job search, the seeker's own applications and the recruiter's organisation jobs. The
/// backend decides openness, ownership, organisation scope and every lifecycle transition.
class JobsApi {
  const JobsApi(this._client);
  final ApiClient _client;

  /// `GET /jobs` (public, paginated; the backend orders featured first, then newest).
  Future<Page<Job>> jobs(
    SearchQuery query, {
    int page = 1,
    int pageSize = 20,
    CancelToken? cancelToken,
  }) => _client.getPage<Job>(
    '/api/v1/jobs',
    parseItem: Job.fromCardJson,
    page: page,
    pageSize: pageSize,
    query: query.toQuery(searchKey: 'q'),
    auth: false,
    cancelToken: cancelToken,
  );

  /// `GET /jobs/{id}` (public; 404 unless the job is publicly visible).
  Future<Job> job(String id, {CancelToken? cancelToken}) => _client.get<Job>(
    '/api/v1/jobs/${Uri.encodeComponent(id)}',
    parse: Job.fromPublicJson,
    auth: false,
    cancelToken: cancelToken,
  );

  /// `POST /jobs/{id}/apply {cover_text}` → 201. An INTERNAL application (the API has no external
  /// apply URL); needs a job-seeker profile. Never retried automatically.
  Future<JobApplication> apply(
    String id, {
    String coverText = '',
    CancelToken? cancelToken,
  }) => _client.post<JobApplication>(
    '/api/v1/jobs/${Uri.encodeComponent(id)}/apply',
    body: <String, Object?>{
      if (coverText.trim().isNotEmpty) 'cover_text': coverText.trim(),
    },
    parse: JobApplication.fromJson,
    cancelToken: cancelToken,
  );

  /// `GET /jobs/me/applications` (own applications, paginated).
  Future<Page<JobApplication>> myApplications({
    int page = 1,
    int pageSize = 20,
    CancelToken? cancelToken,
  }) => _client.getPage<JobApplication>(
    '/api/v1/jobs/me/applications',
    parseItem: JobApplication.fromJson,
    page: page,
    pageSize: pageSize,
    cancelToken: cancelToken,
  );

  /// `POST /jobs/me/applications/{id}/withdraw` → the updated application. Never retried.
  Future<JobApplication> withdraw(String id, {CancelToken? cancelToken}) =>
      _client.post<JobApplication>(
        '/api/v1/jobs/me/applications/${Uri.encodeComponent(id)}/withdraw',
        body: const <String, Object?>{},
        parse: JobApplication.fromJson,
        cancelToken: cancelToken,
      );

  /// `GET /dashboards/recruiter` (the member's own organisation; parameterless).
  Future<RecruiterDashboard> recruiterDashboard({CancelToken? cancelToken}) =>
      _client.get<RecruiterDashboard>(
        '/api/v1/dashboards/recruiter',
        parse: RecruiterDashboard.fromJson,
        cancelToken: cancelToken,
      );

  /// `GET /jobs/employer/jobs` (the organisation's own jobs; `?status=` filter).
  Future<Page<Job>> employerJobs(
    SearchQuery query, {
    int page = 1,
    int pageSize = 20,
    CancelToken? cancelToken,
  }) => _client.getPage<Job>(
    '/api/v1/jobs/employer/jobs',
    parseItem: Job.fromEmployerJson,
    page: page,
    pageSize: pageSize,
    query: {...query.filters},
    cancelToken: cancelToken,
  );

  /// `GET /jobs/employer/jobs/{id}` (a job of another organisation is a plain 404).
  Future<Job> employerJob(String id, {CancelToken? cancelToken}) =>
      _client.get<Job>(
        '/api/v1/jobs/employer/jobs/${Uri.encodeComponent(id)}',
        parse: Job.fromEmployerJson,
        cancelToken: cancelToken,
      );

  /// `POST /jobs/employer/jobs/{id}/close` → the updated job. Never retried.
  Future<Job> closeJob(String id, {CancelToken? cancelToken}) =>
      _client.post<Job>(
        '/api/v1/jobs/employer/jobs/${Uri.encodeComponent(id)}/close',
        body: const <String, Object?>{},
        parse: Job.fromEmployerJson,
        cancelToken: cancelToken,
      );
}
