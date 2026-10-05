import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/widgets.dart' show Locale;
import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/core/api/api_client.dart';
import 'package:racheeta_mobile/core/api/api_exception.dart';
import 'package:racheeta_mobile/core/api/page.dart';
import 'package:racheeta_mobile/core/config/app_config.dart';
import 'package:racheeta_mobile/core/logging/safe_logger.dart';
import 'package:racheeta_mobile/features/auth/application/providers.dart';
import 'package:racheeta_mobile/features/auth/data/auth_models.dart';

import 'support/fake_backend.dart';

Future<void> signIn(
  Harness h, {
  String access = 'access-1',
  String refresh = 'refresh-1',
}) async {
  await h.container
      .read(sessionCoreProvider)
      .startSession(TokenPair(access: access, refresh: refresh));
}

void main() {
  group('buildDio configuration', () {
    test('uses the configured base URL and the three timeouts', () {
      const config = AppConfig(
        environment: AppEnvironment.staging,
        apiBaseUrl: 'https://api.test',
        connectTimeout: Duration(seconds: 3),
        sendTimeout: Duration(seconds: 4),
        receiveTimeout: Duration(seconds: 5),
      );
      final dio = buildDio(config);
      expect(dio.options.baseUrl, 'https://api.test');
      expect(dio.options.connectTimeout, const Duration(seconds: 3));
      expect(dio.options.sendTimeout, const Duration(seconds: 4));
      expect(dio.options.receiveTimeout, const Duration(seconds: 5));
      expect(dio.options.followRedirects, isFalse);
    });

    test('defaults are bounded (never an unlimited wait)', () {
      const config = AppConfig(
        environment: AppEnvironment.staging,
        apiBaseUrl: 'https://api.test',
      );
      expect(
        config.connectTimeout,
        lessThanOrEqualTo(const Duration(seconds: 30)),
      );
      expect(
        config.receiveTimeout,
        lessThanOrEqualTo(const Duration(seconds: 60)),
      );
    });
  });

  group('requests', () {
    late Harness h;
    setUp(() => h = Harness());
    tearDown(() => h.dispose());

    test('attach the bearer token, JSON headers and the UI language', () async {
      h.backend.on(
        'GET',
        '/api/v1/me',
        (_) => FakeBackend.json(200, accountJson()),
      );
      await signIn(h);
      await h.container
          .read(localeControllerProvider.notifier)
          .setLanguage(const Locale('ar'));
      await h.container
          .read(apiClientProvider)
          .get<Object?>('/api/v1/me', parse: (j) => j);
      final seen = h.backend.requests.single;
      expect(seen.authorization, 'Bearer access-1');
      expect(seen.language, 'ar');
      expect(seen.options.headers['Accept'], 'application/json');
    });

    test('Accept-Language follows the selected language', () async {
      h.backend.on(
        'GET',
        '/api/v1/me',
        (_) => FakeBackend.json(200, accountJson()),
      );
      await signIn(h);
      await h.container
          .read(localeControllerProvider.notifier)
          .setLanguage(const Locale('en'));
      await h.container
          .read(apiClientProvider)
          .get<Object?>('/api/v1/me', parse: (j) => j);
      expect(h.backend.requests.single.language, 'en');
    });

    test(
      'an unauthenticated call (login) sends no Authorization header',
      () async {
        h.backend.on(
          'POST',
          '/api/v1/auth/login',
          (_) => FakeBackend.json(200, tokens('a', 'r')),
        );
        await h.container
            .read(authApiProvider)
            .login(email: ' a@b.test ', password: 'pw');
        final seen = h.backend.requests.single;
        expect(seen.authorization, isNull);
        expect(seen.body, {'email': ' a@b.test ', 'password': 'pw'});
        expect(seen.options.contentType, Headers.jsonContentType);
      },
    );

    test(
      'an authenticated call while signed out never reaches the network',
      () async {
        await expectLater(
          h.container
              .read(apiClientProvider)
              .get<Object?>('/api/v1/me', parse: (j) => j),
          throwsA(isA<StaleSessionException>()),
        );
        expect(h.backend.requests, isEmpty);
      },
    );

    test('maps timeouts and transport failures', () async {
      await signIn(h);
      final client = h.container.read(apiClientProvider);
      h.backend.on('GET', '/slow', FakeBackend.timedOut);
      h.backend.on('GET', '/down', FakeBackend.networkDown);
      await expectLater(
        client.get<Object?>('/slow', parse: (j) => j),
        throwsA(
          isA<ApiException>().having(
            (e) => e.kind,
            'kind',
            ApiErrorKind.timeout,
          ),
        ),
      );
      await expectLater(
        client.get<Object?>('/down', parse: (j) => j),
        throwsA(
          isA<ApiException>().having(
            (e) => e.kind,
            'kind',
            ApiErrorKind.network,
          ),
        ),
      );
    });

    test('maps the backend error envelope to a typed exception', () async {
      await signIn(h);
      final client = h.container.read(apiClientProvider);
      h.backend
        ..on(
          'POST',
          '/validation',
          (_) => FakeBackend.error(
            400,
            'validation_error',
            message: 'Bad.',
            details: {
              'email': ['Required.'],
            },
          ),
        )
        ..on(
          'GET',
          '/forbidden',
          (_) => FakeBackend.error(403, 'permission_denied'),
        )
        ..on('GET', '/missing', (_) => FakeBackend.error(404, 'not_found'))
        ..on('GET', '/throttled', (_) => FakeBackend.error(429, 'throttled'))
        ..on('GET', '/boom', (_) => FakeBackend.error(500, 'server_error'))
        ..on('GET', '/teapot', (_) => FakeBackend.error(418, 'weird'));

      Future<ApiException> failure(Future<Object?> call) async {
        try {
          await call;
        } on ApiException catch (e) {
          return e;
        }
        fail('expected an ApiException');
      }

      final validation = await failure(
        client.post<Object?>('/validation', parse: (j) => j, body: {}),
      );
      expect(validation.kind, ApiErrorKind.validation);
      expect(validation.code, 'validation_error');
      expect(validation.fieldError('email'), 'Required.');
      expect(validation.message, 'Bad.');
      expect(
        (await failure(client.get<Object?>('/forbidden', parse: (j) => j)))
            .kind,
        ApiErrorKind.forbidden,
      );
      expect(
        (await failure(client.get<Object?>('/missing', parse: (j) => j))).kind,
        ApiErrorKind.notFound,
      );
      expect(
        (await failure(client.get<Object?>('/throttled', parse: (j) => j)))
            .kind,
        ApiErrorKind.throttled,
      );
      final server = await failure(
        client.get<Object?>('/boom', parse: (j) => j),
      );
      expect(server.kind, ApiErrorKind.server);
      expect(server.isTransient, isTrue);
      expect(
        (await failure(client.get<Object?>('/teapot', parse: (j) => j))).kind,
        ApiErrorKind.rejected,
      );
    });

    test(
      'a non-JSON error page (proxy/gateway) still maps by status',
      () async {
        await signIn(h);
        h.backend.on(
          'GET',
          '/gateway',
          (_) => FakeBackend.text(502, '<html>Bad gateway</html>'),
        );
        await expectLater(
          h.container
              .read(apiClientProvider)
              .get<Object?>('/gateway', parse: (j) => j),
          throwsA(
            isA<ApiException>()
                .having((e) => e.kind, 'kind', ApiErrorKind.server)
                .having((e) => e.code, 'code', 'http_error'),
          ),
        );
      },
    );

    test(
      'an unreadable success body is an error, not silent garbage',
      () async {
        await signIn(h);
        h.backend.on(
          'GET',
          '/garbled',
          (_) => FakeBackend.text(200, 'not json {'),
        );
        await expectLater(
          h.container
              .read(apiClientProvider)
              .get<Object?>('/garbled', parse: (j) => j),
          throwsA(
            isA<ApiException>().having(
              (e) => e.code,
              'code',
              'invalid_response',
            ),
          ),
        );
      },
    );

    test('204 responses decode to nothing', () async {
      await signIn(h);
      h.backend.on('POST', '/void', (_) => FakeBackend.noContent());
      await h.container
          .read(apiClientProvider)
          .postNoContent('/void', body: {});
    });

    test(
      'deleteNoContent sends DELETE with the bearer token and accepts 204',
      () async {
        await signIn(h);
        h.backend.on('DELETE', '/slot/1', (_) => FakeBackend.noContent());
        await h.container.read(apiClientProvider).deleteNoContent('/slot/1');
        final sent = h.backend.to('DELETE', '/slot/1').single;
        expect(sent.authorization, 'Bearer access-1');
        expect(sent.body, isNull);
      },
    );

    test(
      'deleteNoContent maps a refusal to a typed exception and does not retry',
      () async {
        await signIn(h);
        h.backend.on(
          'DELETE',
          '/slot/1',
          (_) => FakeBackend.error(409, 'slot_unavailable'),
        );
        await expectLater(
          h.container.read(apiClientProvider).deleteNoContent('/slot/1'),
          throwsA(
            isA<ApiException>()
                .having((e) => e.code, 'code', 'slot_unavailable')
                .having((e) => e.kind, 'kind', ApiErrorKind.rejected),
          ),
        );
        expect(h.backend.count('DELETE', '/slot/1'), 1);
      },
    );

    test(
      'getPage parses the pagination envelope and sends page/page_size',
      () async {
        await signIn(h);
        h.backend.on(
          'GET',
          '/list',
          (_) => FakeBackend.json(200, {
            'count': 41,
            'next': 'https://api.test/list?page=3',
            'previous': 'https://api.test/list',
            'results': [
              {'n': 1},
              {'n': 2},
            ],
          }),
        );
        final page = await h.container
            .read(apiClientProvider)
            .getPage<int>(
              '/list',
              parseItem: (item) => (item! as Map<String, Object?>)['n']! as int,
              page: 2,
              pageSize: 20,
              query: {'search': 'x'},
            );
        expect(page, isA<Page<int>>());
        expect(page.count, 41);
        expect(page.results, [1, 2]);
        expect(page.hasNext, isTrue);
        expect(page.hasPrevious, isTrue);
        expect(h.backend.requests.single.query, {
          'search': 'x',
          'page': 2,
          'page_size': 20,
        });
      },
    );

    test('page 1 sends no page parameter (backend default)', () async {
      await signIn(h);
      h.backend.on(
        'GET',
        '/list',
        (_) => FakeBackend.json(200, {
          'count': 0,
          'next': null,
          'previous': null,
          'results': <Object?>[],
        }),
      );
      final page = await h.container
          .read(apiClientProvider)
          .getPage<int>('/list', parseItem: (_) => 0);
      expect(page.results, isEmpty);
      expect(h.backend.requests.single.query, isEmpty);
    });

    test('a caller-supplied CancelToken aborts the request', () async {
      await signIn(h);
      final release = Completer<void>();
      h.backend.on('GET', '/hang', (_) async {
        await release.future;
        return FakeBackend.json(200, {});
      });
      final cancel = CancelToken();
      final call = h.container
          .read(apiClientProvider)
          .get<Object?>('/hang', parse: (j) => j, cancelToken: cancel);
      await Future<void>.delayed(Duration.zero);
      cancel.cancel('screen left');
      await expectLater(
        call,
        throwsA(
          isA<ApiException>().having(
            (e) => e.kind,
            'kind',
            ApiErrorKind.cancelled,
          ),
        ),
      );
      release.complete();
    });
  });

  group('logging', () {
    test('never contains tokens, passwords or e-mail addresses', () async {
      final lines = <String>[];
      final h = Harness();
      addTearDown(h.dispose);
      h.backend
        ..on(
          'POST',
          '/api/v1/auth/login',
          (_) =>
              FakeBackend.json(200, tokens('access-SECRET', 'refresh-SECRET')),
        )
        ..on('GET', '/api/v1/me', (_) => FakeBackend.json(200, accountJson()));
      final client = ApiClient(
        dio: buildDio(Harness.config, adapter: h.backend),
        session: h.container.read(sessionCoreProvider),
        languageCode: () => 'en',
        logger: SafeLogger(sink: lines.add),
      );
      await client.post<Object?>(
        '/api/v1/auth/login',
        parse: (j) => j,
        auth: false,
        body: {'email': 'layla@example.com', 'password': 'hunter2'},
      );
      await h.container
          .read(sessionCoreProvider)
          .startSession(
            const TokenPair(access: 'access-SECRET', refresh: 'refresh-SECRET'),
          );
      await client.get<Object?>('/api/v1/me', parse: (j) => j);
      final all = lines.join('\n');
      expect(all, contains('POST /api/v1/auth/login -> 200'));
      for (final secret in [
        'SECRET',
        'hunter2',
        'layla@example.com',
        'Bearer',
      ]) {
        expect(all, isNot(contains(secret)));
      }
    });
  });
}
