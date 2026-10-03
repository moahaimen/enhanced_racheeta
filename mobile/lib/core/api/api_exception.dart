import 'package:flutter/foundation.dart';

/// Coarse classification the UI and the session layer branch on.
enum ApiErrorKind {
  /// No connection, DNS/TLS failure or an unreadable response.
  network,

  /// A connect/send/receive timeout.
  timeout,

  /// 401: missing/expired credentials (after a refresh attempt where applicable).
  unauthorized,

  /// 403.
  forbidden,

  /// 404.
  notFound,

  /// 400 with the backend `validation_error` envelope.
  validation,

  /// 429.
  throttled,

  /// 5xx.
  server,

  /// Anything else the backend rejected (409, 422, …).
  rejected,

  /// The request was cancelled locally (screen left, session ended).
  cancelled,
}

/// Every failure of the API layer. The backend error envelope
/// (`{"error": {"code", "message", "details"?, "codes"?, "meta"?}}`, see `docs/API.md`) is mapped
/// onto this one type; callers never see `DioException`.
@immutable
class ApiException implements Exception {
  const ApiException({
    required this.kind,
    required this.statusCode,
    required this.code,
    required this.message,
    this.details,
    this.codes,
    this.meta,
  });

  final ApiErrorKind kind;

  /// HTTP status, or 0 when no response was received.
  final int statusCode;

  /// Stable machine code (`no_active_account`, `token_not_valid`, `network_error`, …).
  final String code;

  /// Server message in the request language (may be empty for local failures).
  final String message;

  /// Field → messages, for `validation_error`.
  final Map<String, List<String>>? details;

  /// Field → error codes, for `validation_error`.
  final Map<String, List<String>>? codes;

  /// Entitlement metadata for commercial errors.
  final Map<String, Object?>? meta;

  /// First message for [field], for inline form errors.
  String? fieldError(String field) {
    final messages = details?[field];
    return (messages == null || messages.isEmpty) ? null : messages.first;
  }

  /// True when a refresh attempt that failed this way proves the refresh token is dead (as opposed
  /// to a transient network/server problem that must not end the session).
  bool get isDefinitiveRejection =>
      kind == ApiErrorKind.unauthorized ||
      kind == ApiErrorKind.forbidden ||
      kind == ApiErrorKind.validation ||
      kind == ApiErrorKind.notFound;

  bool get isTransient =>
      kind == ApiErrorKind.network ||
      kind == ApiErrorKind.timeout ||
      kind == ApiErrorKind.server ||
      kind == ApiErrorKind.throttled;

  /// Credentials, tokens and payloads are never part of the string form.
  @override
  String toString() =>
      'ApiException(${kind.name}, status=$statusCode, code=$code)';

  static const network = ApiException(
    kind: ApiErrorKind.network,
    statusCode: 0,
    code: 'network_error',
    message: 'Could not reach the server.',
  );

  static const timeout = ApiException(
    kind: ApiErrorKind.timeout,
    statusCode: 0,
    code: 'timeout',
    message: 'The server took too long to respond.',
  );

  static const cancelled = ApiException(
    kind: ApiErrorKind.cancelled,
    statusCode: 0,
    code: 'cancelled',
    message: 'The request was cancelled.',
  );

  /// Maps an HTTP failure. [body] is the decoded JSON (or null / a string for non-JSON bodies).
  factory ApiException.fromResponse(int status, Object? body) {
    final kind = _kindFor(status);
    final error = (body is Map<String, Object?>) ? body['error'] : null;
    if (error is Map<String, Object?> && error['code'] is String) {
      return ApiException(
        kind: kind,
        statusCode: status,
        code: error['code']! as String,
        message: (error['message'] as String?) ?? '',
        details: _stringListMap(error['details']),
        codes: _stringListMap(error['codes']),
        meta: error['meta'] is Map<String, Object?>
            ? error['meta']! as Map<String, Object?>
            : null,
      );
    }
    return ApiException(
      kind: kind,
      statusCode: status,
      code: 'http_error',
      message: 'Request failed with status $status.',
    );
  }

  static ApiErrorKind _kindFor(int status) {
    if (status == 400) return ApiErrorKind.validation;
    if (status == 401) return ApiErrorKind.unauthorized;
    if (status == 403) return ApiErrorKind.forbidden;
    if (status == 404) return ApiErrorKind.notFound;
    if (status == 429) return ApiErrorKind.throttled;
    if (status >= 500) return ApiErrorKind.server;
    return ApiErrorKind.rejected;
  }

  static Map<String, List<String>>? _stringListMap(Object? value) {
    if (value is! Map<String, Object?>) return null;
    final result = <String, List<String>>{};
    value.forEach((key, entry) {
      if (entry is List) {
        result[key] = entry.whereType<String>().toList(growable: false);
      }
    });
    return result;
  }
}

/// A response arrived for a session that no longer exists (logout, expiry or an account switch
/// happened while the request was in flight). Its data must never reach the UI.
class StaleSessionException implements Exception {
  const StaleSessionException();

  @override
  String toString() => 'StaleSessionException';
}
