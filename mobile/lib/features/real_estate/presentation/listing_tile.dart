import 'package:flutter/material.dart';

import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/format/formatters.dart';
import '../../../shared/theme/app_theme.dart';
import '../data/real_estate_models.dart';
import 'real_estate_labels.dart';

/// "1,200,000 IQD" or "Price on request" from the backend's amount and currency (no conversion).
String listingPrice(AppLocalizations l10n, PropertyListing l, String locale) =>
    l.price == null
    ? l10n.priceOnRequest
    : formatMoney(l.price!, l.currency, locale);

class ListingTile extends StatelessWidget {
  const ListingTile({
    required this.listing,
    required this.onTap,
    this.badges = const [],
    super.key,
  });

  final PropertyListing listing;
  final VoidCallback onTap;
  final List<Widget> badges;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final theme = Theme.of(context);
    final place = placeLine(listing.city, listing.governorate, locale);
    return Card(
      key: Key('listing-${listing.id}'),
      margin: const EdgeInsets.only(bottom: RacheetaSpacing.md),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(RacheetaSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(listing.title, style: theme.textTheme.titleMedium),
              const SizedBox(height: RacheetaSpacing.xs),
              Text(
                '${propertyTypeLabel(l10n, listing.propertyType)} · '
                '${transactionLabel(l10n, listing.transactionType)}',
                style: TextStyle(color: theme.colorScheme.primary),
              ),
              if (place.isNotEmpty || listing.district.isNotEmpty)
                Text(
                  [
                    place,
                    listing.district,
                  ].where((text) => text.isNotEmpty).join(' · '),
                ),
              const SizedBox(height: RacheetaSpacing.xs),
              Text(
                listingPrice(l10n, listing, locale),
                style: theme.textTheme.titleSmall,
              ),
              if (listing.areaSqm != null)
                Text(
                  '${l10n.areaLabel}: ${l10n.areaValue(formatDecimal(listing.areaSqm!, locale))}',
                ),
              if (badges.isNotEmpty) ...[
                const SizedBox(height: RacheetaSpacing.sm),
                Wrap(spacing: RacheetaSpacing.sm, children: badges),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
