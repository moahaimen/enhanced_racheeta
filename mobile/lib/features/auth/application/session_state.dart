import 'package:flutter/foundation.dart';

import '../../../core/api/api_exception.dart';
import '../data/auth_models.dart';
import 'session_core.dart';

/// What the whole app knows about the signed-in user. The router and every screen derive from it.
@immutable
sealed class SessionState {
  const SessionState();
}

/// Start-up: a stored session is being re-validated against the backend.
final class SessionRestoring extends SessionState {
  const SessionRestoring();
}

/// Signed out. [endedBy] is set when the system (not the user) ended the session.
final class SessionAnonymous extends SessionState {
  const SessionAnonymous({this.endedBy});
  final SessionEndReason? endedBy;
}

/// A stored session exists but the backend could not be reached to validate it. The credentials
/// are KEPT (a network blip must not sign the user out); the user may retry or sign out.
final class SessionRestoreFailed extends SessionState {
  const SessionRestoreFailed(this.error);
  final ApiException error;
}

final class SessionAuthenticated extends SessionState {
  const SessionAuthenticated(this.account);
  final Account account;
}
