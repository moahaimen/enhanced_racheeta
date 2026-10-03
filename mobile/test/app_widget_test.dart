import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:racheeta_mobile/app/app.dart';
import 'package:racheeta_mobile/features/auth/application/providers.dart';
import 'package:racheeta_mobile/features/auth/application/session_state.dart';

import 'support/fake_backend.dart';

const _login = '/api/v1/auth/login';
const _refresh = '/api/v1/auth/refresh';
const _logout = '/api/v1/auth/logout';
const _me = '/api/v1/me';

Future<Harness> pumpApp(
  WidgetTester tester, {
  String? storedRefresh,
  String language = 'en',
  void Function(FakeBackend backend)? script,
  bool autoRestore = true,
}) async {
  final h = Harness(
    storedRefresh: storedRefresh,
    autoRestore: autoRestore,
    language: language,
  );
  addTearDown(h.dispose);
  script?.call(h.backend);
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: h.container,
      child: const RacheetaApp(),
    ),
  );
  return h;
}

void restorable(FakeBackend b, {String name = 'Layla Hassan'}) => b
  ..on('POST', _refresh, (_) => FakeBackend.json(200, tokens('a2', 'r2')))
  ..on('GET', _me, (_) => FakeBackend.json(200, accountJson(name: name)));

void main() {
  group('start-up', () {
    testWidgets('no stored session → login screen (no loading spinner left)', (
      tester,
    ) async {
      await pumpApp(tester);
      await tester.pumpAndSettle();
      expect(find.text('Sign in'), findsWidgets);
      expect(find.byType(TextField), findsNWidgets(2));
      expect(find.byType(CircularProgressIndicator), findsNothing);
    });

    testWidgets('shows the restoration screen with progress, then the shell', (
      tester,
    ) async {
      final gate = Completer<void>();
      await pumpApp(
        tester,
        storedRefresh: 'r1',
        script: (b) => b
          ..on('POST', _refresh, (_) async {
            await gate.future;
            return FakeBackend.json(200, tokens('a2', 'r2'));
          })
          ..on('GET', _me, (_) => FakeBackend.json(200, accountJson())),
      );
      await tester.pump(const Duration(milliseconds: 50));
      expect(find.text('Restoring your session…'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      gate.complete();
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('home-greeting')), findsOneWidget);
      expect(find.text('Welcome, Layla Hassan'), findsOneWidget);
      expect(find.text('Restoring your session…'), findsNothing);
    });

    testWidgets('unreachable server keeps the session and offers retry', (
      tester,
    ) async {
      final h = await pumpApp(
        tester,
        storedRefresh: 'r1',
        script: (b) => b.on('POST', _refresh, FakeBackend.networkDown),
      );
      await tester.pumpAndSettle();
      expect(find.text("We couldn't verify your session"), findsOneWidget);
      expect(find.text('Try again'), findsOneWidget);
      expect(find.text('Use a different account'), findsOneWidget);
      expect(await h.tokenStore.readRefreshToken(), 'r1');

      restorable(h.backend);
      await tester.tap(find.text('Try again'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('home-greeting')), findsOneWidget);
    });

    testWidgets('"use a different account" signs out locally', (tester) async {
      final h = await pumpApp(
        tester,
        storedRefresh: 'r1',
        script: (b) => b
          ..on('POST', _refresh, FakeBackend.networkDown)
          ..on('POST', _logout, (_) => FakeBackend.noContent()),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Use a different account'));
      await tester.pumpAndSettle();
      expect(find.byType(TextField), findsNWidgets(2));
      expect(await h.tokenStore.readRefreshToken(), isNull);
    });

    testWidgets(
      'a rejected stored session lands on login with the expiry notice',
      (tester) async {
        await pumpApp(
          tester,
          storedRefresh: 'dead',
          script: (b) => b.on(
            'POST',
            _refresh,
            (_) => FakeBackend.error(401, 'token_not_valid'),
          ),
        );
        await tester.pumpAndSettle();
        expect(
          find.text('Your session has expired. Please sign in again.'),
          findsOneWidget,
        );
      },
    );
  });

  group('login screen', () {
    Future<void> fill(
      WidgetTester tester,
      String email,
      String password,
    ) async {
      await tester.enterText(find.byType(TextField).at(0), email);
      await tester.enterText(find.byType(TextField).at(1), password);
    }

    Finder submit() => find.widgetWithText(FilledButton, 'Sign in');

    testWidgets(
      'empty fields are flagged locally without calling the backend',
      (tester) async {
        final h = await pumpApp(tester);
        await tester.pumpAndSettle();
        await tester.tap(submit());
        await tester.pumpAndSettle();
        expect(find.text('This field is required.'), findsNWidgets(2));
        expect(h.backend.requests, isEmpty);
      },
    );

    testWidgets('successful sign-in opens the authenticated shell', (
      tester,
    ) async {
      final h = await pumpApp(
        tester,
        script: (b) => b
          ..on('POST', _login, (_) => FakeBackend.json(200, tokens('a1', 'r1')))
          ..on('GET', _me, (_) => FakeBackend.json(200, accountJson())),
      );
      await tester.pumpAndSettle();
      await fill(tester, 'layla@example.com', 'secret');
      await tester.tap(submit());
      await tester.pumpAndSettle();
      expect(find.text('Welcome, Layla Hassan'), findsOneWidget);
      expect(find.textContaining('Patient'), findsWidgets);
      expect(await h.tokenStore.readRefreshToken(), 'r1');
    });

    testWidgets(
      'while signing in: spinner, disabled button, and duplicate taps are ignored',
      (tester) async {
        final gate = Completer<void>();
        final h = await pumpApp(
          tester,
          script: (b) => b
            ..on('POST', _login, (_) async {
              await gate.future;
              return FakeBackend.json(200, tokens('a1', 'r1'));
            })
            ..on('GET', _me, (_) => FakeBackend.json(200, accountJson())),
        );
        await tester.pumpAndSettle();
        await fill(tester, 'layla@example.com', 'secret');
        await tester.tap(submit());
        await tester.pump(const Duration(milliseconds: 50));

        expect(find.byType(CircularProgressIndicator), findsOneWidget);
        expect(find.text('Signing in…'), findsOneWidget);
        final button = tester.widget<FilledButton>(find.byType(FilledButton));
        expect(button.onPressed, isNull);
        await tester.tap(find.byType(FilledButton), warnIfMissed: false);
        await tester.pump(const Duration(milliseconds: 50));

        gate.complete();
        await tester.pumpAndSettle();
        expect(h.backend.count('POST', _login), 1);
        expect(find.text('Welcome, Layla Hassan'), findsOneWidget);
      },
    );

    testWidgets('wrong credentials show a clear error and re-enable the form', (
      tester,
    ) async {
      await pumpApp(
        tester,
        script: (b) => b.on(
          'POST',
          _login,
          (_) => FakeBackend.error(401, 'no_active_account'),
        ),
      );
      await tester.pumpAndSettle();
      await fill(tester, 'layla@example.com', 'wrong');
      await tester.tap(submit());
      await tester.pumpAndSettle();
      expect(find.text('Incorrect email or password.'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsNothing);
      expect(
        tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
        isNotNull,
      );
    });

    testWidgets('backend field errors appear under the field', (tester) async {
      await pumpApp(
        tester,
        script: (b) => b.on(
          'POST',
          _login,
          (_) => FakeBackend.error(
            400,
            'validation_error',
            details: {
              'email': ['Enter a valid email address.'],
            },
          ),
        ),
      );
      await tester.pumpAndSettle();
      await fill(tester, 'not-an-email', 'x');
      await tester.tap(submit());
      await tester.pumpAndSettle();
      expect(find.text('Enter a valid email address.'), findsOneWidget);
    });

    testWidgets('network failure and throttling have their own messages', (
      tester,
    ) async {
      final h = await pumpApp(
        tester,
        script: (b) => b.on('POST', _login, FakeBackend.networkDown),
      );
      await tester.pumpAndSettle();
      await fill(tester, 'a@b.test', 'pw');
      await tester.tap(submit());
      await tester.pumpAndSettle();
      expect(
        find.text(
          'Could not reach the server. Check your connection and try again.',
        ),
        findsOneWidget,
      );
      h.backend.on('POST', _login, (_) => FakeBackend.error(429, 'throttled'));
      await tester.tap(submit());
      await tester.pumpAndSettle();
      expect(
        find.text('Too many attempts. Wait a moment and try again.'),
        findsOneWidget,
      );
    });

    testWidgets('the password is obscured and can be revealed', (tester) async {
      await pumpApp(tester);
      await tester.pumpAndSettle();
      expect(
        tester.widget<TextField>(find.byType(TextField).at(1)).obscureText,
        isTrue,
      );
      await tester.tap(find.byTooltip('Show password'));
      await tester.pump();
      expect(
        tester.widget<TextField>(find.byType(TextField).at(1)).obscureText,
        isFalse,
      );
    });
  });

  group('authenticated shell', () {
    testWidgets(
      'lists only the finished destinations and opens the account screen',
      (tester) async {
        await pumpApp(tester, storedRefresh: 'r', script: restorable);
        await tester.pumpAndSettle();
        expect(find.text('Home'), findsWidgets);
        expect(find.text('Account'), findsWidgets);
        await tester.tap(find.text('Account').last);
        await tester.pumpAndSettle();
        expect(find.text('layla@example.com'), findsOneWidget);
        expect(find.text('Layla Hassan'), findsOneWidget);
      },
    );

    testWidgets('wide screens use a navigation rail', (tester) async {
      tester.view.physicalSize = const Size(1200, 800);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      await pumpApp(tester, storedRefresh: 'r', script: restorable);
      await tester.pumpAndSettle();
      expect(find.byType(NavigationRail), findsOneWidget);
      expect(find.byType(NavigationBar), findsNothing);
    });

    testWidgets('phones use a bottom navigation bar', (tester) async {
      tester.view.physicalSize = const Size(400, 800);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      await pumpApp(tester, storedRefresh: 'r', script: restorable);
      await tester.pumpAndSettle();
      expect(find.byType(NavigationBar), findsOneWidget);
    });

    testWidgets('logout asks for confirmation; cancel keeps the session', (
      tester,
    ) async {
      final h = await pumpApp(tester, storedRefresh: 'r', script: restorable);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Account').last);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Sign out'));
      await tester.pumpAndSettle();
      expect(find.text('Sign out?'), findsOneWidget);
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();
      expect(
        h.container.read(sessionControllerProvider),
        isA<SessionAuthenticated>(),
      );
    });

    testWidgets(
      'confirmed logout returns to login and clears the stored token',
      (tester) async {
        final h = await pumpApp(
          tester,
          storedRefresh: 'r',
          script: (b) {
            restorable(b);
            b.on('POST', _logout, (_) => FakeBackend.noContent());
          },
        );
        await tester.pumpAndSettle();
        await tester.tap(find.text('Account').last);
        await tester.pumpAndSettle();
        await tester.tap(find.text('Sign out'));
        await tester.pumpAndSettle();
        await tester.tap(
          find.descendant(
            of: find.byType(AlertDialog),
            matching: find.widgetWithText(FilledButton, 'Sign out'),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.byType(TextField), findsNWidgets(2));
        expect(await h.tokenStore.readRefreshToken(), isNull);
        expect(h.backend.to('POST', _logout).single.body, {'refresh': 'r2'});
      },
    );

    testWidgets(
      'a session that expires mid-use sends the user to login with a notice',
      (tester) async {
        final h = await pumpApp(tester, storedRefresh: 'r', script: restorable);
        await tester.pumpAndSettle();
        h.backend
          ..on('GET', _me, (_) => FakeBackend.error(401, 'token_not_valid'))
          ..on(
            'POST',
            _refresh,
            (_) => FakeBackend.error(401, 'token_not_valid'),
          );
        unawaited(
          h.container
              .read(sessionControllerProvider.notifier)
              .refreshAccount()
              .then((_) {}, onError: (Object _) {}),
        );
        await tester.pumpAndSettle();
        expect(find.byType(TextField), findsNWidgets(2));
        expect(
          find.text('Your session has expired. Please sign in again.'),
          findsOneWidget,
        );
      },
    );

    testWidgets('an unverified e-mail is flagged on the home screen', (
      tester,
    ) async {
      await pumpApp(
        tester,
        storedRefresh: 'r',
        script: (b) => b
          ..on(
            'POST',
            _refresh,
            (_) => FakeBackend.json(200, tokens('a', 'r2')),
          )
          ..on(
            'GET',
            _me,
            (_) => FakeBackend.json(200, {
              ...accountJson(),
              'email_verified': false,
            }),
          ),
      );
      await tester.pumpAndSettle();
      expect(
        find.text('Your email address is not verified yet.'),
        findsOneWidget,
      );
    });
  });

  group('localisation', () {
    testWidgets('Arabic renders right-to-left with Arabic text', (
      tester,
    ) async {
      await pumpApp(tester, language: 'ar');
      await tester.pumpAndSettle();
      expect(find.text('تسجيل الدخول'), findsWidgets);
      expect(
        Directionality.of(tester.element(find.byType(TextField).first)),
        TextDirection.rtl,
      );
    });

    testWidgets('English renders left-to-right', (tester) async {
      await pumpApp(tester, language: 'en');
      await tester.pumpAndSettle();
      expect(
        Directionality.of(tester.element(find.byType(TextField).first)),
        TextDirection.ltr,
      );
    });

    testWidgets('switching language at runtime re-renders and is persisted', (
      tester,
    ) async {
      final h = await pumpApp(tester, language: 'en');
      await tester.pumpAndSettle();
      await tester.tap(find.text('العربية'));
      await tester.pumpAndSettle();
      expect(find.text('تسجيل الدخول'), findsWidgets);
      expect(h.preferences.readLanguageCode(), 'ar');
    });

    testWidgets('API errors are shown in the selected language', (
      tester,
    ) async {
      await pumpApp(
        tester,
        language: 'ar',
        script: (b) => b.on(
          'POST',
          _login,
          (_) => FakeBackend.error(401, 'no_active_account'),
        ),
      );
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField).at(0), 'a@b.test');
      await tester.enterText(find.byType(TextField).at(1), 'pw');
      await tester.tap(find.byType(FilledButton));
      await tester.pumpAndSettle();
      expect(
        find.text('البريد الإلكتروني أو كلمة المرور غير صحيحة.'),
        findsOneWidget,
      );
    });
  });
}
