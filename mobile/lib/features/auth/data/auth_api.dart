import 'package:dio/dio.dart';

import '../../../core/api/api_client.dart';
import 'auth_models.dart';

/// The authentication endpoints of `/api/v1/` (see `docs/AUTHENTICATION.md`). Typed, thin, and the
/// only place that knows these paths.
class AuthApi {
  const AuthApi(this._client);
  final ApiClient _client;

  /// `POST /auth/login` → `{access, refresh}`. Wrong credentials: 401 `no_active_account`.
  Future<TokenPair> login({required String email, required String password}) =>
      _client.post<TokenPair>(
        '/api/v1/auth/login',
        body: <String, String>{'email': email, 'password': password},
        parse: TokenPair.fromJson,
        auth: false,
      );

  /// `POST /auth/refresh` → a NEW pair; the old refresh token is blacklisted (rotation).
  Future<TokenPair> refresh(String refreshToken) => _client.post<TokenPair>(
    '/api/v1/auth/refresh',
    body: <String, String>{'refresh': refreshToken},
    parse: TokenPair.fromJson,
    auth: false,
  );

  /// `POST /auth/logout` (204). 400 `token_invalid` when already revoked: callers ignore it.
  Future<void> logout(String refreshToken) => _client.postNoContent(
    '/api/v1/auth/logout',
    body: <String, String>{'refresh': refreshToken},
    auth: false,
  );

  /// `GET /me`: canonical identity, role and permissions.
  Future<Account> me({CancelToken? cancelToken}) => _client.get<Account>(
    '/api/v1/me',
    parse: Account.fromJson,
    cancelToken: cancelToken,
  );
}
