import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/logging/safe_logger.dart';
import '../data/auth_api.dart';
import 'providers.dart';
import 'session_core.dart';
import 'session_state.dart';

/// Orchestrates restore / login / logout on top of [SessionCore].
///
/// Stale-response rule: every operation takes a ticket (`_ticket`); when a later operation
/// (logout, another login, restore) supersedes it, the earlier one throws [StaleSessionException]
/// and its result is dropped. Combined with the session scope (which aborts the HTTP requests of
/// a dead session) a previous account's data can never populate the UI after logout/switching.
class SessionController extends Notifier<SessionState> {
  late SessionCore _core;
  late AuthApi _authApi;
  late SafeLogger _logger;

  int _ticket = 0;

  /// Completes when the start-up restoration finished (used by tests).
  Future<void> get restored => _restored;
  Future<void> _restored = Future<void>.value();

  @override
  SessionState build() {
    _core = ref.read(sessionCoreProvider);
    _authApi = ref.read(authApiProvider);
    _logger = ref.read(loggerProvider);
    final subscription = _core.ended.listen((reason) {
      if (!ref.mounted) return;
      _ticket++;
      state = SessionAnonymous(endedBy: reason);
    });
    ref.onDispose(subscription.cancel);
    // The app restores on start-up; tests turn this off to drive `restore()` themselves.
    if (ref.read(autoRestoreSessionProvider)) {
      _restored = Future<void>.microtask(restore);
    }
    return const SessionRestoring();
  }

  /// Validates a stored session (or concludes there is none). Safe to call again to retry.
  Future<void> restore() async {
    final ticket = ++_ticket;
    state = const SessionRestoring();
    try {
      if (!await _core.loadStoredSession()) {
        _setIfCurrent(ticket, const SessionAnonymous());
        return;
      }
      if (!await _core.refresh()) {
        // Definitively rejected; SessionCore already cleared it and emitted `ended`.
        _setIfCurrent(
          ticket,
          const SessionAnonymous(endedBy: SessionEndReason.expired),
        );
        return;
      }
      final account = await _authApi.me();
      _setIfCurrent(ticket, SessionAuthenticated(account));
    } on StaleSessionException {
      // Superseded by a logout/login; that operation owns the state now.
    } on ApiException catch (error) {
      if (error.kind == ApiErrorKind.unauthorized) {
        await _core.endSession();
        _setIfCurrent(
          ticket,
          const SessionAnonymous(endedBy: SessionEndReason.expired),
        );
      } else {
        _setIfCurrent(ticket, SessionRestoreFailed(error));
      }
    } on FormatException {
      _setIfCurrent(ticket, SessionRestoreFailed(ApiException.network));
    }
  }

  /// Email + password sign-in. Throws [ApiException] (wrong credentials, validation, network…)
  /// for the UI to present; the session is left signed out in that case.
  Future<void> login({required String email, required String password}) async {
    final ticket = ++_ticket;
    final tokens = await _authApi.login(
      email: email.trim(),
      password: password,
    );
    if (ticket != _ticket) throw const StaleSessionException();
    await _core.startSession(tokens);
    try {
      final account = await _authApi.me();
      if (ticket != _ticket) throw const StaleSessionException();
      state = SessionAuthenticated(account);
    } on Object {
      if (ticket == _ticket) {
        final orphan = await _core.endSession();
        state = const SessionAnonymous();
        if (orphan != null) unawaited(_revoke(orphan));
      }
      rethrow;
    }
  }

  /// Signs out. Local state is cleared FIRST (and in-flight requests aborted); revoking the
  /// refresh token on the server is best effort and can never keep the user signed in.
  Future<void> logout() async {
    // While the credentials still exist: e.g. unregister this device's push token. Bounded, and a
    // failure never blocks signing out.
    try {
      await ref
          .read(beforeLogoutProvider)()
          .timeout(ref.read(logoutHookTimeoutProvider));
    } on Object {
      // best effort
    }
    _ticket++;
    final refresh = await _core.endSession();
    if (ref.mounted) state = const SessionAnonymous();
    if (refresh != null) await _revoke(refresh);
  }

  /// Re-reads `/me`; the result is applied only if the same session is still current.
  Future<void> refreshAccount() async {
    final ticket = _ticket;
    final generation = _core.generation;
    final account = await _authApi.me();
    if (ticket != _ticket || generation != _core.generation) {
      throw const StaleSessionException();
    }
    state = SessionAuthenticated(account);
  }

  Future<void> _revoke(String refreshToken) async {
    try {
      await _authApi.logout(refreshToken);
    } on Object catch (error) {
      _logger.info('refresh token revocation skipped (${error.runtimeType})');
    }
  }

  void _setIfCurrent(int ticket, SessionState next) {
    if (ticket == _ticket && ref.mounted) state = next;
  }
}
