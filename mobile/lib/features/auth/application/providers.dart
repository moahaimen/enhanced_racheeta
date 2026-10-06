import 'dart:ui' show Locale, PlatformDispatcher;

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';
import '../../../core/api/session_source.dart';
import '../../../core/config/app_config.dart';
import '../../../core/logging/safe_logger.dart';
import '../../../core/storage/preferences_store.dart';
import '../../../core/storage/token_store.dart';
import '../data/auth_api.dart';
import 'session_controller.dart';
import 'session_core.dart';
import 'session_state.dart';

// Composition root. `main()` overrides the three providers that need real I/O
// (`appConfigProvider`, `preferencesStoreProvider`, and optionally `tokenStoreProvider`);
// tests override them with in-memory fakes and a fake Dio adapter.

final appConfigProvider = Provider<AppConfig>(
  (ref) =>
      throw StateError('appConfigProvider must be overridden at start-up.'),
);

final preferencesStoreProvider = Provider<PreferencesStore>(
  (ref) => throw StateError(
    'preferencesStoreProvider must be overridden at start-up.',
  ),
);

final tokenStoreProvider = Provider<TokenStore>((ref) => SecureTokenStore());

final loggerProvider = Provider<SafeLogger>((ref) => const SafeLogger());

final autoRestoreSessionProvider = Provider<bool>((ref) => true);

/// Work that must happen while the signed-in account's credentials still exist, just before they
/// are cleared on logout (for example unregistering this device's push token, which the backend
/// only accepts from the owning account). The composition root overrides it; it is time-bounded
/// and best effort, so it can never keep the user signed in.
final beforeLogoutProvider = Provider<Future<void> Function()>(
  (ref) => () async {},
);

final dioProvider = Provider<Dio>((ref) {
  final dio = buildDio(ref.watch(appConfigProvider));
  ref.onDispose(() => dio.close(force: true));
  return dio;
});

final Provider<SessionCore> sessionCoreProvider = Provider<SessionCore>((ref) {
  final core = SessionCore(
    store: ref.watch(tokenStoreProvider),
    // A session-free client: the refresh call must not depend on the session it renews
    // (that would be a provider cycle SessionCore -> AuthApi -> ApiClient -> SessionCore).
    refresher: (refreshToken) => AuthApi(
      ApiClient(
        dio: ref.read(dioProvider),
        session: const NoSession(),
        languageCode: () => ref.read(localeControllerProvider).languageCode,
        logger: ref.read(loggerProvider),
      ),
    ).refresh(refreshToken),
    logger: ref.watch(loggerProvider),
  );
  ref.onDispose(core.dispose);
  return core;
});

final Provider<ApiClient> apiClientProvider = Provider<ApiClient>(
  (ref) => ApiClient(
    dio: ref.watch(dioProvider),
    session: ref.watch(sessionCoreProvider),
    languageCode: () => ref.read(localeControllerProvider).languageCode,
    logger: ref.watch(loggerProvider),
  ),
);

final Provider<AuthApi> authApiProvider = Provider<AuthApi>(
  (ref) => AuthApi(ref.watch(apiClientProvider)),
);

final sessionControllerProvider =
    NotifierProvider<SessionController, SessionState>(SessionController.new);

/// UI language: `ar` (default) or `en`. Also sent as `Accept-Language` on every request.
class LocaleController extends Notifier<Locale> {
  static const supported = <Locale>[Locale('ar'), Locale('en')];

  @override
  Locale build() {
    final stored = ref.read(preferencesStoreProvider).readLanguageCode();
    return _resolve(stored ?? PlatformDispatcher.instance.locale.languageCode);
  }

  Future<void> setLanguage(Locale locale) async {
    final next = _resolve(locale.languageCode);
    state = next;
    await ref
        .read(preferencesStoreProvider)
        .writeLanguageCode(next.languageCode);
  }

  static Locale _resolve(String code) =>
      code == 'en' ? const Locale('en') : const Locale('ar');
}

final localeControllerProvider = NotifierProvider<LocaleController, Locale>(
  LocaleController.new,
);
