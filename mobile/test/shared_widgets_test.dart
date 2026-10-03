import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/l10n/generated/app_localizations.dart';
import 'package:racheeta_mobile/shared/theme/app_theme.dart';
import 'package:racheeta_mobile/shared/widgets/async_action_button.dart';
import 'package:racheeta_mobile/shared/widgets/confirm_dialog.dart';
import 'package:racheeta_mobile/shared/widgets/states.dart';

Widget host(Widget child, {Locale locale = const Locale('en')}) => MaterialApp(
  theme: buildRacheetaTheme(),
  locale: locale,
  localizationsDelegates: AppLocalizations.localizationsDelegates,
  supportedLocales: AppLocalizations.supportedLocales,
  home: Scaffold(body: child),
);

void main() {
  group('state views', () {
    testWidgets('LoadingView shows a progress indicator and localized text', (
      tester,
    ) async {
      await tester.pumpWidget(host(const LoadingView()));
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Loading…'), findsOneWidget);
      await tester.pumpWidget(
        host(const LoadingView(), locale: const Locale('ar')),
      );
      expect(find.text('جارٍ التحميل…'), findsOneWidget);
    });

    testWidgets('ErrorView shows the message and a working retry', (
      tester,
    ) async {
      var retried = 0;
      await tester.pumpWidget(
        host(ErrorView(message: 'Boom', onRetry: () async => retried++)),
      );
      expect(find.text('Boom'), findsOneWidget);
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(retried, 1);
    });

    testWidgets('ErrorView without retry has no button', (tester) async {
      await tester.pumpWidget(host(const ErrorView(message: 'Nope')));
      expect(find.byType(FilledButton), findsNothing);
    });

    testWidgets('EmptyView renders the empty message', (tester) async {
      await tester.pumpWidget(host(const EmptyView()));
      expect(find.text('Nothing here yet'), findsOneWidget);
    });
  });

  group('AsyncActionButton (mandatory loading rule)', () {
    testWidgets(
      'spinner + pending label + disabled while running; idle again afterwards',
      (tester) async {
        final gate = Completer<void>();
        var calls = 0;
        await tester.pumpWidget(
          host(
            PrimaryButton(
              label: 'Save',
              pendingLabel: 'Saving…',
              onPressed: () async {
                calls++;
                await gate.future;
              },
            ),
          ),
        );
        await tester.tap(find.text('Save'));
        await tester.pump();
        expect(find.byType(CircularProgressIndicator), findsOneWidget);
        expect(find.text('Saving…'), findsOneWidget);
        expect(
          tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
          isNull,
        );
        await tester.tap(find.byType(FilledButton), warnIfMissed: false);
        expect(calls, 1);

        gate.complete();
        await tester.pumpAndSettle();
        expect(find.byType(CircularProgressIndicator), findsNothing);
        expect(find.text('Save'), findsOneWidget);
      },
    );

    testWidgets('a null action disables the button', (tester) async {
      await tester.pumpWidget(
        host(const PrimaryButton(label: 'Off', onPressed: null)),
      );
      expect(
        tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
        isNull,
      );
    });

    testWidgets('confirm gate: declining runs nothing and shows no spinner', (
      tester,
    ) async {
      var ran = false;
      await tester.pumpWidget(
        host(
          SecondaryButton(
            label: 'Delete',
            confirm: () async => false,
            onPressed: () async => ran = true,
          ),
        ),
      );
      await tester.tap(find.text('Delete'));
      await tester.pumpAndSettle();
      expect(ran, isFalse);
      expect(find.byType(CircularProgressIndicator), findsNothing);
    });

    testWidgets('confirm gate: approving runs the action with progress', (
      tester,
    ) async {
      final gate = Completer<void>();
      await tester.pumpWidget(
        host(
          SecondaryButton(
            label: 'Delete',
            confirm: () async => true,
            onPressed: () => gate.future,
          ),
        ),
      );
      await tester.tap(find.text('Delete'));
      await tester.pump();
      await tester.pump();
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      gate.complete();
      await tester.pumpAndSettle();
      expect(find.byType(CircularProgressIndicator), findsNothing);
    });
  });

  group('showConfirmDialog', () {
    Future<bool?> open(WidgetTester tester, String tap) async {
      bool? result;
      await tester.pumpWidget(
        host(
          Builder(
            builder: (context) => TextButton(
              onPressed: () async => result = await showConfirmDialog(
                context,
                title: 'T',
                message: 'M',
                confirmLabel: 'Yes',
              ),
              child: const Text('open'),
            ),
          ),
        ),
      );
      await tester.tap(find.text('open'));
      await tester.pumpAndSettle();
      expect(find.text('T'), findsOneWidget);
      await tester.tap(find.text(tap));
      await tester.pumpAndSettle();
      return result;
    }

    testWidgets(
      'confirm → true',
      (tester) async => expect(await open(tester, 'Yes'), isTrue),
    );
    testWidgets(
      'cancel → false',
      (tester) async => expect(await open(tester, 'Cancel'), isFalse),
    );
  });
}
