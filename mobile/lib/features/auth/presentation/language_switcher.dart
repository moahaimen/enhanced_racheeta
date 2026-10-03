import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../l10n/generated/app_localizations.dart';
import '../application/providers.dart';

/// Toggles Arabic (RTL) / English. The choice is a non-sensitive preference and is also sent to
/// the backend as `Accept-Language`.
class LanguageSwitcher extends ConsumerWidget {
  const LanguageSwitcher({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final current = ref.watch(localeControllerProvider);
    final isArabic = current.languageCode == 'ar';
    return TextButton.icon(
      icon: const Icon(Icons.language),
      label: Text(isArabic ? l10n.languageEnglish : l10n.languageArabic),
      onPressed: () => ref
          .read(localeControllerProvider.notifier)
          .setLanguage(isArabic ? const Locale('en') : const Locale('ar')),
    );
  }
}
