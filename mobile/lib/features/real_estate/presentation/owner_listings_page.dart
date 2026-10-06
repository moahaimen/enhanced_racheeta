import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/paged_list.dart';
import '../application/real_estate_providers.dart';
import '../data/real_estate_models.dart';
import 'listing_tile.dart';
import 'real_estate_errors.dart';
import 'real_estate_labels.dart';
import 'seller_gate.dart';

/// Chips for an owner listing: the stored status plus the backend's own visibility/expiry verdicts.
List<Widget> ownerBadges(AppLocalizations l10n, PropertyListing listing) => [
  Chip(
    label: Text(publicationLabel(l10n, listing.publicationStatus ?? '')),
    visualDensity: VisualDensity.compact,
  ),
  if (listing.isPublic == true)
    Chip(label: Text(l10n.badgeVisible), visualDensity: VisualDensity.compact),
  if (listing.isExpired == true)
    Chip(label: Text(l10n.badgeExpired), visualDensity: VisualDensity.compact),
];

/// The owner's own listings in the backend's order (newest first).
class OwnerListingsPage extends ConsumerWidget {
  const OwnerListingsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    return SellerGate(title: l10n.ownerListingsTitle, child: const _List());
  }
}

class _List extends ConsumerWidget {
  const _List();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final state = ref.watch(ownerListingsProvider);
    final controller = ref.read(ownerListingsProvider.notifier);
    return AppScaffold(
      title: l10n.ownerListingsTitle,
      scrollable: false,
      body: PagedListView(
        state: state,
        onLoadMore: controller.loadMore,
        onReload: controller.reload,
        errorMessage: (l10n, error) =>
            realEstateErrorMessage(l10n, error, RealEstateAction.load),
        emptyIcon: Icons.apartment,
        emptyTitle: l10n.ownerListingsEmpty,
        emptyMessage: l10n.ownerListingsEmptyBody,
        itemBuilder: (context, listing) => ListingTile(
          listing: listing,
          badges: ownerBadges(l10n, listing),
          onTap: () => context.push('/seller/listings/${listing.id}'),
        ),
      ),
    );
  }
}
