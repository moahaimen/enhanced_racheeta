import 'package:flutter/foundation.dart';

import '../../../core/api/json_reader.dart';
import '../../discovery/data/discovery_models.dart' show Place, Specialty;

/// `EmployerPublic`: the organisation behind a job.
@immutable
class EmployerSummary {
  const EmployerSummary({
    required this.id,
    required this.name,
    required this.isVerified,
    required this.isRecruitmentAgency,
  });

  factory EmployerSummary.fromJson(Object? json) {
    final r = JsonReader.of(json, 'EmployerPublic');
    return EmployerSummary(
      id: r.string('id'),
      name: r.string('name'),
      isVerified: r.booleanOr('is_verified', fallback: false),
      isRecruitmentAgency: r.booleanOr(
        'is_recruitment_agency',
        fallback: false,
      ),
    );
  }

  final String id;
  final String name;
  final bool isVerified;
  final bool isRecruitmentAgency;
}

/// A job: `JobCard` (list), `JobPublic` (detail) or `JobEmployer` (the organisation's own view).
/// Vocabulary fields are kept as the backend's codes so an unknown future value still renders.
/// `application_deadline` is a calendar DATE (not an instant). Salary is shown only when the
/// backend says `salary_visible`; no value is invented.
@immutable
class Job {
  const Job({
    required this.id,
    required this.title,
    required this.employer,
    required this.hiringEmployer,
    required this.hiringOrganizationName,
    required this.profession,
    required this.generalSpecialty,
    required this.detailedSpecialty,
    required this.governorate,
    required this.city,
    required this.employmentType,
    required this.workMode,
    required this.shiftType,
    required this.minimumDegree,
    required this.minimumExperienceYears,
    required this.salaryMin,
    required this.salaryMax,
    required this.salaryCurrency,
    required this.salaryVisible,
    required this.isFeatured,
    required this.publishedAt,
    required this.applicationDeadline,
    this.description,
    this.responsibilities,
    this.requirements,
    this.workplaceText,
    this.numberOfOpenings,
    this.isOpen,
    this.status,
    this.applicationsCount,
    this.closedAt,
  });

  factory Job.fromCardJson(Object? json) =>
      Job._parse(JsonReader.of(json, 'JobCard'));

  factory Job.fromPublicJson(Object? json) {
    final r = JsonReader.of(json, 'JobPublic');
    return Job._parse(
      r,
      description: r.stringOr('description'),
      responsibilities: r.stringOr('responsibilities'),
      requirements: r.stringOr('requirements'),
      workplaceText: r.stringOr('workplace_text'),
      numberOfOpenings: r.integerOrNull('number_of_openings'),
      isOpen: r.boolean('is_open'),
    );
  }

  factory Job.fromEmployerJson(Object? json) {
    final r = JsonReader.of(json, 'JobEmployer');
    return Job._parse(
      r,
      description: r.stringOr('description'),
      responsibilities: r.stringOr('responsibilities'),
      requirements: r.stringOr('requirements'),
      workplaceText: r.stringOr('workplace_text'),
      numberOfOpenings: r.integerOrNull('number_of_openings'),
      isOpen: r.booleanOr('is_open', fallback: false),
      status: r.string('status'),
      applicationsCount: r.integerOrNull('applications_count'),
      closedAt: r.instantOrNull('closed_at'),
    );
  }

  factory Job._parse(
    JsonReader r, {
    String? description,
    String? responsibilities,
    String? requirements,
    String? workplaceText,
    int? numberOfOpenings,
    bool? isOpen,
    String? status,
    int? applicationsCount,
    DateTime? closedAt,
  }) => Job(
    id: r.string('id'),
    title: r.string('title'),
    employer: EmployerSummary.fromJson(r.raw('employer')),
    hiringEmployer: r.optional('hiring_employer', EmployerSummary.fromJson),
    hiringOrganizationName: r.stringOr('hiring_organization_name'),
    profession: r.stringOr('profession'),
    generalSpecialty: r.optional('general_specialty', Specialty.fromJson),
    detailedSpecialty: r.stringOr('detailed_specialty'),
    governorate: r.optional('governorate', Place.fromJson),
    city: r.optional('city', Place.fromJson),
    employmentType: r.stringOr('employment_type'),
    workMode: r.stringOr('work_mode'),
    shiftType: r.stringOr('shift_type'),
    minimumDegree: r.stringOr('minimum_degree'),
    minimumExperienceYears: r.integerOrNull('minimum_experience_years') ?? 0,
    salaryMin: r.stringOrNull('salary_min'),
    salaryMax: r.stringOrNull('salary_max'),
    salaryCurrency: r.stringOr('salary_currency'),
    salaryVisible: r.booleanOr('salary_visible', fallback: false),
    isFeatured: r.booleanOr('is_featured', fallback: false),
    publishedAt: r.instantOrNull('published_at'),
    applicationDeadline: r.calendarDateOrNull('application_deadline'),
    description: description,
    responsibilities: responsibilities,
    requirements: requirements,
    workplaceText: workplaceText,
    numberOfOpenings: numberOfOpenings,
    isOpen: isOpen,
    status: status,
    applicationsCount: applicationsCount,
    closedAt: closedAt,
  );

  final String id;
  final String title;
  final EmployerSummary employer;

  /// Set only for agency jobs that name the organisation they hire for.
  final EmployerSummary? hiringEmployer;
  final String hiringOrganizationName;
  final String profession;
  final Specialty? generalSpecialty;
  final String detailedSpecialty;
  final Place? governorate;
  final Place? city;
  final String employmentType;
  final String workMode;
  final String shiftType;
  final String minimumDegree;
  final int minimumExperienceYears;
  final String? salaryMin;
  final String? salaryMax;
  final String salaryCurrency;
  final bool salaryVisible;
  final bool isFeatured;
  final DateTime? publishedAt;
  final DateTime? applicationDeadline;

  // Detail (public and employer views).
  final String? description;
  final String? responsibilities;
  final String? requirements;
  final String? workplaceText;
  final int? numberOfOpenings;

  /// The backend's own verdict on whether the job accepts applications right now.
  final bool? isOpen;

  // Employer view only.
  final String? status;
  final int? applicationsCount;
  final DateTime? closedAt;

  /// The name shown as "who is hiring": the organisation the agency names, else the employer.
  String get hiringName =>
      hiringEmployer?.name ??
      (hiringOrganizationName.isNotEmpty
          ? hiringOrganizationName
          : employer.name);

  @override
  String toString() => 'Job($profession, $employmentType)';
}

/// `ApplicationSeeker`: the seeker's own application. The profile `snapshot`, the interviews and
/// the transition history are deliberately not modelled: the screen shows only what it needs.
@immutable
class JobApplication {
  const JobApplication({
    required this.id,
    required this.job,
    required this.status,
    required this.coverText,
    required this.submittedAt,
  });

  factory JobApplication.fromJson(Object? json) {
    final r = JsonReader.of(json, 'ApplicationSeeker');
    return JobApplication(
      id: r.string('id'),
      job: Job.fromCardJson(r.raw('job')),
      status: r.string('status'),
      coverText: r.stringOr('cover_text'),
      submittedAt: r.instant('submitted_at'),
    );
  }

  final String id;
  final Job job;

  /// `ApplicationStatusEnum` code; unknown codes are kept.
  final String status;
  final String coverText;
  final DateTime submittedAt;

  /// Statuses from which the seeker may withdraw (a UI hint; the backend decides).
  bool get canWithdraw => const {
    'SUBMITTED',
    'REVIEWING',
    'SHORTLISTED',
    'INTERVIEW',
  }.contains(status);

  @override
  String toString() => 'JobApplication($status)';
}

/// `RecruiterDashboard`: counts computed by the backend for the member's own organisation. The
/// application/interview blocks are null when the account may not see them
/// (`applications_access` then says why).
@immutable
class RecruiterDashboard {
  const RecruiterDashboard({
    required this.organizationName,
    required this.verificationStatus,
    required this.recruitmentStatus,
    required this.canRecruit,
    required this.myRole,
    required this.jobsTotal,
    required this.jobsOpenNow,
    required this.jobsByStatus,
    required this.applicationsAccess,
    required this.applicationsTotal,
    required this.applicationsAwaitingReview,
    required this.applicationsLast7Days,
    required this.interviewsTotal,
    required this.seatsActive,
    required this.seatsLimit,
  });

  factory RecruiterDashboard.fromJson(Object? json) {
    final r = JsonReader.of(json, 'RecruiterDashboard');
    final organization = r.object('organization');
    final jobs = r.object('jobs');
    final byStatus = jobs.object('by_status');
    final applications = r.objectOrNull('applications');
    final interviews = r.objectOrNull('interviews');
    final seats = r.object('seats');
    return RecruiterDashboard(
      organizationName: organization.string('name'),
      verificationStatus: organization.stringOr('verification_status'),
      recruitmentStatus: organization.stringOr('recruitment_status'),
      canRecruit: organization.boolean('can_recruit'),
      myRole: organization.stringOr('my_role'),
      jobsTotal: jobs.integer('total'),
      jobsOpenNow: jobs.integer('open_now'),
      jobsByStatus: {
        for (final code in const [
          'DRAFT',
          'PENDING_ADMIN_REVIEW',
          'PUBLISHED',
          'CLOSED',
          'EXPIRED',
          'REJECTED',
          'SUSPENDED',
          'ARCHIVED',
        ])
          code: byStatus.integerOrNull(code) ?? 0,
      },
      applicationsAccess: r.stringOrNull('applications_access'),
      applicationsTotal: applications?.integer('total'),
      applicationsAwaitingReview: applications?.integer('awaiting_review'),
      applicationsLast7Days: applications?.integer('last_7_days'),
      interviewsTotal: interviews?.integer('total'),
      seatsActive: seats.integer('active_members'),
      seatsLimit: seats.integerOrNull('limit'),
    );
  }

  final String organizationName;
  final String verificationStatus;
  final String recruitmentStatus;
  final bool canRecruit;
  final String myRole;
  final int jobsTotal;
  final int jobsOpenNow;
  final Map<String, int> jobsByStatus;
  final String? applicationsAccess;
  final int? applicationsTotal;
  final int? applicationsAwaitingReview;
  final int? applicationsLast7Days;
  final int? interviewsTotal;
  final int seatsActive;
  final int? seatsLimit;

  bool get hasApplicationFigures => applicationsTotal != null;
}
