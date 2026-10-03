import 'dart:async';

import 'package:racheeta_mobile/features/auth/application/session_controller.dart';
import 'package:racheeta_mobile/features/auth/data/auth_models.dart';

import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/core/api/api_exception.dart';
import 'package:racheeta_mobile/features/auth/application/providers.dart';
import 'package:racheeta_mobile/features/auth/application/session_core.dart';
import 'package:racheeta_mobile/features/auth/application/session_state.dart';

import 'support/fake_backend.dart';

const _login = '/api/v1/auth/login';
const _refresh = '/api/v1/auth/refresh';
const _logout = '/api/v1/auth/logout';
const _me = '/api/v1/me';

Account _account(SessionState s) => (s as SessionAuthenticated).account;

void main() {
  late Harness h;

  SessionController controller() =>
      h.container.read(sessionControllerProvider.notifier);
  SessionState state() => h.container.read(sessionControllerProvider);

  group('login', () {
    setUp(() => h = Harness());
    tearDown(() => h.dispose());

    test(
      'success stores only the refresh token and loads canonical /me',
      () async {
        h.backend
          ..on('POST', _login, (_) => FakeBackend.json(200, tokens('a1', 'r1')))
          ..on('GET', _me, (_) => FakeBackend.json(200, accountJson()));
        await controller().login(email: ' layla@example.com ', password: 'pw');

        expect(_account(state()).fullName, 'Layla Hassan');
        expect(await h.tokenStore.readRefreshToken(), 'r1');
        expect(h.backend.to('POST', _login).single.body, {
          'email': 'layla@example.com',
          'password': 'pw',
        });
        expect(h.backend.to('GET', _me).single.authorization, 'Bearer a1');
        // the access token never reaches persistent storage
        expect(h.preferences.readLanguageCode(), isNot(contains('a1')));
      },
    );

    test(
      'wrong credentials: typed error, stays signed out, nothing stored',
      () async {
        h.backend.on(
          'POST',
          _login,
          (_) => FakeBackend.error(401, 'no_active_account'),
        );
        await expectLater(
          controller().login(email: 'a@b.test', password: 'bad'),
          throwsA(
            isA<ApiException>().having(
              (e) => e.code,
              'code',
              'no_active_account',
            ),
          ),
        );
        expect(state(), isA<SessionRestoring>()); // never authenticated
        expect(await h.tokenStore.readRefreshToken(), isNull);
        expect(h.backend.count('GET', _me), 0);
      },
    );

    test('field validation errors are exposed per field', () async {
      h.backend.on(
        'POST',
        _login,
        (_) => FakeBackend.error(
          400,
          'validation_error',
          details: {
            'email': ['Enter a valid email address.'],
          },
        ),
      );
      await expectLater(
        controller().login(email: 'x', password: 'y'),
        throwsA(
          isA<ApiException>().having(
            (e) => e.fieldError('email'),
            'email',
            'Enter a valid email address.',
          ),
        ),
      );
    });

    test('if /me fails after the token exchange the session is rolled back and the token revoked', () async {
      h.backend
        ..on('POST', _login, (_) => FakeBackend.json(200, tokens('a1', 'r1')))
        ..on('GET', _me, FakeBackend.networkDown)
        ..on('POST', _logout, (_) => FakeBackend.noContent());
      await expectLater(
        controller().login(email: 'a@b.test', password: 'pw'),
        throwsA(isA<ApiException>()),
      );
      expect(state(), isA<SessionAnonymous>());
      expect(await h.tokenStore.readRefreshToken(), isNull);
      await Future<void>.delayed(const Duration(milliseconds: 20));
      expect(h.backend.to('POST', _logout).single.body, {'refresh': 'r1'});
    });
  });

  group('restoration', () {
    tearDown(() => h.dispose());

    test('no stored token → anonymous without touching the network', () async {
      h = Harness();
      await controller().restore();
      expect(state(), isA<SessionAnonymous>());
      expect((state() as SessionAnonymous).endedBy, isNull);
      expect(h.backend.requests, isEmpty);
    });

    test('valid stored token → refresh, rotate, /me, authenticated', () async {
      h = Harness(storedRefresh: 'r-old');
      h.backend
        ..on(
          'POST',
          _refresh,
          (_) => FakeBackend.json(200, tokens('a2', 'r-new')),
        )
        ..on(
          'GET',
          _me,
          (_) => FakeBackend.json(200, accountJson(name: 'Restored')),
        );
      await controller().restore();
      expect(_account(state()).fullName, 'Restored');
      expect(h.backend.to('POST', _refresh).single.body, {'refresh': 'r-old'});
      expect(h.backend.to('POST', _refresh).single.authorization, isNull);
      expect(
        await h.tokenStore.readRefreshToken(),
        'r-new',
      ); // rotated and persisted
      expect(h.backend.to('GET', _me).single.authorization, 'Bearer a2');
    });

    test('auto restore on start-up runs once', () async {
      h = Harness(storedRefresh: 'r', autoRestore: true);
      h.backend
        ..on('POST', _refresh, (_) => FakeBackend.json(200, tokens('a', 'r2')))
        ..on('GET', _me, (_) => FakeBackend.json(200, accountJson()));
      expect(state(), isA<SessionRestoring>());
      await controller().restored;
      expect(state(), isA<SessionAuthenticated>());
      expect(h.backend.count('POST', _refresh), 1);
    });

    test('rejected stored token → cleared and reported as expired', () async {
      h = Harness(storedRefresh: 'dead');
      h.backend.on(
        'POST',
        _refresh,
        (_) => FakeBackend.error(401, 'token_not_valid'),
      );
      await controller().restore();
      expect((state() as SessionAnonymous).endedBy, SessionEndReason.expired);
      expect(await h.tokenStore.readRefreshToken(), isNull);
    });

    test('network failure keeps the credentials and offers a retry', () async {
      h = Harness(storedRefresh: 'r');
      h.backend.on('POST', _refresh, FakeBackend.networkDown);
      await controller().restore();
      expect(state(), isA<SessionRestoreFailed>());
      expect(await h.tokenStore.readRefreshToken(), 'r');

      h.backend
        ..on('POST', _refresh, (_) => FakeBackend.json(200, tokens('a', 'r2')))
        ..on('GET', _me, (_) => FakeBackend.json(200, accountJson()));
      await controller().restore();
      expect(state(), isA<SessionAuthenticated>());
    });

    test(
      'server error while refreshing is transient, not a sign-out',
      () async {
        h = Harness(storedRefresh: 'r');
        h.backend.on(
          'POST',
          _refresh,
          (_) => FakeBackend.error(503, 'server_error'),
        );
        await controller().restore();
        expect(state(), isA<SessionRestoreFailed>());
        expect(await h.tokenStore.readRefreshToken(), 'r');
      },
    );
  });

  group('refresh', () {
    setUp(() => h = Harness());
    tearDown(() => h.dispose());

    Future<void> signIn() async {
      h.backend
        ..on('POST', _login, (_) => FakeBackend.json(200, tokens('a1', 'r1')))
        ..on('GET', _me, (_) => FakeBackend.json(200, accountJson()));
      await controller().login(email: 'a@b.test', password: 'pw');
      h.backend.requests.clear();
    }

    test('a 401 triggers one refresh and the request is retried with the new token', () async {
      await signIn();
      var first = true;
      h.backend
        ..on('GET', _me, (r) {
          if (first) {
            first = false;
            return FakeBackend.error(401, 'token_not_valid');
          }
          return FakeBackend.json(200, accountJson(name: 'After refresh'));
        })
        ..on(
          'POST',
          _refresh,
          (_) => FakeBackend.json(200, tokens('a2', 'r2')),
        );
      await controller().refreshAccount();
      expect(_account(state()).fullName, 'After refresh');
      final calls = h.backend.to('GET', _me);
      expect(calls.map((c) => c.authorization), ['Bearer a1', 'Bearer a2']);
      expect(await h.tokenStore.readRefreshToken(), 'r2');
    });

    test('concurrent 401s share ONE refresh (single flight)', () async {
      await signIn();
      final gate = Completer<void>();
      h.backend
        ..on(
          'GET',
          _me,
          (r) => r.authorization == 'Bearer a1'
              ? FakeBackend.error(401, 'token_not_valid')
              : FakeBackend.json(200, accountJson()),
        )
        ..on('POST', _refresh, (_) async {
          await gate.future;
          return FakeBackend.json(200, tokens('a2', 'r2'));
        });
      final calls = List.generate(
        5,
        (_) => h.container.read(authApiProvider).me(),
      );
      await Future<void>.delayed(const Duration(milliseconds: 20));
      gate.complete();
      final accounts = await Future.wait(calls);
      expect(accounts, hasLength(5));
      expect(h.backend.count('POST', _refresh), 1);
      expect(h.backend.to('POST', _refresh).single.body, {'refresh': 'r1'});
    });

    test(
      'a request that already carries the rotated token does not refresh again',
      () async {
        await signIn();
        h.backend
          ..on(
            'GET',
            _me,
            (r) => r.authorization == 'Bearer a1'
                ? FakeBackend.error(401, 'token_not_valid')
                : FakeBackend.json(200, accountJson()),
          )
          ..on(
            'POST',
            _refresh,
            (_) => FakeBackend.json(200, tokens('a2', 'r2')),
          );
        await h.container.read(authApiProvider).me();
        await h.container.read(authApiProvider).me();
        expect(h.backend.count('POST', _refresh), 1);
      },
    );

    test('refresh rejected → session cleared, router state becomes anonymous/expired', () async {
      await signIn();
      h.backend
        ..on('GET', _me, (_) => FakeBackend.error(401, 'token_not_valid'))
        ..on(
          'POST',
          _refresh,
          (_) => FakeBackend.error(401, 'token_not_valid'),
        );
      await expectLater(
        controller().refreshAccount(),
        throwsA(isA<StaleSessionException>()),
      );
      await Future<void>.delayed(const Duration(milliseconds: 20));
      expect((state() as SessionAnonymous).endedBy, SessionEndReason.expired);
      expect(await h.tokenStore.readRefreshToken(), isNull);
      expect(h.container.read(sessionCoreProvider).accessToken, isNull);
    });

    test('a transient refresh failure leaves the session intact', () async {
      await signIn();
      h.backend
        ..on('GET', _me, (_) => FakeBackend.error(401, 'token_not_valid'))
        ..on('POST', _refresh, FakeBackend.networkDown);
      await expectLater(
        controller().refreshAccount(),
        throwsA(isA<ApiException>()),
      );
      expect(state(), isA<SessionAuthenticated>());
      expect(await h.tokenStore.readRefreshToken(), 'r1');
    });
  });

  group('logout, account switching and stale responses', () {
    setUp(() => h = Harness());
    tearDown(() => h.dispose());

    Future<void> signIn({
      String refresh = 'r1',
      String name = 'Layla Hassan',
    }) async {
      h.backend
        ..on(
          'POST',
          _login,
          (_) => FakeBackend.json(200, tokens('a-$refresh', refresh)),
        )
        ..on('GET', _me, (_) => FakeBackend.json(200, accountJson(name: name)));
      await controller().login(email: 'a@b.test', password: 'pw');
    }

    test(
      'logout clears local state first and revokes the refresh token',
      () async {
        await signIn();
        h.backend.on('POST', _logout, (_) => FakeBackend.noContent());
        await controller().logout();
        expect(state(), isA<SessionAnonymous>());
        expect((state() as SessionAnonymous).endedBy, isNull);
        expect(await h.tokenStore.readRefreshToken(), isNull);
        expect(h.container.read(sessionCoreProvider).accessToken, isNull);
        expect(h.backend.to('POST', _logout).single.body, {'refresh': 'r1'});
      },
    );

    test(
      'logout succeeds locally even if the server is unreachable or rejects',
      () async {
        await signIn();
        h.backend.on('POST', _logout, FakeBackend.networkDown);
        await controller().logout();
        expect(state(), isA<SessionAnonymous>());
        expect(await h.tokenStore.readRefreshToken(), isNull);

        await signIn(refresh: 'r9');
        h.backend.on(
          'POST',
          _logout,
          (_) => FakeBackend.error(400, 'token_invalid'),
        );
        await controller().logout();
        expect(state(), isA<SessionAnonymous>());
      },
    );

    test('after logout no authenticated request leaves the device', () async {
      await signIn();
      h.backend.on('POST', _logout, (_) => FakeBackend.noContent());
      await controller().logout();
      h.backend.requests.clear();
      await expectLater(
        h.container.read(authApiProvider).me(),
        throwsA(isA<StaleSessionException>()),
      );
      expect(h.backend.requests, isEmpty);
    });

    test('account switching: second login fully replaces the first', () async {
      await signIn(refresh: 'r-A', name: 'Account A');
      await signIn(refresh: 'r-B', name: 'Account B');
      expect(_account(state()).fullName, 'Account B');
      expect(await h.tokenStore.readRefreshToken(), 'r-B');
      expect(h.backend.to('GET', _me).last.authorization, 'Bearer a-r-B');
    });

    test('a /me response that arrives after logout is discarded (stale protection)', () async {
      await signIn();
      final release = Completer<void>();
      h.backend
        ..on('GET', _me, (_) async {
          await release.future;
          return FakeBackend.json(200, accountJson(name: 'Previous account'));
        })
        ..on('POST', _logout, (_) => FakeBackend.noContent());
      final pending = controller().refreshAccount();
      final outcome = pending.then<Object?>(
        (_) => null,
        onError: (Object e) => e,
      );
      await Future<void>.delayed(const Duration(milliseconds: 20));
      await controller().logout();
      release.complete();
      expect(await outcome, isA<StaleSessionException>());
      expect(state(), isA<SessionAnonymous>());
    });

    test(
      'a late login response cannot resurrect a session after logout',
      () async {
        final release = Completer<void>();
        h.backend
          ..on('POST', _login, (_) async {
            await release.future;
            return FakeBackend.json(200, tokens('late-a', 'late-r'));
          })
          ..on('GET', _me, (_) => FakeBackend.json(200, accountJson()));
        final login = controller().login(email: 'a@b.test', password: 'pw');
        final outcome = login.then<Object?>(
          (_) => null,
          onError: (Object e) => e,
        );
        await Future<void>.delayed(const Duration(milliseconds: 20));
        await controller().logout();
        release.complete();
        expect(await outcome, isA<StaleSessionException>());
        expect(state(), isA<SessionAnonymous>());
        expect(await h.tokenStore.readRefreshToken(), isNull);
      },
    );

    test(
      'switching accounts aborts the previous account\'s in-flight call',
      () async {
        await signIn(refresh: 'r-A', name: 'Account A');
        final release = Completer<void>();
        h.backend.on('GET', _me, (_) async {
          await release.future;
          return FakeBackend.json(200, accountJson(name: 'A data'));
        });
        final inFlight = h.container.read(authApiProvider).me();
        final outcome = inFlight.then<Object?>(
          (v) => v,
          onError: (Object e) => e,
        );
        await Future<void>.delayed(const Duration(milliseconds: 20));
        h.backend
          ..on(
            'POST',
            _login,
            (_) => FakeBackend.json(200, tokens('a-B', 'r-B')),
          )
          ..on(
            'GET',
            _me,
            (_) => FakeBackend.json(200, accountJson(name: 'Account B')),
          );
        await controller().login(email: 'b@b.test', password: 'pw');
        release.complete();
        expect(await outcome, isA<StaleSessionException>());
        expect(_account(state()).fullName, 'Account B');
      },
    );
  });
}
