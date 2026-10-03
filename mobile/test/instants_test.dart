import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/core/api/json_reader.dart';
import 'package:racheeta_mobile/core/time/instants.dart';
import 'package:racheeta_mobile/features/discovery/data/discovery_models.dart';
import 'package:racheeta_mobile/features/reservations/data/reservation_models.dart';

import 'support/patient_support.dart';

void main() {
  group('parseInstant (timezone policy)', () {
    test('accepts Z and explicit offsets and keeps the instant as UTC', () {
      expect(
        parseInstant('2026-10-05T06:00:00Z'),
        DateTime.utc(2026, 10, 5, 6),
      );
      expect(
        parseInstant('2026-10-05T09:00:00+03:00'),
        DateTime.utc(2026, 10, 5, 6),
      );
      expect(
        parseInstant('2026-10-05T06:00:00.123456Z').isUtc,
        isTrue,
        reason: 'always UTC internally',
      );
      expect(
        parseInstant('2026-10-05T00:30:00-0500'),
        DateTime.utc(2026, 10, 5, 5, 30),
      );
    });

    test(
      'rejects a timestamp without an offset instead of reading it as local',
      () {
        for (final bad in [
          '2026-10-05T06:00:00',
          '2026-10-05',
          '06:00',
          '',
          'not a date',
        ]) {
          expect(() => parseInstant(bad), throwsFormatException, reason: bad);
        }
      },
    );

    test('the wire form is UTC with a Z suffix', () {
      expect(
        toWireInstant(DateTime.parse('2026-10-05T09:00:00+03:00')),
        '2026-10-05T06:00:00.000Z',
      );
      expect(toWireInstant(DateTime.utc(2026, 1, 2, 3)), endsWith('Z'));
    });

    test('dayOf drops the time of the wall-clock value', () {
      expect(dayOf(DateTime(2026, 10, 5, 23, 59)), DateTime(2026, 10, 5));
    });

    test('a picked local date and time converts back to a UTC instant', () {
      final picked = DateTime(2026, 10, 4, 9, 30);
      final utc = deviceLocalToUtc(picked);
      expect(utc.isUtc, isTrue);
      // the device-local fields round-trip through UTC
      expect(deviceWallClock(utc), picked);
      expect(toWireInstant(utc), endsWith('Z'));
    });

    test('the injected local-to-UTC (UTC+3) maps 09:00 to 06:00Z', () {
      DateTime toUtc(DateTime wall) => DateTime.utc(
        wall.year,
        wall.month,
        wall.day,
        wall.hour,
        wall.minute,
      ).subtract(testOffset);
      expect(toUtc(DateTime(2026, 10, 4, 9)), DateTime.utc(2026, 10, 4, 6));
      // 00:30 local is the previous UTC day
      expect(
        toUtc(DateTime(2026, 10, 5, 0, 30)),
        DateTime.utc(2026, 10, 4, 21, 30),
      );
    });

    test('the injected wall clock decides the displayed day (UTC+3)', () {
      DateTime wall(DateTime utc) => utc.toUtc().add(testOffset);
      // 21:30Z is 00:30 the NEXT day for a UTC+3 reader.
      expect(
        dayOf(wall(DateTime.utc(2026, 10, 5, 21, 30))),
        DateTime(2026, 10, 6),
      );
      expect(
        dayOf(wall(DateTime.utc(2026, 10, 5, 20, 59))),
        DateTime(2026, 10, 5),
      );
    });
  });

  group('JsonReader', () {
    test('required fields are strict, optional ones are lenient', () {
      final r = JsonReader.of({'a': 'x', 'n': 3, 'd': 1.5, 'z': null}, 'T');
      expect(r.string('a'), 'x');
      expect(r.integer('n'), 3);
      expect(r.doubleOrNull('d'), 1.5);
      expect(r.stringOrNull('z'), isNull);
      expect(r.stringOr('missing', 'fallback'), 'fallback');
      expect(() => r.string('n'), throwsFormatException);
      expect(() => r.integer('a'), throwsFormatException);
      expect(() => r.string('missing'), throwsFormatException);
      expect(() => JsonReader.of([], 'T'), throwsFormatException);
      expect(() => JsonReader.of(null, 'T'), throwsFormatException);
    });

    test('lists: required must be a list; optional becomes empty', () {
      final r = JsonReader.of({
        'l': [1, 2],
        'bad': 'x',
      }, 'T');
      expect(r.list<int>('l', (v) => v as int), [1, 2]);
      expect(() => r.list<int>('bad', (v) => v as int), throwsFormatException);
      expect(r.listOrEmpty<int>('bad', (v) => v as int), isEmpty);
      expect(r.listOrEmpty<int>('missing', (v) => v as int), isEmpty);
    });

    test('booleans: required is strict, optional falls back', () {
      final r = JsonReader.of({'on': true, 'text': 'x'}, 'T');
      expect(r.boolean('on'), isTrue);
      expect(() => r.boolean('text'), throwsFormatException);
      expect(() => r.boolean('missing'), throwsFormatException);
      expect(r.booleanOr('missing', fallback: true), isTrue);
      expect(r.booleanOr('text', fallback: false), isFalse);
    });

    test('an instant must carry an offset', () {
      expect(
        () => JsonReader.of({'t': '2026-10-05T06:00:00'}, 'T').instant('t'),
        throwsFormatException,
      );
      expect(JsonReader.of({'t': ''}, 'T').instantOrNull('t'), isNull);
    });
  });

  group('Reservation model', () {
    test('parses the backend shape and keeps UTC instants', () {
      final r = Reservation.fromJson(
        reservationJson(
          status: 'CONFIRMED',
          startsAt: '2026-10-05T06:00:00Z',
          note: 'bring results',
        ),
      );
      expect(r.status, ReservationStatus.confirmed);
      expect(r.startsAt, DateTime.utc(2026, 10, 5, 6));
      expect(r.endsAt, DateTime.utc(2026, 10, 5, 6, 30));
      expect(r.providerName, 'Dr. Sara Ahmed');
      expect(r.price, '25000.00');
      expect(r.patientNote, 'bring results');
      expect(r.transitions.single.to, ReservationStatus.confirmed);
    });

    test(
      'every documented status parses; an unknown one is kept, not fatal',
      () {
        for (final code in [
          'PENDING',
          'CONFIRMED',
          'COMPLETED',
          'REJECTED',
          'CANCELLED',
          'NO_SHOW',
        ]) {
          final status = ReservationStatus.parse(code);
          expect(status, isNot(ReservationStatus.unknown), reason: code);
          expect(status.wire, code);
        }
        final future = Reservation.fromJson(
          reservationJson(status: 'ARCHIVED'),
        );
        expect(future.status, ReservationStatus.unknown);
        expect(future.statusCode, 'ARCHIVED');
        expect(future.status.isLive, isFalse);
      },
    );

    test(
      'isUpcoming needs a live status and a future start (a UI hint only)',
      () {
        final now = DateTime.utc(2026, 10, 3, 9);
        Reservation of(String status, String startsAt) => Reservation.fromJson(
          reservationJson(status: status, startsAt: startsAt),
        );
        expect(of('PENDING', '2026-10-05T06:00:00Z').isUpcoming(now), isTrue);
        expect(of('CONFIRMED', '2026-10-05T06:00:00Z').isUpcoming(now), isTrue);
        expect(of('PENDING', '2026-10-03T08:00:00Z').isUpcoming(now), isFalse);
        expect(of('PENDING', '2026-10-03T09:00:00Z').isUpcoming(now), isFalse);
        for (final closed in [
          'COMPLETED',
          'REJECTED',
          'CANCELLED',
          'NO_SHOW',
        ]) {
          expect(
            of(closed, '2026-10-05T06:00:00Z').isUpcoming(now),
            isFalse,
            reason: closed,
          );
        }
      },
    );

    test('a missing required field or an offset-less time is an unreadable response', () {
      expect(
        () => Reservation.fromJson({...reservationJson()}..remove('id')),
        throwsFormatException,
      );
      expect(
        () => Reservation.fromJson(
          reservationJson(startsAt: '2026-10-05T06:00:00'),
        ),
        throwsFormatException,
      );
    });

    test('toString never carries personal data', () {
      final r = Reservation.fromJson(reservationJson(note: 'private note'));
      expect(r.toString(), isNot(contains('private')));
      expect(r.toString(), isNot(contains('Sara')));
    });
  });

  group('AvailabilitySlot model', () {
    test('parses the public availability shape', () {
      final slot = AvailabilitySlot.fromJson(
        slotJson('slot-1', '2026-10-05T06:00:00Z'),
      );
      expect(slot.id, 'slot-1');
      expect(slot.startsAt, DateTime.utc(2026, 10, 5, 6));
      expect(slot.providerId, providerId);
      expect(slot.service.id, serviceId);
    });

    test('an offset-less slot time is rejected', () {
      expect(
        () => AvailabilitySlot.fromJson(slotJson('s', '2026-10-05T06:00:00')),
        throwsFormatException,
      );
    });
  });
}
