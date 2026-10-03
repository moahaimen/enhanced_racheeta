import 'package:flutter/material.dart';

import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/format/formatters.dart';
import '../../../shared/format/labels.dart';
import '../../../shared/theme/app_theme.dart';
import '../data/discovery_models.dart';

/// The one-line place summary ("City, Governorate") from the names the backend supplied.
String placeSummary(ProviderCard card, String languageCode) => [
  card.city?.name(languageCode),
  card.governorate?.name(languageCode),
].whereType<String>().where((name) => name.isNotEmpty).join('، ');

/// Rating line, only from backend data: null average means "no reviews yet", never a made-up value.
String ratingText(AppLocalizations l10n, ProviderCard card, String locale) =>
    card.averageRating == null || card.reviewCount == 0
    ? l10n.noReviews
    : l10n.ratingSummary(
        formatRating(card.averageRating!, locale),
        card.reviewCount,
      );

class ProviderCardTile extends StatelessWidget {
  const ProviderCardTile({required this.card, required this.onTap, super.key});

  final ProviderCard card;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final language = Localizations.localeOf(context).languageCode;
    final specialties = card.specialties
        .map((s) => s.name(language))
        .where((name) => name.isNotEmpty)
        .join('، ');
    final place = placeSummary(card, language);
    return Card(
      margin: const EdgeInsets.only(bottom: RacheetaSpacing.md),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(RacheetaSpacing.lg),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              ExcludeSemantics(
                child: CircleAvatar(
                  backgroundColor: theme.colorScheme.primaryContainer,
                  foregroundColor: theme.colorScheme.onPrimaryContainer,
                  child: Text(
                    card.displayName.isEmpty
                        ? '?'
                        : card.displayName.characters.first,
                  ),
                ),
              ),
              const SizedBox(width: RacheetaSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(card.displayName, style: theme.textTheme.titleMedium),
                    Text(
                      providerTypeLabel(l10n, card.providerType),
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.primary,
                      ),
                    ),
                    if (specialties.isNotEmpty) Text(specialties),
                    if (place.isNotEmpty)
                      Text(
                        place,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    Text(
                      ratingText(l10n, card, language),
                      style: theme.textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
