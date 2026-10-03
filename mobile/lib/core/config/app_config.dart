import 'package:flutter/foundation.dart';

/// Deployment environment, chosen at build time with `--dart-define=APP_ENV=...`.
enum AppEnvironment {
  development,
  staging,
  production;

  static AppEnvironment parse(String value) {
    for (final env in values) {
      if (env.name == value) return env;
    }
    throw ConfigurationError(
      'APP_ENV must be one of ${values.map((e) => e.name).join(', ')} (got "$value").',
    );
  }
}

/// A build is misconfigured. Surfaced as a start-up screen, never as a crash or a silent fallback.
class ConfigurationError implements Exception {
  const ConfigurationError(this.message);
  final String message;

  @override
  String toString() => 'ConfigurationError: $message';
}

/// Build-time configuration. Contains **no secrets**: only the environment name, the public API
/// origin and network timeouts. Values come from `--dart-define` / `--dart-define-from-file`.
@immutable
class AppConfig {
  const AppConfig({
    required this.environment,
    required this.apiBaseUrl,
    this.connectTimeout = const Duration(seconds: 10),
    this.sendTimeout = const Duration(seconds: 20),
    this.receiveTimeout = const Duration(seconds: 20),
  });

  /// Reads `APP_ENV` and `API_BASE_URL`. Development falls back to the Android-emulator host
  /// alias; staging and production have no default and must set `API_BASE_URL` explicitly.
  factory AppConfig.fromEnvironment({
    String appEnv = const String.fromEnvironment(
      'APP_ENV',
      defaultValue: 'development',
    ),
    String apiBaseUrl = const String.fromEnvironment('API_BASE_URL'),
    bool? releaseMode,
  }) {
    final environment = AppEnvironment.parse(appEnv);
    var url = apiBaseUrl.trim();
    if (url.isEmpty && environment == AppEnvironment.development) {
      url = 'http://10.0.2.2:8000';
    }
    final config = AppConfig(
      environment: environment,
      apiBaseUrl: _normalise(url),
    );
    config.validate(releaseMode: releaseMode ?? kReleaseMode);
    return config;
  }

  final AppEnvironment environment;

  /// Origin of the Django API, without a trailing slash and without `/api/v1`.
  final String apiBaseUrl;
  final Duration connectTimeout;
  final Duration sendTimeout;
  final Duration receiveTimeout;

  /// TLS is mandatory everywhere except a debug build pointed at the development environment.
  /// There is no switch that disables certificate verification.
  void validate({required bool releaseMode}) {
    final uri = Uri.tryParse(apiBaseUrl);
    if (apiBaseUrl.isEmpty ||
        uri == null ||
        !uri.hasScheme ||
        uri.host.isEmpty) {
      throw const ConfigurationError(
        'API_BASE_URL is missing or not a valid absolute URL '
        '(example: --dart-define=API_BASE_URL=https://api.example.com).',
      );
    }
    if (uri.scheme != 'https' && uri.scheme != 'http') {
      throw ConfigurationError(
        'API_BASE_URL must use https (got "${uri.scheme}").',
      );
    }
    final cleartextAllowed =
        !releaseMode && environment == AppEnvironment.development;
    if (uri.scheme == 'http' && !cleartextAllowed) {
      throw const ConfigurationError(
        'API_BASE_URL must use https. Cleartext http is allowed only in a debug build '
        'with APP_ENV=development.',
      );
    }
    if (releaseMode && environment == AppEnvironment.development) {
      throw const ConfigurationError(
        'A release build cannot use APP_ENV=development.',
      );
    }
  }

  static String _normalise(String value) =>
      value.replaceAll(RegExp(r'/+$'), '');
}
