import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/misc.dart' show Override;
import 'package:racheeta_mobile/core/api/api_client.dart';
import 'package:racheeta_mobile/core/config/app_config.dart';
import 'package:racheeta_mobile/core/storage/preferences_store.dart';
import 'package:racheeta_mobile/core/storage/token_store.dart';
import 'package:racheeta_mobile/features/auth/application/providers.dart';

/// A request as the (fake) server saw it.
class SeenRequest {
  SeenRequest(this.options);
  final RequestOptions options;

  String get method => options.method;
  String get path => options.path;
  Map<String, Object?> get query => options.queryParameters;
  String? get authorization => options.headers['Authorization'] as String?;
  String? get language => options.headers['Accept-Language'] as String?;
  Object? get body {
    final data = options.data;
    if (data is String) return jsonDecode(data);
    return data;
  }
}

typedef Responder = FutureOr<ResponseBody> Function(SeenRequest request);

/// Scripted HTTP adapter: no network, ever. Routes are matched on `METHOD /path`.
class FakeBackend implements HttpClientAdapter {
  final List<SeenRequest> requests = <SeenRequest>[];
  final Map<String, Responder> _routes = <String, Responder>{};

  void on(String method, String path, Responder responder) =>
      _routes['$method $path'] = responder;

  int count(String method, String path) =>
      requests.where((r) => r.method == method && r.path == path).length;

  List<SeenRequest> to(String method, String path) =>
      requests.where((r) => r.method == method && r.path == path).toList();

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final request = SeenRequest(options);
    requests.add(request);
    final responder = _routes['${options.method} ${options.path}'];
    if (responder == null) {
      return json(404, <String, Object?>{
        'error': <String, Object?>{
          'code': 'not_found',
          'message': 'Not found.',
        },
      });
    }
    final pending = Future<ResponseBody>.value(responder(request));
    if (cancelFuture == null) return pending;
    // Mirror a real adapter: a cancelled request fails with a cancel error.
    final cancelled = cancelFuture.then<ResponseBody>(
      (_) => throw DioException.requestCancelled(
        requestOptions: options,
        reason: 'cancelled',
      ),
    );
    return Future.any(<Future<ResponseBody>>[pending, cancelled]);
  }

  @override
  void close({bool force = false}) {}

  static ResponseBody json(int status, Object? body) => ResponseBody.fromString(
    body == null ? '' : jsonEncode(body),
    status,
    headers: <String, List<String>>{
      Headers.contentTypeHeader: <String>[Headers.jsonContentType],
    },
  );

  static ResponseBody text(int status, String body) =>
      ResponseBody.fromString(body, status);

  static ResponseBody noContent() => ResponseBody.fromString('', 204);

  static ResponseBody error(
    int status,
    String code, {
    String message = 'Failed.',
    Object? details,
  }) => json(status, <String, Object?>{
    'error': <String, Object?>{
      'code': code,
      'message': message,
      'details': ?details,
    },
  });

  /// A transport-level failure (no response at all).
  static Never networkDown(SeenRequest request) =>
      throw DioException.connectionError(
        requestOptions: request.options,
        reason: 'offline',
      );

  static Never timedOut(SeenRequest request) =>
      throw DioException.receiveTimeout(
        timeout: const Duration(seconds: 20),
        requestOptions: request.options,
      );
}

const testAccountJson = <String, Object?>{
  'id': '11111111-1111-4111-8111-111111111111',
  'email': 'layla@example.com',
  'full_name': 'Layla Hassan',
  'phone_number': '',
  'role': 'PATIENT',
  'preferred_language': 'ar',
  'email_verified': true,
  'email_verified_at': '2026-09-01T10:00:00Z',
  'has_password': true,
  'is_staff': false,
  'permissions': <String>[
    'accounts.view_self',
    'providers.search',
    'reservations.create_own',
  ],
  'created_at': '2026-09-01T09:00:00Z',
  'last_login': null,
};

Map<String, Object?> accountJson({
  String id = '11111111-1111-4111-8111-111111111111',
  String name = 'Layla Hassan',
  String role = 'PATIENT',
}) => <String, Object?>{
  ...testAccountJson,
  'id': id,
  'full_name': name,
  'role': role,
};

Map<String, Object?> tokens(String access, String refresh) => <String, Object?>{
  'access': access,
  'refresh': refresh,
};

/// Everything a test needs to run the real wiring against a [FakeBackend].
class Harness {
  Harness({
    String? storedRefresh,
    bool autoRestore = false,
    this.language,
    List<Override> extraOverrides = const <Override>[],
  }) : backend = FakeBackend(),
       tokenStore = MemoryTokenStore(storedRefresh),
       preferences = MemoryPreferencesStore(language) {
    container = ProviderContainer(
      overrides: [..._overrides(autoRestore), ...extraOverrides],
    );
  }

  final FakeBackend backend;
  final MemoryTokenStore tokenStore;
  final MemoryPreferencesStore preferences;
  final String? language;
  late final ProviderContainer container;

  static const config = AppConfig(
    environment: AppEnvironment.staging,
    apiBaseUrl: 'https://api.test',
  );

  List<Override> _overrides(bool autoRestore) => <Override>[
    appConfigProvider.overrideWithValue(config),
    tokenStoreProvider.overrideWithValue(tokenStore),
    preferencesStoreProvider.overrideWithValue(preferences),
    autoRestoreSessionProvider.overrideWithValue(autoRestore),
    dioProvider.overrideWith((ref) => buildDio(config, adapter: backend)),
  ];

  List<Override> get overrides => _overrides(false);

  void dispose() => container.dispose();
}
