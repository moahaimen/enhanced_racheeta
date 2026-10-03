import 'package:flutter/material.dart';

import '../../l10n/generated/app_localizations.dart';
import '../theme/app_theme.dart';
import 'async_action_button.dart';

/// Loading feedback for a backend-connected page (mandatory loading rule).
class LoadingView extends StatelessWidget {
  const LoadingView({this.message, super.key});
  final String? message;

  @override
  Widget build(BuildContext context) {
    final text = message ?? AppLocalizations.of(context).loading;
    return Center(
      child: Semantics(
        liveRegion: true,
        label: text,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CircularProgressIndicator(),
            const SizedBox(height: RacheetaSpacing.lg),
            ExcludeSemantics(child: Text(text, textAlign: TextAlign.center)),
          ],
        ),
      ),
    );
  }
}

/// A failed load, with an optional retry. Never shows raw exception text.
class ErrorView extends StatelessWidget {
  const ErrorView({
    required this.message,
    this.title,
    this.onRetry,
    this.secondaryLabel,
    this.onSecondary,
    super.key,
  });

  final String message;
  final String? title;
  final Future<void> Function()? onRetry;
  final String? secondaryLabel;
  final Future<void> Function()? onSecondary;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(
          maxWidth: RacheetaSpacing.maxContentWidth,
        ),
        child: Padding(
          padding: const EdgeInsets.all(RacheetaSpacing.xl),
          child: Semantics(
            liveRegion: true,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Icon(
                  Icons.error_outline,
                  size: 48,
                  color: theme.colorScheme.error,
                ),
                const SizedBox(height: RacheetaSpacing.lg),
                if (title != null) ...[
                  Text(
                    title!,
                    style: theme.textTheme.titleMedium,
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: RacheetaSpacing.sm),
                ],
                Text(message, textAlign: TextAlign.center),
                if (onRetry != null) ...[
                  const SizedBox(height: RacheetaSpacing.xl),
                  PrimaryButton(
                    label: l10n.retry,
                    icon: Icons.refresh,
                    onPressed: onRetry,
                  ),
                ],
                if (onSecondary != null && secondaryLabel != null) ...[
                  const SizedBox(height: RacheetaSpacing.md),
                  SecondaryButton(
                    label: secondaryLabel!,
                    onPressed: onSecondary,
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// A successful load that has nothing to show (explicit, never a blank screen).
class EmptyView extends StatelessWidget {
  const EmptyView({
    this.title,
    this.message,
    this.icon = Icons.inbox_outlined,
    super.key,
  });
  final String? title;
  final String? message;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(RacheetaSpacing.xl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 48, color: theme.colorScheme.onSurfaceVariant),
            const SizedBox(height: RacheetaSpacing.lg),
            Text(
              title ?? AppLocalizations.of(context).emptyTitle,
              style: theme.textTheme.titleMedium,
              textAlign: TextAlign.center,
            ),
            if (message != null) ...[
              const SizedBox(height: RacheetaSpacing.sm),
              Text(message!, textAlign: TextAlign.center),
            ],
          ],
        ),
      ),
    );
  }
}
