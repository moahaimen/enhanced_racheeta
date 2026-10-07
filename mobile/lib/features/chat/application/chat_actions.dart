import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../auth/application/account_scope.dart';
import '../data/chat_models.dart';
import 'chat_providers.dart';

void refreshChat(WidgetRef ref) {
  ref
    ..invalidate(conversationsProvider)
    ..invalidate(chatUnreadProvider);
}

/// `POST /chat/conversations/{id}/messages/`: exactly one request for the initiating account
/// (see `runAsAccount`); a result that arrives under another account — success or error — is
/// dropped and changes nothing. On success the confirmed message is added to the open thread and
/// the list and unread count are reloaded from the backend.
Future<ChatMessage> sendChatMessage(
  WidgetRef ref,
  String conversationId,
  String body,
) async {
  final account = ref.read(accountIdProvider);
  final message = await runAsAccount(
    ref,
    () => ref.read(chatApiProvider).send(conversationId, body),
    () => refreshChat(ref),
  );
  ref
      .read(
        chatMessagesProvider((account: account, value: conversationId))
            .notifier,
      )
      .add(message);
  return message;
}

/// `POST /chat/reservations/{id}/conversation`: opens (creating on first use) the conversation of
/// one of the caller's own reservations.
Future<Conversation> openReservationConversation(
  WidgetRef ref,
  String reservationId,
) => runAsAccount(
  ref,
  () => ref.read(chatApiProvider).openReservationConversation(reservationId),
  () => ref.invalidate(conversationsProvider),
);
