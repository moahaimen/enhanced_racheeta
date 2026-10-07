import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:racheeta_mobile/app/app.dart';

import 'support/comms_support.dart';
import 'support/domain_support.dart';
import 'support/fake_backend.dart';
import 'support/patient_support.dart';
import 'support/provider_support.dart';

/// Release accessibility audit over the major surfaces of Phases 11A–11E.
///
/// Every page is checked against Flutter's accessibility guidelines — Android and iOS minimum tap
/// target sizes, labelled tap targets (icon-only controls must have a semantic label) and text
/// contrast — in English and Arabic at phone width.
class AuditSurface {
  const AuditSurface(this.name, this.path, this.script, {this.account});
  final String name;
  final String path;
  final void Function(FakeBackend b) script;
  final Map<String, Object?>? account;
}

void _page(FakeBackend b, String path, Object? body) =>
    b.on('GET', path, (_) => FakeBackend.json(200, body));

final List<AuditSurface> surfaces = [
  AuditSurface('home', '/', (b) {
    _page(b, '/api/v1/notifications/unread-count/', {'count': 3});
    _page(b, '/api/v1/chat/unread-count/', {'count': 2});
  }),
  AuditSurface('account', '/account', (_) {}),
  AuditSurface('provider discovery', '/providers', (b) {
    _page(b, '/api/v1/providers', pageJson([cardJson()]));
    _page(b, '/api/v1/specialties', <Object?>[]);
    _page(b, '/api/v1/geo/governorates', <Object?>[]);
  }),
  AuditSurface('reservations', '/reservations', (b) {
    _page(b, '/api/v1/reservations/me', pageJson([reservationJson()]));
  }),
  AuditSurface('reservation detail', '/reservations/$reservationId', (b) {
    _page(b, '/api/v1/reservations/me/$reservationId', reservationJson());
  }),
  AuditSurface('notifications', '/notifications', (b) {
    _page(
      b,
      '/api/v1/notifications/',
      pageJson([
        notificationJson(),
        notificationJson(
          id: 'aaaa1111-0000-4000-8000-000000000002',
          isRead: true,
        ),
      ]),
    );
    _page(b, '/api/v1/notifications/unread-count/', {'count': 1});
  }),
  AuditSurface('conversations', '/chat', (b) {
    _page(
      b,
      '/api/v1/chat/conversations/',
      pageJson([conversationJson(unread: 2)]),
    );
    _page(b, '/api/v1/chat/unread-count/', {'count': 2});
  }),
  AuditSurface('conversation thread', '/chat/$conversationId', (b) {
    _page(
      b,
      '/api/v1/chat/conversations/$conversationId/messages/',
      pageJson([
        messageJson(sequence: 1, mine: true),
        messageJson(sequence: 2),
      ]),
    );
    _page(b, '/api/v1/chat/conversations/', pageJson(<Object?>[]));
    b.on(
      'POST',
      '/api/v1/chat/conversations/$conversationId/read/',
      (_) => FakeBackend.json(200, {'last_read_sequence': 2}),
    );
  }),
  AuditSurface('jobs', '/jobs', (b) {
    _page(b, '/api/v1/jobs', pageJson([jobCardJson()]));
    _page(b, '/api/v1/geo/governorates', <Object?>[]);
  }),
  AuditSurface('job detail', '/jobs/$jobId', (b) {
    _page(b, '/api/v1/jobs/$jobId', jobPublicJson());
  }),
  AuditSurface('real estate', '/real-estate', (b) {
    _page(b, '/api/v1/real-estate/listings', pageJson([listingJson()]));
    _page(b, '/api/v1/geo/governorates', <Object?>[]);
  }),
  AuditSurface('marketplace', '/marketplace', (b) {
    _page(b, '/api/v1/marketplace/categories', [categoryJson()]);
    _page(b, '/api/v1/marketplace/products', pageJson([productPublicJson()]));
  }, account: browsingProviderJson()),
  AuditSurface('provider workspace', '/workspace/reservations', (b) {
    _page(
      b,
      '/api/v1/reservations/provider',
      pageJson([providerReservationJson()]),
    );
  }, account: providerAccountJson()),
];

void main() {
  for (final language in ['en', 'ar']) {
    for (final surface in surfaces) {
      testWidgets(
        '${surface.name} [$language] meets the accessibility guidelines',
        (tester) async {
          final handle = tester.ensureSemantics();
          await pumpPatientApp(
            tester,
            path: surface.path,
            size: const Size(360, 780),
            language: language,
            account: surface.account,
            script: surface.script,
          );
          await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
          await expectLater(tester, meetsGuideline(iOSTapTargetGuideline));
          await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
          await expectLater(tester, meetsGuideline(textContrastGuideline));
          expect(tester.takeException(), isNull);
          handle.dispose();
        },
      );
    }
  }

  testWidgets(
    'semantics tree of the thread exposes message ownership as text, not only alignment',
    (tester) async {
      final handle = tester.ensureSemantics();
      await pumpPatientApp(
        tester,
        path: '/chat/$conversationId',
        size: const Size(360, 780),
        script: surfaces
            .firstWhere((s) => s.name == 'conversation thread')
            .script,
      );
      // each bubble is announced with who wrote it and when (not just left/right placement)
      expect(find.bySemanticsLabel(RegExp(r'^You, ')), findsOneWidget);
      expect(
        find.bySemanticsLabel(RegExp(r'^Dr\. Sara Ahmed, ')),
        findsOneWidget,
      );
      handle.dispose();
    },
  );

  for (final language in ['en', 'ar']) {
    testWidgets(
      'login [$language] meets the accessibility guidelines and is labelled',
      (tester) async {
        final handle = tester.ensureSemantics();
        tester.view.physicalSize = const Size(360, 780);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.reset);
        final h = Harness(
          storedRefresh: null,
          autoRestore: true,
          language: language,
        );
        addTearDown(h.dispose);
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: h.container,
            child: const RacheetaApp(),
          ),
        );
        await tester.pumpAndSettle();
        await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
        await expectLater(tester, meetsGuideline(iOSTapTargetGuideline));
        await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
        await expectLater(tester, meetsGuideline(textContrastGuideline));
        // both fields and the actions are reachable by label
        expect(find.byType(TextField), findsNWidgets(2));
        expect(tester.takeException(), isNull);
        handle.dispose();
      },
    );
  }

  testWidgets(
    'an unread notification is announced as unread (not only drawn bold)',
    (tester) async {
      final handle = tester.ensureSemantics();
      await pumpPatientApp(
        tester,
        path: '/notifications',
        size: const Size(360, 780),
        script: surfaces.firstWhere((s) => s.name == 'notifications').script,
      );
      // the row is one tappable node whose label starts with its state
      expect(find.bySemanticsLabel(RegExp(r'^Unread')), findsOneWidget);
      expect(find.bySemanticsLabel(RegExp(r'^Read')), findsOneWidget);
      handle.dispose();
    },
  );

  testWidgets(
    'RTL: the back control sits on the leading (right) edge and chevrons mirror',
    (tester) async {
      final handle = tester.ensureSemantics();
      final h = await pumpPatientApp(
        tester,
        size: const Size(360, 780),
        language: 'ar',
        script: surfaces.firstWhere((s) => s.name == 'conversations').script,
      );
      // Home: the Explore rows end in a chevron that must point in the reading direction
      final chevrons = tester
          .widgetList<Icon>(find.byIcon(Icons.chevron_right))
          .toList();
      expect(chevrons, isNotEmpty);
      for (final icon in chevrons) {
        expect(icon.icon!.matchTextDirection, isTrue);
      }
      await tester.tap(find.byKey(const Key('explore-messages')));
      await tester.pumpAndSettle();
      final back = tester.getCenter(find.byType(BackButton));
      expect(
        back.dx,
        greaterThan(180),
        reason: 'back is on the right in Arabic',
      );
      expect(h.backend.count('GET', '/api/v1/chat/conversations/'), 1);
      handle.dispose();
    },
  );
}
