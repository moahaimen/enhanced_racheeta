import '../auth/application/session_state.dart';
import 'push_routes.dart';
import 'push_source.dart';

/// Turns "the user tapped a push" into at most one navigation, at the right moment.
///
/// * **Waits for the session.** While the stored session is being restored the tap is held; it is
///   delivered when an account is signed in and dropped when the session ends up signed out, so a
///   signed-out user is never taken into a private screen and a tap is never replayed after a
///   later sign-in.
/// * **Never across accounts.** A tap is held only while the session is still being restored (the
///   same device user); it is never kept across a sign-out, so it cannot reach another account.
/// * **Validated.** Only routes from [routeForPush] are used (known `type`, UUID id); anything
///   else is ignored.
/// * **Once.** The same push can reach the app through several callbacks (initial message, opened
///   from background). A Firebase message id is remembered for the session; a push without one is
///   suppressed only for a short window, so a later, genuinely new push for the same resource is
///   never swallowed.
///
/// Pure Dart (no Firebase, no Flutter) so it is unit-tested directly.
class PushIntentCoordinator {
  PushIntentCoordinator({
    required this.session,
    required this.navigate,
    required this.now,
  });

  static const Duration _anonymousWindow = Duration(seconds: 5);
  static const int _maxRemembered = 32;

  final SessionState Function() session;
  final void Function(String route) navigate;
  final DateTime Function() now;

  final Map<String, DateTime?> _seen = <String, DateTime?>{};
  String? _pendingRoute;

  /// A push was tapped (or launched the app).
  void onOpened(PushMessageData message) {
    final route = routeForPush(message.data);
    if (route == null || _isDuplicate(message, route)) return;
    switch (session()) {
      case SessionAuthenticated():
        _pendingRoute = null;
        navigate(route);
      case SessionRestoring() || SessionRestoreFailed():
        _pendingRoute = route;
      case SessionAnonymous():
        _pendingRoute = null;
    }
  }

  /// The session state changed: deliver or drop a held tap.
  void onSessionChanged() {
    final route = _pendingRoute;
    if (route == null) return;
    switch (session()) {
      case SessionAuthenticated():
        _pendingRoute = null;
        navigate(route);
      case SessionAnonymous():
        _pendingRoute = null;
      case SessionRestoring() || SessionRestoreFailed():
        break;
    }
  }

  bool _isDuplicate(PushMessageData message, String route) {
    final now = this.now();
    final id = message.messageId;
    final key = id != null && id.isNotEmpty ? 'id:$id' : 'route:$route';
    final windowed = !(id != null && id.isNotEmpty);
    final seenAt = _seen[key];
    if (_seen.containsKey(key)) {
      if (!windowed) return true;
      if (seenAt != null && now.difference(seenAt) < _anonymousWindow) {
        return true;
      }
    }
    _seen[key] = windowed ? now : null;
    while (_seen.length > _maxRemembered) {
      _seen.remove(_seen.keys.first);
    }
    return false;
  }
}
