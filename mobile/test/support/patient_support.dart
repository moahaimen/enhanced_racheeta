import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/misc.dart' show Override;
import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/app/app.dart';
import 'package:racheeta_mobile/app/router.dart';
import 'package:racheeta_mobile/core/time/time_providers.dart';

import 'fake_backend.dart';

/// "Now" for every patient test: 2026-10-03 09:00 UTC. The wall clock is fixed at UTC+3 (Baghdad)
/// so grouping/formatting never depends on the machine running the tests.
final DateTime testNow = DateTime.utc(2026, 10, 3, 9);
const Duration testOffset = Duration(hours: 3);

const providerId = '22222222-2222-4222-8222-222222222222';
const serviceId = '33333333-3333-4333-8333-333333333333';
const reservationId = '44444444-4444-4444-8444-444444444444';

Map<String, Object?> placeJson(String id, String ar, String en) => {
  'id': id,
  'slug': en.toLowerCase(),
  'name_ar': ar,
  'name_en': en,
};

Map<String, Object?> cardJson({
  String id = providerId,
  String name = 'Dr. Sara Ahmed',
  String type = 'DOCTOR',
  String kind = 'PRACTITIONER',
  double? rating = 4.5,
  int reviews = 12,
}) => {
  'id': id,
  'display_name': name,
  'image_url': '',
  'kind': kind,
  'provider_type': type,
  'average_rating': rating,
  'review_count': reviews,
  'governorate': placeJson('g1', 'بغداد', 'Baghdad'),
  'city': placeJson('c1', 'الكرادة', 'Karrada'),
  'specialties': [
    {
      'id': 's1',
      'slug': 'cardiology',
      'name_ar': 'أمراض القلب',
      'name_en': 'Cardiology',
      'parent': null,
    },
  ],
};

Map<String, Object?> serviceJson({
  String id = serviceId,
  String title = 'Consultation',
  int? duration = 30,
  String price = '25000.00',
}) => {
  'id': id,
  'title': title,
  'description': 'A first visit',
  'duration_minutes': duration,
  'price': price,
  'currency': 'IQD',
  'specialty': null,
};

Map<String, Object?> providerJson({
  String id = providerId,
  String name = 'Dr. Sara Ahmed',
  List<Map<String, Object?>>? services,
  String? verifiedAt = '2026-09-01T10:00:00Z',
}) => {
  ...cardJson(id: id, name: name),
  'about': 'Cardiologist with ten years of practice.',
  'address': 'Street 14, Karrada',
  'phone': '+9647700000000',
  'public_email': 'clinic@example.com',
  'website': 'https://clinic.example.com',
  'latitude': null,
  'longitude': null,
  'verified_at': verifiedAt,
  'services': services ?? [serviceJson()],
  'related_providers': <Object?>[],
};

Map<String, Object?> slotJson(
  String id,
  String startsAtUtc, {
  int minutes = 30,
}) {
  final start = DateTime.parse(startsAtUtc);
  return {
    'id': id,
    'starts_at': startsAtUtc,
    'ends_at': start.add(Duration(minutes: minutes)).toIso8601String(),
    'is_active': true,
    'created_at': '2026-10-01T10:00:00Z',
    'provider': {
      'id': providerId,
      'display_name': 'Dr. Sara Ahmed',
      'provider_type': 'DOCTOR',
      'kind': 'PRACTITIONER',
      'image_url': '',
    },
    'service': serviceJson(),
  };
}

Map<String, Object?> reservationJson({
  String id = reservationId,
  String status = 'PENDING',
  String startsAt = '2026-10-05T06:00:00Z',
  String note = '',
  String provider = 'Dr. Sara Ahmed',
  List<Map<String, Object?>>? transitions,
}) => {
  'id': id,
  'availability_slot_id': 'slot-1',
  'provider_id': providerId,
  'service_id': serviceId,
  'provider_name_snapshot': provider,
  'service_title_snapshot': 'Consultation',
  'price_snapshot': '25000.00',
  'currency_snapshot': 'IQD',
  'duration_minutes_snapshot': 30,
  'starts_at': startsAt,
  'ends_at': DateTime.parse(startsAt)
      .add(const Duration(minutes: 30))
      .toIso8601String(),
  'status': status,
  'status_changed_at': '2026-10-03T08:00:00Z',
  'patient_note': note,
  'created_at': '2026-10-03T08:00:00Z',
  'review_id': null,
  'transitions':
      transitions ??
      [
        {
          'from_status': 'PENDING',
          'to_status': status,
          'reason': '',
          'created_at': '2026-10-03T08:00:00Z',
        },
      ],
};

Map<String, Object?> pageJson(
  List<Object?> results, {
  int? count,
  String? next,
}) => {
  'count': count ?? results.length,
  'next': next,
  'previous': null,
  'results': results,
};

final List<Override> clockOverrides = [
  nowProvider.overrideWithValue(() => testNow),
  wallClockProvider.overrideWithValue((utc) => utc.toUtc().add(testOffset)),
  // the inverse: a date/time picked in the UTC+3 wall clock, as a UTC instant
  localToUtcProvider.overrideWithValue(
    (wall) => DateTime.utc(
      wall.year,
      wall.month,
      wall.day,
      wall.hour,
      wall.minute,
    ).subtract(testOffset),
  ),
];

/// Scripts the session endpoints so the app starts signed in as [accountJsonBody].
void signedInAs(FakeBackend b, Map<String, Object?> accountJsonBody) => b
  ..on(
    'POST',
    '/api/v1/auth/refresh',
    (_) => FakeBackend.json(200, tokens('a2', 'r2')),
  )
  ..on('GET', '/api/v1/me', (_) => FakeBackend.json(200, accountJsonBody));

/// Boots the whole app signed in and opens [path].
Future<Harness> pumpPatientApp(
  WidgetTester tester, {
  required void Function(FakeBackend backend) script,
  String path = '/',
  String language = 'en',
  Map<String, Object?>? account,
  Size? size,
}) async {
  if (size != null) {
    tester.view.physicalSize = size;
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
  }
  final h = Harness(
    storedRefresh: 'r1',
    autoRestore: true,
    language: language,
    extraOverrides: clockOverrides,
  );
  addTearDown(h.dispose);
  signedInAs(h.backend, account ?? accountJson());
  script(h.backend);
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: h.container,
      child: const RacheetaApp(),
    ),
  );
  await tester.pumpAndSettle();
  if (path != '/') {
    h.container.read(routerProvider).go(path);
    await tester.pumpAndSettle();
    // Pages created on the last frame start their requests on a zero-length timer; run it so no
    // timer is left pending when the test ends, then settle the answers.
    await tester.pump(const Duration(milliseconds: 50));
    await tester.pumpAndSettle();
  }
  return h;
}
