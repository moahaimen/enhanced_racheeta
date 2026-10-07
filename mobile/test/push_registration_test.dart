import 'dart:async';

import 'package:dio/dio.dart' show ResponseBody;
import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/core/logging/safe_logger.dart';
import 'package:racheeta_mobile/features/auth/application/providers.dart';
import 'package:racheeta_mobile/features/push/push_registration.dart';
import 'package:racheeta_mobile/features/push/push_source.dart';

import 'support/comms_support.dart';
import 'support/fake_backend.dart';
import 'support/patient_support.dart' show signedInAs;

const _register = '/api/v1/notifications/push-devices/';
const _unregister = '/api/v1/notifications/push-devices/unregister/';
const _logout = '/api/v1/auth/logout';

final Map<String, Object?> _a = accountJson(name: 'Account A');
final Map<String, Object?> _b = accountJson(
  id: '99999999-9999-4999-8999-999999999999',
  name: 'Account B',
);

ResponseBody _device() => FakeBackend.json(200, {
  'id': 'f1',
  'platform': 'ANDROID',
  'is_active': true,
  'last_registered_at': '2026-10-03T08:00:00Z',
});

Future<void> _settle([int ms = 60]) =>
    Future<void>.delayed(Duration(milliseconds: ms));

/// Boots the real session + push wiring against a scripted backend, with a fake FCM source.
Future<Harness> _boot(
  FakePushSource source, {
  Map<String, Object?>? account,
  bool signedIn = true,
  void Function(FakeBackend b)? script,
  SafeLogger? logger,
}) async {
  final h = Harness(
    storedRefresh: signedIn ? 'r1' : null,
    autoRestore: true,
    extraOverrides: [
      pushSourceProvider.overrideWithValue(source),
      beforeLogoutProvider.overrideWith(
        (ref) =>
            () => ref
                .read(pushRegistrationProvider.notifier)
                .unregisterForLogout(),
      ),
      if (logger != null) loggerProvider.overrideWithValue(logger),
    ],
  );
  addTearDown(h.dispose);
  signedInAs(h.backend, account ?? _a);
  h.backend.on('POST', _register, (_) => _device());
  h.backend.on('POST', _unregister, (_) => FakeBackend.noContent());
  h.backend.on('POST', _logout, (_) => FakeBackend.noContent());
  script?.call(h.backend);
  h.container.listen(pushRegistrationProvider, (_, _) {});
  await h.container.read(sessionControllerProvider.notifier).restored;
  await _settle();
  return h;
}

Future<void> _switchTo(Harness h, Map<String, Object?> account) async {
  h.backend.on('GET', '/api/v1/me', (_) => FakeBackend.json(200, account));
  await h.container.read(sessionControllerProvider.notifier).refreshAccount();
  await _settle();
}

PushState _state(Harness h) => h.container.read(pushRegistrationProvider);

void main() {
  group('registration', () {
    test('a signed-in account with permission registers this device once (idempotent upsert)', () async {
      final source = FakePushSource();
      final h = await _boot(source);
      final posts = h.backend.to('POST', _register);
      expect(posts, hasLength(1));
      expect(posts.single.body, {
        'token': 'fake-fcm-token-1',
        'platform': 'ANDROID',
      });
      expect(posts.single.authorization, startsWith('Bearer '));
      expect(_state(h).registered, isTrue);
    });

    test(
      'no signed-in account: no token is requested and nothing is registered',
      () async {
        final source = FakePushSource();
        final h = await _boot(source, signedIn: false);
        expect(source.tokenCalls, 0);
        expect(h.backend.count('POST', _register), 0);
        expect(_state(h).registered, isFalse);
      },
    );

    test('a build without Firebase never touches the backend', () async {
      final source = FakePushSource(available: false);
      final h = await _boot(source);
      expect(source.tokenCalls, 0);
      expect(h.backend.count('POST', _register), 0);
    });

    test('denied or undetermined permission registers nothing; granting later registers', () async {
      final source = FakePushSource(
        currentPermission: PushPermission.notDetermined,
      )..permissionAfterRequest = PushPermission.granted;
      final h = await _boot(source);
      expect(h.backend.count('POST', _register), 0);
      expect(_state(h).permission, PushPermission.notDetermined);
      await h.container
          .read(pushRegistrationProvider.notifier)
          .requestPermission();
      await _settle();
      expect(source.permissionRequests, 1);
      expect(h.backend.count('POST', _register), 1);
      expect(_state(h).registered, isTrue);

      final denied = FakePushSource(currentPermission: PushPermission.denied);
      final h2 = await _boot(denied);
      expect(h2.backend.count('POST', _register), 0);
      expect(denied.tokenCalls, 0);
    });

    test('a refused permission request stays unregistered and is not asked again by itself', () async {
      final source = FakePushSource(
        currentPermission: PushPermission.notDetermined,
      )..permissionAfterRequest = PushPermission.denied;
      final h = await _boot(source);
      await h.container
          .read(pushRegistrationProvider.notifier)
          .requestPermission();
      await _settle();
      expect(h.backend.count('POST', _register), 0);
      expect(_state(h).permission, PushPermission.denied);
      expect(source.permissionRequests, 1);
    });

    test(
      'a token refresh registers the new token for the current account',
      () async {
        final source = FakePushSource();
        final h = await _boot(source);
        source.refreshes.add('fake-fcm-token-2');
        await _settle();
        final posts = h.backend.to('POST', _register);
        expect(posts, hasLength(2));
        expect((posts.last.body! as Map)['token'], 'fake-fcm-token-2');
      },
    );

    test('a registration failure is silent, not retried and does not leak the token', () async {
      final lines = <String>[];
      final source = FakePushSource(fixedToken: 'fake-fcm-token-SECRET');
      final h = await _boot(
        source,
        logger: SafeLogger(sink: lines.add),
        script: (b) => b.on(
          'POST',
          _register,
          (_) => FakeBackend.error(
            500,
            'server_error',
            message: 'fake-fcm-token-SECRET raw',
          ),
        ),
      );
      await Future<void>.delayed(const Duration(milliseconds: 200));
      expect(h.backend.count('POST', _register), 1);
      expect(_state(h).registered, isFalse);
      expect(lines.join('\n'), isNot(contains('SECRET')));
    });
  });

  group('token refresh respects notification permission', () {
    for (final permission in [
      PushPermission.denied,
      PushPermission.notDetermined,
    ]) {
      test('${permission.name}: a token refresh registers nothing', () async {
        final source = FakePushSource(currentPermission: permission);
        final h = await _boot(source);
        source.refreshes.add('fake-fcm-token-2');
        source.refreshes.add('fake-fcm-token-3');
        await _settle();
        expect(h.backend.count('POST', _register), 0);
        expect(_state(h).registered, isFalse);
        expect(_state(h).permission, permission);
      });
    }

    test('granted: a token refresh still registers the new token', () async {
      final source = FakePushSource();
      final h = await _boot(source);
      source.refreshes.add('fake-fcm-token-9');
      await _settle();
      final posts = h.backend.to('POST', _register);
      expect((posts.last.body! as Map)['token'], 'fake-fcm-token-9');
    });

    test('a refresh that arrives before start-up has read the OS permission still honours it (denied)', () async {
      final gate = Completer<void>();
      final source = FakePushSource(currentPermission: PushPermission.denied)
        ..permissionGate = gate;
      final h = await _boot(source);
      source.refreshes.add('fake-fcm-token-2');
      await _settle();
      gate.complete();
      await _settle();
      expect(h.backend.count('POST', _register), 0);
    });

    test('a refresh that arrives before start-up finished registers once when granted', () async {
      final gate = Completer<void>();
      final source = FakePushSource()..permissionGate = gate;
      final h = await _boot(source);
      source.fixedToken =
          'fake-fcm-token-2'; // FCM now issues the rotated token
      source.refreshes.add('fake-fcm-token-2');
      await _settle();
      gate.complete();
      await _settle();
      final posts = h.backend.to('POST', _register);
      expect(posts.map((p) => (p.body! as Map)['token']).toSet(), {
        'fake-fcm-token-2',
      });
      expect(_state(h).registered, isTrue);
    });

    test(
      'a refresh after the user denies the prompt registers nothing',
      () async {
        final source = FakePushSource(
          currentPermission: PushPermission.notDetermined,
        )..permissionAfterRequest = PushPermission.denied;
        final h = await _boot(source);
        await h.container
            .read(pushRegistrationProvider.notifier)
            .requestPermission();
        source.refreshes.add('fake-fcm-token-2');
        await _settle();
        expect(h.backend.count('POST', _register), 0);
      },
    );
  });

  group('races', () {
    test('token arrives after logout: nothing is registered for the signed-out session', () async {
      final gate = Completer<String?>();
      final source = FakePushSource()..tokenGate = gate;
      final h = await _boot(source);
      expect(
        h.backend.count('POST', _register),
        0,
        reason: 'token still being issued',
      );
      await h.container.read(sessionControllerProvider.notifier).logout();
      await _settle();
      gate.complete('fake-fcm-token-1');
      await _settle();
      expect(h.backend.count('POST', _register), 0);
      expect(_state(h).registered, isFalse);
    });

    test('account switches during token acquisition: A\'s callback is dropped, B registers once', () async {
      final gate = Completer<String?>();
      final source = FakePushSource()..tokenGate = gate;
      final h = await _boot(source);
      await _switchTo(h, _b);
      gate.complete('fake-fcm-token-1');
      await _settle();
      expect(h.backend.to('POST', _register), hasLength(1));
      expect(_state(h).registered, isTrue);
    });

    test('A\'s registration finishing after the switch to B never marks B registered; B registers after it', () async {
      final gateA = Completer<void>();
      var calls = 0;
      final source = FakePushSource();
      final h = await _boot(
        source,
        script: (b) => b.on('POST', _register, (_) async {
          if (++calls == 1) await gateA.future;
          return _device();
        }),
      );
      expect(calls, 1, reason: 'A\'s registration is in flight');
      await _switchTo(h, _b);
      expect(
        calls,
        1,
        reason: 'ownership requests are serialised: B waits for A\'s to finish',
      );
      expect(_state(h).registered, isFalse);
      gateA.complete();
      await _settle(150);
      expect(calls, 2, reason: 'B registers once A\'s request is done');
      expect(_state(h).registered, isTrue);
    });

    test('a refresh during an account switch converges on the current account only', () async {
      final source = FakePushSource();
      final h = await _boot(source);
      await _switchTo(h, _b);
      source.refreshes.add('fake-fcm-token-3');
      await _settle();
      // each account registered what it saw; after logout a refresh registers nothing
      final before = h.backend.count('POST', _register);
      await h.container.read(sessionControllerProvider.notifier).logout();
      await _settle();
      source.refreshes.add('fake-fcm-token-4');
      await _settle();
      expect(h.backend.count('POST', _register), before);
    });
  });

  group('logout', () {
    test('the device is unregistered BEFORE credentials are cleared, then the session is revoked', () async {
      final source = FakePushSource();
      final h = await _boot(source);
      await h.container.read(sessionControllerProvider.notifier).logout();
      final unregisters = h.backend.to('POST', _unregister);
      expect(unregisters, hasLength(1));
      expect(unregisters.single.body, {'token': 'fake-fcm-token-1'});
      expect(
        unregisters.single.authorization,
        startsWith('Bearer '),
        reason: 'still authenticated when it was sent',
      );
      final order = h.backend.requests.map((r) => r.path).toList();
      expect(order.indexOf(_unregister), lessThan(order.indexOf(_logout)));
    });

    test('a failing unregister never blocks or reverses signing out', () async {
      final source = FakePushSource();
      final h = await _boot(
        source,
        script: (b) => b.on('POST', _unregister, FakeBackend.networkDown),
      );
      await h.container.read(sessionControllerProvider.notifier).logout();
      expect(h.backend.count('POST', _unregister), 1);
      expect(h.backend.count('POST', _logout), 1);
      expect(await h.tokenStore.readRefreshToken(), isNull);
    });

    test('logging out without push configured sends no unregister', () async {
      final source = FakePushSource(available: false);
      final h = await _boot(source);
      await h.container.read(sessionControllerProvider.notifier).logout();
      expect(h.backend.count('POST', _unregister), 0);
    });

    test('after logout the next account registers this token and nothing of A remains', () async {
      final source = FakePushSource();
      final h = await _boot(source);
      await h.container.read(sessionControllerProvider.notifier).logout();
      await _settle();
      expect(_state(h).registered, isFalse);
      expect(
        h.container.read(sessionControllerProvider).runtimeType.toString(),
        'SessionAnonymous',
      );
    });
  });
}
