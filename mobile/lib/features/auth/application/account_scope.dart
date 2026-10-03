import 'package:flutter_riverpod/flutter_riverpod.dart';

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
