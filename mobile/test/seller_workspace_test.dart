import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/app/router.dart';

import 'support/domain_support.dart';
import 'support/fake_backend.dart';
import 'support/patient_support.dart';
import 'support/provider_support.dart' show switchAccountTo;

const _dash = '/api/v1/real-estate/owner/dashboard';
const _own = '/api/v1/real-estate/owner/listings';
const _ownOne = '/api/v1/real-estate/owner/listings/$listingId';
const _publish = '/api/v1/real-estate/owner/listings/$listingId/publish';
const _unpublish = '/api/v1/real-estate/owner/listings/$listingId/unpublish';
const _tall = Size(800, 2400);

final Map<String, Object?> _a = sellerAccountJson(name: 'Seller A');
final Map<String, Object?> _b = sellerAccountJson(
  id: otherSellerAccountId,
  name: 'Seller B',
);

void main() {
  group('navigation and permissions', () {
    testWidgets(
      'a patient has no seller entry and the screens refuse a deep link',
      (tester) async {
        final h = await pumpPatientApp(tester, size: _tall, script: (_) {});
        expect(find.byKey(const Key('explore-real-estate')), findsOneWidget);
        expect(find.byKey(const Key('explore-seller-workspace')), findsNothing);
        h.container.read(routerProvider).go('/seller');
        await tester.pumpAndSettle();
        expect(
          find.text('This area is for property-owner accounts.'),
          findsOneWidget,
        );
        h.container.read(routerProvider).go('/seller/listings');
        await tester.pumpAndSettle();
        expect(
          find.text('This area is for property-owner accounts.'),
          findsOneWidget,
        );
        h.container.read(routerProvider).go('/seller/listings/$listingId');
        await tester.pumpAndSettle();
        expect(
          find.text('This area is for property-owner accounts.'),
          findsOneWidget,
        );
        expect(h.backend.count('GET', _dash), 0);
        expect(h.backend.count('GET', _own), 0);
        expect(h.backend.count('GET', _ownOne), 0);
      },
    );

    testWidgets(
      'a seller sees the workspace entry on Home and it opens the dashboard',
      (tester) async {
        await pumpPatientApp(
          tester,
          size: _tall,
          account: _a,
          script: (b) => b.on(
            'GET',
            _dash,
            (_) => FakeBackend.json(200, ownerDashboardJson()),
          ),
        );
        expect(
          find.byKey(const Key('explore-seller-workspace')),
          findsOneWidget,
        );
        await tester.tap(find.byKey(const Key('explore-seller-workspace')));
        await tester.pumpAndSettle();
        expect(find.byKey(const Key('seller-counts')), findsOneWidget);
      },
    );

    testWidgets('losing the capability on a /me refresh replaces the screen', (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: '/seller',
        size: _tall,
        account: _a,
        script: (b) => b.on(
          'GET',
          _dash,
          (_) => FakeBackend.json(200, ownerDashboardJson()),
        ),
      );
      expect(find.byKey(const Key('seller-counts')), findsOneWidget);
      await switchAccountTo(
        tester,
        h,
        sellerAccountJson(permissions: ['accounts.view_self']),
      );
      await tester.pumpAndSettle();
      expect(
        find.text('This area is for property-owner accounts.'),
        findsOneWidget,
      );
      expect(find.byKey(const Key('seller-counts')), findsNothing);
    });
  });

  group('dashboard', () {
    testWidgets('shows exactly the counts the backend computed', (
      tester,
    ) async {
      await pumpPatientApp(
        tester,
        path: '/seller',
        size: _tall,
        account: _a,
        script: (b) => b.on(
          'GET',
          _dash,
          (_) => FakeBackend.json(200, ownerDashboardJson()),
        ),
      );
      Finder row(String label, String value) => find.descendant(
        of: find.byKey(const Key('seller-counts')),
        matching: find.text(value),
      );
      expect(find.text('Total listings'), findsOneWidget);
      expect(row('Total listings', '6'), findsOneWidget);
      expect(find.text('Visible to the public'), findsOneWidget);
      expect(find.textContaining('views'), findsNothing);
      expect(find.textContaining('Revenue'), findsNothing);
    });

    testWidgets(
      'failure shows a safe message; retry recovers; 403 explains the missing profile',
      (tester) async {
        var fail = true;
        await pumpPatientApp(
          tester,
          path: '/seller',
          size: _tall,
          account: _a,
          script: (b) => b.on(
            'GET',
            _dash,
            (_) => fail
                ? FakeBackend.error(500, 'server_error', message: 'Traceback')
                : FakeBackend.json(200, ownerDashboardJson()),
          ),
        );
        expect(find.textContaining('Traceback'), findsNothing);
        fail = false;
        await tester.tap(find.text('Try again'));
        await tester.pumpAndSettle();
        expect(find.byKey(const Key('seller-counts')), findsOneWidget);
      },
    );

    testWidgets('no seller profile (403) gets the guidance text', (
      tester,
    ) async {
      await pumpPatientApp(
        tester,
        path: '/seller',
        size: _tall,
        account: _a,
        script: (b) => b.on(
          'GET',
          _dash,
          (_) => FakeBackend.error(403, 'permission_denied'),
        ),
      );
      expect(
        find.text(
          'Create your seller profile on the Racheeta website to use this area.',
        ),
        findsOneWidget,
      );
    });
  });

  group('own listings', () {
    testWidgets(
      'lists the owner\'s listings with the backend\'s status, visibility and expiry',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          path: '/seller/listings',
          size: _tall,
          account: _a,
          script: (b) => b.on(
            'GET',
            _own,
            (_) => FakeBackend.json(
              200,
              pageJson([
                ownerListingJson(
                  id: 'l1',
                  title: 'Published one',
                  status: 'PUBLISHED',
                  isPublic: true,
                ),
                ownerListingJson(
                  id: 'l2',
                  title: 'Expired one',
                  status: 'PUBLISHED',
                  isExpired: true,
                ),
                ownerListingJson(id: 'l3', title: 'Draft one'),
              ]),
            ),
          ),
        );
        expect(find.text('Published one'), findsOneWidget);
        expect(find.text('Draft'), findsOneWidget);
        expect(find.text('Visible'), findsOneWidget);
        expect(find.text('Expired'), findsOneWidget);
        expect(h.backend.to('GET', _own).single.query['page_size'], 20);
      },
    );

    testWidgets('empty state, pagination and failure', (tester) async {
      await pumpPatientApp(
        tester,
        path: '/seller/listings',
        size: _tall,
        account: _a,
        script: (b) => b.on('GET', _own, (r) {
          if (r.query['page'] == 2) {
            return FakeBackend.json(
              200,
              pageJson([
                ownerListingJson(id: 'l2', title: 'Second listing'),
              ], count: 2),
            );
          }
          return FakeBackend.json(
            200,
            pageJson(
              [ownerListingJson(title: 'First listing')],
              count: 2,
              next: 'https://api.test/x?page=2',
            ),
          );
        }),
      );
      await tester.tap(find.text('Load more'));
      await tester.pumpAndSettle();
      expect(find.text('First listing'), findsOneWidget);
      expect(find.text('Second listing'), findsOneWidget);
    });

    testWidgets('an empty list explains where listings are created', (
      tester,
    ) async {
      await pumpPatientApp(
        tester,
        path: '/seller/listings',
        size: _tall,
        account: _a,
        script: (b) => b.on(
          'GET',
          _own,
          (_) => FakeBackend.json(200, pageJson(<Object?>[])),
        ),
      );
      expect(find.text('You have no listings yet'), findsOneWidget);
    });
  });

  group('publish and unpublish', () {
    Future<Harness> open(
      WidgetTester tester, {
      String status = 'DRAFT',
      Responder? onPublish,
      Responder? onUnpublish,
    }) {
      var current = status;
      return pumpPatientApp(
        tester,
        path: '/seller/listings/$listingId',
        size: _tall,
        account: _a,
        script: (b) {
          b
            ..on(
              'GET',
              _ownOne,
              (_) => FakeBackend.json(
                200,
                ownerListingJson(
                  status: current,
                  isPublic: current == 'PUBLISHED',
                ),
              ),
            )
            ..on(
              'GET',
              _own,
              (_) => FakeBackend.json(
                200,
                pageJson([ownerListingJson(status: current)]),
              ),
            )
            ..on(
              'GET',
              _dash,
              (_) => FakeBackend.json(200, ownerDashboardJson()),
            )
            ..on('POST', _publish, (r) {
              if (onPublish != null) return onPublish(r);
              current = 'PUBLISHED';
              return FakeBackend.json(
                200,
                ownerListingJson(status: 'PUBLISHED', isPublic: true),
              );
            })
            ..on('POST', _unpublish, (r) {
              if (onUnpublish != null) return onUnpublish(r);
              current = 'DRAFT';
              return FakeBackend.json(200, ownerListingJson(status: 'DRAFT'));
            });
        },
      );
    }

    testWidgets(
      'a draft offers Publish only; one POST without a body, then reload from the backend',
      (tester) async {
        final h = await open(tester);
        expect(find.byKey(const Key('listing-publish')), findsOneWidget);
        expect(find.byKey(const Key('listing-unpublish')), findsNothing);
        await tester.tap(find.byKey(const Key('listing-publish')));
        await tester.pumpAndSettle();
        final posts = h.backend.to('POST', _publish);
        expect(posts, hasLength(1));
        expect(posts.single.body, isNull);
        expect(find.text('The listing was published.'), findsOneWidget);
        expect(h.backend.count('GET', _ownOne), 2, reason: 'detail refetched');
        expect(find.byKey(const Key('listing-unpublish')), findsOneWidget);
        expect(find.byKey(const Key('listing-publish')), findsNothing);
      },
    );

    testWidgets(
      'a published listing offers Unpublish behind a confirmation; declining sends nothing',
      (tester) async {
        final h = await open(tester, status: 'PUBLISHED');
        await tester.tap(find.byKey(const Key('listing-unpublish')));
        await tester.pumpAndSettle();
        expect(find.text('Unpublish this listing?'), findsOneWidget);
        await tester.tap(find.text('Keep published'));
        await tester.pumpAndSettle();
        expect(h.backend.count('POST', _unpublish), 0);

        await tester.tap(find.byKey(const Key('listing-unpublish')));
        await tester.pumpAndSettle();
        await tester.tap(
          find.descendant(
            of: find.byType(AlertDialog),
            matching: find.text('Unpublish'),
          ),
        );
        await tester.pumpAndSettle();
        expect(h.backend.count('POST', _unpublish), 1);
        expect(find.text('The listing was unpublished.'), findsOneWidget);
      },
    );

    testWidgets(
      'a duplicate tap while publishing sends ONE request and shows progress',
      (tester) async {
        final gate = Completer<void>();
        final h = await open(
          tester,
          onPublish: (_) async {
            await gate.future;
            return FakeBackend.json(200, ownerListingJson(status: 'PUBLISHED'));
          },
        );
        await tester.tap(find.byKey(const Key('listing-publish')));
        await tester.pump(const Duration(milliseconds: 30));
        expect(find.text('Publishing…'), findsOneWidget);
        expect(find.byType(CircularProgressIndicator), findsOneWidget);
        await tester.tap(find.text('Publishing…'), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 30));
        expect(h.backend.count('POST', _publish), 1);
        gate.complete();
        await tester.pumpAndSettle();
        expect(h.backend.count('POST', _publish), 1);
      },
    );

    for (final c in [
      (
        'validation_error',
        400,
        "This listing can't be published yet. Complete it on the Racheeta website.",
      ),
      (
        'seller_not_eligible',
        403,
        "Your account can't manage listings right now.",
      ),
      (
        'invalid_transition',
        400,
        "This listing can't be changed that way right now.",
      ),
    ]) {
      testWidgets(
        '${c.$1} (${c.$2}) shows its fixed message, never the raw text, and is not retried',
        (tester) async {
          final h = await open(
            tester,
            onPublish: (_) => FakeBackend.error(
              c.$2,
              c.$1,
              message: 'raw: contact_phone invalid for user 42',
              details: c.$1 == 'validation_error'
                  ? {
                      'expires_at': ['This field is required.'],
                    }
                  : null,
            ),
          );
          await tester.tap(find.byKey(const Key('listing-publish')));
          await tester.pumpAndSettle();
          expect(find.text(c.$3), findsOneWidget);
          expect(find.textContaining('user 42'), findsNothing);
          await tester.pump(const Duration(seconds: 30));
          expect(h.backend.count('POST', _publish), 1);
          expect(
            h.backend.count('GET', _ownOne),
            2,
            reason: 'the true state is refetched after a refusal',
          );
        },
      );
    }

    testWidgets('a network failure is never retried automatically', (
      tester,
    ) async {
      final h = await open(tester, onPublish: FakeBackend.networkDown);
      await tester.tap(find.byKey(const Key('listing-publish')));
      await tester.pumpAndSettle();
      expect(find.textContaining('Could not reach the server'), findsOneWidget);
      await tester.pump(const Duration(seconds: 30));
      expect(h.backend.count('POST', _publish), 1);
    });

    testWidgets(
      'a foreign listing id is the generic not-found text with no actions',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/seller/listings/$listingId',
          size: _tall,
          account: _a,
          script: (b) =>
              b.on('GET', _ownOne, (_) => FakeBackend.error(404, 'not_found')),
        );
        expect(find.text("We couldn't find that."), findsOneWidget);
        expect(find.byKey(const Key('listing-publish')), findsNothing);
      },
    );

    testWidgets(
      'the owner list, detail and dashboard are reloaded after publishing',
      (tester) async {
        var status = 'DRAFT';
        final h = await pumpPatientApp(
          tester,
          path: '/seller',
          size: _tall,
          account: _a,
          script: (b) => b
            ..on(
              'GET',
              _dash,
              (_) => FakeBackend.json(200, ownerDashboardJson()),
            )
            ..on(
              'GET',
              _own,
              (_) => FakeBackend.json(
                200,
                pageJson([ownerListingJson(status: status)]),
              ),
            )
            ..on(
              'GET',
              _ownOne,
              (_) => FakeBackend.json(200, ownerListingJson(status: status)),
            )
            ..on('POST', _publish, (_) {
              status = 'PUBLISHED';
              return FakeBackend.json(
                200,
                ownerListingJson(status: 'PUBLISHED'),
              );
            }),
        );
        final router = h.container.read(routerProvider);
        router.go('/seller/listings');
        await tester.pumpAndSettle();
        expect(h.backend.count('GET', _own), 1);
        await tester.tap(find.text('My clinic floor'));
        await tester.pumpAndSettle();
        await tester.tap(find.byKey(const Key('listing-publish')));
        await tester.pumpAndSettle();
        router.go('/seller/listings');
        await tester.pumpAndSettle();
        expect(
          h.backend.count('GET', _own),
          2,
          reason: 'the cached list was invalidated',
        );
        router.go('/seller');
        await tester.pumpAndSettle();
        expect(
          h.backend.count('GET', _dash),
          2,
          reason: 'the dashboard was invalidated',
        );
      },
    );
  });

  group(
    'account isolation (the account changes while the screen stays open)',
    () {
      testWidgets('A\'s listings never appear under B', (tester) async {
        var who = 'A';
        final gateB = Completer<void>();
        final h = await pumpPatientApp(
          tester,
          path: '/seller/listings',
          size: _tall,
          account: _a,
          script: (b) => b.on('GET', _own, (_) async {
            if (who == 'B') await gateB.future;
            return FakeBackend.json(
              200,
              pageJson([ownerListingJson(title: 'LISTING OF $who')]),
            );
          }),
        );
        expect(find.text('LISTING OF A'), findsOneWidget);
        who = 'B';
        await switchAccountTo(tester, h, _b);
        expect(
          find.text('LISTING OF A'),
          findsNothing,
          reason: 'while B is loading',
        );
        gateB.complete();
        await tester.pumpAndSettle();
        expect(find.text('LISTING OF A'), findsNothing);
        expect(find.text('LISTING OF B'), findsOneWidget);
      });

      testWidgets('A\'s dashboard counts never appear under B', (tester) async {
        var who = 'A';
        final gateB = Completer<void>();
        final h = await pumpPatientApp(
          tester,
          path: '/seller',
          size: _tall,
          account: _a,
          script: (b) => b.on('GET', _dash, (_) async {
            if (who == 'B') await gateB.future;
            return FakeBackend.json(200, {
              ...ownerDashboardJson(),
              'listings_total': who == 'A' ? 111 : 222,
            });
          }),
        );
        expect(find.text('111'), findsOneWidget);
        who = 'B';
        await switchAccountTo(tester, h, _b);
        expect(find.text('111'), findsNothing);
        gateB.complete();
        await tester.pumpAndSettle();
        expect(find.text('222'), findsOneWidget);
      });

      testWidgets('A\'s open listing and its publish button never reach B', (
        tester,
      ) async {
        var who = 'A';
        final gateB = Completer<void>();
        final h = await pumpPatientApp(
          tester,
          path: '/seller/listings/$listingId',
          size: _tall,
          account: _a,
          script: (b) => b.on('GET', _ownOne, (_) async {
            if (who == 'B') {
              await gateB.future;
              return FakeBackend.error(404, 'not_found');
            }
            return FakeBackend.json(
              200,
              ownerListingJson(title: 'SECRET LISTING OF A'),
            );
          }),
        );
        expect(find.text('SECRET LISTING OF A'), findsWidgets);
        who = 'B';
        await switchAccountTo(tester, h, _b);
        expect(find.text('SECRET LISTING OF A'), findsNothing);
        expect(find.byKey(const Key('listing-publish')), findsNothing);
        gateB.complete();
        await tester.pumpAndSettle();
        expect(find.text("We couldn't find that."), findsOneWidget);
        expect(h.backend.count('POST', _publish), 0);
      });

      testWidgets(
        'a late success of A\'s publish is never shown to B and invalidates nothing',
        (tester) async {
          final gate = Completer<void>();
          var who = 'A';
          final h = await pumpPatientApp(
            tester,
            path: '/seller/listings/$listingId',
            size: _tall,
            account: _a,
            script: (b) => b
              ..on('GET', _ownOne, (_) {
                if (who == 'B') return FakeBackend.error(404, 'not_found');
                return FakeBackend.json(200, ownerListingJson());
              })
              ..on('POST', _publish, (_) async {
                await gate.future;
                return FakeBackend.json(
                  200,
                  ownerListingJson(status: 'PUBLISHED'),
                );
              }),
          );
          await tester.tap(find.byKey(const Key('listing-publish')));
          await tester.pump(const Duration(milliseconds: 30));
          who = 'B';
          await switchAccountTo(tester, h, _b);
          await tester.pumpAndSettle();
          final gets = h.backend.count('GET', _ownOne);
          gate.complete();
          await tester.pumpAndSettle();
          expect(find.text('The listing was published.'), findsNothing);
          expect(h.backend.count('GET', _ownOne), gets);
        },
      );

      testWidgets('a late error of A\'s publish is never shown to B', (
        tester,
      ) async {
        final gate = Completer<void>();
        var who = 'A';
        final h = await pumpPatientApp(
          tester,
          path: '/seller/listings/$listingId',
          size: _tall,
          account: _a,
          script: (b) => b
            ..on('GET', _ownOne, (_) {
              if (who == 'B') return FakeBackend.error(404, 'not_found');
              return FakeBackend.json(200, ownerListingJson());
            })
            ..on('POST', _publish, (_) async {
              await gate.future;
              return FakeBackend.error(400, 'validation_error');
            }),
        );
        await tester.tap(find.byKey(const Key('listing-publish')));
        await tester.pump(const Duration(milliseconds: 30));
        who = 'B';
        await switchAccountTo(tester, h, _b);
        await tester.pumpAndSettle();
        gate.complete();
        await tester.pumpAndSettle();
        expect(find.textContaining("can't be published yet"), findsNothing);
        expect(find.byKey(const Key('listing-message')), findsNothing);
      });
    },
  );

  group('Arabic', () {
    testWidgets('the seller workspace renders right-to-left', (tester) async {
      await pumpPatientApp(
        tester,
        path: '/seller',
        size: const Size(360, 780),
        language: 'ar',
        account: _a,
        script: (b) => b.on(
          'GET',
          _dash,
          (_) => FakeBackend.json(200, ownerDashboardJson()),
        ),
      );
      expect(find.text('مالك العقار'), findsWidgets);
      expect(find.text('إجمالي الإعلانات'), findsOneWidget);
      expect(
        Directionality.of(tester.element(find.text('إجمالي الإعلانات'))),
        TextDirection.rtl,
      );
      expect(tester.takeException(), isNull);
    });
  });
}
