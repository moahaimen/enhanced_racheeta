import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../discovery/application/discovery_providers.dart';
import '../data/reservation_models.dart';
import 'reservation_providers.dart';

/// Longest note the backend accepts (`ReservationCreateRequest.patient_note`, maxLength 1000).
const int maxPatientNoteLength = 1000;

/// After a booking or a cancellation everything derived from it is reloaded from the backend:
/// the list, every opened detail, and every availability snapshot (the slot is taken, or free
/// again).
void invalidateReservationData(WidgetRef ref) {
  ref
    ..invalidate(reservationListProvider)
    ..invalidate(reservationDetailProvider)
    ..invalidate(availabilityProvider);
}

/// `POST /reservations`. One call, no retry (no idempotency key exists). Throws the API's
/// `ApiException` untouched so the UI can map conflicts and validation errors.
Future<Reservation> bookSlot(
  WidgetRef ref, {
  required String slotId,
  required String note,
}) async {
  final reservation = await ref
      .read(reservationsApiProvider)
      .create(slotId: slotId, note: note);
  invalidateReservationData(ref);
  return reservation;
}

/// `POST /reservations/me/{id}/cancel`. The backend decides eligibility.
Future<Reservation> cancelReservation(WidgetRef ref, String id) async {
  final reservation = await ref.read(reservationsApiProvider).cancel(id);
  invalidateReservationData(ref);
  return reservation;
}
