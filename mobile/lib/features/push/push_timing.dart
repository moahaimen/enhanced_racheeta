import 'package:flutter_riverpod/flutter_riverpod.dart';

/// How long after an ownership request whose outcome the client could not observe (timeout,
/// transport error) the current account's token registration is repeated once more.
///
/// Why: a request that timed out on the client may still be processed by the server later, and the
/// device-token endpoint has no ordering information, so a straggler could re-assign the token to
/// an account that is no longer signed in. Repeating the (idempotent) registration after the
/// longest time a request can linger converges the owner back to the current account. It must be
/// longer than the client timeouts plus the server/proxy request limit.
final pushRepairDelayProvider = Provider<Duration>(
  (ref) => const Duration(minutes: 2),
);
