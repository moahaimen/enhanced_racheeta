import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../auth/application/account_scope.dart';
import '../../reservations/data/reservation_models.dart';
import '../data/provider_models.dart';
import 'provider_providers.dart';

/// Backend-derived provider state is reloaded after a successful change. Availability changes do
/// not affect any dashboard figure; reservation changes affect the list, the detail and the
/// dashboard.
void invalidateProviderSlots(WidgetRef ref) =>
    ref.invalidate(providerSlotsProvider);

void invalidateProviderReservations(WidgetRef ref) {
  ref
    ..invalidate(providerReservationListProvider)
    ..invalidate(providerReservationDetailProvider)
    ..invalidate(providerDashboardProvider);
}

/// Runs a mutation for the account that started it.
///
/// * the initiating account id is captured BEFORE the call;
/// * if a different account (or none) is signed in when the call finishes, the result is dropped
///   with a [StaleSessionException] and nothing is invalidated, so account A's success or error
///   can never surface under account B;
/// * data is invalidated only after the backend answered successfully;
/// * there is no retry: one call per deliberate tap.
Future<T> _asAccount<T>(
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
    if (ref.read(accountIdProvider) != startedAs) {
      throw const StaleSessionException();
    }
    rethrow;
  }
  if (ref.read(accountIdProvider) != startedAs) {
    throw const StaleSessionException();
  }
  invalidate();
  return result;
}

/// `POST /reservations/provider/availability`.
Future<ProviderSlot> createSlot(
  WidgetRef ref, {
  required String serviceId,
  required DateTime startsAt,
}) => _asAccount(
  ref,
  () => ref
      .read(providerApiProvider)
      .createSlot(serviceId: serviceId, startsAt: startsAt),
  () => invalidateProviderSlots(ref),
);

/// `DELETE /reservations/provider/availability/{id}`.
Future<void> deactivateSlot(WidgetRef ref, String slotId) => _asAccount(
  ref,
  () => ref.read(providerApiProvider).deactivateSlot(slotId),
  () => invalidateProviderSlots(ref),
);

/// `POST /reservations/provider/{id}/transition`.
Future<ProviderReservation> transitionReservation(
  WidgetRef ref, {
  required String id,
  required ReservationStatus target,
}) => _asAccount(
  ref,
  () => ref.read(providerApiProvider).transition(id, target),
  () => invalidateProviderReservations(ref),
);
