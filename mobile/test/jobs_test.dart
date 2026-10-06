import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/core/paging/paged_notifier.dart';
import 'package:racheeta_mobile/features/jobs/application/jobs_providers.dart';
import 'package:racheeta_mobile/shared/search/search_query.dart';

import 'support/domain_support.dart';
import 'support/fake_backend.dart';
import 'support/patient_support.dart';
import 'support/provider_support.dart' show switchAccountTo;

const _jobs = '/api/v1/jobs';
const _job = '/api/v1/jobs/$jobId';
const _apply = '/api/v1/jobs/$jobId/apply';
const _mine = '/api/v1/jobs/me/applications';
const _withdraw = '/api/v1/jobs/me/applications/$applicationId/withdraw';
const _tall = Size(800, 2400);
const _phone = Size(360, 780);

void _govs(FakeBackend b) => b.on(
  'GET',
  '/api/v1/geo/governorates',
  (_) => FakeBackend.json(200, [
    {
      'id': 'g1',
      'slug': 'baghdad',
      'name_ar': 'بغداد',
      'name_en': 'Baghdad',
      'country': 'x',
    },
  ]),
);

void main() {
  group('navigation', () {
    testWidgets(
      'everyone sees Jobs; the recruiter entry needs the server to list it',
      (tester) async {
        await pumpPatientApp(
          tester,
          size: _tall,
          script: (b) => b.on(
            'GET',
            '/api/v1/dashboards/',
            (_) => FakeBackend.json(200, {
              'dashboards': ['patient'],
            }),
          ),
        );
        expect(find.byKey(const Key('explore-jobs')), findsOneWidget);
        expect(
          find.byKey(const Key('explore-recruiter-workspace')),
          findsNothing,
        );
      },
    );

    testWidgets(
      'an account the server lists as a recruiter gets the recruiter entry',
      (tester) async {
        await pumpPatientApp(
          tester,
          size: _tall,
          account: recruiterAccountJson(),
          script: (b) => b.on(
            'GET',
            '/api/v1/dashboards/',
            (_) => FakeBackend.json(200, {
              'dashboards': ['doctor', 'recruiter'],
            }),
          ),
        );
        expect(
          find.byKey(const Key('explore-recruiter-workspace')),
          findsOneWidget,
        );
      },
    );
  });

  group('job search', () {
    testWidgets(
      'lists jobs with employer, vocabulary labels, place, salary and the deadline DATE',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: '/jobs',
          size: _tall,
          script: (b) => b.on(
            'GET',
            _jobs,
            (_) => FakeBackend.json(
              200,
              pageJson([
                jobCardJson(featured: true),
                jobCardJson(
                  id: 'j2',
                  title: 'Hidden pay',
                  salaryVisible: false,
                ),
              ]),
            ),
          ),
        );
        expect(find.text('Staff nurse'), findsOneWidget);
        expect(find.text('Al Noor Hospital'), findsWidgets);
        expect(find.text('Nurse · Full time · On site'), findsWidgets);
        expect(find.text('1,200,000 – 1,800,000 IQD'), findsOneWidget);
        expect(find.text('Featured'), findsOneWidget);
        // a calendar date is shown as the same day regardless of the time zone
        expect(find.textContaining('Oct 5, 2026'), findsWidgets);
        // salary the backend marks hidden is never shown
        expect(find.text('Hidden pay'), findsOneWidget);
        expect(find.textContaining('IQD'), findsOneWidget);
        expect(h.backend.to('GET', _jobs).single.query, {'page_size': 20});
      },
    );

    testWidgets('unknown future vocabulary codes render as the raw code', (
      tester,
    ) async {
      await pumpPatientApp(
        tester,
        path: '/jobs',
        size: _tall,
        script: (b) => b.on(
          'GET',
          _jobs,
          (_) => FakeBackend.json(
            200,
            pageJson([
              jobCardJson(
                profession: 'ASTRONAUT',
                employment: 'GIG',
                workMode: 'ORBITAL',
              ),
            ]),
          ),
        ),
      );
      expect(find.text('ASTRONAUT · GIG · ORBITAL'), findsOneWidget);
    });

    testWidgets(
      'search is debounced and sent as `q`; filters are the documented parameters',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: '/jobs',
          size: _tall,
          script: (b) {
            _govs(b);
            b.on(
              'GET',
              _jobs,
              (_) => FakeBackend.json(
                200,
                pageJson(
                  [jobCardJson()],
                  count: 40,
                  next: 'https://api.test/x?page=2',
                ),
              ),
            );
          },
        );
        await tester.enterText(find.byKey(const Key('search-field')), 'icu');
        await tester.pump(const Duration(milliseconds: 100));
        expect(h.backend.count('GET', _jobs), 1, reason: 'still debouncing');
        await tester.pump(const Duration(milliseconds: 500));
        await tester.pumpAndSettle();
        expect(h.backend.to('GET', _jobs).last.query, {
          'q': 'icu',
          'page_size': 20,
        });

        await tester.tap(find.byKey(const Key('filters-button')));
        await tester.pumpAndSettle();
        Future<void> pick(String label, String option) async {
          await tester.tap(
            find.widgetWithText(DropdownButtonFormField<String?>, label),
          );
          await tester.pumpAndSettle();
          await tester.tap(find.text(option).last);
          await tester.pumpAndSettle();
        }

        await pick('Profession', 'Nurse');
        await pick('Employment type', 'Full time');
        await pick('Work mode', 'Remote');
        await pick('Governorate', 'Baghdad');
        await tester.tap(find.byKey(const Key('filters-apply')));
        await tester.pumpAndSettle();
        final query = h.backend.to('GET', _jobs).last.query;
        expect(query, {
          'q': 'icu',
          'profession': 'NURSE',
          'employment_type': 'FULL_TIME',
          'work_mode': 'REMOTE',
          'governorate': 'g1',
          'page_size': 20,
        });
        expect(
          query.containsKey('page'),
          isFalse,
          reason: 'a new query restarts at page 1',
        );
      },
    );

    testWidgets(
      'pagination keeps items when a page fails; empty and error states are safe',
      (tester) async {
        var fail = true;
        await pumpPatientApp(
          tester,
          path: '/jobs',
          size: _tall,
          script: (b) => b.on('GET', _jobs, (r) {
            if (r.query['page'] == 2) {
              return fail
                  ? FakeBackend.error(500, 'server_error')
                  : FakeBackend.json(
                      200,
                      pageJson([
                        jobCardJson(id: 'j2', title: 'Second job'),
                      ], count: 2),
                    );
            }
            return FakeBackend.json(
              200,
              pageJson(
                [jobCardJson(title: 'First job')],
                count: 2,
                next: 'https://api.test/x?page=2',
              ),
            );
          }),
        );
        await tester.tap(find.text('Load more'));
        await tester.pumpAndSettle();
        expect(find.text('Could not load more results.'), findsOneWidget);
        expect(find.text('First job'), findsOneWidget);
        fail = false;
        await tester.tap(find.text('Load more'));
        await tester.pumpAndSettle();
        expect(find.text('Second job'), findsOneWidget);
      },
    );

    testWidgets(
      'an empty result offers to clear the filters; a server error is safe',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: '/jobs',
          size: _tall,
          script: (b) => b.on(
            'GET',
            _jobs,
            (r) => FakeBackend.json(
              200,
              pageJson(
                r.query.containsKey('profession')
                    ? <Object?>[]
                    : [jobCardJson()],
              ),
            ),
          ),
        );
        h.container
            .read(jobQueryProvider.notifier)
            .update(const SearchQuery(filters: {'profession': 'DENTIST'}));
        await tester.pumpAndSettle();
        expect(find.text('No jobs found'), findsOneWidget);
        await tester.tap(find.text('Clear filters'));
        await tester.pumpAndSettle();
        expect(find.text('Staff nurse'), findsOneWidget);
      },
    );

    testWidgets('a failure is safe and retry recovers', (tester) async {
      var fail = true;
      await pumpPatientApp(
        tester,
        path: '/jobs',
        size: _tall,
        script: (b) => b.on(
          'GET',
          _jobs,
          (_) => fail
              ? FakeBackend.error(500, 'server_error', message: 'Traceback')
              : FakeBackend.json(200, pageJson([jobCardJson()])),
        ),
      );
      expect(find.textContaining('Traceback'), findsNothing);
      fail = false;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.text('Staff nurse'), findsOneWidget);
    });

    testWidgets(
      'a slow answer for an older query can never replace newer results',
      (tester) async {
        final slow = Completer<void>();
        final h = await pumpPatientApp(
          tester,
          path: '/jobs',
          size: _tall,
          script: (b) => b.on('GET', _jobs, (r) async {
            if (r.query['q'] == 'old') {
              await slow.future;
              return FakeBackend.json(
                200,
                pageJson([jobCardJson(title: 'OLD RESULT')]),
              );
            }
            return FakeBackend.json(
              200,
              pageJson([jobCardJson(title: 'NEW RESULT')]),
            );
          }),
        );
        final q = h.container.read(jobQueryProvider.notifier);
        q.update(const SearchQuery(search: 'old'));
        await tester.pump(const Duration(milliseconds: 50));
        q.update(const SearchQuery(search: 'new'));
        await tester.pump(const Duration(milliseconds: 50));
        slow.complete();
        await tester.pumpAndSettle();
        final state = h.container.read(jobsProvider);
        expect(state.phase, PagedPhase.ready);
        expect(state.items.map((j) => j.title), ['NEW RESULT']);
      },
    );

    testWidgets('the search form is reset when the account changes', (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: '/jobs',
        size: _tall,
        script: (b) => b.on(
          'GET',
          _jobs,
          (_) => FakeBackend.json(200, pageJson([jobCardJson()])),
        ),
      );
      h.container
          .read(jobQueryProvider.notifier)
          .update(
            const SearchQuery(
              search: 'private',
              filters: {'profession': 'NURSE'},
            ),
          );
      await tester.pumpAndSettle();
      await switchAccountTo(
        tester,
        h,
        accountJson(
          id: '99999999-9999-4999-8999-999999999999',
          name: 'Patient B',
        ),
      );
      await tester.pumpAndSettle();
      expect(h.container.read(jobQueryProvider), const SearchQuery());
    });

    testWidgets('Arabic right-to-left at phone width', (tester) async {
      await pumpPatientApp(
        tester,
        path: '/jobs',
        size: _phone,
        language: 'ar',
        script: (b) => b.on(
          'GET',
          _jobs,
          (_) => FakeBackend.json(200, pageJson([jobCardJson()])),
        ),
      );
      expect(find.text('ممرض · دوام كامل · في الموقع'), findsOneWidget);
      expect(find.text('الوظائف'), findsWidgets);
      expect(
        Directionality.of(
          tester.element(find.text('ممرض · دوام كامل · في الموقع')),
        ),
        TextDirection.rtl,
      );
      expect(tester.takeException(), isNull);
    });
  });

  group('job detail', () {
    testWidgets(
      'shows the public fields and the internal application form (no external link)',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/jobs/$jobId',
          size: _tall,
          script: (b) =>
              b.on('GET', _job, (_) => FakeBackend.json(200, jobPublicJson())),
        );
        expect(find.text('Staff nurse'), findsWidgets);
        expect(find.byKey(const Key('job-salary')), findsOneWidget);
        expect(find.text('Care for patients in the ICU.'), findsOneWidget);
        expect(find.text('Monitor vitals.'), findsOneWidget);
        expect(find.text('Valid licence.'), findsOneWidget);
        expect(find.text('2 years'), findsOneWidget);
        expect(find.byKey(const Key('apply-submit')), findsOneWidget);
      },
    );

    testWidgets(
      'a job that is not open shows a notice and no form; an unknown job is the generic text',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/jobs/$jobId',
          size: _tall,
          script: (b) => b.on(
            'GET',
            _job,
            (_) => FakeBackend.json(200, jobPublicJson(isOpen: false)),
          ),
        );
        expect(find.byKey(const Key('job-closed')), findsOneWidget);
        expect(find.byKey(const Key('apply-submit')), findsNothing);
      },
    );

    testWidgets('a hidden job is the generic not-found text', (tester) async {
      await pumpPatientApp(
        tester,
        path: '/jobs/$jobId',
        size: _tall,
        script: (b) =>
            b.on('GET', _job, (_) => FakeBackend.error(404, 'not_found')),
      );
      expect(find.text("We couldn't find that."), findsOneWidget);
    });

    testWidgets('renders Arabic right-to-left', (tester) async {
      await pumpPatientApp(
        tester,
        path: '/jobs/$jobId',
        size: _phone,
        language: 'ar',
        script: (b) =>
            b.on('GET', _job, (_) => FakeBackend.json(200, jobPublicJson())),
      );
      expect(find.text('المسؤوليات'), findsOneWidget);
      expect(find.text('إرسال الطلب'), findsOneWidget);
      expect(
        Directionality.of(tester.element(find.text('المسؤوليات'))),
        TextDirection.rtl,
      );
    });
  });

  group('applying', () {
    Future<Harness> open(WidgetTester tester, {Responder? apply}) =>
        pumpPatientApp(
          tester,
          path: '/jobs/$jobId',
          size: _tall,
          script: (b) => b
            ..on('GET', _job, (_) => FakeBackend.json(200, jobPublicJson()))
            ..on(
              'GET',
              _mine,
              (_) => FakeBackend.json(200, pageJson([applicationJson()])),
            )
            ..on(
              'POST',
              _apply,
              apply ?? (_) => FakeBackend.json(201, applicationJson()),
            ),
        );

    testWidgets(
      'one POST with the trimmed note, then the success state; the form is replaced',
      (tester) async {
        final h = await open(tester);
        await tester.enterText(
          find.byKey(const Key('apply-cover')),
          '  I would like to join.  ',
        );
        await tester.tap(find.byKey(const Key('apply-submit')));
        await tester.pumpAndSettle();
        final posts = h.backend.to('POST', _apply);
        expect(posts, hasLength(1));
        expect(posts.single.body, {'cover_text': 'I would like to join.'});
        expect(find.text('Your application was sent.'), findsOneWidget);
        expect(
          find.byKey(const Key('apply-submit')),
          findsNothing,
          reason: 'nothing left to send',
        );
        expect(find.byKey(const Key('apply-view-mine')), findsOneWidget);
      },
    );

    testWidgets('an empty note sends no cover_text', (tester) async {
      final h = await open(tester);
      await tester.tap(find.byKey(const Key('apply-submit')));
      await tester.pumpAndSettle();
      expect(h.backend.to('POST', _apply).single.body, isEmpty);
    });

    testWidgets('a note over 2000 characters is blocked before any request', (
      tester,
    ) async {
      final h = await open(tester);
      await tester.enterText(find.byKey(const Key('apply-cover')), 'x' * 2001);
      await tester.tap(find.byKey(const Key('apply-submit')));
      await tester.pumpAndSettle();
      expect(
        find.text('The note must be at most 2000 characters.'),
        findsOneWidget,
      );
      expect(h.backend.count('POST', _apply), 0);
    });

    testWidgets('a duplicate tap sends ONE request and shows progress', (
      tester,
    ) async {
      final gate = Completer<void>();
      final h = await open(
        tester,
        apply: (_) async {
          await gate.future;
          return FakeBackend.json(201, applicationJson());
        },
      );
      await tester.tap(find.byKey(const Key('apply-submit')));
      await tester.pump(const Duration(milliseconds: 30));
      expect(find.text('Sending…'), findsOneWidget);
      await tester.tap(find.text('Sending…'), warnIfMissed: false);
      await tester.pump(const Duration(milliseconds: 30));
      expect(h.backend.count('POST', _apply), 1);
      gate.complete();
      await tester.pumpAndSettle();
      expect(h.backend.count('POST', _apply), 1);
    });

    for (final c in [
      ('already_applied', 409, 'You have already applied to this job.'),
      ('job_not_open', 409, 'This job is no longer open for applications.'),
      ('deadline_passed', 409, 'The application deadline has passed.'),
      (
        'contact_information_not_allowed',
        400,
        'Remove phone numbers, e-mail addresses and links from the note.',
      ),
      (
        'entitlement_required',
        403,
        "Your plan doesn't allow more applications right now.",
      ),
      (
        'usage_limit_reached',
        403,
        "Your plan doesn't allow more applications right now.",
      ),
      (
        'permission_denied',
        403,
        'Create your professional profile on the Racheeta website to apply.',
      ),
    ]) {
      testWidgets(
        '${c.$1} (${c.$2}) shows its fixed message, never the raw text, and is not retried',
        (tester) async {
          final h = await open(
            tester,
            apply: (_) => FakeBackend.error(
              c.$2,
              c.$1,
              message: 'raw: applicant 42 phone 0770',
            ),
          );
          await tester.tap(find.byKey(const Key('apply-submit')));
          await tester.pumpAndSettle();
          expect(find.text(c.$3), findsOneWidget);
          expect(find.textContaining('applicant 42'), findsNothing);
          await tester.pump(const Duration(seconds: 30));
          expect(h.backend.count('POST', _apply), 1);
          if (c.$1 == 'already_applied') {
            expect(
              find.byKey(const Key('apply-submit')),
              findsNothing,
              reason: 'the backend says it was already sent',
            );
          } else {
            expect(find.byKey(const Key('apply-submit')), findsOneWidget);
          }
        },
      );
    }

    testWidgets('a network failure is never retried automatically', (
      tester,
    ) async {
      final h = await open(tester, apply: FakeBackend.networkDown);
      await tester.tap(find.byKey(const Key('apply-submit')));
      await tester.pumpAndSettle();
      expect(find.textContaining('Could not reach the server'), findsOneWidget);
      await tester.pump(const Duration(seconds: 30));
      expect(h.backend.count('POST', _apply), 1);
    });

    testWidgets(
      'A\'s note, messages and "applied" state never reach B on the same screen',
      (tester) async {
        final h = await open(
          tester,
          apply: (_) => FakeBackend.error(409, 'already_applied'),
        );
        await tester.enterText(
          find.byKey(const Key('apply-cover')),
          'private note of A',
        );
        await tester.tap(find.byKey(const Key('apply-submit')));
        await tester.pumpAndSettle();
        expect(find.byKey(const Key('apply-message')), findsOneWidget);
        await switchAccountTo(
          tester,
          h,
          accountJson(
            id: '99999999-9999-4999-8999-999999999999',
            name: 'Patient B',
          ),
        );
        await tester.pumpAndSettle();
        expect(find.byKey(const Key('apply-message')), findsNothing);
        expect(find.text('private note of A'), findsNothing);
        expect(
          find.byKey(const Key('apply-submit')),
          findsOneWidget,
          reason: 'B has not applied',
        );
      },
    );

    for (final late in ['success', 'error']) {
      testWidgets(
        'a late $late of A\'s application is never shown to B and invalidates nothing',
        (tester) async {
          final gate = Completer<void>();
          final h = await open(
            tester,
            apply: (_) async {
              await gate.future;
              return late == 'success'
                  ? FakeBackend.json(201, applicationJson())
                  : FakeBackend.error(409, 'job_not_open');
            },
          );
          await tester.tap(find.byKey(const Key('apply-submit')));
          await tester.pump(const Duration(milliseconds: 30));
          await switchAccountTo(
            tester,
            h,
            accountJson(
              id: '99999999-9999-4999-8999-999999999999',
              name: 'Patient B',
            ),
          );
          await tester.pumpAndSettle();
          final mineBefore = h.backend.count('GET', _mine);
          gate.complete();
          await tester.pumpAndSettle();
          expect(find.text('Your application was sent.'), findsNothing);
          expect(
            find.text('This job is no longer open for applications.'),
            findsNothing,
          );
          expect(find.byKey(const Key('apply-submit')), findsOneWidget);
          expect(h.backend.count('GET', _mine), mineBefore);
        },
      );
    }
  });

  group('my applications', () {
    Future<Harness> open(
      WidgetTester tester, {
      Responder? onWithdraw,
      List<Map<String, Object?>>? items,
    }) {
      return pumpPatientApp(
        tester,
        path: '/jobs/applications',
        size: _tall,
        script: (b) => b
          ..on(
            'GET',
            _mine,
            (_) =>
                FakeBackend.json(200, pageJson(items ?? [applicationJson()])),
          )
          ..on(
            'POST',
            _withdraw,
            onWithdraw ??
                (_) =>
                    FakeBackend.json(200, applicationJson(status: 'WITHDRAWN')),
          ),
      );
    }

    testWidgets(
      'lists applications with the backend status; the résumé snapshot is never shown',
      (tester) async {
        await open(
          tester,
          items: [
            applicationJson(),
            applicationJson(
              id: 'a2',
              status: 'ACCEPTED',
              title: 'Accepted job',
            ),
            applicationJson(
              id: 'a3',
              status: 'AWAITING_ROBOTS',
              title: 'Future status',
            ),
          ],
        );
        expect(find.byKey(Key('status-$applicationId')), findsOneWidget);
        expect(find.text('Submitted'), findsOneWidget);
        expect(find.text('Accepted'), findsOneWidget);
        expect(find.text('AWAITING_ROBOTS'), findsOneWidget);
        expect(find.textContaining('résumé data'), findsNothing);
        // only open applications can be withdrawn
        expect(find.byKey(Key('withdraw-$applicationId')), findsOneWidget);
        expect(find.byKey(const Key('withdraw-a2')), findsNothing);
        expect(find.byKey(const Key('withdraw-a3')), findsNothing);
      },
    );

    testWidgets(
      'withdrawing is confirmed; declining sends nothing; confirming sends one POST and reloads',
      (tester) async {
        final h = await open(tester);
        await tester.tap(find.byKey(Key('withdraw-$applicationId')));
        await tester.pumpAndSettle();
        expect(find.text('Withdraw this application?'), findsOneWidget);
        await tester.tap(find.text('Keep application'));
        await tester.pumpAndSettle();
        expect(h.backend.count('POST', _withdraw), 0);
        await tester.tap(find.byKey(Key('withdraw-$applicationId')));
        await tester.pumpAndSettle();
        await tester.tap(
          find.descendant(
            of: find.byType(AlertDialog),
            matching: find.text('Withdraw'),
          ),
        );
        await tester.pumpAndSettle();
        expect(h.backend.to('POST', _withdraw).single.body, isEmpty);
        expect(find.text('The application was withdrawn.'), findsOneWidget);
        expect(h.backend.count('GET', _mine), 2);
      },
    );

    testWidgets('a refused withdrawal shows a fixed message and refetches', (
      tester,
    ) async {
      final h = await open(
        tester,
        onWithdraw: (_) =>
            FakeBackend.error(400, 'invalid_transition', message: 'raw text'),
      );
      await tester.tap(find.byKey(Key('withdraw-$applicationId')));
      await tester.pumpAndSettle();
      await tester.tap(
        find.descendant(
          of: find.byType(AlertDialog),
          matching: find.text('Withdraw'),
        ),
      );
      await tester.pumpAndSettle();
      expect(
        find.text("This application can't be changed that way right now."),
        findsOneWidget,
      );
      expect(find.textContaining('raw text'), findsNothing);
      expect(h.backend.count('POST', _withdraw), 1);
      expect(h.backend.count('GET', _mine), 2);
    });

    testWidgets('empty list, and A\'s applications never appear under B', (
      tester,
    ) async {
      var who = 'A';
      final gateB = Completer<void>();
      final h = await pumpPatientApp(
        tester,
        path: '/jobs/applications',
        size: _tall,
        script: (b) => b.on('GET', _mine, (_) async {
          if (who == 'B') await gateB.future;
          return FakeBackend.json(
            200,
            pageJson([applicationJson(title: 'APPLICATION OF $who')]),
          );
        }),
      );
      expect(find.text('APPLICATION OF A'), findsOneWidget);
      who = 'B';
      await switchAccountTo(
        tester,
        h,
        accountJson(
          id: '99999999-9999-4999-8999-999999999999',
          name: 'Patient B',
        ),
      );
      expect(find.text('APPLICATION OF A'), findsNothing);
      gateB.complete();
      await tester.pumpAndSettle();
      expect(find.text('APPLICATION OF B'), findsOneWidget);
    });

    testWidgets('a late success of A\'s withdrawal is never shown to B', (
      tester,
    ) async {
      final gate = Completer<void>();
      final h = await open(
        tester,
        onWithdraw: (_) async {
          await gate.future;
          return FakeBackend.json(200, applicationJson(status: 'WITHDRAWN'));
        },
      );
      await tester.tap(find.byKey(Key('withdraw-$applicationId')));
      await tester.pumpAndSettle();
      await tester.tap(
        find.descendant(
          of: find.byType(AlertDialog),
          matching: find.text('Withdraw'),
        ),
      );
      await tester.pump(const Duration(milliseconds: 30));
      await switchAccountTo(
        tester,
        h,
        accountJson(
          id: '99999999-9999-4999-8999-999999999999',
          name: 'Patient B',
        ),
      );
      await tester.pumpAndSettle();
      final gets = h.backend.count('GET', _mine);
      gate.complete();
      await tester.pumpAndSettle();
      expect(find.text('The application was withdrawn.'), findsNothing);
      expect(h.backend.count('GET', _mine), gets);
    });

    testWidgets('an empty list explains itself', (tester) async {
      await open(tester, items: const []);
      expect(find.text("You haven't applied to any job yet"), findsOneWidget);
    });
  });
}
