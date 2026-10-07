import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'support/comms_support.dart';
import 'support/patient_support.dart';
import 'accessibility_audit_test.dart' show AuditSurface, surfaces;

/// Large-text audit: every audited surface is rendered at 1.0, 1.5 and 2.0 system text scale, in
/// English and Arabic, at phone width. Nothing may overflow or throw, and the page's primary
/// content must still be present (text scaling is never disabled by the app).
void main() {
  for (final scale in [1.0, 1.5, 2.0]) {
    for (final language in ['en', 'ar']) {
      for (final AuditSurface surface in surfaces) {
        testWidgets('${surface.name} [$language] at ${scale}x text', (
          tester,
        ) async {
          tester.platformDispatcher.textScaleFactorTestValue = scale;
          addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
          await pumpPatientApp(
            tester,
            path: surface.path,
            size: const Size(360, 780),
            language: language,
            account: surface.account,
            script: surface.script,
          );
          expect(
            tester.takeException(),
            isNull,
            reason: 'no overflow or layout error',
          );
          // the page rendered something and the AppBar title is present
          expect(find.byType(AppBar), findsWidgets);
          expect(find.byType(Scaffold), findsWidgets);
        });
      }
    }
  }

  testWidgets(
    'the composer stays usable at 2.0x: field and send button are both on screen',
    (tester) async {
      tester.platformDispatcher.textScaleFactorTestValue = 2.0;
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
      await pumpPatientApp(
        tester,
        path: '/chat/$conversationId',
        size: const Size(360, 780),
        script: surfaces
            .firstWhere((s) => s.name == 'conversation thread')
            .script,
      );
      final view = tester.view.physicalSize / tester.view.devicePixelRatio;
      for (final key in ['composer-field', 'composer-send']) {
        final rect = tester.getRect(find.byKey(Key(key)));
        expect(rect.bottom, lessThanOrEqualTo(view.height), reason: key);
        expect(rect.top, greaterThanOrEqualTo(0), reason: key);
      }
      expect(tester.takeException(), isNull);
    },
  );
}
