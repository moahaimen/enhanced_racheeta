import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/time/time_providers.dart';
import '../features/auth/application/account_scope.dart';
import '../features/auth/application/providers.dart';
import '../features/chat/application/chat_providers.dart';
import '../features/notifications/application/notifications_providers.dart';
import '../features/push/push_intents.dart';
import '../features/push/push_registration.dart';
import '../features/push/push_source.dart';
import 'router.dart';

/// Wires push into the running app (watched once by the root widget):
///
/// * keeps the device token registered for the signed-in account ([PushRegistration]);
/// * routes a tapped push — from the background or the one that launched the app — through the
///   [PushIntentCoordinator] into the existing `GoRouter`, after the session is resolved;
/// * on a foreground push only *refreshes* backend state (counts, lists, the open thread).
///   Push is a delivery hint: the persistent notification and the message are fetched from the
///   backend, nothing from the payload is stored or shown as a notification of its own.
final pushBootstrapProvider = Provider<void>((ref) {
  ref.watch(pushRegistrationProvider);
  final source = ref.watch(pushSourceProvider);
  if (!source.isAvailable) return;

  final coordinator = PushIntentCoordinator(
    session: () => ref.read(sessionControllerProvider),
    navigate: (route) => unawaited(ref.read(routerProvider).push<void>(route)),
    now: ref.read(nowProvider),
  );
  ref.listen(
    sessionControllerProvider,
    (_, _) => coordinator.onSessionChanged(),
  );

  final subscriptions = <StreamSubscription<PushMessageData>>[
    source.openedMessages.listen(coordinator.onOpened, onError: (Object _) {}),
    source.foregroundMessages.listen(
      (message) => refreshForPush(ref, message),
      onError: (Object _) {},
    ),
  ];
  ref.onDispose(() {
    for (final subscription in subscriptions) {
      unawaited(subscription.cancel());
    }
  });

  // The push that launched the app (terminated state): held until the session is restored.
  unawaited(
    source
        .initialMessage()
        .then((message) {
          if (message != null && ref.mounted) coordinator.onOpened(message);
        })
        .catchError((Object _) {}),
  );
});

/// Reloads what a push may have changed, for the signed-in account only.
void refreshForPush(Ref ref, PushMessageData message) {
  final account = ref.read(accountIdProvider);
  if (account == null) return;
  ref
    ..invalidate(notificationUnreadProvider)
    ..invalidate(notificationsProvider)
    ..invalidate(chatUnreadProvider)
    ..invalidate(conversationsProvider);
  final conversation = message.data['conversation_id'];
  if (message.data['type'] == 'chat_message' && conversation != null) {
    final open = chatMessagesProvider((account: account, value: conversation));
    // Only an open thread is refreshed (merging the latest page); none is created for the push.
    if (ref.exists(open)) unawaited(ref.read(open.notifier).refresh());
  }
}
