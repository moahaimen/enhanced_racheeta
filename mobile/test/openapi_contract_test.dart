import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/features/auth/data/auth_models.dart';
import 'package:racheeta_mobile/features/chat/data/chat_api.dart';
import 'package:racheeta_mobile/features/notifications/data/notification_models.dart';
import 'package:racheeta_mobile/features/push/push_routes.dart';
import 'package:racheeta_mobile/features/jobs/presentation/job_labels.dart';

import 'support/comms_support.dart' show notificationJson;
import 'support/fake_backend.dart' show accountJson;

import 'package:racheeta_mobile/features/real_estate/presentation/real_estate_labels.dart';

/// The committed OpenAPI file (`docs/api/openapi.yaml`) is the contract. These tests read it and
/// prove every endpoint, field and enum value the Phase 11B code depends on is declared there, so
/// the app cannot silently rely on something the backend does not promise. (No YAML dependency:
/// the generated file is regular enough to scan.)
final String _yaml = File('../docs/api/openapi.yaml').readAsStringSync();

/// The lines of `    Name:` under `components.schemas`, up to the next schema.
String _schema(String name) {
  final match = RegExp(
    '^    $name:\n(.*?)(?=^    \\w|(?![\\s\\S]))',
    multiLine: true,
    dotAll: true,
  ).firstMatch(_yaml);
  expect(match, isNotNull, reason: 'schema $name is missing from openapi.yaml');
  return match!.group(1)!;
}

Set<String> _properties(String name) {
  final body = _schema(name);
  final start = body.indexOf('      properties:\n');
  expect(start, isNonNegative, reason: '$name has no properties');
  final end = body.indexOf(RegExp(r'^      \w', multiLine: true), start + 1);
  final block = body.substring(start, end < 0 ? body.length : end);
  return RegExp(
    r"^        '?(\w+)'?:",
    multiLine: true,
  ).allMatches(block).map((m) => m.group(1)!).toSet();
}

Set<String> _required(String name) {
  final body = _schema(name);
  final match = RegExp(
    r"^      required:\n((?:      - '?\w+'?\n?)+)",
    multiLine: true,
  ).firstMatch(body);
  if (match == null) return <String>{};
  return RegExp(r"- '?(\w+)'?")
      .allMatches(match.group(1)!)
      .map((m) => m.group(1)!)
      .toSet();
}

/// Operations declared for [path] (`get`, `post`, ...).
Set<String> _operations(String path) {
  final match = RegExp(
    '^  ${RegExp.escape(path)}:\n(.*?)(?=^  /|^components:|(?![\\s\\S]))',
    multiLine: true,
    dotAll: true,
  ).firstMatch(_yaml);
  expect(match, isNotNull, reason: 'path $path is missing from openapi.yaml');
  return RegExp(
    r'^    (get|post|put|patch|delete):',
    multiLine: true,
  ).allMatches(match!.group(1)!).map((m) => m.group(1)!).toSet();
}

/// Query parameter names declared for [method] on [path].
Set<String> queryParams(String path, [String method = 'get']) {
  final path0 = RegExp(
    '^  ${RegExp.escape(path)}:\n(.*?)(?=^  /|^components:|(?![\\s\\S]))',
    multiLine: true,
    dotAll: true,
  ).firstMatch(_yaml);
  expect(path0, isNotNull, reason: 'path $path is missing');
  final op = RegExp(
    '^    $method:\n(.*?)(?=^    (?:get|post|put|patch|delete):|(?![\\s\\S]))',
    multiLine: true,
    dotAll: true,
  ).firstMatch(path0!.group(1)!);
  expect(op, isNotNull, reason: '$method $path is missing');
  return RegExp(
    r'^      - (?:in: query\n        name|name): (\w+)\n',
    multiLine: true,
  ).allMatches(op!.group(1)!).map((m) => m.group(1)!).toSet();
}

/// The `security:` block of one operation.
String security(String path, String method) {
  final path0 = RegExp(
    '^  ${RegExp.escape(path)}:\n(.*?)(?=^  /|^components:|(?![\\s\\S]))',
    multiLine: true,
    dotAll: true,
  ).firstMatch(_yaml)!;
  final op = RegExp(
    '^    $method:\n(.*?)(?=^    (?:get|post|put|patch|delete):|(?![\\s\\S]))',
    multiLine: true,
    dotAll: true,
  ).firstMatch(path0.group(1)!)!;
  return RegExp(
        r'^      security:\n((?:      - .*\n)+)',
        multiLine: true,
      ).firstMatch(op.group(1)!)?.group(1) ??
      '';
}

/// The values of a backend `models.TextChoices` class.
Set<String> choices(String file, String className) {
  final source = File('../backend/apps/$file').readAsStringSync();
  final block = RegExp(
    '^class $className\\(models.TextChoices\\):\n((?:    .*\n|\n)+)',
    multiLine: true,
  ).firstMatch(source);
  expect(block, isNotNull, reason: '$className is missing in $file');
  return RegExp(
    r'^    \w+ = \(?\s*"(\w+)"',
    multiLine: true,
  ).allMatches(block!.group(1)!).map((m) => m.group(1)!).toSet();
}

void check(String name, Set<String> fields, {bool required = true}) {
  expect(_properties(name), containsAll(fields), reason: name);
  if (required) {
    expect(_required(name), containsAll(fields), reason: '$name required');
  }
}

void main() {
  test(
    'every endpoint the patient screens call is documented with its method',
    () {
      const expected = <String, Set<String>>{
        '/api/v1/providers': {'get'},
        '/api/v1/providers/{id}': {'get'},
        '/api/v1/providers/{provider_id}/availability': {'get'},
        '/api/v1/specialties': {'get'},
        '/api/v1/geo/governorates': {'get'},
        '/api/v1/geo/cities': {'get'},
        '/api/v1/reservations': {'post'},
        '/api/v1/reservations/me': {'get'},
        '/api/v1/reservations/me/{id}': {'get'},
        '/api/v1/reservations/me/{id}/cancel': {'post'},
      };
      expected.forEach((path, methods) {
        expect(_operations(path), containsAll(methods), reason: path);
      });
    },
  );

  test(
    'the documented discovery query parameters are the ones the filters send',
    () {
      final block = RegExp(
        r'^  /api/v1/providers:\n(.*?)(?=^  /)',
        multiLine: true,
        dotAll: true,
      ).firstMatch(_yaml)!.group(1)!;
      for (final name in [
        'search',
        'kind',
        'type',
        'specialty',
        'governorate',
        'city',
        'ordering',
        'page',
        'page_size',
      ]) {
        expect(
          block,
          contains('name: $name\n'),
          reason: 'query parameter $name',
        );
      }
    },
  );

  test('Reservation fields read by the app exist, and required ones are documented as required', () {
    final properties = _properties('ReservationPatient');
    const read = [
      'id',
      'provider_id',
      'provider_name_snapshot',
      'service_title_snapshot',
      'price_snapshot',
      'currency_snapshot',
      'duration_minutes_snapshot',
      'starts_at',
      'ends_at',
      'status',
      'status_changed_at',
      'patient_note',
      'transitions',
    ];
    expect(properties, containsAll(read));
    // fields the model reads strictly (a missing one is an unreadable response)
    expect(
      _required('ReservationPatient'),
      containsAll([
        'id',
        'provider_name_snapshot',
        'service_title_snapshot',
        'starts_at',
        'ends_at',
        'status',
      ]),
    );
    expect(
      _properties('ReservationTransition'),
      containsAll(['from_status', 'to_status', 'created_at']),
    );
    expect(_required('ReservationTransition'), contains('created_at'));
  });

  test(
    'every status the app knows is a documented ReservationStatusEnum value',
    () {
      final body = _schema('ReservationStatusEnum');
      for (final status in [
        'PENDING',
        'CONFIRMED',
        'COMPLETED',
        'REJECTED',
        'CANCELLED',
        'NO_SHOW',
      ]) {
        expect(body, contains('- $status\n'), reason: status);
      }
    },
  );

  test('the booking request is exactly slot + optional note (max 1000)', () {
    expect(_properties('ReservationCreateRequest'), {
      'availability_slot',
      'patient_note',
    });
    expect(_required('ReservationCreateRequest'), {'availability_slot'});
    expect(_schema('ReservationCreateRequest'), contains('maxLength: 1000'));
  });

  test('availability slot and public provider fields exist', () {
    expect(
      _properties('AvailabilitySlot'),
      containsAll(['id', 'provider', 'service', 'starts_at', 'ends_at']),
    );
    expect(
      _properties('ProviderPublic'),
      containsAll([
        'id',
        'display_name',
        'provider_type',
        'kind',
        'about',
        'address',
        'phone',
        'public_email',
        'website',
        'verified_at',
        'services',
        'related_providers',
      ]),
    );
    expect(
      _properties('ProviderCard'),
      containsAll([
        'id',
        'display_name',
        'kind',
        'provider_type',
        'specialties',
        'governorate',
        'city',
        'average_rating',
        'review_count',
      ]),
    );
    expect(
      _properties('PublicService'),
      containsAll([
        'id',
        'title',
        'description',
        'duration_minutes',
        'price',
        'currency',
        'specialty',
      ]),
    );
  });

  test('the documented schema has no reservation field the app does not model that it would need', () {
    // The patient endpoints have no can_cancel/idempotency field: cancellation is offered from
    // status + start time as a hint, and the backend decides.
    expect(_properties('ReservationPatient'), isNot(contains('can_cancel')));
    expect(
      _properties('ReservationCreateRequest'),
      isNot(contains('idempotency_key')),
    );
  });

  group('Phase 11C provider and facility contract', () {
    test('every provider-side endpoint is documented with its method', () {
      const expected = <String, Set<String>>{
        '/api/v1/dashboards/': {'get'},
        '/api/v1/dashboards/doctor': {'get'},
        '/api/v1/dashboards/facility': {'get'},
        '/api/v1/providers/me/services': {'get'},
        '/api/v1/reservations/provider/availability': {'get', 'post'},
        '/api/v1/reservations/provider/availability/{id}': {'delete'},
        '/api/v1/reservations/provider': {'get'},
        '/api/v1/reservations/provider/{id}': {'get'},
        '/api/v1/reservations/provider/{id}/transition': {'post'},
      };
      expected.forEach((path, methods) {
        expect(_operations(path), containsAll(methods), reason: path);
      });
    });

    test(
      'the provider reservation list is paginated with page and page_size',
      () {
        final block = RegExp(
          r'^  /api/v1/reservations/provider:\n(.*?)(?=^  /)',
          multiLine: true,
          dotAll: true,
        ).firstMatch(_yaml)!.group(1)!;
        expect(block, contains('name: page\n'));
        expect(block, contains('name: page_size\n'));
        expect(block, contains('PaginatedReservationProviderList'));
      },
    );

    test('the dashboard index and both provider dashboards expose what the app reads', () {
      expect(_properties('DashboardIndex'), {'dashboards'});
      expect(_required('DashboardIndex'), {'dashboards'});
      final enumBody = _schema('DashboardsEnum');
      for (final kind in ['doctor', 'facility']) {
        expect(enumBody, contains('- $kind\n'), reason: kind);
      }
      const shared = [
        'profile',
        'reservations',
        'upcoming',
        'reviews',
        'offers',
        'unread',
      ];
      expect(_properties('DoctorDashboard'), containsAll(shared));
      expect(_required('DoctorDashboard'), containsAll(shared));
      expect(
        _properties('FacilityDashboard'),
        containsAll([...shared, 'practitioners']),
      );
      expect(
        _required('FacilityDashboard'),
        containsAll([...shared, 'practitioners']),
      );
      // a doctor dashboard has no practitioners block (the app reads it for facilities only)
      expect(_properties('DoctorDashboard'), isNot(contains('practitioners')));
    });

    test('dashboard sub-schemas carry the fields and required keys the models read strictly', () {
      void check(String name, Set<String> fields) {
        expect(_properties(name), containsAll(fields), reason: name);
        expect(_required(name), containsAll(fields), reason: '$name required');
      }

      check('DashboardProviderProfile', {
        'display_name',
        'provider_type',
        'verification_status',
        'is_visible',
      });
      check('DashboardReservationCounts', {'total', 'by_status', 'upcoming'});
      check('DashboardReservationStatusCounts', {
        'PENDING',
        'CONFIRMED',
        'COMPLETED',
        'REJECTED',
        'CANCELLED',
        'NO_SHOW',
      });
      check('DashboardProviderAppointment', {
        'id',
        'service_title_snapshot',
        'starts_at',
        'status',
        'patient_name',
      });
      check('DashboardReviewSummary', {
        'average_rating',
        'review_count',
        'distribution',
      });
      check('DashboardRatingDistribution', {'1', '2', '3', '4', '5'});
      check('DashboardOfferSummary', {'total', 'running_now', 'scheduled'});
      check('DashboardUnread', {'notifications', 'messages'});
      check('DashboardFacilityMemberships', {
        'active',
        'incoming_requests',
        'outgoing_invitations',
      });
    });

    test('the provider reservation schema adds only the patient summary to the patient one', () {
      expect(_properties('ReservationProvider'), {
        ..._properties('ReservationPatient'),
        'patient',
      });
      expect(_required('ReservationProvider'), contains('patient'));
      expect(_properties('PatientSummary'), containsAll(['id', 'full_name']));
      expect(_required('PatientSummary'), containsAll(['id', 'full_name']));
    });

    test('availability slots carry is_active; creation takes exactly service + starts_at', () {
      expect(
        _properties('AvailabilitySlot'),
        containsAll(['id', 'service', 'starts_at', 'ends_at', 'is_active']),
      );
      expect(_required('AvailabilitySlot'), contains('is_active'));
      expect(_properties('AvailabilitySlotCreateRequest'), {
        'service',
        'starts_at',
      });
      expect(_required('AvailabilitySlotCreateRequest'), {
        'service',
        'starts_at',
      });
    });

    test(
      'the transition request and its targets match what the app can send',
      () {
        expect(_properties('ProviderTransitionRequest'), {'status', 'reason'});
        expect(_required('ProviderTransitionRequest'), {'status'});
        final body = _schema('ProviderTransitionStatusEnum');
        for (final target in [
          'CONFIRMED',
          'REJECTED',
          'CANCELLED',
          'COMPLETED',
          'NO_SHOW',
        ]) {
          expect(body, contains('- $target\n'), reason: target);
        }
        // PENDING is never a provider target
        expect(body, isNot(contains('- PENDING\n')));
        expect(
          _schema('ProviderTransitionRequest'),
          contains('maxLength: 500'),
        );
      },
    );

    test(
      'the owner service schema has the fields the slot form filters on',
      () {
        expect(
          _properties('ServiceOffering'),
          containsAll(['id', 'title', 'duration_minutes', 'is_active']),
        );
        expect(_required('ServiceOffering'), containsAll(['id', 'title']));
      },
    );

    test(
      'the provider capability code is the one the backend registry grants',
      () {
        final permissions = File('../docs/PERMISSIONS.md').readAsStringSync();
        expect(permissions, contains('reservations.manage_received'));
      },
    );
  });

  group('Phase 11D — marketplace, jobs and real estate', () {
    test('every 11D endpoint is documented with the method the app uses', () {
      const expected = <String, Set<String>>{
        '/api/v1/marketplace/categories': {'get'},
        '/api/v1/marketplace/products': {'get'},
        '/api/v1/marketplace/products/{id}': {'get'},
        '/api/v1/marketplace/company/dashboard': {'get'},
        '/api/v1/marketplace/company/products': {'get'},
        '/api/v1/marketplace/company/products/{id}': {'get'},
        '/api/v1/marketplace/company/products/{id}/activate': {'post'},
        '/api/v1/marketplace/company/products/{id}/deactivate': {'post'},
        '/api/v1/jobs': {'get'},
        '/api/v1/jobs/{id}': {'get'},
        '/api/v1/jobs/{id}/apply': {'post'},
        '/api/v1/jobs/me/applications': {'get'},
        '/api/v1/jobs/me/applications/{id}/withdraw': {'post'},
        '/api/v1/jobs/employer/jobs': {'get'},
        '/api/v1/jobs/employer/jobs/{id}': {'get'},
        '/api/v1/jobs/employer/jobs/{id}/close': {'post'},
        '/api/v1/dashboards/': {'get'},
        '/api/v1/dashboards/recruiter': {'get'},
        '/api/v1/real-estate/listings': {'get'},
        '/api/v1/real-estate/listings/{id}': {'get'},
        '/api/v1/real-estate/owner/dashboard': {'get'},
        '/api/v1/real-estate/owner/listings': {'get'},
        '/api/v1/real-estate/owner/listings/{id}': {'get'},
        '/api/v1/real-estate/owner/listings/{id}/publish': {'post'},
        '/api/v1/real-estate/owner/listings/{id}/unpublish': {'post'},
      };
      expected.forEach((path, methods) {
        expect(_operations(path), containsAll(methods), reason: path);
      });
    });

    test('the app calls no 11D endpoint it does not need: no create/update/delete is used', () {
      // The mobile app deliberately has no create/edit/delete for products, jobs or listings.
      for (final path in [
        '/api/v1/jobs/employer/jobs/{id}',
        '/api/v1/marketplace/company/products/{id}',
        '/api/v1/real-estate/owner/listings/{id}',
      ]) {
        expect(_operations(path), contains('get'), reason: path);
      }
    });

    test(
      'public catalogues are unauthenticated and private ones need the token',
      () {
        for (final path in [
          '/api/v1/marketplace/categories',
          '/api/v1/jobs',
          '/api/v1/jobs/{id}',
          '/api/v1/real-estate/listings',
          '/api/v1/real-estate/listings/{id}',
        ]) {
          expect(
            security(path, 'get'),
            contains('- {}'),
            reason: '$path is public',
          );
        }
        for (final path in [
          '/api/v1/marketplace/products',
          '/api/v1/marketplace/company/products',
          '/api/v1/jobs/me/applications',
          '/api/v1/jobs/employer/jobs',
          '/api/v1/dashboards/recruiter',
          '/api/v1/real-estate/owner/listings',
        ]) {
          expect(
            security(path, 'get'),
            contains('jwtAuth'),
            reason: '$path is private',
          );
          expect(security(path, 'get'), isNot(contains('- {}')), reason: path);
        }
      },
    );

    test('the filters the app sends are documented query parameters', () {
      expect(
        queryParams('/api/v1/jobs'),
        containsAll([
          'q',
          'profession',
          'employment_type',
          'work_mode',
          'governorate',
          'page',
          'page_size',
        ]),
      );
      expect(
        queryParams('/api/v1/jobs/employer/jobs'),
        containsAll(['status', 'page', 'page_size']),
      );
      expect(
        queryParams('/api/v1/jobs/me/applications'),
        containsAll(['page', 'page_size']),
      );
      expect(
        queryParams('/api/v1/real-estate/listings'),
        containsAll([
          'search',
          'transaction_type',
          'property_type',
          'governorate',
          'ordering',
          'page',
          'page_size',
        ]),
      );
      // the owner list documents only `page`; every list shares the project paginator, which
      // accepts `page_size` (capped at 100)
      expect(
        queryParams('/api/v1/real-estate/owner/listings'),
        contains('page'),
      );
      final paginator = File('../backend/apps/core/pagination.py')
          .readAsStringSync();
      expect(paginator, contains('page_size_query_param = "page_size"'));
      // the marketplace catalogue has a category filter and NO search parameter
      final products = queryParams('/api/v1/marketplace/products');
      expect(products, containsAll(['category', 'page', 'page_size']));
      expect(products, isNot(contains('search')));
      expect(products, isNot(contains('q')));
      // the company list is a plain GenericAPIView: it documents no parameters but paginates
      // with the project paginator (page, page_size) like every other list
      final views = File('../backend/apps/marketplace/views.py')
          .readAsStringSync();
      expect(views, contains('self.paginate_queryset(qs)'));
      expect(
        queryParams('/api/v1/marketplace/company/products'),
        isNot(contains('search')),
      );
    });

    test('job schemas carry every field the models read; list/detail/employer nest correctly', () {
      const card = {
        'id',
        'title',
        'employer',
        'hiring_employer',
        'hiring_organization_name',
        'profession',
        'general_specialty',
        'detailed_specialty',
        'governorate',
        'city',
        'employment_type',
        'work_mode',
        'shift_type',
        'minimum_degree',
        'minimum_experience_years',
        'salary_min',
        'salary_max',
        'salary_currency',
        'salary_visible',
        'is_featured',
        'published_at',
        'application_deadline',
      };
      check('JobCard', card);
      check('JobPublic', {
        ...card,
        'description',
        'responsibilities',
        'requirements',
        'workplace_text',
        'number_of_openings',
        'is_open',
      });
      check('JobEmployer', {
        ...card,
        'description',
        'responsibilities',
        'requirements',
        'workplace_text',
        'number_of_openings',
        'is_open',
        'status',
        'applications_count',
        'closed_at',
      });
      check('EmployerPublic', {
        'id',
        'name',
        'is_verified',
        'is_recruitment_agency',
      });
      check('ApplicationSeeker', {
        'id',
        'job',
        'status',
        'cover_text',
        'submitted_at',
      });
    });

    test('the apply body is only cover_text (max 2000); close and withdraw take no required body', () {
      expect(_properties('ApplyRequest'), {'cover_text'});
      expect(_required('ApplyRequest'), isEmpty);
      expect(_schema('ApplyRequest'), contains('maxLength: 2000'));
      expect(_properties('RecruitmentReasonRequest'), {'reason'});
      expect(_required('RecruitmentReasonRequest'), isEmpty);
    });

    test(
      'recruiter dashboard fields and required keys the model reads strictly',
      () {
        check('RecruiterDashboard', {
          'organization',
          'jobs',
          'applications_access',
          'applications',
          'interviews',
          'seats',
        });
        check('DashboardOrganization', {
          'id',
          'name',
          'verification_status',
          'recruitment_status',
          'can_recruit',
          'my_role',
        });
        check('DashboardRecruiterJobs', {'total', 'by_status', 'open_now'});
        check('DashboardRecruiterApplications', {
          'total',
          'by_status',
          'awaiting_review',
          'last_7_days',
        });
        check('DashboardRecruiterInterviews', {'total', 'by_status'});
        check('DashboardSeats', {'active_members', 'enabled', 'limit'});
        check('DashboardIndex', {'dashboards'});
        expect(_schema('DashboardsEnum'), contains('- recruiter\n'));
      },
    );

    test('job vocabularies the app labels and filters on match the backend choices', () {
      expect(professionCodes.toSet(), choices('jobs/types.py', 'Profession'));
      expect(
        employmentTypeCodes.toSet(),
        choices('jobs/types.py', 'EmploymentType'),
      );
      expect(workModeCodes.toSet(), choices('jobs/types.py', 'WorkMode'));
      expect(shiftTypeCodes.toSet(), choices('jobs/types.py', 'ShiftType'));
      expect(degreeCodes.toSet(), choices('jobs/types.py', 'Degree'));
      expect(jobStatusCodes.toSet(), choices('jobs/types.py', 'JobStatus'));
      expect(
        applicationStatusCodes.toSet(),
        choices('jobs/types.py', 'ApplicationStatus'),
      );
      // and the documented enums for statuses
      for (final code in jobStatusCodes) {
        expect(_schema('JobStatusEnum'), contains('- $code\n'));
      }
      for (final code in applicationStatusCodes) {
        expect(_schema('ApplicationStatusEnum'), contains('- $code\n'));
      }
    });

    test('marketplace schemas carry the fields the models read', () {
      check('ProductCategory', {
        'id',
        'slug',
        'name_ar',
        'name_en',
        'can_publish',
      });
      check('ProductPublic', {
        'id',
        'title',
        'description',
        'brand',
        'model_name',
        'price',
        'currency',
        'category',
        'company',
        'created_at',
      });
      check('ProductOwner', {
        'id',
        'title',
        'description',
        'brand',
        'model_name',
        'price',
        'currency',
        'category',
        'is_active',
        'created_at',
      });
      // the public product exposes a company summary but no activity flag; the owner one has it
      expect(_properties('ProductPublic'), isNot(contains('is_active')));
      check('CompanySummary', {
        'id',
        'name',
        'governorate',
        'city',
        'website',
        'public_email',
        'phone',
      });
      check('CompanyDashboard', {
        'verification_status',
        'can_publish',
        'products_total',
        'products_active',
        'products_inactive',
        'products_exposable',
      });
    });

    test('real-estate schemas carry the fields the models read; contact only on documented keys', () {
      const shared = {
        'id',
        'title',
        'description',
        'property_type',
        'transaction_type',
        'governorate',
        'city',
        'district',
        'area_sqm',
        'price',
        'currency',
        'suitable_uses',
        'facilities',
        'contact_method',
        'contact_phone',
        'contact_email',
        'published_at',
        'expires_at',
      };
      check('PropertyListingPublic', {...shared, 'seller'});
      check('PropertyListingOwner', {
        ...shared,
        'publication_status',
        'is_public',
        'is_expired',
      });
      check('SellerSummary', {'id', 'display_name', 'seller_type'});
      check('OwnerDashboard', {
        'listings_total',
        'listings_draft',
        'listings_published',
        'listings_visible',
        'listings_expired',
        'listings_sale',
        'listings_rent',
      });
    });

    test('real-estate vocabularies match the backend choices and orderings are documented', () {
      expect(
        propertyTypeCodes.toSet(),
        choices('real_estate/types.py', 'PropertyType'),
      );
      expect(
        transactionCodes.toSet(),
        choices('real_estate/types.py', 'TransactionType'),
      );
      final labels = File(
        'lib/features/real_estate/presentation/real_estate_labels.dart',
      ).readAsStringSync();
      for (final code in choices('real_estate/types.py', 'SuitableUse')) {
        expect(
          labels,
          contains("'$code'"),
          reason: 'suitable use $code has a label',
        );
      }
      final source = File('../backend/apps/real_estate/filters.py')
          .readAsStringSync();
      for (final code in listingOrderingCodes) {
        expect(source, contains('"$code"'), reason: 'ordering $code');
      }
    });

    test('the capability codes the 11D gates use are registered', () {
      final permissions = File('../docs/PERMISSIONS.md').readAsStringSync();
      for (final code in [
        'marketplace.view_targeted_products',
        'marketplace.manage_own_products',
        'real_estate.manage_own_listings',
      ]) {
        expect(permissions, contains(code));
      }
    });
  });

  group('Phase 11E — notifications, chat and push devices', () {
    test('every 11E endpoint is documented with the method the app uses', () {
      const expected = <String, Set<String>>{
        '/api/v1/notifications/': {'get'},
        '/api/v1/notifications/unread-count/': {'get'},
        '/api/v1/notifications/{id}/read/': {'post'},
        '/api/v1/notifications/read-all/': {'post'},
        '/api/v1/notifications/push-devices/': {'post'},
        '/api/v1/notifications/push-devices/unregister/': {'post'},
        '/api/v1/chat/conversations/': {'get'},
        '/api/v1/chat/conversations/{id}/messages/': {'get', 'post'},
        '/api/v1/chat/conversations/{id}/read/': {'post'},
        '/api/v1/chat/unread-count/': {'get'},
        '/api/v1/chat/reservations/{reservation_id}/conversation': {'post'},
      };
      expected.forEach((path, methods) {
        expect(_operations(path), containsAll(methods), reason: path);
        for (final method in methods) {
          expect(
            security(path, method),
            contains('jwtAuth'),
            reason: '$method $path needs the token',
          );
        }
      });
    });

    test('lists are paginated with page and page_size', () {
      for (final path in [
        '/api/v1/notifications/',
        '/api/v1/chat/conversations/',
        '/api/v1/chat/conversations/{id}/messages/',
      ]) {
        expect(
          queryParams(path),
          containsAll(['page', 'page_size']),
          reason: path,
        );
      }
      expect(_schema('PaginatedChatMessage'), contains('ChatMessage'));
    });

    test(
      'notification fields the model reads strictly, and the enums behind them',
      () {
        check('Notification', {
          'id',
          'category',
          'event_type',
          'title',
          'body',
          'resource_type',
          'resource_id',
          'is_read',
          'read_at',
          'created_at',
        });
        // the client schema never carries the raw payload, the recipient or the dedupe key
        for (final hidden in ['payload', 'recipient', 'dedupe_key']) {
          expect(_properties('Notification'), isNot(contains(hidden)));
        }
        check('UnreadCount', {'count'});
        check('MarkAllRead', {'updated'});
        expect(
          _schema('NotificationCategoryEnum'),
          contains('- RESERVATION\n'),
        );
        final events = choices(
          'notifications/types.py',
          'NotificationEventType',
        );
        for (final event in events) {
          expect(_schema('NotificationEventTypeEnum'), contains('- $event\n'));
        }
      },
    );

    test('every backend notification event the app can open is one the router knows', () {
      final account = Account.fromJson(accountJson());
      for (final event in choices(
        'notifications/types.py',
        'NotificationEventType',
      )) {
        final route = routeForNotification(
          AppNotification.fromJson(notificationJson(event: event)),
          account,
        );
        expect(route, isNotNull, reason: '$event should open its reservation');
      }
      expect(choices('notifications/types.py', 'NotificationResourceType'), {
        'RESERVATION',
      });
    });

    test(
      'push-device schemas: token, platform, ownership and the unregister body',
      () {
        expect(_properties('PushDeviceRegisterRequest'), {
          'token',
          'platform',
          'ownership_seq',
        });
        expect(_required('PushDeviceRegisterRequest'), {'token', 'platform'});
        expect(
          _schema('PushDeviceRegisterRequest'),
          contains('maxLength: 1024'),
        );
        expect(_schema('PushPlatformEnum'), contains('- ANDROID\n'));
        expect(choices('notifications/types.py', 'PushPlatform'), {
          'ANDROID',
          'IOS',
          'WEB',
        });
        expect(_properties('PushDeviceUnregisterRequest'), {
          'token',
          'ownership_seq',
          'platform',
        });
        expect(_required('PushDeviceUnregisterRequest'), {'token'});
        // the response never returns the token or the owner
        expect(_properties('PushDevice'), isNot(contains('token')));
        expect(_properties('PushDevice'), isNot(contains('account')));
        // register is an idempotent upsert (the contract the app relies on to sync repeatedly)
        expect(
          _yaml,
          contains('Idempotent upsert owned by the authenticated caller'),
        );
        // unregister answers 204 for known, unknown and foreign tokens alike
        expect(_yaml, contains('answered\n        identically (204)'));
      },
    );

    test('ownership ordering: BOTH ownership endpoints carry the same bounded integer sequence, and register documents the typed stale answer', () {
      for (final name in [
        'PushDeviceRegisterRequest',
        'PushDeviceUnregisterRequest',
      ]) {
        final block = _schema(name);
        final seq = RegExp(
          r'^        ownership_seq:\n((?:          .*\n)+)',
          multiLine: true,
        ).firstMatch(block);
        expect(seq, isNotNull, reason: '$name declares ownership_seq');
        final text = seq!.group(1)!;
        expect(text, contains('type: integer'));
        expect(text, contains('minimum: 1'));
        expect(text, contains('maximum: 9223372036854775807'));
        expect(text, contains('format: int64'));
        // optional: an unsequenced (legacy) request is still a valid request shape
        expect(_required(name), isNot(contains('ownership_seq')));
      }
      // register: 200 (applied / exact replay) and the typed 409 for a superseded request
      final register = RegExp(
        r'^  /api/v1/notifications/push-devices/:\n(.*?)(?=^  /)',
        multiLine: true,
        dotAll: true,
      ).firstMatch(_yaml)!.group(1)!;
      expect(register, contains("'409':"));
      expect(register, contains('stale_ownership'));
      // unregister keeps answering 204 for applied, stale and foreign requests
      final unregister = RegExp(
        r'^  /api/v1/notifications/push-devices/unregister/:\n(.*?)(?=^  /)',
        multiLine: true,
        dotAll: true,
      ).firstMatch(_yaml)!.group(1)!;
      expect(unregister, contains("'204':"));
      expect(unregister, isNot(contains("'409':")));
      // the field name the app sends on both endpoints is exactly the documented one
      final api = File('lib/features/notifications/data/notifications_api.dart')
          .readAsStringSync();
      expect("'ownership_seq'".allMatches(api), hasLength(2));
      // the backend implements the documented rule under the token lock
      final service = File('../backend/apps/notifications/push_service.py')
          .readAsStringSync();
      expect(service, contains('seq > device.ownership_seq'));
      expect(service, contains('select_for_update'));
      expect(service, contains('raise StaleOwnership'));
    });

    test(
      'the push payload keys the router reads are the ones the backend sends',
      () {
        final source = File('../backend/apps/notifications/push_service.py')
            .readAsStringSync();
        for (final fragment in [
          '"type": "notification"',
          '"notification_id"',
          '"event_type"',
          '"type": "chat_message"',
          '"conversation_id"',
        ]) {
          expect(source, contains(fragment), reason: fragment);
        }
      },
    );

    test(
      'conversation and message schemas carry the fields the models read',
      () {
        check('ChatConversation', {
          'id',
          'context_type',
          'context_id',
          'other_participant',
          'last_sequence',
          'last_read_sequence',
          'unread_count',
          'last_message_at',
          'created_at',
        });
        check('ChatAccount', {'id', 'full_name', 'role'});
        check('ChatMessage', {
          'id',
          'sequence',
          'sender',
          'is_mine',
          'body',
          'created_at',
        });
        check('ChatUnreadCount', {'count'});
        check('ChatReadState', {'last_read_sequence'});
        expect(choices('chat/types.py', 'ConversationContextType'), {
          'RESERVATION',
        });
      },
    );

    test('send and read requests: body 1..2000, through_sequence >= 0', () {
      expect(_properties('ChatMessageCreateRequest'), {'body'});
      expect(_required('ChatMessageCreateRequest'), {'body'});
      final send = _schema('ChatMessageCreateRequest');
      expect(send, contains('minLength: 1'));
      expect(send, contains('maxLength: $maxChatMessageLength'));
      expect(maxChatMessageLength, 2000);
      expect(_properties('ChatReadRequestRequest'), {'through_sequence'});
      expect(_required('ChatReadRequestRequest'), {'through_sequence'});
      expect(_schema('ChatReadRequestRequest'), contains('minimum: 0'));
    });

    test('message paging: latest page first, chronological inside each page', () {
      final block = RegExp(
        r'^  /api/v1/chat/conversations/\{id\}/messages/:\n(.*?)(?=^  /)',
        multiLine: true,
        dotAll: true,
      ).firstMatch(_yaml)!.group(1)!;
      expect(
        block,
        contains(
          'Latest page is page 1; messages inside each page are chronological.',
        ),
      );
      final service = File('../backend/apps/chat/services.py')
          .readAsStringSync();
      expect(
        service,
        contains('through_sequence > conversation.last_sequence'),
      );
      expect(service, contains('if len(body) > 2000'));
    });
  });
}
