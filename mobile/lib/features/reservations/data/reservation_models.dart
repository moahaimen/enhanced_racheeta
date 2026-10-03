import 'package:flutter/foundation.dart';

import '../../../core/api/json_reader.dart';

/// `ReservationStatusEnum`. Unknown future codes are kept (as [ReservationStatus.unknown] with the
/// raw code on the reservation) instead of failing the whole list.
enum ReservationStatus {
  pending('PENDING'),
  confirmed('CONFIRMED'),
  completed('COMPLETED'),
  rejected('REJECTED'),
  cancelled('CANCELLED'),
  noShow('NO_SHOW'),
  unknown('');

  const ReservationStatus(this.wire);
  final String wire;

  static ReservationStatus parse(String code) {
    for (final status in values) {
      if (status.wire == code && status != unknown) return status;
    }
    return unknown;
  }

  /// The statuses from which the backend allows a patient to cancel (docs/RESERVATIONS.md). Used
  /// ONLY to decide whether to *offer* the action; the backend decides whether it succeeds.
  bool get isLive => this == pending || this == confirmed;
}

/// `ReservationTransition`: an entry of the reservation's status history.
@immutable
class ReservationTransition {
  const ReservationTransition({
    required this.from,
    required this.to,
    required this.createdAt,
  });

  factory ReservationTransition.fromJson(Object? json) {
    final r = JsonReader.of(json, 'ReservationTransition');
    return ReservationTransition(
      from: ReservationStatus.parse(r.stringOr('from_status')),
      to: ReservationStatus.parse(r.stringOr('to_status')),
      createdAt: r.instant('created_at'),
    );
  }

  final ReservationStatus from;
  final ReservationStatus to;
  final DateTime createdAt;
}

/// `ReservationPatient`: the patient's view of a reservation. Provider/service/price/time are
/// immutable snapshots taken at booking time. Instants are UTC.
@immutable
class Reservation {
  const Reservation({
    required this.id,
    required this.providerId,
    required this.providerName,
    required this.serviceTitle,
    required this.price,
    required this.currency,
    required this.durationMinutes,
    required this.startsAt,
    required this.endsAt,
    required this.status,
    required this.statusCode,
    required this.statusChangedAt,
    required this.patientNote,
    required this.transitions,
  });

  factory Reservation.fromJson(Object? json) {
    final r = JsonReader.of(json, 'Reservation');
    final code = r.string('status');
    return Reservation(
      id: r.string('id'),
      providerId: r.string('provider_id'),
      providerName: r.string('provider_name_snapshot'),
      serviceTitle: r.string('service_title_snapshot'),
      price: r.stringOr('price_snapshot'),
      currency: r.stringOr('currency_snapshot'),
      durationMinutes: r.integerOrNull('duration_minutes_snapshot'),
      startsAt: r.instant('starts_at'),
      endsAt: r.instant('ends_at'),
      status: ReservationStatus.parse(code),
      statusCode: code,
      statusChangedAt: r.instantOrNull('status_changed_at'),
      patientNote: r.stringOr('patient_note'),
      transitions: r.listOrEmpty('transitions', ReservationTransition.fromJson),
    );
  }

  final String id;
  final String providerId;
  final String providerName;
  final String serviceTitle;
  final String price;
  final String currency;
  final int? durationMinutes;
  final DateTime startsAt;
  final DateTime endsAt;
  final ReservationStatus status;
  final String statusCode;
  final DateTime? statusChangedAt;
  final String patientNote;
  final List<ReservationTransition> transitions;

  /// Whether the appointment is still ahead and the reservation live. A display grouping and a hint
  /// for offering "Cancel"; never an authorization decision.
  bool isUpcoming(DateTime nowUtc) => status.isLive && startsAt.isAfter(nowUtc);

  /// `toString` carries no personal data (the note and names are omitted).
  @override
  String toString() => 'Reservation(${status.wire})';
}
