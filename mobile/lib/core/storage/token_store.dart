import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Persistence for the one long-lived credential: the refresh token.
///
/// The access token is deliberately **never** persisted (it lives in memory only and is recovered
/// by rotating the refresh token on start-up), which matches `docs/AUTHENTICATION.md`.
abstract interface class TokenStore {
  Future<String?> readRefreshToken();
  Future<void> writeRefreshToken(String token);
  Future<void> clear();
}

/// Platform secure storage: Android Keystore-backed encrypted preferences / iOS Keychain.
/// Never `SharedPreferences`.
class SecureTokenStore implements TokenStore {
  SecureTokenStore({FlutterSecureStorage? storage})
    : _storage =
          storage ??
          const FlutterSecureStorage(
            iOptions: IOSOptions(
              accessibility: KeychainAccessibility.first_unlock_this_device,
            ),
          );

  static const _refreshKey = 'racheeta.session.refresh';
  final FlutterSecureStorage _storage;

  @override
  Future<String?> readRefreshToken() => _storage.read(key: _refreshKey);

  @override
  Future<void> writeRefreshToken(String token) =>
      _storage.write(key: _refreshKey, value: token);

  @override
  Future<void> clear() => _storage.delete(key: _refreshKey);
}

/// Volatile store for tests and previews. Never used in the shipped app.
class MemoryTokenStore implements TokenStore {
  MemoryTokenStore([this._refresh]);
  String? _refresh;

  @override
  Future<String?> readRefreshToken() async => _refresh;

  @override
  Future<void> writeRefreshToken(String token) async => _refresh = token;

  @override
  Future<void> clear() async => _refresh = null;
}
