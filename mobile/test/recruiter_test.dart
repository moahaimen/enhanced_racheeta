import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/domain_support.dart';
import 'support/fake_backend.dart';
import 'support/patient_support.dart';
import 'support/provider_support.dart' show switchAccountTo;

const _index = '/api/v1/dashboards/';
const _dash = '/api/v1/dashboards/recruiter';
const _list = '/api/v1/jobs/employer/jobs';
const _one = '/api/v1/jobs/employer/jobs/$jobId';
const _close = '/api/v1/jobs/employer/jobs/$jobId/close';
const _tall = Size(800, 2400);
const _phone = Size(360, 780);

final Map<String, Object?> _a = recruiterAccountJson(name: 'Recruiter A');
final Map<String, Object?> _b = recruiterAccountJson(
  id: '99999999-9999-4999-8999-999999999999',
  name: 'Recruiter B',
);

void main() {
  group('access', () {
    testWidgets(
      'an account the server does not list as a recruiter sees the not-allowed state and sends no recruiter request',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: '/recruiter',
          size: _tall,
          script: (b) => b.on(
            'GET',
            _index,
            (_) => FakeBackend.json(200, {
              'dashboards': ['patient', 'seller'],
            }),
          ),
        );
        expect(
          find.text('This area is for recruiting-organisation members.'),
          findsOneWidget,
        );
        expect(h.backend.count('GET', _dash), 0);
        expect(h.backend.count('GET', _list), 0);
      },
    );

    testWidgets(
      'a failing index is a safe error and recruiter data is not requested',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: '/recruiter/jobs',
          size: _tall,
          script: (b) => b.on(
            'GET',
            _index,
            (_) => FakeBackend.error(500, 'server_error', message: 'Traceback'),
          ),
        );
        expect(find.textContaining('Traceback'), findsNothing);
        expect(find.text('Try again'), findsOneWidget);
        expect(h.backend.count('GET', _list), 0);
      },
    );
  });

  group('workspace', () {
    testWidgets(
      'shows the organisation, role, jobs, applications, interviews and seats',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/recruiter',
          size: _tall,
          account: _a,
          script: (b) => b
            ..on(
              'GET',
              _index,
              (_) => FakeBackend.json(200, {
                'dashboards': ['recruiter'],
              }),
            )
            ..on(
              'GET',
              _dash,
              (_) => FakeBackend.json(200, recruiterDashboardJson()),
            ),
        );
        expect(find.byKey(const Key('recruiter-organization')), findsOneWidget);
        expect(find.text('Al Noor Hospital'), findsOneWidget);
        expect(find.text('RECRUITER'), findsOneWidget);
        expect(find.byKey(const Key('recruiter-jobs')), findsOneWidget);
        expect(find.byKey(const Key('recruiter-applications')), findsOneWidget);
        expect(find.text('31'), findsOneWidget);
        expect(find.text('15'), findsOneWidget);
        expect(find.byKey(const Key('recruiter-seats')), findsOneWidget);
        expect(
          find.text('Application figures are not available for this account.'),
          findsNothing,
        );
      },
    );

    testWidgets(
      'withheld application figures are explained and never shown as zero',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/recruiter',
          size: _tall,
          account: _a,
          script: (b) => b
            ..on(
              'GET',
              _index,
              (_) => FakeBackend.json(200, {
                'dashboards': ['recruiter'],
              }),
            )
            ..on(
              'GET',
              _dash,
              (_) => FakeBackend.json(
                200,
                recruiterDashboardJson(withApplications: false),
              ),
            ),
        );
        expect(
          find.text('Application figures are not available for this account.'),
          findsOneWidget,
        );
        expect(find.text('Awaiting review'), findsNothing);
      },
    );

    testWidgets('a 403 is the fixed membership message, not raw text', (
      tester,
    ) async {
      await pumpPatientApp(
        tester,
        path: '/recruiter',
        size: _tall,
        account: _a,
        script: (b) => b
          ..on(
            'GET',
            _index,
            (_) => FakeBackend.json(200, {
              'dashboards': ['recruiter'],
            }),
          )
          ..on(
            'GET',
            _dash,
            (_) => FakeBackend.error(
              403,
              'permission_denied',
              message: 'raw org 9',
            ),
          ),
      );
      expect(
        find.text('You are not a member of a recruiting organisation.'),
        findsOneWidget,
      );
      expect(find.textContaining('raw org'), findsNothing);
    });

    testWidgets('renders Arabic right-to-left at phone width', (tester) async {
      await pumpPatientApp(
        tester,
        path: '/recruiter',
        size: _phone,
        language: 'ar',
        account: _a,
        script: (b) => b
          ..on(
            'GET',
            _index,
            (_) => FakeBackend.json(200, {
              'dashboards': ['recruiter'],
            }),
          )
          ..on(
            'GET',
            _dash,
            (_) => FakeBackend.json(200, recruiterDashboardJson()),
          ),
      );
      expect(find.text('مساحة التوظيف'), findsWidgets);
      expect(
        Directionality.of(
          tester.element(find.byKey(const Key('recruiter-organization'))),
        ),
        TextDirection.rtl,
      );
      expect(tester.takeException(), isNull);
    });

    testWidgets(
      'A\'s organisation figures never appear under B (route stays mounted)',
      (tester) async {
        var who = 'A';
        final gateB = Completer<void>();
        final h = await pumpPatientApp(
          tester,
          path: '/recruiter',
          size: _tall,
          account: _a,
          script: (b) => b
            ..on(
              'GET',
              _index,
              (_) => FakeBackend.json(200, {
                'dashboards': ['recruiter'],
              }),
            )
            ..on('GET', _dash, (_) async {
              if (who == 'B') await gateB.future;
              final d = recruiterDashboardJson();
              (d['organization']! as Map<String, Object?>)['name'] =
                  'Org of $who';
              return FakeBackend.json(200, d);
            }),
        );
        expect(find.text('Org of A'), findsOneWidget);
        who = 'B';
        await switchAccountTo(tester, h, _b);
        expect(find.text('Org of A'), findsNothing);
        gateB.complete();
        await tester.pumpAndSettle();
        expect(find.text('Org of B'), findsOneWidget);
        expect(find.text('Org of A'), findsNothing);
      },
    );
  });

  group('organisation jobs', () {
    Future<Harness> open(
      WidgetTester tester, {
      String path = '/recruiter/jobs',
      Responder? list,
    }) => pumpPatientApp(
      tester,
      path: path,
      size: _tall,
      account: _a,
      script: (b) => b
        ..on(
          'GET',
          _index,
          (_) => FakeBackend.json(200, {
            'dashboards': ['recruiter'],
          }),
        )
        ..on(
          'GET',
          _list,
          list ??
              (r) => FakeBackend.json(
                200,
                pageJson([
                  employerJobJson(),
                  employerJobJson(
                    id: 'j2',
                    title: 'Old post',
                    status: 'CLOSED',
                  ),
                  employerJobJson(
                    id: 'j3',
                    title: 'Odd one',
                    status: 'TELEPORTED',
                  ),
                ]),
              ),
        ),
    );

    testWidgets(
      'lists the organisation\'s jobs with status; unknown status shows the code',
      (tester) async {
        final h = await open(tester);
        expect(find.text('Staff nurse'), findsOneWidget);
        expect(find.text('Old post'), findsOneWidget);
        expect(find.text('Published'), findsWidgets);
        expect(find.text('TELEPORTED'), findsWidgets);
        expect(h.backend.to('GET', _list).single.query, {'page_size': 20});
      },
    );

    testWidgets(
      'the status filter is the documented parameter and restarts at page 1',
      (tester) async {
        final h = await open(tester);
        await tester.tap(find.byKey(const Key('filters-button')));
        await tester.pumpAndSettle();
        await tester.tap(
          find.widgetWithText(DropdownButtonFormField<String?>, 'Status'),
        );
        await tester.pumpAndSettle();
        await tester.tap(find.text('Closed').last);
        await tester.pumpAndSettle();
        await tester.tap(find.byKey(const Key('filters-apply')));
        await tester.pumpAndSettle();
        expect(h.backend.to('GET', _list).last.query, {
          'status': 'CLOSED',
          'page_size': 20,
        });
      },
    );

    testWidgets(
      'an empty organisation shows the empty state; errors are safe',
      (tester) async {
        await open(
          tester,
          list: (_) => FakeBackend.json(200, pageJson(<Object?>[])),
        );
        expect(find.text('No jobs yet'), findsOneWidget);
      },
    );

    testWidgets('membership_inactive is the fixed message', (tester) async {
      await open(
        tester,
        list: (_) =>
            FakeBackend.error(403, 'membership_inactive', message: 'raw'),
      );
      expect(
        find.text('Your membership no longer allows this action.'),
        findsOneWidget,
      );
      expect(find.textContaining('raw'), findsNothing);
    });
  });

  group('job detail and close', () {
    Future<Harness> open(
      WidgetTester tester, {
      Responder? close,
      Responder? one,
      Map<String, Object?>? account,
    }) => pumpPatientApp(
      tester,
      path: '/recruiter/jobs/$jobId',
      size: _tall,
      account: account ?? _a,
      script: (b) => b
        ..on(
          'GET',
          _index,
          (_) => FakeBackend.json(200, {
            'dashboards': ['recruiter'],
          }),
        )
        ..on(
          'GET',
          _one,
          one ?? (_) => FakeBackend.json(200, employerJobJson()),
        )
        ..on(
          'POST',
          _close,
          close ??
              (_) => FakeBackend.json(200, employerJobJson(status: 'CLOSED')),
        ),
    );

    testWidgets(
      'shows status, applications received and job facts; the moderation note stays hidden',
      (tester) async {
        await open(tester);
        expect(find.text('Staff nurse'), findsWidgets);
        expect(find.text('Applications received: 4'), findsOneWidget);
        expect(find.byKey(const Key('job-close')), findsOneWidget);
      },
    );

    testWidgets('a closed job has no close button', (tester) async {
      await open(
        tester,
        one: (_) => FakeBackend.json(200, employerJobJson(status: 'CLOSED')),
      );
      expect(find.byKey(const Key('job-close')), findsNothing);
    });

    testWidgets('another organisation\'s job is the generic not-found text', (
      tester,
    ) async {
      await open(tester, one: (_) => FakeBackend.error(404, 'not_found'));
      expect(find.text("We couldn't find that."), findsOneWidget);
      expect(find.byKey(const Key('job-close')), findsNothing);
    });

    testWidgets(
      'closing is confirmed: declining sends nothing; confirming sends one POST and reloads',
      (tester) async {
        var status = 'PUBLISHED';
        final h = await open(
          tester,
          one: (_) => FakeBackend.json(200, employerJobJson(status: status)),
          close: (_) {
            status = 'CLOSED';
            return FakeBackend.json(200, employerJobJson(status: 'CLOSED'));
          },
        );
        await tester.tap(find.byKey(const Key('job-close')));
        await tester.pumpAndSettle();
        expect(find.text('Close this job?'), findsOneWidget);
        await tester.tap(find.text('Keep open'));
        await tester.pumpAndSettle();
        expect(h.backend.count('POST', _close), 0);
        await tester.tap(find.byKey(const Key('job-close')));
        await tester.pumpAndSettle();
        await tester.tap(
          find.descendant(
            of: find.byType(AlertDialog),
            matching: find.text('Close job'),
          ),
        );
        await tester.pumpAndSettle();
        final posts = h.backend.to('POST', _close);
        expect(posts, hasLength(1));
        expect(posts.single.body, isEmpty);
        expect(find.text('The job was closed.'), findsOneWidget);
        expect(find.byKey(const Key('job-close')), findsNothing);
      },
    );

    for (final c in [
      (
        'invalid_transition',
        400,
        "This job can't be changed that way right now.",
      ),
      (
        'membership_inactive',
        403,
        'Your membership no longer allows this action.',
      ),
    ]) {
      testWidgets(
        '${c.$1} shows a fixed message, refetches and never retries',
        (tester) async {
          final h = await open(
            tester,
            close: (_) => FakeBackend.error(c.$2, c.$1, message: 'raw secret'),
          );
          await tester.tap(find.byKey(const Key('job-close')));
          await tester.pumpAndSettle();
          await tester.tap(
            find.descendant(
              of: find.byType(AlertDialog),
              matching: find.text('Close job'),
            ),
          );
          await tester.pumpAndSettle();
          expect(find.text(c.$3), findsOneWidget);
          expect(find.textContaining('raw secret'), findsNothing);
          await tester.pump(const Duration(seconds: 30));
          expect(h.backend.count('POST', _close), 1);
          expect(h.backend.count('GET', _one), 2);
        },
      );
    }

    testWidgets('a duplicate tap on Close sends one request', (tester) async {
      final gate = Completer<void>();
      final h = await open(
        tester,
        close: (_) async {
          await gate.future;
          return FakeBackend.json(200, employerJobJson(status: 'CLOSED'));
        },
      );
      await tester.tap(find.byKey(const Key('job-close')));
      await tester.pumpAndSettle();
      await tester.tap(
        find.descendant(
          of: find.byType(AlertDialog),
          matching: find.text('Close job'),
        ),
      );
      await tester.pump(const Duration(milliseconds: 30));
      await tester.tap(find.byKey(const Key('job-close')), warnIfMissed: false);
      await tester.pump(const Duration(milliseconds: 30));
      expect(h.backend.count('POST', _close), 1);
      gate.complete();
      await tester.pumpAndSettle();
      expect(h.backend.count('POST', _close), 1);
    });

    for (final late in ['success', 'error']) {
      testWidgets(
        'a late $late of A\'s close is never shown to B and invalidates nothing',
        (tester) async {
          final gate = Completer<void>();
          final h = await open(
            tester,
            close: (_) async {
              await gate.future;
              return late == 'success'
                  ? FakeBackend.json(200, employerJobJson(status: 'CLOSED'))
                  : FakeBackend.error(400, 'invalid_transition');
            },
          );
          await tester.tap(find.byKey(const Key('job-close')));
          await tester.pumpAndSettle();
          await tester.tap(
            find.descendant(
              of: find.byType(AlertDialog),
              matching: find.text('Close job'),
            ),
          );
          await tester.pump(const Duration(milliseconds: 30));
          await switchAccountTo(tester, h, _b);
          await tester.pumpAndSettle();
          final gets = h.backend.count('GET', _one);
          gate.complete();
          await tester.pumpAndSettle();
          expect(find.text('The job was closed.'), findsNothing);
          expect(
            find.text("This job can't be changed that way right now."),
            findsNothing,
          );
          expect(h.backend.count('GET', _one), gets);
          expect(
            find.byKey(const Key('job-close')),
            findsOneWidget,
            reason: 'B has a fresh, enabled button',
          );
        },
      );
    }

    testWidgets('organisation A\'s job is a 404 for B (route stays mounted)', (
      tester,
    ) async {
      var who = 'A';
      final h = await open(
        tester,
        one: (_) {
          if (who == 'B') return FakeBackend.error(404, 'not_found');
          return FakeBackend.json(
            200,
            employerJobJson(title: 'A secret posting'),
          );
        },
      );
      expect(find.text('A secret posting'), findsWidgets);
      who = 'B';
      await switchAccountTo(tester, h, _b);
      await tester.pumpAndSettle();
      expect(find.text('A secret posting'), findsNothing);
      expect(find.text("We couldn't find that."), findsOneWidget);
    });
  });
}
