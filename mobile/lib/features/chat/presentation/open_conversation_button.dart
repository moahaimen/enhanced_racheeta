import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_exception.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/async_action_button.dart';
import '../../auth/application/account_scope.dart';
import '../../notifications/presentation/communication_errors.dart';
import '../../push/push_routes.dart';
import '../application/chat_actions.dart';

/// "Message the other party" on a reservation: opens (creating on first use) the one conversation
/// of that reservation and goes to it. The backend decides who may (only the reservation's own
/// participants; anyone else gets a plain 404). One request per tap; the button, its error text and
/// any pending state belong to the signed-in account and are replaced when it changes.
class OpenConversationButton extends ConsumerWidget {
  const OpenConversationButton({
    required this.reservationId,
    required this.label,
    super.key,
  });
  final String reservationId;
  final String label;

  @override
  Widget build(BuildContext context, WidgetRef ref) => KeyedSubtree(
    key: ValueKey('open-chat-${ref.watch(accountIdProvider)}'),
    child: _Inner(reservationId: reservationId, label: label),
  );
}

class _Inner extends ConsumerStatefulWidget {
  const _Inner({required this.reservationId, required this.label});
  final String reservationId;
  final String label;

  @override
  ConsumerState<_Inner> createState() => _InnerState();
}

class _InnerState extends ConsumerState<_Inner> {
  String? _error;

  Future<void> _open() async {
    final l10n = AppLocalizations.of(context);
    final accountId = ref.read(accountIdProvider);
    setState(() => _error = null);
    try {
      final conversation = await openReservationConversation(
        ref,
        widget.reservationId,
      );
      if (!mounted || ref.read(accountIdProvider) != accountId) return;
      await context.push('$chatRoute/${conversation.id}');
    } on StaleSessionException {
      // another account is signed in: nothing to do
    } on ApiException catch (error) {
      if (!mounted || ref.read(accountIdProvider) != accountId) return;
      setState(
        () => _error = error.kind == ApiErrorKind.notFound
            ? l10n.chatOpenFailed
            : communicationErrorMessage(l10n, error),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SecondaryButton(
          key: const Key('open-conversation'),
          label: widget.label,
          pendingLabel: l10n.chatOpening,
          icon: Icons.chat_bubble_outline,
          onPressed: _open,
        ),
        if (_error != null)
          Padding(
            padding: const EdgeInsets.only(top: RacheetaSpacing.sm),
            child: Semantics(
              liveRegion: true,
              child: Text(
                _error!,
                key: const Key('open-conversation-error'),
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
          ),
      ],
    );
  }
}
