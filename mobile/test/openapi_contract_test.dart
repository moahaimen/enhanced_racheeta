import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// The committed OpenAPI file (`docs/api/openapi.yaml`) is the contract. These tests read it and
/// prove every endpoint, field and enum value the Phase 11B code depends on is declared there, so
/// the app cannot silently rely on something the backend does not promise. (No YAML dependency:
/// the generated file is regular enough to scan.)
final String _yaml = File('../docs/api/openapi.yaml').readAsStringSync();

/// The lines of `    Name:` under `components.schemas`, up to the next schema.
String _schema(String name) {
  final match = RegExp(
    '^    $name:\n(.*?)(?=^    \\w|\\z)',
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
    '^  ${RegExp.escape(path)}:\n(.*?)(?=^  /|^components:|\\z)',
    multiLine: true,
    dotAll: true,
  ).firstMatch(_yaml);
  expect(match, isNotNull, reason: 'path $path is missing from openapi.yaml');
  return RegExp(
    r'^    (get|post|put|patch|delete):',
    multiLine: true,
  ).allMatches(match!.group(1)!).map((m) => m.group(1)!).toSet();
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
}
