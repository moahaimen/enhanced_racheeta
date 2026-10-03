import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/features/provider/data/provider_models.dart';
import 'package:racheeta_mobile/features/provider/data/provider_transitions.dart';
import 'package:racheeta_mobile/features/reservations/data/reservation_models.dart';

import 'support/patient_support.dart';
import 'support/provider_support.dart';

void main() {
  group('ProviderReservation', () {
    test('parses the provider schema (patient summary included)', () {
      final r = ProviderReservation.fromJson(
        providerReservationJson(note: 'x', patient: 'Layla Hassan'),
      );
      expect(r.patientName, 'Layla Hassan');
      expect(r.patientId, patientRecordId);
      expect(r.reservation.status, ReservationStatus.pending);
      expect(r.reservation.startsAt, DateTime.utc(2026, 10, 5, 6));
      expect(r.reservation.patientNote, 'x');
    });

    test(
      'a missing patient or an offset-less time is an unreadable response',
      () {
        expect(
          () => ProviderReservation.fromJson(
            {...providerReservationJson()}..remove('patient'),
          ),
          throwsFormatException,
        );
        expect(
          () => ProviderReservation.fromJson(
            providerReservationJson(startsAt: '2026-10-05T06:00:00'),
          ),
          throwsFormatException,
        );
      },
    );

    test('toString carries no personal data', () {
      final r = ProviderReservation.fromJson(
        providerReservationJson(note: 'private', patient: 'Layla Hassan'),
      );
      expect(r.toString(), isNot(contains('Layla')));
      expect(r.toString(), isNot(contains('private')));
    });
  });

  group('ProviderSlot and OwnService', () {
    test('a slot parses with its service and activity', () {
      final slot = ProviderSlot.fromJson(
        ownSlotJson('s', '2026-10-05T06:00:00Z', active: false),
      );
      expect(slot.startsAt, DateTime.utc(2026, 10, 5, 6));
      expect(slot.endsAt, DateTime.utc(2026, 10, 5, 6, 30));
      expect(slot.isActive, isFalse);
      expect(slot.serviceId, serviceId);
      expect(slot.durationMinutes, 30);
    });

    test('isCurrent needs an active slot that has not ended', () {
      final now = DateTime.utc(2026, 10, 5, 6, 15);
      expect(
        ProviderSlot.fromJson(ownSlotJson('s', '2026-10-05T06:00:00Z'))
            .isCurrent(now),
        isTrue,
        reason: 'in progress',
      );
      expect(
        ProviderSlot.fromJson(ownSlotJson('s', '2026-10-05T05:00:00Z'))
            .isCurrent(now),
        isFalse,
      );
      expect(
        ProviderSlot.fromJson(
          ownSlotJson('s', '2026-10-05T07:00:00Z', active: false),
        ).isCurrent(now),
        isFalse,
      );
    });

    test('an offset-less slot time is rejected', () {
      expect(
        () => ProviderSlot.fromJson(ownSlotJson('s', '2026-10-05T06:00:00')),
        throwsFormatException,
      );
    });

    test(
      'a service can have slots only when active with a positive duration',
      () {
        expect(OwnService.fromJson(ownServiceJson()).canHaveSlots, isTrue);
        expect(
          OwnService.fromJson(ownServiceJson(duration: null)).canHaveSlots,
          isFalse,
        );
        expect(
          OwnService.fromJson(ownServiceJson(duration: 0)).canHaveSlots,
          isFalse,
        );
        expect(
          OwnService.fromJson(ownServiceJson(active: false)).canHaveSlots,
          isFalse,
        );
      },
    );
  });

  group('dashboards', () {
    test('the index decides: facility wins, then doctor, else none', () {
      DashboardIndex of(List<String> v) =>
          DashboardIndex.fromJson({'dashboards': v});
      expect(of(['doctor']).providerKind, ProviderDashboardKind.doctor);
      expect(
        of(['patient', 'facility']).providerKind,
        ProviderDashboardKind.facility,
      );
      expect(
        of(['doctor', 'facility']).providerKind,
        ProviderDashboardKind.facility,
      );
      expect(of(['patient', 'admin']).providerKind, isNull);
      expect(of(<String>[]).providerKind, isNull);
      expect(() => DashboardIndex.fromJson({}), throwsFormatException);
    });

    test('a doctor dashboard parses and has no memberships', () {
      final d = ProviderDashboard.fromJson(
        ProviderDashboardKind.doctor,
        dashboardJson(),
      );
      expect(d.profile.displayName, 'Dr. Sara Ahmed');
      expect(d.total, 9);
      expect(d.upcomingCount, 3);
      expect(d.byStatus[ReservationStatus.confirmed], 3);
      expect(d.upcoming.single.patientName, 'Layla Hassan');
      expect(d.upcoming.single.startsAt, DateTime.utc(2026, 10, 5, 6));
      expect(d.reviews.average, 4.5);
      expect(d.reviews.distribution[5], 3);
      expect(d.offers.runningNow, 2);
      expect(d.unread.messages, 2);
      expect(d.memberships, isNull);
    });

    test('a facility dashboard carries its membership counts', () {
      final d = ProviderDashboard.fromJson(
        ProviderDashboardKind.facility,
        dashboardJson(facility: true),
      );
      expect(d.memberships!.active, 5);
      expect(d.memberships!.incomingRequests, 1);
      expect(d.memberships!.outgoingInvitations, 2);
    });

    test('no reviews means a null average, never a made-up number', () {
      final d = ProviderDashboard.fromJson(
        ProviderDashboardKind.doctor,
        dashboardJson(average: null, reviews: 0),
      );
      expect(d.reviews.average, isNull);
      expect(d.reviews.count, 0);
    });

    test('a missing required block is an unreadable response', () {
      for (final key in [
        'profile',
        'reservations',
        'reviews',
        'offers',
        'unread',
      ]) {
        expect(
          () => ProviderDashboard.fromJson(
            ProviderDashboardKind.doctor,
            {...dashboardJson()}..remove(key),
          ),
          throwsFormatException,
          reason: key,
        );
      }
      expect(
        () => ProviderDashboard.fromJson(
          ProviderDashboardKind.facility,
          {...dashboardJson(facility: true)}..remove('practitioners'),
        ),
        throwsFormatException,
      );
    });
  });

  group('offeredTransitions (a UI hint that mirrors the backend rules)', () {
    final now = DateTime.utc(2026, 10, 3, 9);
    Reservation of(String status, String startsAt) => Reservation.fromJson(
      reservationJson(status: status, startsAt: startsAt),
    );

    test(
      'PENDING: confirm only before it starts; reject and cancel always',
      () {
        expect(offeredTransitions(of('PENDING', '2026-10-05T06:00:00Z'), now), [
          ReservationStatus.confirmed,
          ReservationStatus.rejected,
          ReservationStatus.cancelled,
        ]);
        expect(offeredTransitions(of('PENDING', '2026-10-02T06:00:00Z'), now), [
          ReservationStatus.rejected,
          ReservationStatus.cancelled,
        ]);
      },
    );

    test(
      'CONFIRMED: complete and no-show only after it started; cancel always',
      () {
        expect(
          offeredTransitions(of('CONFIRMED', '2026-10-05T06:00:00Z'), now),
          [ReservationStatus.cancelled],
        );
        expect(
          offeredTransitions(of('CONFIRMED', '2026-10-02T06:00:00Z'), now),
          [
            ReservationStatus.completed,
            ReservationStatus.noShow,
            ReservationStatus.cancelled,
          ],
        );
        // the boundary: starting exactly now counts as started
        expect(
          offeredTransitions(of('CONFIRMED', '2026-10-03T09:00:00Z'), now),
          contains(ReservationStatus.completed),
        );
      },
    );

    test('closed and unknown statuses offer nothing', () {
      for (final status in [
        'COMPLETED',
        'REJECTED',
        'CANCELLED',
        'NO_SHOW',
        'ARCHIVED',
      ]) {
        expect(
          offeredTransitions(of(status, '2026-10-05T06:00:00Z'), now),
          isEmpty,
          reason: status,
        );
      }
    });
  });
}
