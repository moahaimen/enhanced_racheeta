import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import '../../core/logging/safe_logger.dart';
import '../auth/application/account_scope.dart';
import '../auth/application/providers.dart';
import '../notifications/application/notifications_providers.dart';
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
/// **The race this exists for.** `POST /notifications/push-devices/` transfers the (globally
/// unique) token to whichever account calls it, and the server has no notion of client ordering.
/// Dropping a stale *response* on the client does not undo a *write*: if account A's request is
/// still in flight when B signs in, B's request could commit first and A's later, handing the token
/// back to A. The protocol below makes that impossible whenever a request's outcome is observed:
///
/// 1. **One ownership request at a time.** Every register / unregister runs through [run], a FIFO
///    lane, and the next one starts only after the previous returned (a response or its own
///    timeout). B's registration therefore cannot reach the server before A's has finished.
/// 2. **Never cancelled by the session.** These requests use `ApiClient.postDetached`: ending the
///    session does not abort them client-side, so the lane really waits for the server's answer
///    instead of starting the next request while an abandoned one may still commit.
/// 3. **Intent, not a captured account.** A queued registration decides *when its turn comes*
///    which account is current; if the account changed while a request was in flight it simply
///    registers for the new current account afterwards ("repair").
/// 4. **Logout is ordered.** The unregister is queued behind any in-flight registration, with the
///    signing-out account's own bearer captured up front, so it still completes after credentials
///    are cleared (and after the logout hook's time bound expired).
/// 5. **Unobservable outcomes.** A timeout or transport error after the request was sent leaves the
///    server state unknown (the request may still be processed later). The belief is then marked
///    unknown (the next sync always re-registers) and one more registration is scheduled after
///    [pushRepairDelayProvider], longer than any request can linger. This bounded, idempotent
///    re-registration is what converges the owner in that residual case; a strict proof there would
///    need server-side ordering (see docs/DECISIONS.md ADR-057).
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
        await ref
            .read(notificationsApiProvider)
            .registerDevice(token, bearer: bearer);
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
          // A definitive refusal: nothing changed on the server.
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
    final logger = _logger;
    return lane.run(() async {
      try {
        final token = await source.token().timeout(
          _tokenTimeout,
          onTimeout: () => null,
        );
        if (token == null || token.isEmpty) return;
        await api.unregisterDevice(token, bearer: bearer);
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
