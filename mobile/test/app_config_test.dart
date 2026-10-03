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
  });
}
