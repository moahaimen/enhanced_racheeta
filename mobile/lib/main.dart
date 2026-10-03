import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app/app.dart';
import 'core/config/app_config.dart';
import 'core/storage/preferences_store.dart';
import 'features/auth/application/providers.dart';

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
  runApp(
    ProviderScope(
      overrides: [
        appConfigProvider.overrideWithValue(config),
        preferencesStoreProvider.overrideWithValue(
          SharedPreferencesStore(preferences),
        ),
      ],
      child: const RacheetaApp(),
    ),
  );
}
