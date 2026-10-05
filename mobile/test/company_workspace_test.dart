import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/app/router.dart';

import 'support/domain_support.dart';
import 'support/fake_backend.dart';
import 'support/patient_support.dart';
import 'support/provider_support.dart' show switchAccountTo;

const _dash = '/api/v1/marketplace/company/dashboard';
const _own = '/api/v1/marketplace/company/products';
const _ownOne = '/api/v1/marketplace/company/products/$productId';
const _activate = '/api/v1/marketplace/company/products/$productId/activate';
const _deactivate =
    '/api/v1/marketplace/company/products/$productId/deactivate';
const _tall = Size(800, 2400);

final Map<String, Object?> _a = companyAccountJson(name: 'Company A');
final Map<String, Object?> _b = companyAccountJson(
  id: otherCompanyAccountId,
  name: 'Company B',
);

void main() {
  group('permissions', () {
    testWidgets(
      'a provider has no company entry and a deep link is refused without requests',
      (tester) async {
        final h = await pumpPatientApp(
          tester,
          size: _tall,
          account: browsingProviderJson(),
          script: (_) {},
        );
        expect(
          find.byKey(const Key('explore-company-workspace')),
          findsNothing,
        );
        h.container.read(routerProvider).go('/company');
        await tester.pumpAndSettle();
        expect(
          find.text('This area is for medical company accounts.'),
          findsOneWidget,
        );
        h.container.read(routerProvider).go('/company/products/$productId');
        await tester.pumpAndSettle();
        expect(
          find.text('This area is for medical company accounts.'),
          findsOneWidget,
        );
        expect(h.backend.count('GET', _dash), 0);
        expect(h.backend.count('GET', _own), 0);
        expect(h.backend.count('GET', _ownOne), 0);
      },
    );

    testWidgets('losing the capability on a /me refresh replaces the screen', (
      tester,
    ) async {
      final h = await pumpPatientApp(
        tester,
        path: '/company',
        size: _tall,
        account: _a,
        script: (b) => b.on(
          'GET',
          _dash,
          (_) => FakeBackend.json(200, companyDashboardJson()),
        ),
      );
      expect(find.byKey(const Key('company-counts')), findsOneWidget);
      await switchAccountTo(
        tester,
        h,
        companyAccountJson(permissions: ['accounts.view_self']),
      );
      await tester.pumpAndSettle();
      expect(
        find.text('This area is for medical company accounts.'),
        findsOneWidget,
      );
    });
  });

  group('dashboard', () {
    testWidgets('shows the backend counts, verification and publishing state', (
      tester,
    ) async {
      await pumpPatientApp(
        tester,
        path: '/company',
        size: _tall,
        account: _a,
        script: (b) => b.on(
          'GET',
          _dash,
          (_) => FakeBackend.json(200, companyDashboardJson()),
        ),
      );
      expect(find.text('Verified'), findsOneWidget);
      expect(find.text('You can publish products.'), findsOneWidget);
      expect(find.text('7'), findsOneWidget);
      expect(find.text('Visible to providers'), findsOneWidget);
      expect(find.textContaining('Revenue'), findsNothing);
      expect(find.textContaining('Sales'), findsNothing);
    });

    testWidgets('an unverified company is told publishing is unavailable', (
      tester,
    ) async {
      await pumpPatientApp(
        tester,
        path: '/company',
        size: _tall,
        account: _a,
        script: (b) => b.on(
          'GET',
          _dash,
          (_) => FakeBackend.json(
            200,
            companyDashboardJson(status: 'PENDING', canPublish: false),
          ),
        ),
      );
      expect(
        find.text('Publishing is unavailable until your company is verified.'),
        findsOneWidget,
      );
      expect(find.text('Pending review'), findsOneWidget);
    });

    testWidgets(
      'no company profile (403) gets guidance; a server error is safe and retry recovers',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/company',
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
            'Create your company profile on the Racheeta website to use this area.',
          ),
          findsOneWidget,
        );
      },
    );

    testWidgets('a failure is safe and retry recovers', (tester) async {
      var fail = true;
      await pumpPatientApp(
        tester,
        path: '/company',
        size: _tall,
        account: _a,
        script: (b) => b.on(
          'GET',
          _dash,
          (_) => fail
              ? FakeBackend.error(500, 'server_error', message: 'Traceback')
              : FakeBackend.json(200, companyDashboardJson()),
        ),
      );
      expect(find.textContaining('Traceback'), findsNothing);
      fail = false;
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('company-counts')), findsOneWidget);
    });
  });

  group('own products', () {
    testWidgets(
      'lists products with status chips, paginates and explains an empty list',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/company/products',
          size: _tall,
          account: _a,
          script: (b) => b.on('GET', _own, (r) {
            if (r.query['page'] == 2) {
              return FakeBackend.json(
                200,
                pageJson([
                  productOwnerJson(id: 'p2', title: 'Second product'),
                ], count: 2),
              );
            }
            return FakeBackend.json(
              200,
              pageJson(
                [productOwnerJson(title: 'Active one', active: true)],
                count: 2,
                next: 'https://api.test/x?page=2',
              ),
            );
          }),
        );
        expect(find.text('Active one'), findsOneWidget);
        expect(find.text('Active'), findsOneWidget);
        await tester.tap(find.text('Load more'));
        await tester.pumpAndSettle();
        expect(find.text('Second product'), findsOneWidget);
        expect(find.text('Inactive'), findsOneWidget);
      },
    );

    testWidgets('an empty list says where products are created', (
      tester,
    ) async {
      await pumpPatientApp(
        tester,
        path: '/company/products',
        size: _tall,
        account: _a,
        script: (b) => b.on(
          'GET',
          _own,
          (_) => FakeBackend.json(200, pageJson(<Object?>[])),
        ),
      );
      expect(find.text('You have no products yet'), findsOneWidget);
    });
  });

  group('activate and deactivate', () {
    Future<Harness> open(
      WidgetTester tester, {
      bool active = false,
      Responder? onActivate,
      Responder? onDeactivate,
    }) {
      var current = active;
      return pumpPatientApp(
        tester,
        path: '/company/products/$productId',
        size: _tall,
        account: _a,
        script: (b) => b
          ..on(
            'GET',
            _ownOne,
            (_) => FakeBackend.json(200, productOwnerJson(active: current)),
          )
          ..on(
            'GET',
            _own,
            (_) => FakeBackend.json(
              200,
              pageJson([productOwnerJson(active: current)]),
            ),
          )
          ..on(
            'GET',
            _dash,
            (_) => FakeBackend.json(200, companyDashboardJson()),
          )
          ..on('POST', _activate, (r) {
            if (onActivate != null) return onActivate(r);
            current = true;
            return FakeBackend.json(200, productOwnerJson(active: true));
          })
          ..on('POST', _deactivate, (r) {
            if (onDeactivate != null) return onDeactivate(r);
            current = false;
            return FakeBackend.json(200, productOwnerJson(active: false));
          }),
      );
    }

    testWidgets(
      'an inactive product offers Activate only; one POST, no body, then reload',
      (tester) async {
        final h = await open(tester);
        expect(find.byKey(const Key('product-deactivate')), findsNothing);
        await tester.tap(find.byKey(const Key('product-activate')));
        await tester.pumpAndSettle();
        final posts = h.backend.to('POST', _activate);
        expect(posts, hasLength(1));
        expect(posts.single.body, isNull);
        expect(find.text('The product was activated.'), findsOneWidget);
        expect(h.backend.count('GET', _ownOne), 2);
        expect(find.byKey(const Key('product-deactivate')), findsOneWidget);
      },
    );

    testWidgets('deactivating needs confirmation; declining sends nothing', (
      tester,
    ) async {
      final h = await open(tester, active: true);
      await tester.tap(find.byKey(const Key('product-deactivate')));
      await tester.pumpAndSettle();
      expect(find.text('Deactivate this product?'), findsOneWidget);
      await tester.tap(find.text('Keep active'));
      await tester.pumpAndSettle();
      expect(h.backend.count('POST', _deactivate), 0);
      await tester.tap(find.byKey(const Key('product-deactivate')));
      await tester.pumpAndSettle();
      await tester.tap(
        find.descendant(
          of: find.byType(AlertDialog),
          matching: find.text('Deactivate'),
        ),
      );
      await tester.pumpAndSettle();
      expect(h.backend.count('POST', _deactivate), 1);
      expect(find.text('The product was deactivated.'), findsOneWidget);
    });

    testWidgets('a duplicate tap sends ONE request and shows progress', (
      tester,
    ) async {
      final gate = Completer<void>();
      final h = await open(
        tester,
        onActivate: (_) async {
          await gate.future;
          return FakeBackend.json(200, productOwnerJson(active: true));
        },
      );
      await tester.tap(find.byKey(const Key('product-activate')));
      await tester.pump(const Duration(milliseconds: 30));
      expect(find.text('Activating…'), findsOneWidget);
      await tester.tap(find.text('Activating…'), warnIfMissed: false);
      await tester.pump(const Duration(milliseconds: 30));
      expect(h.backend.count('POST', _activate), 1);
      gate.complete();
      await tester.pumpAndSettle();
      expect(h.backend.count('POST', _activate), 1);
    });

    for (final c in [
      (
        'company_not_verified',
        403,
        'Your company must be verified before products can be activated.',
      ),
      (
        'category_unavailable',
        409,
        "This product's category can't be used for publishing right now.",
      ),
      (
        'invalid_transition',
        400,
        "This product can't be changed that way right now.",
      ),
    ]) {
      testWidgets(
        '${c.$1} (${c.$2}) shows its fixed message, never the raw text, and is not retried',
        (tester) async {
          final h = await open(
            tester,
            onActivate: (_) => FakeBackend.error(
              c.$2,
              c.$1,
              message: 'raw: product 42 owned by company 7',
            ),
          );
          await tester.tap(find.byKey(const Key('product-activate')));
          await tester.pumpAndSettle();
          expect(find.text(c.$3), findsOneWidget);
          expect(find.textContaining('company 7'), findsNothing);
          await tester.pump(const Duration(seconds: 30));
          expect(h.backend.count('POST', _activate), 1);
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
      final h = await open(tester, onActivate: FakeBackend.networkDown);
      await tester.tap(find.byKey(const Key('product-activate')));
      await tester.pumpAndSettle();
      expect(find.textContaining('Could not reach the server'), findsOneWidget);
      await tester.pump(const Duration(seconds: 30));
      expect(h.backend.count('POST', _activate), 1);
    });

    testWidgets(
      'another company\'s product is the generic not-found text with no actions',
      (tester) async {
        await pumpPatientApp(
          tester,
          path: '/company/products/$productId',
          size: _tall,
          account: _a,
          script: (b) =>
              b.on('GET', _ownOne, (_) => FakeBackend.error(404, 'not_found')),
        );
        expect(find.text("We couldn't find that."), findsOneWidget);
        expect(find.byKey(const Key('product-activate')), findsNothing);
      },
    );

    testWidgets('the list, detail and dashboard are reloaded after a change', (
      tester,
    ) async {
      var active = false;
      final h = await pumpPatientApp(
        tester,
        path: '/company',
        size: _tall,
        account: _a,
        script: (b) => b
          ..on(
            'GET',
            _dash,
            (_) => FakeBackend.json(200, companyDashboardJson()),
          )
          ..on(
            'GET',
            _own,
            (_) => FakeBackend.json(
              200,
              pageJson([productOwnerJson(active: active)]),
            ),
          )
          ..on(
            'GET',
            _ownOne,
            (_) => FakeBackend.json(200, productOwnerJson(active: active)),
          )
          ..on('POST', _activate, (_) {
            active = true;
            return FakeBackend.json(200, productOwnerJson(active: true));
          }),
      );
      final router = h.container.read(routerProvider);
      router.go('/company/products');
      await tester.pumpAndSettle();
      await tester.tap(find.text('My thermometer'));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('product-activate')));
      await tester.pumpAndSettle();
      router.go('/company/products');
      await tester.pumpAndSettle();
      expect(h.backend.count('GET', _own), 2);
      router.go('/company');
      await tester.pumpAndSettle();
      expect(h.backend.count('GET', _dash), 2);
    });
  });

  group('account isolation (the account changes while the screen stays open)', () {
    testWidgets('A\'s products and dashboard never appear under B', (
      tester,
    ) async {
      var who = 'A';
      final gateB = Completer<void>();
      final h = await pumpPatientApp(
        tester,
        path: '/company/products',
        size: _tall,
        account: _a,
        script: (b) => b.on('GET', _own, (_) async {
          if (who == 'B') await gateB.future;
          return FakeBackend.json(
            200,
            pageJson([productOwnerJson(title: 'PRODUCT OF $who')]),
          );
        }),
      );
      expect(find.text('PRODUCT OF A'), findsOneWidget);
      who = 'B';
      await switchAccountTo(tester, h, _b);
      expect(find.text('PRODUCT OF A'), findsNothing);
      gateB.complete();
      await tester.pumpAndSettle();
      expect(find.text('PRODUCT OF B'), findsOneWidget);
      expect(find.text('PRODUCT OF A'), findsNothing);
    });

    testWidgets('A\'s dashboard figures never appear under B', (tester) async {
      var who = 'A';
      final gateB = Completer<void>();
      final h = await pumpPatientApp(
        tester,
        path: '/company',
        size: _tall,
        account: _a,
        script: (b) => b.on('GET', _dash, (_) async {
          if (who == 'B') await gateB.future;
          return FakeBackend.json(200, {
            ...companyDashboardJson(),
            'products_total': who == 'A' ? 111 : 222,
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

    testWidgets(
      'A\'s open product and its action never reach B (wrong-company resource is a 404)',
      (tester) async {
        var who = 'A';
        final gateB = Completer<void>();
        final h = await pumpPatientApp(
          tester,
          path: '/company/products/$productId',
          size: _tall,
          account: _a,
          script: (b) => b.on('GET', _ownOne, (_) async {
            if (who == 'B') {
              await gateB.future;
              return FakeBackend.error(404, 'not_found');
            }
            return FakeBackend.json(
              200,
              productOwnerJson(title: 'SECRET PRODUCT OF A'),
            );
          }),
        );
        expect(find.text('SECRET PRODUCT OF A'), findsWidgets);
        who = 'B';
        await switchAccountTo(tester, h, _b);
        expect(find.text('SECRET PRODUCT OF A'), findsNothing);
        expect(find.byKey(const Key('product-activate')), findsNothing);
        gateB.complete();
        await tester.pumpAndSettle();
        expect(find.text("We couldn't find that."), findsOneWidget);
        expect(h.backend.count('POST', _activate), 0);
      },
    );

    for (final late in ['success', 'error']) {
      testWidgets(
        'a late $late of A\'s activation is never shown to B and invalidates nothing',
        (tester) async {
          final gate = Completer<void>();
          var who = 'A';
          final h = await pumpPatientApp(
            tester,
            path: '/company/products/$productId',
            size: _tall,
            account: _a,
            script: (b) => b
              ..on('GET', _ownOne, (_) {
                if (who == 'B') return FakeBackend.error(404, 'not_found');
                return FakeBackend.json(200, productOwnerJson());
              })
              ..on('POST', _activate, (_) async {
                await gate.future;
                return late == 'success'
                    ? FakeBackend.json(200, productOwnerJson(active: true))
                    : FakeBackend.error(403, 'company_not_verified');
              }),
          );
          await tester.tap(find.byKey(const Key('product-activate')));
          await tester.pump(const Duration(milliseconds: 30));
          who = 'B';
          await switchAccountTo(tester, h, _b);
          await tester.pumpAndSettle();
          final gets = h.backend.count('GET', _ownOne);
          gate.complete();
          await tester.pumpAndSettle();
          expect(find.text('The product was activated.'), findsNothing);
          expect(find.textContaining('must be verified'), findsNothing);
          expect(find.byKey(const Key('product-message')), findsNothing);
          expect(h.backend.count('GET', _ownOne), gets);
        },
      );
    }
  });

  group('Arabic', () {
    testWidgets('the company workspace renders right-to-left at phone width', (
      tester,
    ) async {
      await pumpPatientApp(
        tester,
        path: '/company',
        size: const Size(360, 780),
        language: 'ar',
        account: _a,
        script: (b) => b.on(
          'GET',
          _dash,
          (_) => FakeBackend.json(200, companyDashboardJson()),
        ),
      );
      expect(find.text('مساحة الشركة'), findsWidgets);
      expect(find.text('إجمالي المنتجات'), findsOneWidget);
      expect(
        Directionality.of(tester.element(find.text('إجمالي المنتجات'))),
        TextDirection.rtl,
      );
      expect(tester.takeException(), isNull);
    });
  });
}
