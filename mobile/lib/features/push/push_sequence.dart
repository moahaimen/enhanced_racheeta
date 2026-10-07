import 'dart:async';
import 'dart:math' as math;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/storage/preferences_store.dart';
import '../../core/time/time_providers.dart';
import '../auth/application/providers.dart';

/// Allocates the monotonically increasing ownership sequence that orders every push-token
/// register and unregister on the server (`ownership_seq`).
///
/// `value = max(lastPersisted + 1, wall-clock microseconds)`, persisted BEFORE it is returned, so:
///
/// * it is strictly greater than every value ever handed out on this installation — across
///   account switches, logout/login, app restarts, and a wall clock that moves backwards (the
///   clock is only an input; `lastPersisted + 1` is the floor);
/// * a crash after persisting but before sending only skips a number (gaps are harmless; the
///   server compares, it never requires contiguity);
/// * overlapping calls are serialised, so two operations can never receive the same value.
///
/// The value is an opaque ordering number (not sensitive) and is not logged.
class PushOwnershipSequence {
  PushOwnershipSequence({required this.store, required this.clock});

  final PreferencesStore store;
  final DateTime Function() clock;
  Future<void> _chain = Future<void>.value();

  Future<int> next() {
    final result = Completer<int>();
    _chain = _chain.then((_) async {
      try {
        final last = store.readPushOwnershipSeq() ?? 0;
        final value = math.max(last + 1, clock().microsecondsSinceEpoch);
        await store.writePushOwnershipSeq(value); // persisted before it is used
        result.complete(value);
      } on Object catch (error, stack) {
        result.completeError(error, stack);
      }
    });
    return result.future;
  }
}

final pushOwnershipSequenceProvider = Provider<PushOwnershipSequence>(
  (ref) => PushOwnershipSequence(
    store: ref.watch(preferencesStoreProvider),
    clock: ref.watch(nowProvider),
  ),
);
