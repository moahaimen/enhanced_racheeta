import 'package:flutter_riverpod/flutter_riverpod.dart';

/// How long after an ownership request whose outcome the client could not observe (timeout,
/// transport error) the current account's token registration is repeated once more.
///
/// This is resilience, not correctness: the server orders ownership operations by their client
/// sequence, so a request that lands late can never take the token back from a newer one. The
/// repair only covers the case where the lost request was the *current* account's own
/// registration (so the server may not have it yet).
final pushRepairDelayProvider = Provider<Duration>(
  (ref) => const Duration(minutes: 2),
);
