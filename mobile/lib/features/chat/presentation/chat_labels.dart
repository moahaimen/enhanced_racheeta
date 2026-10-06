import '../../../l10n/generated/app_localizations.dart';

/// Label of what a conversation is about. Only `RESERVATION` exists today; an unknown future
/// context type degrades to a neutral label instead of failing.
String conversationContextLabel(AppLocalizations l10n, String contextType) =>
    switch (contextType) {
      'RESERVATION' => l10n.chatContextReservation,
      _ => l10n.chatContextOther,
    };
