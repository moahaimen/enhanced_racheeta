import 'dart:async';

import 'package:dio/dio.dart' show ResponseBody;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/app/router.dart';
import 'package:racheeta_mobile/features/auth/application/providers.dart';
import 'package:racheeta_mobile/features/notifications/application/notifications_providers.dart';
import 'package:racheeta_mobile/features/auth/application/session_state.dart';
import 'package:racheeta_mobile/features/push/push_registration.dart';

import 'support/comms_support.dart';
import 'support/domain_support.dart';
import 'support/fake_backend.dart';
import 'support/patient_support.dart';
import 'support/provider_support.dart';

/// Release smoke suite over the accepted account-isolation primitives (Phases 11B–11E).
///
/// Two table-driven scenarios, each run over representative screens:
///  1. **A → B while requests are in flight**: A's private data is on screen, `/me` switches to B
///     (same route stays mounted) while B's answer is still being held; nothing of A may be visible
///     in between or afterwards, and B's answer then replaces it.
///  2. **Session expiry**: the access token and the refresh token are both rejected during a list
///     fetch, a detail fetch, a mutation, a message send, a notification read and the FCM
///     synchronisation; the session must end, the login screen must show, and no private data of
///     the expired account may survive on screen.
const _tall = Size(800, 2400);

Map<String, Object?> _other(Map<String, Object?> of) => {
  ...of,
  'id': '99999999-9999-4999-8999-999999999999',
  'full_name': 'Account B',
};

class _Switch {
  const _Switch(this.name, this.path, this.endpoint, this.account, this.body);
  final String name;
  final String path;
  final String endpoint;
  final Map<String, Object?> account;

  /// The response for the given marker (`A` or `B`).
  final Object? Function(String marker) body;
}

final _switchCases = <_Switch>[
  _Switch(
    'reservation detail',
    '/reservations/$reservationId',
    '/api/v1/reservations/me/$reservationId',
    accountJson(name: 'Account A'),
    (m) => reservationJson(provider: 'PRIVATE-$m'),
  ),
  _Switch(
    'provider workspace bookings',
    '/workspace/reservations',
    '/api/v1/reservations/provider',
    providerAccountJson(),
    (m) => pageJson([providerReservationJson(patient: 'PRIVATE-$m')]),
  ),
  _Switch(
    'marketplace',
    '/marketplace',
    '/api/v1/marketplace/products',
    browsingProviderJson(),
    (m) => pageJson([productPublicJson(title: 'PRIVATE-$m')]),
  ),
  _Switch(
    'my job applications',
    '/jobs/applications',
    '/api/v1/jobs/me/applications',
    accountJson(name: 'Account A'),
    (m) => pageJson([applicationJson(title: 'PRIVATE-$m')]),
  ),
  _Switch(
    'seller listings',
    '/seller/listings',
    '/api/v1/real-estate/owner/listings',
    sellerAccountJson(),
    (m) => pageJson([ownerListingJson(title: 'PRIVATE-$m')]),
  ),
  _Switch(
    'notifications',
    '/notifications',
    '/api/v1/notifications/',
    accountJson(name: 'Account A'),
    (m) => pageJson([notificationJson(title: 'PRIVATE-$m')]),
  ),
  _Switch(
    'conversation list',
    '/chat',
    '/api/v1/chat/conversations/',
    accountJson(name: 'Account A'),
    (m) => pageJson([conversationJson(name: 'PRIVATE-$m')]),
  ),
  _Switch(
    'conversation thread',
    '/chat/$conversationId',
    '/api/v1/chat/conversations/$conversationId/messages/',
    accountJson(name: 'Account A'),
    (m) => pageJson([messageJson(sequence: 1, body: 'PRIVATE-$m')]),
  ),
];

void _commonScript(FakeBackend b) {
  for (final path in [
    '/api/v1/notifications/unread-count/',
    '/api/v1/chat/unread-count/',
  ]) {
    b.on('GET', path, (_) => FakeBackend.json(200, {'count': 0}));
  }
  b.on(
    'GET',
    '/api/v1/chat/conversations/$conversationId/messages/',
    (_) => FakeBackend.json(200, pageJson(<Object?>[])),
  );
  b.on(
    'POST',
    '/api/v1/chat/conversations/$conversationId/read/',
    (_) => FakeBackend.json(200, {'last_read_sequence': 1}),
  );
  b.on(
    'GET',
    '/api/v1/chat/conversations/',
    (_) => FakeBackend.json(200, pageJson(<Object?>[])),
  );
  b.on(
    'GET',
    '/api/v1/real-estate/owner/dashboard',
    (_) => FakeBackend.json(200, ownerDashboardJson()),
  );
}

void main() {
  group('A → B while requests are in flight (same route stays mounted)', () {
    for (final c in _switchCases) {
      testWidgets(c.name, (tester) async {
        var who = 'A';
        final gateB = Completer<void>();
        final h = await pumpPatientApp(
          tester,
          path: c.path,
          size: _tall,
          account: c.account,
          script: (b) {
            _commonScript(b);
            b.on('GET', c.endpoint, (_) async {
              if (who == 'B') await gateB.future;
              return FakeBackend.json(200, c.body(who));
            });
          },
        );
        expect(find.textContaining('PRIVATE-A'), findsWidgets);
        who = 'B';
        await switchAccountTo(tester, h, _other(c.account));
        expect(
          find.textContaining('PRIVATE-A'),
          findsNothing,
          reason: 'A\'s data is gone the moment B is active',
        );
        gateB.complete();
        await tester.pumpAndSettle();
        expect(find.textContaining('PRIVATE-A'), findsNothing);
        expect(find.textContaining('PRIVATE-B'), findsWidgets);
      });
    }
  });

  group('FCM registration in flight during an account switch', () {
    testWidgets(
      'A\'s pending registration never registers or marks B; B registers after it',
      (tester) async {
        final gate = Completer<void>();
        var calls = 0;
        final source = FakePushSource();
        final h = await pumpPatientApp(
          tester,
          size: _tall,
          overrides: [pushSourceProvider.overrideWithValue(source)],
          script: (b) =>
              b.on('POST', '/api/v1/notifications/push-devices/', (_) async {
                if (++calls == 1) await gate.future;
                return FakeBackend.json(200, {
                  'id': 'f1',
                  'platform': 'ANDROID',
                  'is_active': true,
                  'last_registered_at': '2026-10-03T08:00:00Z',
                });
              }),
        );
        expect(calls, 1);
        await switchAccountTo(tester, h, _other(accountJson()));
        expect(h.container.read(pushRegistrationProvider).registered, isFalse);
        gate.complete();
        await tester.runAsync(
          () => Future<void>.delayed(const Duration(milliseconds: 100)),
        );
        await tester.pumpAndSettle();
        expect(calls, 2);
        expect(h.container.read(pushRegistrationProvider).registered, isTrue);
      },
    );
  });

  group('session expiry', () {
    /// Both the access token and the refresh token get rejected from now on.
    void expire(Harness h, {required bool Function() expired}) {
      h.backend.on('POST', '/api/v1/auth/refresh', (_) {
        if (expired()) return FakeBackend.error(401, 'token_not_valid');
        return FakeBackend.json(200, tokens('a2', 'r2'));
      });
    }

    ResponseBody unauthorized() => FakeBackend.error(401, 'token_not_valid');

    Future<void> expectSignedOut(WidgetTester tester, Harness h) async {
      await tester.pumpAndSettle();
      expect(
        h.container.read(sessionControllerProvider),
        isA<SessionAnonymous>(),
      );
      expect(find.textContaining('PRIVATE'), findsNothing);
      expect(
        find.byType(TextField),
        findsNWidgets(2),
        reason: 'the login form',
      );
      expect(find.textContaining('Traceback'), findsNothing);
    }

    testWidgets('during a list fetch (pull to refresh)', (tester) async {
      var expired = false;
      final h = await pumpPatientApp(
        tester,
        path: '/notifications',
        size: _tall,
        script: (b) {
          b.on(
            'GET',
            '/api/v1/notifications/unread-count/',
            (_) =>
                expired ? unauthorized() : FakeBackend.json(200, {'count': 1}),
          );
          b.on(
            'GET',
            '/api/v1/notifications/',
            (_) => expired
                ? unauthorized()
                : FakeBackend.json(
                    200,
                    pageJson([notificationJson(title: 'PRIVATE-A')]),
                  ),
          );
        },
      );
      expire(h, expired: () => expired);
      expect(find.text('PRIVATE-A'), findsOneWidget);
      expired = true;
      // what pull-to-refresh / "Try again" do: reload the list from the backend
      h.container.invalidate(notificationsProvider);
      await tester.pump(const Duration(milliseconds: 300));
      await expectSignedOut(tester, h);
    });

    testWidgets('during a detail fetch', (tester) async {
      var expired = false;
      final h = await pumpPatientApp(
        tester,
        path: '/reservations',
        size: _tall,
        script: (b) {
          b.on(
            'GET',
            '/api/v1/reservations/me',
            (_) => FakeBackend.json(
              200,
              pageJson([reservationJson(provider: 'PRIVATE-A')]),
            ),
          );
          b.on(
            'GET',
            '/api/v1/reservations/me/$reservationId',
            (_) => expired
                ? unauthorized()
                : FakeBackend.json(200, reservationJson(provider: 'PRIVATE-A')),
          );
        },
      );
      expire(h, expired: () => expired);
      expired = true;
      h.container.read(routerProvider).go('/reservations/$reservationId');
      await tester.pump(const Duration(milliseconds: 100));
      await expectSignedOut(tester, h);
    });

    testWidgets('during a mutation (withdraw an application)', (tester) async {
      var expired = false;
      final h = await pumpPatientApp(
        tester,
        path: '/jobs/applications',
        size: _tall,
        script: (b) {
          b.on(
            'GET',
            '/api/v1/jobs/me/applications',
            (_) => FakeBackend.json(
              200,
              pageJson([applicationJson(title: 'PRIVATE-A')]),
            ),
          );
          b.on(
            'POST',
            '/api/v1/jobs/me/applications/$applicationId/withdraw',
            (_) => expired
                ? unauthorized()
                : FakeBackend.json(200, applicationJson(status: 'WITHDRAWN')),
          );
        },
      );
      expire(h, expired: () => expired);
      expired = true;
      await tester.tap(find.byKey(Key('withdraw-$applicationId')));
      await tester.pumpAndSettle();
      await tester.tap(
        find.descendant(
          of: find.byType(AlertDialog),
          matching: find.text('Withdraw'),
        ),
      );
      await tester.pump(const Duration(milliseconds: 200));
      await expectSignedOut(tester, h);
      expect(
        h.backend.count(
          'POST',
          '/api/v1/jobs/me/applications/$applicationId/withdraw',
        ),
        1,
        reason: 'never replayed',
      );
    });

    testWidgets('during a message send', (tester) async {
      var expired = false;
      final h = await pumpPatientApp(
        tester,
        path: '/chat/$conversationId',
        size: _tall,
        script: (b) {
          _commonScript(b);
          b.on(
            'GET',
            '/api/v1/chat/conversations/$conversationId/messages/',
            (_) => FakeBackend.json(
              200,
              pageJson([messageJson(sequence: 1, body: 'PRIVATE-A')]),
            ),
          );
          b.on(
            'POST',
            '/api/v1/chat/conversations/$conversationId/messages/',
            (_) => expired
                ? unauthorized()
                : FakeBackend.json(201, messageJson(sequence: 2, mine: true)),
          );
        },
      );
      expire(h, expired: () => expired);
      await tester.enterText(
        find.byKey(const Key('composer-field')),
        'draft that must vanish',
      );
      await tester.pump();
      expired = true;
      await tester.tap(find.byKey(const Key('composer-send')));
      await tester.pump(const Duration(milliseconds: 200));
      await expectSignedOut(tester, h);
      expect(find.text('draft that must vanish'), findsNothing);
      expect(
        h.backend.count(
          'POST',
          '/api/v1/chat/conversations/$conversationId/messages/',
        ),
        1,
      );
    });

    testWidgets('during a notification read', (tester) async {
      var expired = false;
      final h = await pumpPatientApp(
        tester,
        path: '/notifications',
        size: _tall,
        script: (b) {
          b.on(
            'GET',
            '/api/v1/notifications/unread-count/',
            (_) => FakeBackend.json(200, {'count': 1}),
          );
          b.on(
            'GET',
            '/api/v1/notifications/',
            (_) => FakeBackend.json(
              200,
              pageJson([
                notificationJson(title: 'PRIVATE-A', event: 'FUTURE_EVENT'),
              ]),
            ),
          );
          b.on(
            'POST',
            '/api/v1/notifications/$notificationId/read/',
            (_) => expired
                ? unauthorized()
                : FakeBackend.json(200, notificationJson(isRead: true)),
          );
        },
      );
      expire(h, expired: () => expired);
      expired = true;
      await tester.tap(find.byKey(const Key('notification-$notificationId')));
      await tester.pump(const Duration(milliseconds: 200));
      await expectSignedOut(tester, h);
    });

    testWidgets('during FCM synchronisation', (tester) async {
      var expired = false;
      final source = FakePushSource();
      final h = await pumpPatientApp(
        tester,
        size: _tall,
        overrides: [pushSourceProvider.overrideWithValue(source)],
        script: (b) => b.on(
          'POST',
          '/api/v1/notifications/push-devices/',
          (_) => expired
              ? unauthorized()
              : FakeBackend.json(200, {
                  'id': 'f1',
                  'platform': 'ANDROID',
                  'is_active': true,
                  'last_registered_at': '2026-10-03T08:00:00Z',
                }),
        ),
      );
      expire(h, expired: () => expired);
      expired = true;
      source.fixedToken = 'fake-fcm-token-2';
      source.refreshes.add('fake-fcm-token-2');
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 100)),
      );
      await tester.pumpAndSettle();
      // the detached registration is refused (401) without crashing; the state is not "registered"
      expect(h.container.read(pushRegistrationProvider).registered, isFalse);
      expect(tester.takeException(), isNull);
      expect(
        h.backend.count('POST', '/api/v1/notifications/push-devices/'),
        greaterThanOrEqualTo(2),
      );
    });
  });

  testWidgets(
    'without any Firebase configuration the release app starts and works',
    (tester) async {
      final h = await pumpPatientApp(
        tester,
        size: _tall,
        script: _commonScript,
      );
      expect(find.byKey(const Key('home-greeting')), findsOneWidget);
      expect(h.backend.count('POST', '/api/v1/notifications/push-devices/'), 0);
      expect(tester.takeException(), isNull);
    },
  );
}
