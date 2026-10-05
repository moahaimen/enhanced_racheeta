import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/intl.dart' show DateFormat;
import 'package:racheeta_mobile/app/router.dart';

import 'support/fake_backend.dart';
import 'support/patient_support.dart';
import 'support/provider_support.dart';

const _slots = '/api/v1/reservations/provider/availability';
const _services = '/api/v1/providers/me/services';
const _list = '/workspace/availability';
const _form = '/workspace/availability/new';
const _tall = Size(800, 2400);

String _day(int day) => DateFormat.MMMEd('en').format(DateTime(2026, 10, day));
String _time(int day, int hour, [int minute = 0]) =>
    DateFormat.jm('en').format(DateTime(2026, 10, day, hour, minute));

// "Now" is 2026-10-03T09:00Z. Local (UTC+3) days/times in the comments.
final List<Map<String, Object?>> _items = [
  ownSlotJson('past', '2026-10-01T06:00:00Z'), // ended: hidden
  ownSlotJson('off', '2026-10-04T06:00:00Z', active: false), // inactive: hidden
  ownSlotJson('a', '2026-10-04T07:00:00Z'), // Oct 4, 10:00
  ownSlotJson('b', '2026-10-04T21:30:00Z'), // Oct 5, 00:30 (next local day)
  ownSlotJson('c', '2026-10-05T06:00:00Z', title: 'Follow-up'), // Oct 5, 09:00
];

void listScript(FakeBackend b, {List<Map<String, Object?>>? items}) => b.on(
  'GET',
  _slots,
  (_) => FakeBackend.json(200, pageJson(items ?? _items)),
);

void formScript(
  FakeBackend b, {
  List<Map<String, Object?>>? services,
  Responder? create,
}) {
  b.on(
    'GET',
    _services,
    (_) => FakeBackend.json(200, services ?? [ownServiceJson()]),
  );
  if (create != null) b.on('POST', _slots, create);
}

Future<void> _fillForm(WidgetTester tester, {bool pickService = true}) async {
  if (pickService) {
    await tester.tap(find.byKey(const Key('slot-service')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Consultation · 30 min').last);
    await tester.pumpAndSettle();
  }
  await tester.tap(find.byKey(const Key('slot-date')));
  await tester.pumpAndSettle();
  await tester.tap(find.text('OK'));
  await tester.pumpAndSettle();
  await tester.tap(find.byKey(const Key('slot-time')));
  await tester.pumpAndSettle();
  await tester.tap(find.text('OK'));
  await tester.pumpAndSettle();
}

Finder _create() => find.widgetWithText(FilledButton, 'Create availability');

void main() {
  group('availability list', () {
    testWidgets(
      'shows active upcoming slots grouped by LOCAL day, in local time',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: _list,
          size: _tall,
          account: providerAccountJson(),
          script: listScript,
        );
        expect(h.backend.to('GET', _slots).single.query['page_size'], 100);
        expect(find.text(_day(4)), findsOneWidget);
        expect(find.text(_day(5)), findsOneWidget);
        // 07:00Z → 10:00 on Oct 4; 21:30Z → 00:30 on Oct 5; 06:00Z → 09:00 on Oct 5
        expect(
          find.text('${_time(4, 10)} – ${_time(4, 10, 30)}'),
          findsOneWidget,
        );
        expect(
          find.text('${_time(5, 0, 30)} – ${_time(5, 1)}'),
          findsOneWidget,
        );
        expect(
          find.text('${_time(5, 9)} – ${_time(5, 9, 30)}'),
          findsOneWidget,
        );
        // the ended and the inactive slots are not shown
        expect(find.byKey(const Key('slot-past')), findsNothing);
        expect(find.byKey(const Key('slot-off')), findsNothing);
        expect(find.byKey(const Key('slot-a')), findsOneWidget);
        expect(find.text('Follow-up'), findsOneWidget);
        expect(
          find.text("Times are shown in your device's time zone."),
          findsOneWidget,
        );
      },
    );

    testWidgets('an empty list explains itself and offers to add', (
      tester,
    ) async {
      await pumpPatientApp(
        tester,
        path: _list,
        size: _tall,
        account: providerAccountJson(),
        script: (b) => listScript(b, items: const []),
      );
      expect(find.text('No upcoming availability'), findsOneWidget);
      expect(find.text('Add availability'), findsWidgets);
    });

    testWidgets('a failure shows a safe message and Try again recovers', (
      tester,
    ) async {
      var fail = true;
      await pumpPatientApp(
        tester,
        path: _list,
        size: _tall,
        account: providerAccountJson(),
        script: (b) => b.on(
          'GET',
          _slots,
          (_) => fail
              ? FakeBackend.error(500, 'server_error', message: 'Traceback')
              : FakeBackend.json(200, pageJson(_items)),
        ),
      );
      expect(find.textContaining('Traceback'), findsNothing);
      fail = false;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('slot-a')), findsOneWidget);
    });

    testWidgets(
      'pages with only past slots offer Load more and the next page is requested',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: _list,
          size: _tall,
          account: providerAccountJson(),
          script: (b) => b.on('GET', _slots, (r) {
            if (r.query['page'] == 2) {
              return FakeBackend.json(
                200,
                pageJson([
                  ownSlotJson('late', '2026-10-06T06:00:00Z'),
                ], count: 2),
              );
            }
            return FakeBackend.json(
              200,
              pageJson(
                [ownSlotJson('old', '2026-09-01T06:00:00Z')],
                count: 2,
                next: 'https://api.test/x?page=2',
              ),
            );
          }),
        );
        expect(
          find.text('No upcoming times in the pages loaded so far.'),
          findsOneWidget,
        );
        await tester.tap(find.text('Load more'));
        await tester.pumpAndSettle();
        expect(find.byKey(const Key('slot-late')), findsOneWidget);
        expect(h.backend.to('GET', _slots).map((r) => r.query['page']), [
          null,
          2,
        ]);
      },
    );

    testWidgets('renders Arabic right-to-left', (tester) async {
      await pumpPatientApp(
        tester,
        path: _list,
        size: _tall,
        language: 'ar',
        account: providerAccountJson(),
        script: listScript,
      );
      expect(find.text('إضافة موعد متاح'), findsOneWidget);
      expect(find.text('إزالة'), findsWidgets);
      expect(
        Directionality.of(tester.element(find.text('إضافة موعد متاح'))),
        TextDirection.rtl,
      );
    });
  });

  group('removing a slot', () {
    Future<Harness> open(WidgetTester tester, {Responder? remove}) async {
      var removed = false;
      return pumpPatientApp(
        tester,
        path: _list,
        size: _tall,
        account: providerAccountJson(),
        script: (b) {
          b.on(
            'GET',
            _slots,
            (_) => FakeBackend.json(
              200,
              pageJson([
                for (final item in _items)
                  if (!(removed && item['id'] == 'a')) item,
              ]),
            ),
          );
          b.on('DELETE', '$_slots/a', (r) {
            removed = true;
            return remove != null ? remove(r) : FakeBackend.noContent();
          });
        },
      );
    }

    Finder removeOn(String id) => find.descendant(
      of: find.byKey(Key('slot-$id')),
      matching: find.text('Remove'),
    );

    Future<void> confirmRemove(WidgetTester tester) async {
      await tester.tap(
        find.descendant(
          of: find.byType(AlertDialog),
          matching: find.text('Remove'),
        ),
      );
      await tester.pumpAndSettle();
    }

    testWidgets('declining the confirmation sends nothing', (tester) async {
      final h = await open(tester);
      await tester.tap(removeOn('a'));
      await tester.pumpAndSettle();
      expect(find.text('Remove this time?'), findsOneWidget);
      await tester.tap(find.text('Keep'));
      await tester.pumpAndSettle();
      expect(h.backend.count('DELETE', '$_slots/a'), 0);
    });

    testWidgets(
      'confirming deactivates once and reloads the list from the backend',
      (tester) async {
        final h = await open(tester);
        await tester.tap(removeOn('a'));
        await tester.pumpAndSettle();
        await confirmRemove(tester);
        expect(h.backend.count('DELETE', '$_slots/a'), 1);
        expect(find.text('The time was removed.'), findsOneWidget);
        expect(
          h.backend.count('GET', _slots),
          2,
          reason: 'refetched after success',
        );
        expect(find.byKey(const Key('slot-a')), findsNothing);
        expect(find.byKey(const Key('slot-c')), findsOneWidget);
      },
    );

    testWidgets(
      'a slot used by a live reservation is refused with its own message',
      (tester) async {
        final h = await open(
          tester,
          remove: (_) => FakeBackend.error(409, 'slot_unavailable'),
        );
        await tester.tap(removeOn('a'));
        await tester.pumpAndSettle();
        await confirmRemove(tester);
        expect(
          find.text("A live booking uses this time, so it can't be removed."),
          findsOneWidget,
        );
        expect(
          h.backend.count('DELETE', '$_slots/a'),
          1,
          reason: 'not retried',
        );
      },
    );

    testWidgets(
      'a slot that no longer exists shows the generic text and refreshes the list',
      (tester) async {
        final h = await open(
          tester,
          remove: (_) => FakeBackend.error(404, 'not_found'),
        );
        await tester.tap(removeOn('a'));
        await tester.pumpAndSettle();
        await confirmRemove(tester);
        expect(find.text("We couldn't find that."), findsOneWidget);
        expect(h.backend.count('GET', _slots), 2);
      },
    );

    testWidgets(
      'a duplicate tap while removing sends ONE request and shows progress',
      (tester) async {
        final gate = Completer<void>();
        final h = await open(
          tester,
          remove: (_) async {
            await gate.future;
            return FakeBackend.noContent();
          },
        );
        await tester.tap(removeOn('a'));
        await tester.pumpAndSettle();
        await tester.tap(
          find.descendant(
            of: find.byType(AlertDialog),
            matching: find.text('Remove'),
          ),
        );
        await tester.pump(const Duration(milliseconds: 20));
        expect(find.text('Removing…'), findsOneWidget);
        await tester.tap(find.text('Removing…'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 20));
        expect(h.backend.count('DELETE', '$_slots/a'), 1);
        gate.complete();
        await tester.pumpAndSettle();
        expect(h.backend.count('DELETE', '$_slots/a'), 1);
      },
    );

    testWidgets('a network failure is not retried automatically', (
      tester,
    ) async {
      final h = await open(tester, remove: FakeBackend.networkDown);
      await tester.tap(removeOn('a'));
      await tester.pumpAndSettle();
      await confirmRemove(tester);
      expect(find.textContaining('Could not reach the server'), findsOneWidget);
      await tester.pump(const Duration(seconds: 30));
      expect(h.backend.count('DELETE', '$_slots/a'), 1);
    });
  });

  group('creating a slot', () {
    testWidgets(
      'sends the documented body with the START AS UTC and confirms from the backend',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: _form,
          size: _tall,
          account: providerAccountJson(),
          script: (b) => formScript(
            b,
            create: (_) => FakeBackend.json(
              201,
              ownSlotJson('new', '2026-10-04T06:00:00Z'),
            ),
          ),
        );
        expect(tester.widget<FilledButton>(_create()).onPressed, isNull);
        expect(
          find.text('Choose a service, a date and a start time.'),
          findsOneWidget,
        );

        await _fillForm(tester);
        // the summary is the picked LOCAL time (tomorrow 9:00 for the UTC+3 reader)
        expect(
          tester.widget<Text>(find.byKey(const Key('slot-summary'))).data,
          contains(_time(4, 9)),
        );
        await tester.tap(_create());
        await tester.pumpAndSettle();

        final posts = h.backend.to('POST', _slots);
        expect(posts, hasLength(1));
        expect(posts.single.body, {
          'service': serviceId,
          // 09:00 local (UTC+3) is 06:00Z — never the local clock labelled as UTC
          'starts_at': '2026-10-04T06:00:00.000Z',
        });
        expect(find.text('Availability added.'), findsOneWidget);
        // the date and time are cleared so the next slot is a deliberate choice
        expect(tester.widget<FilledButton>(_create()).onPressed, isNull);
      },
    );

    testWidgets(
      'the list is reloaded from the backend after a successful creation',
      (tester) async {
        var created = false;
        final h = await pumpPatientApp(
          tester,
          path: _list,
          size: _tall,
          account: providerAccountJson(),
          script: (b) {
            b.on(
              'GET',
              _slots,
              (_) => FakeBackend.json(
                200,
                pageJson([
                  ..._items,
                  if (created)
                    ownSlotJson(
                      'new',
                      '2026-10-04T09:00:00Z',
                      title: 'Brand new',
                    ),
                ]),
              ),
            );
            formScript(
              b,
              create: (_) {
                created = true;
                return FakeBackend.json(
                  201,
                  ownSlotJson('new', '2026-10-04T09:00:00Z'),
                );
              },
            );
          },
        );
        expect(h.backend.count('GET', _slots), 1);
        expect(find.text('Brand new'), findsNothing);
        h.container.read(routerProvider).go(_form);
        await tester.pumpAndSettle();
        await _fillForm(tester);
        await tester.tap(_create());
        await tester.pumpAndSettle();
        h.container.read(routerProvider).go(_list);
        await tester.pumpAndSettle();
        expect(h.backend.count('GET', _slots), 2);
        expect(find.text('Brand new'), findsOneWidget);
      },
    );

    testWidgets(
      'a duplicate tap while creating sends ONE request and shows progress',
      (tester) async {
        final gate = Completer<void>();
        final h = await pumpPatientApp(
          tester,
          path: _form,
          size: _tall,
          account: providerAccountJson(),
          script: (b) => formScript(
            b,
            create: (_) async {
              await gate.future;
              return FakeBackend.json(
                201,
                ownSlotJson('new', '2026-10-04T06:00:00Z'),
              );
            },
          ),
        );
        await _fillForm(tester);
        await tester.tap(_create());
        await tester.pump(const Duration(milliseconds: 20));
        expect(find.text('Adding…'), findsOneWidget);
        await tester.tap(find.text('Adding…'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 20));
        expect(h.backend.count('POST', _slots), 1);
        gate.complete();
        await tester.pumpAndSettle();
        expect(h.backend.count('POST', _slots), 1);
      },
    );

    for (final c in [
      ('slot_conflict', 409, 'This time overlaps another active time.'),
      ('invalid_availability', 400, 'The start time must be in the future.'),
      (
        'service_unavailable',
        409,
        "This service can't be used for availability. It must be active and have a duration.",
      ),
    ]) {
      testWidgets(
        '${c.$1} (${c.$2}) shows its own message and is not retried',
        (tester) async {
          final h = await pumpPatientApp(
            tester,
            path: _form,
            size: _tall,
            account: providerAccountJson(),
            script: (b) => formScript(
              b,
              create: (_) =>
                  FakeBackend.error(c.$2, c.$1, message: 'raw server text'),
            ),
          );
          await _fillForm(tester);
          await tester.tap(_create());
          await tester.pumpAndSettle();
          expect(find.text(c.$3), findsOneWidget);
          expect(find.textContaining('raw server text'), findsNothing);
          await tester.pump(const Duration(seconds: 30));
          expect(h.backend.count('POST', _slots), 1);
          // the input is kept so the provider can adjust it deliberately
          expect(tester.widget<FilledButton>(_create()).onPressed, isNotNull);
        },
      );
    }

    testWidgets('a network failure is never retried automatically', (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: _form,
        size: _tall,
        account: providerAccountJson(),
        script: (b) => formScript(b, create: FakeBackend.networkDown),
      );
      await _fillForm(tester);
      await tester.tap(_create());
      await tester.pumpAndSettle();
      expect(find.textContaining('Could not reach the server'), findsOneWidget);
      await tester.pump(const Duration(seconds: 30));
      expect(h.backend.count('POST', _slots), 1);
    });

    testWidgets('no usable service explains what to do and offers no form', (
      tester,
    ) async {
      await pumpPatientApp(
        tester,
        path: _form,
        size: _tall,
        account: providerAccountJson(),
        script: (b) => formScript(
          b,
          services: [
            ownServiceJson(id: 's1', duration: null),
            ownServiceJson(id: 's2', active: false),
          ],
        ),
      );
      expect(
        find.text(
          'You need an active service with a duration before adding availability. Set one up on the Racheeta website.',
        ),
        findsOneWidget,
      );
      expect(_create(), findsNothing);
    });

    testWidgets('only active services that have a duration can be chosen', (
      tester,
    ) async {
      await pumpPatientApp(
        tester,
        path: _form,
        size: _tall,
        account: providerAccountJson(),
        script: (b) => formScript(
          b,
          services: [
            ownServiceJson(),
            ownServiceJson(id: 's2', title: 'No duration', duration: null),
            ownServiceJson(id: 's3', title: 'Switched off', active: false),
          ],
        ),
      );
      await tester.tap(find.byKey(const Key('slot-service')));
      await tester.pumpAndSettle();
      expect(find.text('Consultation · 30 min'), findsWidgets);
      expect(find.textContaining('No duration'), findsNothing);
      expect(find.textContaining('Switched off'), findsNothing);
    });

    testWidgets('a services failure offers Try again', (tester) async {
      var fail = true;
      await pumpPatientApp(
        tester,
        path: _form,
        size: _tall,
        account: providerAccountJson(),
        script: (b) => b.on(
          'GET',
          _services,
          (_) => fail
              ? FakeBackend.error(500, 'server_error')
              : FakeBackend.json(200, [ownServiceJson()]),
        ),
      );
      expect(find.text('Try again'), findsOneWidget);
      fail = false;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('slot-service')), findsOneWidget);
    });

    testWidgets('renders Arabic right-to-left', (tester) async {
      await pumpPatientApp(
        tester,
        path: _form,
        size: _tall,
        language: 'ar',
        account: providerAccountJson(),
        script: formScript,
      );
      expect(find.text('اختر الخدمة والتاريخ ووقت البدء.'), findsOneWidget);
      expect(find.text('إنشاء الموعد'), findsOneWidget);
      expect(
        Directionality.of(tester.element(find.text('إنشاء الموعد'))),
        TextDirection.rtl,
      );
    });
  });
}
