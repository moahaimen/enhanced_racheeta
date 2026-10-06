import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/api/error_messages.dart';
import '../../../core/paging/paged_notifier.dart';
import '../../../core/time/time_providers.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/format/formatters.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/async_action_button.dart';
import '../../../shared/widgets/states.dart';
import '../../auth/application/account_scope.dart';
import '../../notifications/presentation/communication_errors.dart';
import '../application/chat_actions.dart';
import '../application/chat_providers.dart';
import '../data/chat_api.dart';
import '../data/chat_models.dart';

/// One conversation. Messages are shown exactly as the backend orders them (`sequence`, oldest at
/// the top, newest at the bottom); the thread, the composer draft and the send state are all keyed
/// by the signed-in account, so another account's messages, draft or in-flight send can never
/// appear here after `/me` changes while this screen stays mounted.
class ConversationPage extends ConsumerWidget {
  const ConversationPage({required this.conversationId, super.key});
  final String conversationId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final accountId = ref.watch(accountIdProvider);
    final key = (account: accountId, value: conversationId);
    final state = ref.watch(chatMessagesProvider(key));
    final controller = ref.read(chatMessagesProvider(key).notifier);

    // Header: the list entry when it is already loaded, else the other party named in the thread.
    final listed = ref
        .watch(conversationsProvider)
        .items
        .where((c) => c.id == conversationId)
        .firstOrNull;
    final otherName =
        listed?.other.fullName ??
        state.messages.where((m) => !m.isMine).firstOrNull?.sender.fullName;
    final title = (otherName == null || otherName.isEmpty)
        ? l10n.conversationTitle
        : otherName;

    if (state.phase == PagedPhase.loading) {
      return AppScaffold(
        title: title,
        scrollable: false,
        body: const LoadingView(),
      );
    }
    if (state.phase == PagedPhase.error) {
      return AppScaffold(
        title: title,
        scrollable: false,
        body: ErrorView(
          message: communicationErrorMessage(l10n, state.error!),
          onRetry: () async => controller.reload(),
        ),
      );
    }
    return AppScaffold(
      title: title,
      scrollable: false,
      body: Column(
        children: [
          Expanded(
            child: _MessageList(
              state: state,
              onLoadOlder: controller.loadOlder,
              onRefresh: controller.refresh,
            ),
          ),
          // A send pending for the previous account must not disable this account's composer and
          // its draft must not survive: a new account gets a fresh composer.
          KeyedSubtree(
            key: ValueKey('composer-$accountId-$conversationId'),
            child: _Composer(conversationId: conversationId),
          ),
        ],
      ),
    );
  }
}

class _MessageList extends StatelessWidget {
  const _MessageList({
    required this.state,
    required this.onLoadOlder,
    required this.onRefresh,
  });
  final ChatMessagesState state;
  final Future<void> Function() onLoadOlder;
  final Future<void> Function() onRefresh;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final messages = state.messages;
    if (messages.isEmpty) {
      return EmptyView(
        icon: Icons.chat_bubble_outline,
        title: l10n.chatNoMessages,
      );
    }
    // Reversed list: index 0 is the newest message at the bottom, and older messages added at
    // the far end never move what the reader is looking at.
    final newestFirst = messages.reversed.toList(growable: false);
    final extra = state.hasOlder ? 1 : 0;
    return RefreshIndicator(
      onRefresh: onRefresh,
      child: ListView.builder(
        key: const Key('message-list'),
        reverse: true,
        itemCount: newestFirst.length + extra,
        itemBuilder: (context, index) {
          if (index == newestFirst.length) {
            return Padding(
              padding: const EdgeInsets.symmetric(vertical: RacheetaSpacing.md),
              child: Column(
                children: [
                  if (state.loadOlderError != null)
                    Text(
                      l10n.chatLoadOlderFailed,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  if (state.loadingOlder)
                    const CircularProgressIndicator()
                  else
                    SecondaryButton(
                      key: const Key('load-older'),
                      label: l10n.chatLoadOlder,
                      onPressed: onLoadOlder,
                    ),
                ],
              ),
            );
          }
          return _Bubble(message: newestFirst[index]);
        },
      ),
    );
  }
}

class _Bubble extends ConsumerWidget {
  const _Bubble({required this.message});
  final ChatMessage message;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final wallClock = ref.watch(wallClockProvider);
    final mine = message.isMine;
    final who = mine ? l10n.chatYou : message.sender.fullName;
    final time = formatDateTime(message.createdAt, wallClock, locale);
    // Directional alignment: "mine" is always the end side, in both left-to-right and
    // right-to-left layouts, so RTL never swaps who wrote what.
    return Align(
      alignment: mine
          ? AlignmentDirectional.centerEnd
          : AlignmentDirectional.centerStart,
      child: Semantics(
        label: '$who, $time',
        child: Container(
          key: Key(mine ? 'mine-${message.id}' : 'theirs-${message.id}'),
          constraints: BoxConstraints(
            maxWidth: MediaQuery.sizeOf(context).width * 0.78,
          ),
          margin: const EdgeInsets.symmetric(vertical: RacheetaSpacing.xs),
          padding: const EdgeInsets.all(RacheetaSpacing.md),
          decoration: BoxDecoration(
            color: mine
                ? theme.colorScheme.primaryContainer
                : theme.colorScheme.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(message.body),
              const SizedBox(height: RacheetaSpacing.xs),
              Text(time, style: theme.textTheme.bodySmall),
            ],
          ),
        ),
      ),
    );
  }
}

class _Composer extends ConsumerStatefulWidget {
  const _Composer({required this.conversationId});
  final String conversationId;

  @override
  ConsumerState<_Composer> createState() => _ComposerState();
}

class _ComposerState extends ConsumerState<_Composer> {
  final TextEditingController _controller = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  String _sendError(AppLocalizations l10n, ApiException error) {
    final codes = error.codes?['body'] ?? const <String>[];
    if (codes.contains('blank')) return l10n.chatErrorBlank;
    if (codes.contains('max_length')) {
      return l10n.chatErrorTooLong(maxChatMessageLength);
    }
    return switch (error.kind) {
      ApiErrorKind.validation || ApiErrorKind.rejected => l10n.chatErrorSend,
      _ => apiErrorMessage(l10n, error),
    };
  }

  Future<void> _send() async {
    final l10n = AppLocalizations.of(context);
    final text = _controller.text.trim();
    if (text.isEmpty) {
      setState(() => _error = l10n.chatErrorBlank);
      return;
    }
    if (text.length > maxChatMessageLength) {
      setState(() => _error = l10n.chatErrorTooLong(maxChatMessageLength));
      return;
    }
    final accountId = ref.read(accountIdProvider);
    setState(() => _error = null);
    try {
      await sendChatMessage(ref, widget.conversationId, text);
      if (!mounted || ref.read(accountIdProvider) != accountId) return;
      _controller.clear();
      setState(() {});
    } on StaleSessionException {
      // The account changed while this was running: its outcome is never shown to the new one.
    } on ApiException catch (error) {
      if (!mounted || ref.read(accountIdProvider) != accountId) return;
      setState(() => _error = _sendError(l10n, error));
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(top: RacheetaSpacing.sm),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(bottom: RacheetaSpacing.sm),
              child: Semantics(
                liveRegion: true,
                child: Text(
                  _error!,
                  key: const Key('composer-error'),
                  style: TextStyle(color: theme.colorScheme.error),
                ),
              ),
            ),
          TextField(
            key: const Key('composer-field'),
            controller: _controller,
            minLines: 1,
            maxLines: 4,
            keyboardType: TextInputType.multiline,
            textInputAction: TextInputAction.newline,
            onChanged: (_) => setState(() => _error = null),
            decoration: InputDecoration(labelText: l10n.chatComposerLabel),
          ),
          const SizedBox(height: RacheetaSpacing.sm),
          // The theme's buttons are full width, so the button sits under the field (not in a Row).
          PrimaryButton(
            key: const Key('composer-send'),
            label: l10n.chatSend,
            pendingLabel: l10n.chatSending,
            icon: Icons.send,
            onPressed: _controller.text.trim().isEmpty ? null : _send,
          ),
        ],
      ),
    );
  }
}
