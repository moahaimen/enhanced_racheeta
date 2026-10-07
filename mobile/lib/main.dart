import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app/app.dart';
import 'core/config/app_config.dart';
import 'core/storage/preferences_store.dart';
import 'features/auth/application/providers.dart';
import 'features/push/firebase_push_source.dart';
import 'features/push/push_registration.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final AppConfig config;
  try {
    config = AppConfig.fromEnvironment();
  } on ConfigurationError catch (error) {
    runApp(ConfigurationErrorApp(error: error));
    return;
  }

  final preferences = await SharedPreferences.getInstance();
  // Push is optional: without Firebase client configuration (--dart-define FIREBASE_*) the app
  // runs with push disabled and everything else unchanged.
  final pushSource = await createPushSource(FirebaseConfig.fromEnvironment());
  runApp(
    ProviderScope(
      overrides: [
        appConfigProvider.overrideWithValue(config),
        preferencesStoreProvider.overrideWithValue(
          SharedPreferencesStore(preferences),
        ),
        pushSourceProvider.overrideWithValue(pushSource),
        beforeLogoutProvider.overrideWith(
          (ref) =>
              () => ref
                  .read(pushRegistrationProvider.notifier)
                  .unregisterForLogout(),
        ),
      ],
      child: const RacheetaApp(),
    ),
  );
}
