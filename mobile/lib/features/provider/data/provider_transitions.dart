import '../../reservations/data/reservation_models.dart';

/// Which provider transitions to OFFER for a reservation. This mirrors the backend state machine
/// (`PROVIDER_TRANSITIONS` and the time rules in `transition_as_provider`) only as a convenience
/// for choosing buttons; the backend decides whether a transition is valid and a refusal
/// (`invalid_transition`) is shown and followed by a refetch.
///
/// * PENDING   → CONFIRMED (only before the appointment starts), REJECTED, CANCELLED
/// * CONFIRMED → COMPLETED and NO_SHOW (only after it started), CANCELLED
/// * every other status: none
List<ReservationStatus> offeredTransitions(
  Reservation reservation,
  DateTime nowUtc,
) {
  final started = !reservation.startsAt.isAfter(nowUtc);
  switch (reservation.status) {
    case ReservationStatus.pending:
      return [
        if (!started) ReservationStatus.confirmed,
        ReservationStatus.rejected,
        ReservationStatus.cancelled,
      ];
    case ReservationStatus.confirmed:
      return [
        if (started) ...[ReservationStatus.completed, ReservationStatus.noShow],
        ReservationStatus.cancelled,
      ];
    case ReservationStatus.completed ||
        ReservationStatus.rejected ||
        ReservationStatus.cancelled ||
        ReservationStatus.noShow ||
        ReservationStatus.unknown:
      return const [];
  }
}
