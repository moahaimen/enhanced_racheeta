import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';

import 'providers.dart';
import 'session_state.dart';

/// The id of the signed-in account, or null. Every account-specific provider `ref.watch`es this,
/// so when the account changes (logout, expiry, switching) its state is discarded and rebuilt:
/// one account's data can never be shown to the next. (`Provider` only notifies on a changed
/// value, so a `/me` refresh for the same account does not reset anything.)
final accountIdProvider = Provider<String?>((ref) {
  final session = ref.watch(sessionControllerProvider);
  return session is SessionAuthenticated ? session.account.id : null;
});

/// A record id scoped to the signed-in account. Families keyed by this never hand one account's
/// cached value to another: when the account changes the key changes, so the new account starts
/// from a loading state instead of seeing the previous account's data while it reloads (Riverpod
/// keeps the last value while a provider re-evaluates).
typedef AccountScoped<T> = ({String? account, T value});

/// Runs one non-idempotent mutation for the account that started it.
///
/// * the initiating account id is captured BEFORE the call and the call runs exactly once
///   (never retried);
/// * if a different account (or none) is signed in when it finishes, the result — success or
///   error — is dropped with a [StaleSessionException] and nothing is invalidated, so account A's
///   outcome can never surface under account B;
/// * [invalidate] runs only after the backend answered successfully for the same account.
Future<T> runAsAccount<T>(
  WidgetRef ref,
  Future<T> Function() call,
  void Function() invalidate,
) async {
  final startedAs = ref.read(accountIdProvider);
  if (startedAs == null) throw const StaleSessionException();
  final T result;
  try {
    result = await call();
  } on ApiException {
    if (!_stillSignedInAs(ref, startedAs)) throw const StaleSessionException();
    rethrow;
  }
  if (!_stillSignedInAs(ref, startedAs)) throw const StaleSessionException();
  invalidate();
  return result;
}

/// Whether [account] is still the signed-in account. A screen that was unmounted while the call
/// ran (an account switch can replace a gated route) can no longer prove that, so the result is
/// treated as stale rather than risking it reaching another account.
bool _stillSignedInAs(WidgetRef ref, String account) {
  try {
    return ref.read(accountIdProvider) == account;
  } on StateError {
    return false;
  }
}
