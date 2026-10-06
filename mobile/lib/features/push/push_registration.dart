import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import '../../core/logging/safe_logger.dart';
import '../auth/application/account_scope.dart';
import '../auth/application/providers.dart';
import '../notifications/application/notifications_providers.dart';
import 'push_source.dart';

final pushSourceProvider = Provider<PushSource>(
  (ref) => const DisabledPushSource(),
);

/// What the UI needs to know about push for the signed-in account.
class PushState {
  const PushState({
    this.permission = PushPermission.notDetermined,
    this.registered = false,
  });
  final PushPermission permission;

  /// This device's token was accepted by the backend for the current account.
  final bool registered;
}

/// Keeps this device's FCM token registered for exactly the signed-in account.
///
/// * **Account-keyed:** the notifier watches the account id and is rebuilt on every change, so each
///   account starts from a clean state and every asynchronous step carries `(account, epoch)`; a
///   step that finishes for a previous account or after logout is discarded without touching the
///   backend or the state.
/// * **Idempotent:** `POST /notifications/push-devices/` is an upsert (a token owned by another
///   account is transferred to the caller), so synchronising again after a rotation, a permission
///   grant or an app start is safe and nothing is retried in a loop.
/// * **Permission-aware:** a token is registered only once the OS allows notifications; denying
///   them never affects the persistent notification centre or chat.
/// * The token is held only in local variables and never logged.
class PushRegistration extends Notifier<PushState> {
  int _epoch = 0;
  late SafeLogger _logger;

  @override
  PushState build() {
    _logger = ref.read(loggerProvider);
    final account = ref.watch(accountIdProvider);
    final source = ref.watch(pushSourceProvider);
    final epoch = ++_epoch;
    if (account == null || !source.isAvailable) return const PushState();
    final subscription = source.tokenRefreshes.listen(
      (token) => unawaited(_sync(account, epoch, token)),
      onError: (Object _) {},
    );
    ref.onDispose(subscription.cancel);
    unawaited(Future<void>.microtask(() => _start(account, epoch)));
    return const PushState();
  }

  bool _current(String account, int epoch) =>
      ref.mounted && epoch == _epoch && ref.read(accountIdProvider) == account;

  Future<void> _start(String account, int epoch) async {
    try {
      final permission = await ref.read(pushSourceProvider).permission();
      if (!_current(account, epoch)) return;
      state = PushState(permission: permission);
      if (permission == PushPermission.granted) await _sync(account, epoch);
    } on Object catch (error) {
      _logger.info('push start skipped (${error.runtimeType})');
    }
  }

  /// Asks the OS for permission (once, from an explicit user action) and registers on success.
  Future<void> requestPermission() async {
    final account = ref.read(accountIdProvider);
    final source = ref.read(pushSourceProvider);
    if (account == null || !source.isAvailable) return;
    final epoch = _epoch;
    try {
      final permission = await source.requestPermission();
      if (!_current(account, epoch)) return;
      state = PushState(permission: permission, registered: state.registered);
      if (permission == PushPermission.granted) await _sync(account, epoch);
    } on Object catch (error) {
      _logger.info('push permission request failed (${error.runtimeType})');
    }
  }

  Future<void> _sync(String account, int epoch, [String? known]) async {
    try {
      final source = ref.read(pushSourceProvider);
      final token = known ?? await source.token();
      // The account may have changed or logged out while the token was being issued.
      if (token == null || token.isEmpty || !_current(account, epoch)) return;
      await ref.read(notificationsApiProvider).registerDevice(token);
      if (!_current(account, epoch)) return;
      state = PushState(permission: state.permission, registered: true);
    } on ApiException catch (error) {
      _logger.info('push registration failed (${error.kind.name})');
    } on Object catch (error) {
      _logger.info('push registration skipped (${error.runtimeType})');
    }
  }

  /// Called by the session layer BEFORE credentials are cleared on logout: deactivates this
  /// device's registration for the signed-in account (the endpoint needs that account's
  /// authorization). Best effort and time-bounded by the caller; a failure only leaves the
  /// registration to be transferred when the next account registers this token.
  Future<void> unregisterForLogout() async {
    final account = ref.read(accountIdProvider);
    final source = ref.read(pushSourceProvider);
    if (account == null || !source.isAvailable) return;
    try {
      final token = await source.token();
      if (token == null || token.isEmpty || !_current(account, _epoch)) return;
      await ref.read(notificationsApiProvider).unregisterDevice(token);
    } on Object catch (error) {
      _logger.info('push unregister skipped (${error.runtimeType})');
    }
  }
}

final pushRegistrationProvider = NotifierProvider<PushRegistration, PushState>(
  PushRegistration.new,
  retry: (_, _) => null,
);
