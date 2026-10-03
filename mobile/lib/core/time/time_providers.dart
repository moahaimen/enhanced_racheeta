import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'instants.dart';

/// Injectable clock (UTC) so "upcoming vs past" and availability windows are testable.
final nowProvider = Provider<DateTime Function()>(
  (ref) =>
      () => DateTime.now().toUtc(),
);

/// Injectable UTC → wall-clock conversion (the device's local time in production).
final wallClockProvider = Provider<WallClock>((ref) => deviceWallClock);
