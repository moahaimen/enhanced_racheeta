import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/features/auth/application/providers.dart';

import 'fake_backend.dart';
import 'patient_support.dart';

const providerAccountId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const otherProviderAccountId = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const patientRecordId = '55555555-5555-4555-8555-555555555555';

/// A PROVIDER account as `/me` returns it (capability codes from the backend role registry).
Map<String, Object?> providerAccountJson({
  String id = providerAccountId,
  String name = 'Dr. Sara Ahmed',
  List<String>? permissions,
}) => {
  ...accountJson(id: id, name: name, role: 'PROVIDER'),
  'permissions':
      permissions ??
      <String>[
        'accounts.view_self',
        'accounts.edit_self',
        'providers.search',
        'providers.manage_own_profile',
        'reservations.manage_received',
        'offers.manage_own',
      ],
};

Map<String, Object?> dashboardJson({
  bool facility = false,
  String name = 'Dr. Sara Ahmed',
  int total = 9,
  int upcoming = 3,
  double? average = 4.5,
  int reviews = 6,
  List<Map<String, Object?>>? upcomingList,
}) => {
  'profile': {
    'display_name': name,
    'provider_type': facility ? 'MEDICAL_CENTER' : 'DOCTOR',
    'verification_status': 'VERIFIED',
    'is_visible': true,
  },
  'reservations': {
    'total': total,
    'upcoming': upcoming,
    'by_status': {
      'PENDING': 2,
      'CONFIRMED': 3,
      'COMPLETED': 2,
      'REJECTED': 1,
      'CANCELLED': 1,
      'NO_SHOW': 0,
    },
  },
  'upcoming':
      upcomingList ??
      [
        {
          'id': reservationId,
          'provider_name_snapshot': name,
          'service_title_snapshot': 'Consultation',
          'starts_at': '2026-10-05T06:00:00Z',
          'ends_at': '2026-10-05T06:30:00Z',
          'status': 'CONFIRMED',
          'patient_name': 'Layla Hassan',
        },
      ],
  'reviews': {
    'average_rating': average,
    'review_count': reviews,
    'distribution': {'1': 0, '2': 0, '3': 1, '4': 2, '5': 3},
  },
  'offers': {'total': 4, 'running_now': 2, 'scheduled': 1},
  'unread': {'notifications': 7, 'messages': 2},
  if (facility)
    'practitioners': {
      'active': 5,
      'incoming_requests': 1,
      'outgoing_invitations': 2,
    },
};

Map<String, Object?> providerReservationJson({
  String id = reservationId,
  String status = 'PENDING',
  String startsAt = '2026-10-05T06:00:00Z',
  String patient = 'Layla Hassan',
  String note = '',
  List<Map<String, Object?>>? transitions,
}) => {
  ...reservationJson(
    id: id,
    status: status,
    startsAt: startsAt,
    note: note,
    transitions: transitions,
  ),
  'patient': {'id': patientRecordId, 'full_name': patient},
};

/// A slot as the provider list returns it (with `is_active`).
Map<String, Object?> ownSlotJson(
  String id,
  String startsAtUtc, {
  bool active = true,
  int minutes = 30,
  String title = 'Consultation',
}) {
  final slot = slotJson(id, startsAtUtc, minutes: minutes);
  return {
    ...slot,
    'is_active': active,
    'service': {...(slot['service']! as Map<String, Object?>), 'title': title},
  };
}

Map<String, Object?> ownServiceJson({
  String id = serviceId,
  String title = 'Consultation',
  int? duration = 30,
  bool active = true,
}) => {
  'id': id,
  'title': title,
  'description': '',
  'specialty': null,
  'price': '25000.00',
  'currency': 'IQD',
  'duration_minutes': duration,
  'is_active': active,
  'created_at': '2026-09-01T10:00:00Z',
  'updated_at': '2026-09-01T10:00:00Z',
};

/// Scripts the dashboard endpoints for an account.
void dashboardsFor(
  FakeBackend b, {
  bool facility = false,
  Map<String, Object?>? dashboard,
  List<String>? index,
}) {
  final kind = facility ? 'facility' : 'doctor';
  b
    ..on(
      'GET',
      '/api/v1/dashboards/',
      (_) => FakeBackend.json(200, {
        'dashboards': index ?? [kind],
      }),
    )
    ..on(
      'GET',
      '/api/v1/dashboards/$kind',
      (_) =>
          FakeBackend.json(200, dashboard ?? dashboardJson(facility: facility)),
    );
}

/// Makes `/me` answer as [account] and refreshes the session: the authenticated account changes
/// while the widget tree (and any open screen) stays exactly where it is, which is the situation
/// that hides stale-state bugs (a logout/login would rebuild the routes).
Future<void> switchAccountTo(
  WidgetTester tester,
  Harness h,
  Map<String, Object?> account,
) async {
  h.backend.on('GET', '/api/v1/me', (_) => FakeBackend.json(200, account));
  await tester.runAsync(
    () => h.container.read(sessionControllerProvider.notifier).refreshAccount(),
  );
  await tester.pump(const Duration(milliseconds: 50));
  await tester.pump(const Duration(milliseconds: 50));
}
