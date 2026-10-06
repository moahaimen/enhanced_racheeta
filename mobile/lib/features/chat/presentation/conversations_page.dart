import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/time/time_providers.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/format/formatters.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/paged_list.dart';
import '../../account/role_label.dart';
import '../../notifications/presentation/communication_errors.dart';
import '../../push/push_routes.dart';
import '../application/chat_providers.dart';
import '../data/chat_models.dart';
import 'chat_labels.dart';

/// The signed-in account's existing conversations. Conversations start from a reservation (the
/// only context the backend supports); the list only shows what the backend scopes to this
/// account — nothing about membership is inferred on the device.
class ConversationsPage extends ConsumerWidget {
  const ConversationsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final wallClock = ref.watch(wallClockProvider);
    final state = ref.watch(conversationsProvider);
    final controller = ref.read(conversationsProvider.notifier);
    return AppScaffold(
      title: l10n.chatTitle,
      scrollable: false,
      body: PagedListView<Conversation>(
        state: state,
        onLoadMore: controller.loadMore,
        onReload: () {
          controller.reload();
          ref.invalidate(chatUnreadProvider);
        },
        errorMessage: communicationErrorMessage,
        emptyIcon: Icons.chat_bubble_outline,
        emptyTitle: l10n.chatEmpty,
        emptyMessage: l10n.chatEmptyBody,
        showCount: false,
        itemBuilder: (context, conversation) => _ConversationTile(
          conversation: conversation,
          time: conversation.lastMessageAt == null
              ? null
              : formatDateTime(conversation.lastMessageAt!, wallClock, locale),
        ),
      ),
    );
  }
}

class _ConversationTile extends StatelessWidget {
  const _ConversationTile({required this.conversation, this.time});
  final Conversation conversation;
  final String? time;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final name = conversation.other.fullName.isEmpty
        ? l10n.conversationTitle
        : conversation.other.fullName;
    return Card(
      key: Key('conversation-${conversation.id}'),
      margin: const EdgeInsets.only(bottom: RacheetaSpacing.sm),
      child: ListTile(
        minTileHeight: RacheetaSpacing.minTouchTarget,
        title: Text(
          name,
          style: TextStyle(
            fontWeight: conversation.hasUnread
                ? FontWeight.w700
                : FontWeight.w500,
          ),
        ),
        subtitle: Text(
          [
            roleLabel(l10n, conversation.other.role),
            conversationContextLabel(l10n, conversation.contextType),
            ?time,
          ].join(' · '),
        ),
        trailing: conversation.hasUnread
            ? Semantics(
                label: l10n.chatUnread(conversation.unreadCount),
                child: Badge(
                  key: Key('unread-badge-${conversation.id}'),
                  label: Text('${conversation.unreadCount}'),
                ),
              )
            : const Icon(Icons.chevron_right),
        onTap: () => context.push('$chatRoute/${conversation.id}'),
      ),
    );
  }
}
