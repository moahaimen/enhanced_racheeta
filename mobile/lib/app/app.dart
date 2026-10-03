import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/config/app_config.dart';
import '../features/auth/application/providers.dart';
import '../l10n/generated/app_localizations.dart';
import '../shared/theme/app_theme.dart';
import 'router.dart';

/// Root widget: theme, localisation (Arabic RTL / English) and the session-aware router.
class RacheetaApp extends ConsumerWidget {
  const RacheetaApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp.router(
      onGenerateTitle: (context) => AppLocalizations.of(context).appName,
      theme: buildRacheetaTheme(),
      locale: ref.watch(localeControllerProvider),
      supportedLocales: LocaleController.supported,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      routerConfig: ref.watch(routerProvider),
    );
  }
}

/// Shown instead of the app when the build is misconfigured (for example a release build without
/// an https `API_BASE_URL`). A visible, explicit failure rather than a silent insecure fallback.
class ConfigurationErrorApp extends StatelessWidget {
  const ConfigurationErrorApp({required this.error, super.key});
  final ConfigurationError error;

  @override
  Widget build(BuildContext context) => MaterialApp(
    theme: buildRacheetaTheme(),
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    home: Builder(
      builder: (context) => Scaffold(
        body: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(RacheetaSpacing.xl),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.settings_suggest_outlined, size: 48),
                  const SizedBox(height: RacheetaSpacing.lg),
                  Text(
                    AppLocalizations.of(context).configErrorTitle,
                    style: Theme.of(context).textTheme.titleLarge,
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: RacheetaSpacing.md),
                  Text(error.message, textAlign: TextAlign.center),
                ],
              ),
            ),
          ),
        ),
      ),
    ),
  );
}
