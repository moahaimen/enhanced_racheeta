import 'package:flutter_riverpod/flutter_riverpod.dart';

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

/// `POST /reservations/provider/availability`.
Future<ProviderSlot> createSlot(
  WidgetRef ref, {
  required String serviceId,
  required DateTime startsAt,
}) => runAsAccount(
  ref,
  () => ref
      .read(providerApiProvider)
      .createSlot(serviceId: serviceId, startsAt: startsAt),
  () => invalidateProviderSlots(ref),
);

/// `DELETE /reservations/provider/availability/{id}`.
Future<void> deactivateSlot(WidgetRef ref, String slotId) => runAsAccount(
  ref,
  () => ref.read(providerApiProvider).deactivateSlot(slotId),
  () => invalidateProviderSlots(ref),
);

/// `POST /reservations/provider/{id}/transition`.
Future<ProviderReservation> transitionReservation(
  WidgetRef ref, {
  required String id,
  required ReservationStatus target,
}) => runAsAccount(
  ref,
  () => ref.read(providerApiProvider).transition(id, target),
  () => invalidateProviderReservations(ref),
);
