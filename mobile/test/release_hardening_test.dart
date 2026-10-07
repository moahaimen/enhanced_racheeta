import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/core/paging/paged_notifier.dart';
import 'package:racheeta_mobile/l10n/generated/app_localizations.dart';
import 'package:racheeta_mobile/shared/theme/app_theme.dart';
import 'package:racheeta_mobile/shared/widgets/app_text_field.dart';
import 'package:racheeta_mobile/shared/widgets/async_action_button.dart';
import 'package:racheeta_mobile/shared/widgets/paged_list.dart';

Widget _host(Widget child, {double textScale = 1}) => MaterialApp(
  theme: buildRacheetaTheme(),
  localizationsDelegates: AppLocalizations.localizationsDelegates,
  supportedLocales: AppLocalizations.supportedLocales,
  builder: (context, child) => MediaQuery(
    data: MediaQuery.of(
      context,
    ).copyWith(textScaler: TextScaler.linear(textScale)),
    child: child!,
  ),
  home: Scaffold(body: child),
);

void main() {
  group('release configuration', () {
    test('Android release never falls back to the debug signing key', () {
      final gradle = File('android/app/build.gradle.kts').readAsStringSync();
      expect(gradle, isNot(contains('signingConfigs.getByName("debug")')));
      for (final variable in [
        'RACHEETA_ANDROID_KEYSTORE_PATH',
        'RACHEETA_ANDROID_STORE_PASSWORD',
        'RACHEETA_ANDROID_KEY_ALIAS',
        'RACHEETA_ANDROID_KEY_PASSWORD',
      ]) {
        expect(gradle, contains(variable));
      }
      expect(gradle, contains('Android release signing is required'));
    });

    test('Android release has network access but forbids cleartext', () {
      final main = File(
        'android/app/src/main/AndroidManifest.xml',
      ).readAsStringSync();
      final debug = File(
        'android/app/src/debug/AndroidManifest.xml',
      ).readAsStringSync();
      expect(main, contains('android.permission.INTERNET'));
      expect(main, contains('android:usesCleartextTraffic="false"'));
      expect(debug, contains('android:usesCleartextTraffic="true"'));
      expect(main, contains('android:label="Racheeta"'));
    });

    test('first store version and public app name are pinned', () {
      final pubspec = File('pubspec.yaml').readAsStringSync();
      final plist = File('ios/Runner/Info.plist').readAsStringSync();
      expect(pubspec, contains('version: 1.0.0+1'));
      expect(plist, contains('<string>Racheeta</string>'));
    });
  });

  group('accessibility and rendering hardening', () {
    testWidgets('shared form controls meet tap-target and labelling guidelines', (
      tester,
    ) async {
      final controller = TextEditingController();
      addTearDown(controller.dispose);
      final semantics = tester.ensureSemantics();
      addTearDown(semantics.dispose);
      await tester.pumpWidget(
        _host(
          Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              children: [
                AppTextField(controller: controller, label: 'Email'),
                const SizedBox(height: 24),
                PrimaryButton(label: 'Continue', onPressed: _noop),
              ],
            ),
          ),
        ),
      );
      await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
      await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
    });

    testWidgets('core controls remain usable at 200% text scaling', (
      tester,
    ) async {
      final controller = TextEditingController();
      addTearDown(controller.dispose);
      await tester.pumpWidget(
        _host(
          Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              children: [
                AppTextField(
                  controller: controller,
                  label: 'A deliberately long field label for text scaling',
                ),
                const SizedBox(height: 24),
                PrimaryButton(
                  label: 'A deliberately long primary action label',
                  onPressed: _noop,
                ),
              ],
            ),
          ),
          textScale: 2,
        ),
      );
      expect(tester.takeException(), isNull);
      expect(find.byType(TextField), findsOneWidget);
      expect(find.byType(FilledButton), findsOneWidget);
    });

    testWidgets('large paged results remain lazily built', (tester) async {
      var built = 0;
      final state = PagedState<int>(
        phase: PagedPhase.ready,
        items: List<int>.generate(1000, (index) => index),
        count: 1000,
      );
      await tester.pumpWidget(
        _host(
          PagedListView<int>(
            state: state,
            onLoadMore: _noop,
            onReload: () {},
            itemBuilder: (context, item) {
              built++;
              return SizedBox(height: 56, child: Text('Row $item'));
            },
            errorMessage: (_, _) => 'error',
            emptyTitle: 'empty',
          ),
        ),
      );
      expect(find.byKey(const Key('paged-count')), findsOneWidget);
      expect(built, lessThan(100), reason: 'ListView.builder must stay lazy');
    });
  });
}

Future<void> _noop() async {}
