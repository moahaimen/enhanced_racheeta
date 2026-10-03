import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';

import '../config/app_config.dart';
import '../logging/safe_logger.dart';
import 'api_exception.dart';
import 'page.dart';
import 'session_source.dart';

/// Builds the `Dio` used by [ApiClient]: base URL and the three timeouts come from [AppConfig].
/// Statuses are never thrown by Dio (`validateStatus` accepts all) so the client maps them itself.
Dio buildDio(AppConfig config, {HttpClientAdapter? adapter}) {
  final dio = Dio(
    BaseOptions(
      baseUrl: config.apiBaseUrl,
      connectTimeout: config.connectTimeout,
      sendTimeout: config.sendTimeout,
      receiveTimeout: config.receiveTimeout,
      responseType: ResponseType.plain,
      validateStatus: (_) => true,
      followRedirects: false,
    ),
  );
  if (adapter != null) dio.httpClientAdapter = adapter;
  return dio;
}

/// The one HTTP layer of the app. Every feature goes through it; nothing else touches Dio.
///
/// * prefixes `/api/v1/` paths with the configured origin and sends `Accept-Language`;
/// * attaches `Authorization: Bearer <access>` for authenticated calls;
/// * on 401 rotates the refresh token once (single flight) and retries the request once;
/// * maps every failure to [ApiException]; a response that belongs to a session that has ended is
///   discarded with [StaleSessionException];
/// * logs method, path, status and duration only (see `SafeLogger`).
class ApiClient {
  ApiClient({
    required this._dio,
    required this._session,
    required this._languageCode,
    this._logger = const SafeLogger(),
  });

  final Dio _dio;
  final AuthSessionSource _session;
  final String Function() _languageCode;
  final SafeLogger _logger;

  Future<T> get<T>(
    String path, {
    required T Function(Object? json) parse,
    Map<String, Object?>? query,
    bool auth = true,
    CancelToken? cancelToken,
  }) async => parse(
    await _request(
      'GET',
      path,
      query: query,
      auth: auth,
      cancelToken: cancelToken,
    ),
  );

  Future<T> post<T>(
    String path, {
    required T Function(Object? json) parse,
    Object? body,
    bool auth = true,
    CancelToken? cancelToken,
  }) async => parse(
    await _request(
      'POST',
      path,
      body: body,
      auth: auth,
      cancelToken: cancelToken,
    ),
  );

  Future<T> patch<T>(
    String path, {
    required T Function(Object? json) parse,
    Object? body,
    bool auth = true,
    CancelToken? cancelToken,
  }) async => parse(
    await _request(
      'PATCH',
      path,
      body: body,
      auth: auth,
      cancelToken: cancelToken,
    ),
  );

  /// For endpoints that answer 204 / no body.
  Future<void> postNoContent(
    String path, {
    Object? body,
    bool auth = true,
    CancelToken? cancelToken,
  }) async {
    await _request(
      'POST',
      path,
      body: body,
      auth: auth,
      cancelToken: cancelToken,
    );
  }

  /// One page of a list endpoint (`?page=`, `?page_size=`). The backend caps `page_size` at 100.
  Future<Page<T>> getPage<T>(
    String path, {
    required T Function(Object? item) parseItem,
    int page = 1,
    int? pageSize,
    Map<String, Object?>? query,
    bool auth = true,
    CancelToken? cancelToken,
  }) {
    final params = <String, Object?>{
      ...?query,
      if (page > 1) 'page': page,
      'page_size': ?pageSize,
    };
    return get<Page<T>>(
      path,
      parse: (json) => Page<T>.fromJson(json, parseItem),
      query: params.isEmpty ? null : params,
      auth: auth,
      cancelToken: cancelToken,
    );
  }

  Future<Object?> _request(
    String method,
    String path, {
    Object? body,
    Map<String, Object?>? query,
    required bool auth,
    CancelToken? cancelToken,
  }) async {
    final scope = auth ? _session.scope : null;
    if (auth && scope == null) {
      throw const StaleSessionException(); // signed out: never hit the API
    }
    var refreshed = false;
    while (true) {
      final usedAccess = auth ? _session.accessToken : null;
      final response = await _once(
        method,
        path,
        body: body,
        query: query,
        accessToken: usedAccess,
        scope: scope,
        cancelToken: cancelToken,
      );
      _ensureCurrent(scope);

      if (response.statusCode == 401 &&
          auth &&
          !refreshed &&
          _session.canRefresh) {
        refreshed = true;
        // Another request may already have rotated the token while this one was in flight.
        final current = _session.accessToken;
        if (current != null && current != usedAccess) continue;
        final recovered = await _session.refresh();
        _ensureCurrent(scope);
        if (recovered) continue;
      }

      final status = response.statusCode ?? 0;
      final decoded = _decode(
        response.data,
        success: status >= 200 && status < 300,
      );
      if (status >= 200 && status < 300) return decoded;
      throw ApiException.fromResponse(status, decoded);
    }
  }

  void _ensureCurrent(SessionScope? scope) {
    if (scope == null) return;
    final now = _session.scope;
    if (now == null || now.generation != scope.generation) {
      throw const StaleSessionException();
    }
  }

  Future<Response<String>> _once(
    String method,
    String path, {
    required Object? body,
    required Map<String, Object?>? query,
    required String? accessToken,
    required SessionScope? scope,
    required CancelToken? cancelToken,
  }) async {
    final token = CancelToken();
    scope?.track(token);
    // A caller-supplied token (e.g. a screen that was left) cancels this request too.
    unawaited(
      cancelToken?.whenCancel.then<void>(
        (_) => token.cancel('caller cancelled'),
      ),
    );

    final stopwatch = Stopwatch()..start();
    try {
      final response = await _dio.request<String>(
        path,
        data: body,
        queryParameters: query,
        cancelToken: token,
        options: Options(
          method: method,
          contentType: body == null ? null : Headers.jsonContentType,
          headers: <String, Object>{
            'Accept': 'application/json',
            'Accept-Language': _languageCode(),
            if (accessToken != null) 'Authorization': 'Bearer $accessToken',
          },
        ),
      );
      _logger.info(
        '$method $path -> ${response.statusCode} (${stopwatch.elapsedMilliseconds}ms)',
      );
      return response;
    } on DioException catch (error) {
      _logger.warning('$method $path failed: ${error.type.name}');
      throw _map(error, scope);
    } finally {
      scope?.release(token);
    }
  }

  Exception _map(DioException error, SessionScope? scope) {
    switch (error.type) {
      case DioExceptionType.cancel:
        if (scope != null && scope.isEnded) {
          return const StaleSessionException();
        }
        return ApiException.cancelled;
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
      case DioExceptionType.transformTimeout:
        return ApiException.timeout;
      case DioExceptionType.connectionError:
      case DioExceptionType.badCertificate:
      case DioExceptionType.badResponse:
      case DioExceptionType.unknown:
        return ApiException.network;
    }
  }

  Object? _decode(String? raw, {required bool success}) {
    if (raw == null || raw.isEmpty) return null;
    try {
      return jsonDecode(raw);
    } on FormatException {
      if (success) {
        throw const ApiException(
          kind: ApiErrorKind.server,
          statusCode: 200,
          code: 'invalid_response',
          message: 'The server sent an unreadable response.',
        );
      }
      return null; // non-JSON error page (proxy, gateway): fall back to the status code
    }
  }
}
