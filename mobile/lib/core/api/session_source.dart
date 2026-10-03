import 'package:dio/dio.dart';

/// Identifies one authenticated session. A new scope is created on every login and the old one is
/// cancelled on logout/expiry, so work started under a previous account can be recognised and
/// discarded (`generation`) and its in-flight HTTP requests aborted (tracked tokens).
class SessionScope {
  SessionScope(this.generation);

  final int generation;
  final Set<CancelToken> _active = <CancelToken>{};
  bool _ended = false;

  bool get isEnded => _ended;

  /// Registers an in-flight request. If the session already ended the request is cancelled at
  /// once, so a late caller can never reach the network under a dead session.
  void track(CancelToken token) {
    if (_ended) {
      token.cancel('session ended');
    } else {
      _active.add(token);
    }
  }

  void release(CancelToken token) => _active.remove(token);

  /// Ends the scope and aborts everything still in flight under it.
  void end() {
    if (_ended) return;
    _ended = true;
    for (final token in _active.toList(growable: false)) {
      token.cancel('session ended');
    }
    _active.clear();
  }
}

/// What the API client needs from the session layer. Keeps `ApiClient` free of any dependency on
/// storage, state management or UI (and breaks the client ↔ session construction cycle).
abstract interface class AuthSessionSource {
  /// The in-memory access token of the current session, or null when signed out.
  String? get accessToken;

  /// The current session scope, or null when signed out.
  SessionScope? get scope;

  /// True when a refresh token exists, i.e. a 401 may be recovered by rotating it.
  bool get canRefresh;

  /// Rotates the refresh token. Concurrent callers share ONE network call. Returns false when the
  /// session was definitively rejected (and has been cleared); throws `ApiException` for a
  /// transient failure (the session is kept).
  Future<bool> refresh();
}

/// A source with no session: for the credential endpoints (login / refresh / logout), which never
/// carry a bearer token and must not depend on the session they are creating or renewing.
final class NoSession implements AuthSessionSource {
  const NoSession();

  @override
  String? get accessToken => null;

  @override
  SessionScope? get scope => null;

  @override
  bool get canRefresh => false;

  @override
  Future<bool> refresh() async => false;
}
