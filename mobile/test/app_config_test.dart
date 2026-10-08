import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/core/config/app_config.dart';

void main() {
  group('AppConfig', () {
    test('development falls back to the emulator host and allows cleartext in debug', () {
      final config = AppConfig.fromEnvironment(
        appEnv: 'development',
        apiBaseUrl: '',
        releaseMode: false,
      );
      expect(config.apiBaseUrl, 'http://10.0.2.2:8000');
      expect(config.environment, AppEnvironment.development);
    });

    test('staging and production have no default URL', () {
      for (final env in ['staging', 'production']) {
        expect(
          () => AppConfig.fromEnvironment(
            appEnv: env,
            apiBaseUrl: '',
            releaseMode: false,
          ),
          throwsA(isA<ConfigurationError>()),
        );
      }
    });

    test('normalises a trailing slash', () {
      final config = AppConfig.fromEnvironment(
        appEnv: 'production',
        apiBaseUrl: 'https://api.racheeta.example///',
        releaseMode: true,
      );
      expect(config.apiBaseUrl, 'https://api.racheeta.example');
    });

    test('cleartext http is rejected outside a debug development build', () {
      for (final (env, release) in [
        ('staging', false),
        ('production', false),
        ('production', true),
        ('development', true),
      ]) {
        expect(
          () => AppConfig.fromEnvironment(
            appEnv: env,
            apiBaseUrl: 'http://api.example.com',
            releaseMode: release,
          ),
          throwsA(isA<ConfigurationError>()),
          reason: '$env release=$release',
        );
      }
    });

    test('a release build can never run the development environment', () {
      expect(
        () => AppConfig.fromEnvironment(
          appEnv: 'development',
          apiBaseUrl: 'https://api.example.com',
          releaseMode: true,
        ),
        throwsA(isA<ConfigurationError>()),
      );
    });

    test(
      'rejects unknown environments, non-http schemes and malformed URLs',
      () {
        expect(
          () => AppConfig.fromEnvironment(
            appEnv: 'prod',
            apiBaseUrl: 'https://x.test',
            releaseMode: false,
          ),
          throwsA(isA<ConfigurationError>()),
        );
        for (final bad in [
          'ftp://api.example.com',
          'api.example.com',
          'https://',
        ]) {
          expect(
            () => AppConfig.fromEnvironment(
              appEnv: 'staging',
              apiBaseUrl: bad,
              releaseMode: false,
            ),
            throwsA(isA<ConfigurationError>()),
            reason: bad,
          );
        }
      },
    );

    test('https is accepted everywhere', () {
      for (final env in ['development', 'staging', 'production']) {
        expect(
          AppConfig.fromEnvironment(
            appEnv: env,
            apiBaseUrl: 'https://api.example.com',
            releaseMode: env != 'development',
          ).apiBaseUrl,
          'https://api.example.com',
        );
      }
    });

    group('release safety', () {
      test('a production release without an explicit URL fails (no default, no localhost)', () {
        expect(
          () => AppConfig.fromEnvironment(
            appEnv: 'production',
            apiBaseUrl: '',
            releaseMode: true,
          ),
          throwsA(isA<ConfigurationError>()),
        );
        // the default environment (no --dart-define) is development, which a release rejects
        expect(
          () => AppConfig.fromEnvironment(
            appEnv: 'development',
            apiBaseUrl: '',
            releaseMode: true,
          ),
          throwsA(isA<ConfigurationError>()),
        );
        expect(
          () => AppConfig.fromEnvironment(
            appEnv: 'production',
            apiBaseUrl: '   ',
            releaseMode: true,
          ),
          throwsA(isA<ConfigurationError>()),
        );
      });

      test('release, staging and production never accept localhost or the emulator alias, even over https', () {
        for (final host in [
          'https://localhost',
          'https://LOCALHOST:8443',
          'https://10.0.2.2',
          'https://10.0.2.2:8000',
          'https://127.0.0.1',
          'https://127.1.2.3',
          'https://[::1]',
          'https://0.0.0.0',
          'https://api.localhost',
        ]) {
          for (final (env, release) in [
            ('production', true),
            ('production', false),
            ('staging', true),
            ('staging', false),
          ]) {
            expect(
              () => AppConfig.fromEnvironment(
                appEnv: env,
                apiBaseUrl: host,
                releaseMode: release,
              ),
              throwsA(isA<ConfigurationError>()),
              reason: '$host in $env release=$release',
            );
          }
        }
      });

      test(
        'a debug development build may still use the local development API',
        () {
          for (final url in [
            'http://10.0.2.2:8000',
            'http://localhost:8000',
            'https://127.0.0.1:8443',
          ]) {
            expect(
              AppConfig.fromEnvironment(
                appEnv: 'development',
                apiBaseUrl: url,
                releaseMode: false,
              ).apiBaseUrl,
              url,
            );
          }
        },
      );

      test(
        'the URL must be a plain origin: no credentials, query or fragment',
        () {
          for (final url in [
            'https://user:pw@api.example.com',
            'https://user@api.example.com',
            'https://api.example.com?x=1',
            'https://api.example.com/#frag',
          ]) {
            expect(
              () => AppConfig.fromEnvironment(
                appEnv: 'production',
                apiBaseUrl: url,
                releaseMode: true,
              ),
              throwsA(isA<ConfigurationError>()),
              reason: url,
            );
          }
        },
      );

      test(
        'the URL must be an origin only: a path would be prepended to /api/v1',
        () {
          for (final url in [
            'https://api.example.com/api',
            'https://api.example.com/api/v1',
            'https://api.example.com/v1/',
            'https://api.example.com/prefix/nested',
          ]) {
            for (final env in ['production', 'staging']) {
              expect(
                () => AppConfig.fromEnvironment(
                  appEnv: env,
                  apiBaseUrl: url,
                  releaseMode: true,
                ),
                throwsA(isA<ConfigurationError>()),
                reason: '$url in $env',
              );
            }
          }
          expect(
            () => AppConfig.fromEnvironment(
              appEnv: 'development',
              apiBaseUrl: 'http://10.0.2.2:8000/api',
              releaseMode: false,
            ),
            throwsA(isA<ConfigurationError>()),
          );
          // A bare origin, with or without trailing slashes, still works.
          for (final url in [
            'https://api.example.com',
            'https://api.example.com/',
          ]) {
            expect(
              AppConfig.fromEnvironment(
                appEnv: 'production',
                apiBaseUrl: url,
                releaseMode: true,
              ).apiBaseUrl,
              'https://api.example.com',
            );
          }
        },
      );

      test('a valid production release URL is accepted and the error is a safe message', () {
        final config = AppConfig.fromEnvironment(
          appEnv: 'production',
          apiBaseUrl: 'https://api.racheeta.example',
          releaseMode: true,
        );
        expect(config.environment, AppEnvironment.production);
        try {
          AppConfig.fromEnvironment(
            appEnv: 'production',
            apiBaseUrl: 'https://user:topsecret@api.example.com',
            releaseMode: true,
          );
          fail('expected a ConfigurationError');
        } on ConfigurationError catch (error) {
          expect(error.message, isNot(contains('topsecret')));
        }
      });
    });
  });
}
