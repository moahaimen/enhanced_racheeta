import 'package:flutter/material.dart';

import '../../l10n/generated/app_localizations.dart';

/// Asks the user to confirm a consequential action. Resolves to true only on explicit confirm.
Future<bool> showConfirmDialog(
  BuildContext context, {
  required String title,
  required String message,
  required String confirmLabel,
  String? cancelLabel,
}) async {
  final l10n = AppLocalizations.of(context);
  final result = await showDialog<bool>(
    context: context,
    builder: (dialogContext) => AlertDialog(
      title: Text(title),
      content: Text(message),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(dialogContext).pop(false),
          child: Text(cancelLabel ?? l10n.cancel),
        ),
        FilledButton(
          onPressed: () => Navigator.of(dialogContext).pop(true),
          style: FilledButton.styleFrom(minimumSize: const Size(88, 48)),
          child: Text(confirmLabel),
        ),
      ],
    ),
  );
  return result ?? false;
}
