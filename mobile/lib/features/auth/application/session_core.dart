import 'dart:async';

import '../../../core/api/api_exception.dart';
import '../../../core/api/session_source.dart';
import '../../../core/logging/safe_logger.dart';
import '../../../core/storage/token_store.dart';
import '../data/auth_models.dart';

/// Why a session ended without the user asking for it.
enum SessionEndReason { expired, loggedOut }

/// Performs the network rotation. Injected so this class has no dependency on `ApiClient`.
typedef RefreshExecutor = Future<TokenPair> Function(String refreshToken);

/// Pure-Dart owner of the credentials. No Flutter, no Riverpod, no UI.
///
/// * the **access token lives in memory only**; the **refresh token is persisted in secure
///   storage** and rotated on every refresh (the new one is written before it is used);
/// * [refresh] is **single flight**: any number of concurrent 401s cause exactly one rotation;
/// * every login and every end of session starts a new [SessionScope] (a new `generation`) and
///   cancels the old one, so late responses of a previous account cannot be applied.
class SessionCore implements AuthSessionSource {
  SessionCore({
    required this._store,
    required this._refresher,
    this._logger = const SafeLogger(),
  });

  final TokenStore _store;
  final RefreshExecutor _refresher;
  final SafeLogger _logger;

  String? _access;
  String? _refresh;
  SessionScope? _scope;
  int _generation = 0;
  Future<bool>? _refreshInFlight;
  final StreamController<SessionEndReason> _ended =
      StreamController<SessionEndReason>.broadcast();

  /// Fires when the session is ended by the system (a refresh was definitively rejected).
  Stream<SessionEndReason> get ended => _ended.stream;

  int get generation => _generation;

  @override
  String? get accessToken => _access;

  @override
  SessionScope? get scope => _scope;

  @override
  bool get canRefresh => _refresh != null;

  /// Loads a persisted refresh token (start-up). Returns true when one exists.
  Future<bool> loadStoredSession() async {
    final stored = await _store.readRefreshToken();
    if (stored == null || stored.isEmpty) return false;
    _refresh = stored;
    return true;
  }

  /// Adopts a fresh login. Replaces any previous session (and aborts its requests).
  Future<void> startSession(TokenPair tokens) async {
    _replaceScope();
    _access = tokens.access;
    _refresh = tokens.refresh;
    await _persistRefresh(tokens.refresh);
  }

  /// Local sign-out: forgets the credentials and aborts everything in flight. Returns the refresh
  /// token that was current so the caller can ask the backend to revoke it.
  Future<String?> endSession() async {
    final previous = _refresh;
    _replaceScope(startNew: false);
    _access = null;
    _refresh = null;
    await _clearStore();
    return previous;
  }

  @override
  Future<bool> refresh() {
    final running = _refreshInFlight;
    if (running != null) return running;
    final attempt = _rotate();
    _refreshInFlight = attempt;
    return attempt.whenComplete(() => _refreshInFlight = null);
  }

  Future<bool> _rotate() async {
    final generation = _generation;
    final token = _refresh;
    if (token == null) return false;
    try {
      final pair = await _refresher(token);
      if (generation != _generation) {
        return false; // signed out/switched meanwhile: discard
      }
      _access = pair.access;
      _refresh = pair.refresh;
      // A session restored from storage has no scope yet; the first successful rotation creates it.
      _scope ??= SessionScope(_generation);
      // Persist the rotated token BEFORE anything can use it; the old one is already blacklisted.
      await _persistRefresh(pair.refresh);
      return true;
    } on ApiException catch (error) {
      if (generation != _generation) return false;
      if (error.isDefinitiveRejection) {
        _logger.warning('refresh rejected (${error.code}); ending session');
        _replaceScope(startNew: false);
        _access = null;
        _refresh = null;
        await _clearStore();
        _ended.add(SessionEndReason.expired);
        return false;
      }
      rethrow; // network/timeout/5xx/429: keep the session, let the caller report the failure
    }
  }

  void _replaceScope({bool startNew = true}) {
    _scope?.end();
    _generation += 1;
    _refreshInFlight = null;
    _scope = startNew ? SessionScope(_generation) : null;
  }

  Future<void> _persistRefresh(String token) async {
    try {
      await _store.writeRefreshToken(token);
    } on Object catch (error) {
      // The in-memory session still works; the user may have to sign in again after a restart.
      _logger.warning('could not persist refresh token (${error.runtimeType})');
    }
  }

  Future<void> _clearStore() async {
    // Retry once: a refresh token left on the device after sign-out would restore the session.
    for (var attempt = 0; attempt < 2; attempt++) {
      try {
        await _store.clear();
        return;
      } on Object catch (error) {
        _logger.warning(
          'could not clear stored session (${error.runtimeType})',
        );
      }
    }
  }

  Future<void> dispose() => _ended.close();
}
