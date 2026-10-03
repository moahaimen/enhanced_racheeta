import 'package:flutter/foundation.dart';

import '../../../core/api/json_reader.dart';
import '../../reservations/data/reservation_models.dart';

/// `ReservationProvider`: the provider's view of a reservation (the shared reservation fields plus
/// the `patient` summary the API exposes to the provider). Instants are UTC.
@immutable
class ProviderReservation {
  const ProviderReservation({
    required this.reservation,
    required this.patientId,
    required this.patientName,
  });

  factory ProviderReservation.fromJson(Object? json) {
    final r = JsonReader.of(json, 'ReservationProvider');
    final patient = r.object('patient');
    return ProviderReservation(
      reservation: Reservation.fromJson(json),
      patientId: patient.string('id'),
      patientName: patient.stringOr('full_name'),
    );
  }

  final Reservation reservation;
  final String patientId;
  final String patientName;

  String get id => reservation.id;

  /// No personal data in the string form (logs).
  @override
  String toString() => 'ProviderReservation(${reservation.status.wire})';
}

/// `AvailabilitySlot` as the provider sees it in `GET /reservations/provider/availability`
/// (includes inactive and past slots; the API has no filter for them).
@immutable
class ProviderSlot {
  const ProviderSlot({
    required this.id,
    required this.startsAt,
    required this.endsAt,
    required this.isActive,
    required this.serviceId,
    required this.serviceTitle,
    required this.durationMinutes,
  });

  factory ProviderSlot.fromJson(Object? json) {
    final r = JsonReader.of(json, 'AvailabilitySlot');
    final service = r.object('service');
    return ProviderSlot(
      id: r.string('id'),
      startsAt: r.instant('starts_at'),
      endsAt: r.instant('ends_at'),
      isActive: r.booleanOr('is_active', fallback: true),
      serviceId: service.string('id'),
      serviceTitle: service.stringOr('title'),
      durationMinutes: service.integerOrNull('duration_minutes'),
    );
  }

  final String id;
  final DateTime startsAt;
  final DateTime endsAt;
  final bool isActive;
  final String serviceId;
  final String serviceTitle;
  final int? durationMinutes;

  /// A presentation filter only: active and not yet ended. The backend remains the authority on
  /// what patients can book.
  bool isCurrent(DateTime nowUtc) => isActive && endsAt.isAfter(nowUtc);
}

/// `ServiceOffering` (owner view) from `GET /providers/me/services`: what a slot can be created
/// for. The backend only accepts an active service that has a duration.
@immutable
class OwnService {
  const OwnService({
    required this.id,
    required this.title,
    required this.durationMinutes,
    required this.isActive,
  });

  factory OwnService.fromJson(Object? json) {
    final r = JsonReader.of(json, 'ServiceOffering');
    return OwnService(
      id: r.string('id'),
      title: r.string('title'),
      durationMinutes: r.integerOrNull('duration_minutes'),
      isActive: r.booleanOr('is_active', fallback: true),
    );
  }

  final String id;
  final String title;
  final int? durationMinutes;
  final bool isActive;

  /// A convenience for the picker (the backend refuses anything else).
  bool get canHaveSlots =>
      isActive && durationMinutes != null && durationMinutes! > 0;
}

/// `DashboardsEnum` values the provider workspace cares about.
enum ProviderDashboardKind {
  doctor('doctor'),
  facility('facility');

  const ProviderDashboardKind(this.wire);
  final String wire;
}

/// `DashboardIndex`: the dashboards the server says this account may open right now.
@immutable
class DashboardIndex {
  const DashboardIndex(this.dashboards);

  factory DashboardIndex.fromJson(Object? json) {
    final r = JsonReader.of(json, 'DashboardIndex');
    return DashboardIndex(r.list<String>('dashboards', (v) => v! as String));
  }

  final List<String> dashboards;

  /// The provider dashboard to open, decided by the server's list (never by a role label):
  /// facility wins over doctor, null when the account has neither (e.g. no provider profile yet).
  ProviderDashboardKind? get providerKind {
    if (dashboards.contains(ProviderDashboardKind.facility.wire)) {
      return ProviderDashboardKind.facility;
    }
    if (dashboards.contains(ProviderDashboardKind.doctor.wire)) {
      return ProviderDashboardKind.doctor;
    }
    return null;
  }
}

@immutable
class DashboardProfile {
  const DashboardProfile({
    required this.displayName,
    required this.providerType,
    required this.verificationStatus,
    required this.isVisible,
  });

  factory DashboardProfile.fromJson(Object? json) {
    final r = JsonReader.of(json, 'DashboardProviderProfile');
    return DashboardProfile(
      displayName: r.string('display_name'),
      providerType: r.stringOr('provider_type'),
      verificationStatus: r.stringOr('verification_status'),
      isVisible: r.boolean('is_visible'),
    );
  }

  final String displayName;
  final String providerType;
  final String verificationStatus;
  final bool isVisible;
}

@immutable
class DashboardAppointment {
  const DashboardAppointment({
    required this.id,
    required this.serviceTitle,
    required this.patientName,
    required this.startsAt,
    required this.status,
  });

  factory DashboardAppointment.fromJson(Object? json) {
    final r = JsonReader.of(json, 'DashboardProviderAppointment');
    return DashboardAppointment(
      id: r.string('id'),
      serviceTitle: r.string('service_title_snapshot'),
      patientName: r.stringOr('patient_name'),
      startsAt: r.instant('starts_at'),
      status: ReservationStatus.parse(r.string('status')),
    );
  }

  final String id;
  final String serviceTitle;
  final String patientName;
  final DateTime startsAt;
  final ReservationStatus status;
}

@immutable
class ReviewSummary {
  const ReviewSummary({
    required this.average,
    required this.count,
    required this.distribution,
  });

  factory ReviewSummary.fromJson(Object? json) {
    final r = JsonReader.of(json, 'DashboardReviewSummary');
    final distribution = r.object('distribution');
    return ReviewSummary(
      average: r.doubleOrNull('average_rating'),
      count: r.integer('review_count'),
      distribution: {
        for (var stars = 1; stars <= 5; stars++)
          stars: distribution.integerOrNull('$stars') ?? 0,
      },
    );
  }

  /// Null when the provider has no reviews: shown as "no reviews yet", never as a made-up value.
  final double? average;
  final int count;
  final Map<int, int> distribution;
}

@immutable
class OfferSummary {
  const OfferSummary({
    required this.total,
    required this.runningNow,
    required this.scheduled,
  });

  factory OfferSummary.fromJson(Object? json) {
    final r = JsonReader.of(json, 'DashboardOfferSummary');
    return OfferSummary(
      total: r.integer('total'),
      runningNow: r.integer('running_now'),
      scheduled: r.integer('scheduled'),
    );
  }

  final int total;
  final int runningNow;
  final int scheduled;
}

@immutable
class UnreadSummary {
  const UnreadSummary({required this.notifications, required this.messages});

  factory UnreadSummary.fromJson(Object? json) {
    final r = JsonReader.of(json, 'DashboardUnread');
    return UnreadSummary(
      notifications: r.integer('notifications'),
      messages: r.integer('messages'),
    );
  }

  final int notifications;
  final int messages;
}

@immutable
class MembershipSummary {
  const MembershipSummary({
    required this.active,
    required this.incomingRequests,
    required this.outgoingInvitations,
  });

  factory MembershipSummary.fromJson(Object? json) {
    final r = JsonReader.of(json, 'DashboardFacilityMemberships');
    return MembershipSummary(
      active: r.integer('active'),
      incomingRequests: r.integer('incoming_requests'),
      outgoingInvitations: r.integer('outgoing_invitations'),
    );
  }

  final int active;
  final int incomingRequests;
  final int outgoingInvitations;
}

/// `DoctorDashboard` / `FacilityDashboard`. Only what the backend returns: no revenue, no views,
/// and for a facility no totals over its practitioners' reservations (the API has no such
/// relation; `memberships` are counts of the facility's own membership records).
@immutable
class ProviderDashboard {
  const ProviderDashboard({
    required this.kind,
    required this.profile,
    required this.total,
    required this.upcomingCount,
    required this.byStatus,
    required this.upcoming,
    required this.reviews,
    required this.offers,
    required this.unread,
    required this.memberships,
  });

  factory ProviderDashboard.fromJson(ProviderDashboardKind kind, Object? json) {
    final r = JsonReader.of(json, 'ProviderDashboard');
    final reservations = r.object('reservations');
    final byStatus = reservations.object('by_status');
    return ProviderDashboard(
      kind: kind,
      profile: DashboardProfile.fromJson(r.raw('profile')),
      total: reservations.integer('total'),
      upcomingCount: reservations.integer('upcoming'),
      byStatus: {
        for (final status in ReservationStatus.values)
          if (status != ReservationStatus.unknown)
            status: byStatus.integerOrNull(status.wire) ?? 0,
      },
      upcoming: r.list('upcoming', DashboardAppointment.fromJson),
      reviews: ReviewSummary.fromJson(r.raw('reviews')),
      offers: OfferSummary.fromJson(r.raw('offers')),
      unread: UnreadSummary.fromJson(r.raw('unread')),
      memberships: kind == ProviderDashboardKind.facility
          ? MembershipSummary.fromJson(r.raw('practitioners'))
          : null,
    );
  }

  final ProviderDashboardKind kind;
  final DashboardProfile profile;
  final int total;
  final int upcomingCount;
  final Map<ReservationStatus, int> byStatus;
  final List<DashboardAppointment> upcoming;
  final ReviewSummary reviews;
  final OfferSummary offers;
  final UnreadSummary unread;

  /// Facility only.
  final MembershipSummary? memberships;
}
