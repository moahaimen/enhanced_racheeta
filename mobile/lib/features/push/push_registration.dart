import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import '../../core/logging/safe_logger.dart';
import '../auth/application/account_scope.dart';
import '../auth/application/providers.dart';
import '../notifications/application/notifications_providers.dart';
import 'push_sequence.dart';
import 'push_source.dart';
import 'push_timing.dart';

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

  /// The backend accepted this device's token for the current account (and nothing since has
  /// made that uncertain).
  final bool registered;
}

typedef PushOwner = ({String account, String token});

/// The ONE place that mutates which account owns this installation's FCM token on the server.
///
/// **Correctness comes from the server's sequence ordering.** Every register and unregister
/// carries `ownership_seq`, allocated by [PushOwnershipSequence] (persisted, strictly increasing
/// across accounts, logouts, restarts and clock changes). Under the token row lock the server
/// applies an operation only if its sequence is greater than the one stored for the token, and an
/// older/equal/unsequenced one changes nothing. So the final owner depends on the sequences, not
/// on which HTTP request arrives or commits first — including a request the client gave up on
/// (timeout, transport error) that lands after a newer one: it is rejected as stale.
///
/// The lane below is therefore no longer what makes ownership correct; it keeps the client tidy:
///
/// 1. **One ownership request at a time, in order,** so each request's sequence is allocated when
///    it is about to be sent and sequences increase in send order; the next request waits for the
///    previous one's own outcome or timeout.
/// 2. **Never cancelled by the session** (`ApiClient.postDetached`): ending the session does not
///    abort a request client-side.
/// 3. **Intent, not a captured account:** a queued registration decides at its turn which account
///    is current (and registers it after a request for a previous account finished).
/// 4. **Logout is ordered:** the unregister is queued behind an in-flight registration and carries
///    the signing-out account's own bearer, captured up front.
/// 5. **Resilience, not correctness:** a request whose outcome was never seen leaves the belief
///    "unknown" (the next sync re-registers) and schedules ONE bounded repair after
///    [pushRepairDelayProvider] in case the *current* account's own registration was the lost one.
///    A stale straggler can no longer take the token back, repair or not.
class PushOwnershipLane {
  Future<void> _tail = Future<void>.value();
  Timer? _repair;
  void Function()? onRepair;

  /// The last registration the server confirmed (null: none known). Beliefs never outlive the
  /// process and are only used to skip a redundant, idempotent registration.
  PushOwner? owner;

  /// An ownership request ended without an observable outcome.
  bool unknown = false;
  int repairAttempts = 0;

  Future<T> run<T>(Future<T> Function() operation) {
    final done = Completer<T>();
    _tail = _tail.then((_) async {
      try {
        done.complete(await operation());
      } on Object catch (error, stack) {
        done.completeError(error, stack);
      }
    });
    return done.future;
  }

  bool believes(String account, String token) =>
      !unknown && owner?.account == account && owner?.token == token;

  void scheduleRepair(Duration delay) {
    if (repairAttempts >= 3) return;
    repairAttempts++;
    _repair?.cancel();
    _repair = Timer(delay, () => onRepair?.call());
  }

  void dispose() => _repair?.cancel();
}

final pushOwnershipLaneProvider = Provider<PushOwnershipLane>((ref) {
  final lane = PushOwnershipLane();
  ref.onDispose(lane.dispose);
  return lane;
});

/// Keeps this device's FCM token registered for exactly the signed-in account.
///
/// * **Account-keyed state:** the notifier watches the account id and is rebuilt on every change,
///   so each account starts from a clean [PushState] and a late step can never publish another
///   account's result.
/// * **Ownership goes through [PushOwnershipLane]** (see there): serialised, session-independent,
///   intent-based, with ordered logout cleanup and a bounded repair for unobservable outcomes.
/// * **Permission-aware, on EVERY path:** the OS permission is re-read inside each synchronisation,
///   so a token refresh, a startup race or a permission grant can never register while
///   notifications are denied or undetermined. Denial never affects persistent notifications.
/// * The token lives only in local variables and is never logged.
class PushRegistration extends Notifier<PushState> {
  static const Duration _tokenTimeout = Duration(seconds: 10);

  int _epoch = 0;
  late SafeLogger _logger;

  @override
  PushState build() {
    _logger = ref.read(loggerProvider);
    final account = ref.watch(accountIdProvider);
    final source = ref.watch(pushSourceProvider);
    ref.read(pushOwnershipLaneProvider).onRepair = () =>
        unawaited(_reconcile(force: true));
    final epoch = ++_epoch;
    if (account == null || !source.isAvailable) return const PushState();
    final subscription = source.tokenRefreshes.listen(
      (token) => unawaited(_reconcile(knownToken: token)),
      onError: (Object _) {},
    );
    ref.onDispose(subscription.cancel);
    unawaited(Future<void>.microtask(() => _start(account, epoch)));
    return const PushState();
  }

  bool _current(String account, int epoch) =>
      ref.mounted && epoch == _epoch && ref.read(accountIdProvider) == account;

  void _publish(
    String account, {
    PushPermission? permission,
    bool? registered,
  }) {
    if (!ref.mounted || ref.read(accountIdProvider) != account) return;
    state = PushState(
      permission: permission ?? state.permission,
      registered: registered ?? state.registered,
    );
  }

  Future<void> _start(String account, int epoch) async {
    try {
      final permission = await ref.read(pushSourceProvider).permission();
      if (!_current(account, epoch)) return;
      _publish(account, permission: permission);
      if (permission == PushPermission.granted) await _reconcile();
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
      _publish(account, permission: permission);
      if (permission == PushPermission.granted) await _reconcile();
    } on Object catch (error) {
      _logger.info('push permission request failed (${error.runtimeType})');
    }
  }

  Future<void> _reconcile({String? knownToken, bool force = false}) async {
    final lane = ref.read(pushOwnershipLaneProvider);
    try {
      await lane.run(() => _runReconcile(lane, knownToken, force));
    } on Object catch (error) {
      _logger.info('push sync skipped (${error.runtimeType})');
    }
  }

  /// Runs inside the lane, when its turn comes: makes the server's owner of this token the account
  /// that is signed in *now*.
  Future<void> _runReconcile(
    PushOwnershipLane lane,
    String? knownToken,
    bool force,
  ) async {
    var mustSend = force;
    for (var attempt = 0; attempt < 3; attempt++) {
      if (!ref.mounted) return;
      final account = ref.read(accountIdProvider);
      final source = ref.read(pushSourceProvider);
      if (account == null || !source.isAvailable) return;
      // Re-read the OS permission on every synchronisation (see the class comment).
      final permission = await source.permission();
      if (permission != PushPermission.granted) {
        _publish(account, permission: permission);
        return;
      }
      final token =
          knownToken ??
          await source.token().timeout(_tokenTimeout, onTimeout: () => null);
      if (token == null || token.isEmpty) return;

      // Everything above awaited: decide and capture the credentials in one synchronous step.
      if (!ref.mounted || ref.read(accountIdProvider) != account) continue;
      if (!mustSend && lane.believes(account, token)) {
        _publish(account, permission: permission, registered: true);
        return;
      }
      final bearer = ref.read(sessionCoreProvider).accessToken;
      if (bearer == null) return;

      try {
        // A fresh sequence for THIS request, persisted before it is sent; the server applies it
        // only if it is newer than whatever it already holds for the token.
        final seq = await ref.read(pushOwnershipSequenceProvider).next();
        await ref
            .read(notificationsApiProvider)
            .registerDevice(token, bearer: bearer, ownershipSeq: seq);
        lane
          ..owner = (account: account, token: token)
          ..unknown = false
          ..repairAttempts = 0;
        mustSend = false;
      } on ApiException catch (error) {
        if (_outcomeUnobserved(error)) {
          // The server may or may not have applied it (and may still): remember that, and repair.
          lane.unknown = true;
          if (ref.mounted) {
            lane.scheduleRepair(ref.read(pushRepairDelayProvider));
          }
          _logger.info(
            'push registration outcome unknown (${error.kind.name})',
          );
        } else {
          // A definitive refusal (including `stale_ownership`: a newer operation already governs
          // the token): nothing changed on the server.
          _logger.info('push registration refused (${error.kind.name})');
        }
      }

      if (ref.mounted && ref.read(accountIdProvider) == account) {
        _publish(
          account,
          permission: permission,
          registered: lane.believes(account, token),
        );
        return;
      }
      // The account changed while the request was in flight: it has finished now (the lane waited
      // for it), so make the new current account the owner.
      knownToken = null;
    }
  }

  static bool _outcomeUnobserved(ApiException error) =>
      error.kind == ApiErrorKind.network ||
      error.kind == ApiErrorKind.timeout ||
      error.kind == ApiErrorKind.server ||
      error.kind == ApiErrorKind.cancelled;

  /// Called by the session layer BEFORE credentials are cleared on logout. Queued behind any
  /// in-flight registration so it can never be overtaken by it, and it carries the signing-out
  /// account's own bearer (captured now) so it still completes if the caller's time bound expires
  /// and the credentials are cleared first. Best effort: a failure leaves the registration to be
  /// transferred when the next account registers this token.
  Future<void> unregisterForLogout() {
    final account = ref.read(accountIdProvider);
    final source = ref.read(pushSourceProvider);
    final bearer = ref.read(sessionCoreProvider).accessToken;
    if (account == null || bearer == null || !source.isAvailable) {
      return Future<void>.value();
    }
    final lane = ref.read(pushOwnershipLaneProvider);
    final api = ref.read(notificationsApiProvider);
    final sequence = ref.read(pushOwnershipSequenceProvider);
    final logger = _logger;
    return lane.run(() async {
      try {
        final token = await source.token().timeout(
          _tokenTimeout,
          onTimeout: () => null,
        );
        if (token == null || token.isEmpty) return;
        // Allocated when its turn comes, so it is greater than any registration sent before it.
        await api.unregisterDevice(
          token,
          bearer: bearer,
          ownershipSeq: await sequence.next(),
        );
        if (lane.owner?.account == account) lane.owner = null;
      } on Object catch (error) {
        lane.unknown = true;
        logger.info('push unregister skipped (${error.runtimeType})');
      }
    });
  }
}

final pushRegistrationProvider = NotifierProvider<PushRegistration, PushState>(
  PushRegistration.new,
  retry: (_, _) => null,
);
