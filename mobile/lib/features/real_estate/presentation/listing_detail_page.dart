import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/time/time_providers.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/format/formatters.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/states.dart';
import '../application/real_estate_providers.dart';
import '../data/real_estate_models.dart';
import 'listing_tile.dart';
import 'real_estate_errors.dart';
import 'real_estate_labels.dart';

/// One public listing, exactly the fields the public API exposes (the contact values are only the
/// ones the seller's contact method makes public).
class ListingDetailPage extends ConsumerWidget {
  const ListingDetailPage({required this.listingId, super.key});
  final String listingId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final detail = ref.watch(listingDetailProvider(listingId));
    return detail.when(
      loading: () => AppScaffold(
        title: l10n.listingDetailTitle,
        body: const LoadingView(),
      ),
      error: (error, _) => AppScaffold(
        title: l10n.listingDetailTitle,
        scrollable: false,
        body: ErrorView(
          message: error is ApiException
              ? realEstateErrorMessage(l10n, error, RealEstateAction.load)
              : l10n.errorUnknown,
          onRetry: () async => ref.invalidate(listingDetailProvider(listingId)),
        ),
      ),
      data: (listing) =>
          ListingBody(title: l10n.listingDetailTitle, listing: listing),
    );
  }
}

/// The shared listing card used by the public detail and the owner's detail.
class ListingBody extends ConsumerWidget {
  const ListingBody({
    required this.title,
    required this.listing,
    this.top = const [],
    this.bottom = const [],
    super.key,
  });

  final String title;
  final PropertyListing listing;
  final List<Widget> top;
  final List<Widget> bottom;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final theme = Theme.of(context);
    final wallClock = ref.watch(wallClockProvider);
    final place = placeLine(listing.city, listing.governorate, locale);
    final uses = listing.suitableUses
        .map((code) => suitableUseLabel(l10n, code))
        .join('، ');
    final contacts = [
      if (listing.contactPhone != null && listing.contactPhone!.isNotEmpty)
        (l10n.detailPhone, listing.contactPhone!),
      if (listing.contactEmail != null && listing.contactEmail!.isNotEmpty)
        (l10n.detailEmail, listing.contactEmail!),
    ];
    Widget row(String label, String value) => Padding(
      padding: const EdgeInsets.only(bottom: RacheetaSpacing.sm),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          SelectableText(value),
        ],
      ),
    );

    return AppScaffold(
      title: title,
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          ...top,
          Card(
            child: Padding(
              padding: const EdgeInsets.all(RacheetaSpacing.lg),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Semantics(
                    header: true,
                    child: Text(
                      listing.title,
                      style: theme.textTheme.headlineSmall,
                    ),
                  ),
                  const SizedBox(height: RacheetaSpacing.xs),
                  Text(
                    '${propertyTypeLabel(l10n, listing.propertyType)} · '
                    '${transactionLabel(l10n, listing.transactionType)}',
                    style: TextStyle(color: theme.colorScheme.primary),
                  ),
                  const SizedBox(height: RacheetaSpacing.sm),
                  Text(
                    listingPrice(l10n, listing, locale),
                    key: const Key('listing-price'),
                    style: theme.textTheme.titleLarge,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: RacheetaSpacing.lg),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(RacheetaSpacing.lg),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (place.isNotEmpty) row(l10n.detailLocation, place),
                  if (listing.district.isNotEmpty)
                    row(l10n.districtLabel, listing.district),
                  if (listing.areaSqm != null)
                    row(
                      l10n.areaLabel,
                      l10n.areaValue(formatDecimal(listing.areaSqm!, locale)),
                    ),
                  if (uses.isNotEmpty) row(l10n.suitableForLabel, uses),
                  if (listing.facilities.isNotEmpty)
                    row(l10n.facilitiesLabel, listing.facilities),
                  if (listing.expiresAt != null)
                    row(
                      l10n.listingValidUntil,
                      formatDate(listing.expiresAt!, wallClock, locale),
                    ),
                ],
              ),
            ),
          ),
          if (listing.description.isNotEmpty) ...[
            const SizedBox(height: RacheetaSpacing.lg),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(RacheetaSpacing.lg),
                child: SelectableText(listing.description),
              ),
            ),
          ],
          if (listing.seller != null) ...[
            const SizedBox(height: RacheetaSpacing.lg),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(RacheetaSpacing.lg),
                child: row(
                  l10n.listedByLabel,
                  '${listing.seller!.displayName} · '
                  '${sellerTypeLabel(l10n, listing.seller!.sellerType)}',
                ),
              ),
            ),
          ],
          if (contacts.isNotEmpty) ...[
            const SizedBox(height: RacheetaSpacing.lg),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(RacheetaSpacing.lg),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Semantics(
                      header: true,
                      child: Text(
                        l10n.detailContact,
                        style: theme.textTheme.titleMedium,
                      ),
                    ),
                    const SizedBox(height: RacheetaSpacing.sm),
                    for (final (label, value) in contacts) row(label, value),
                  ],
                ),
              ),
            ),
          ],
          ...bottom,
        ],
      ),
    );
  }
}
