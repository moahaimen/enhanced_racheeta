import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../auth/application/account_scope.dart';
import '../data/real_estate_models.dart';
import 'real_estate_providers.dart';

/// After a lifecycle change the owner's list, opened details and dashboard are reloaded from the
/// backend (the public catalogue is not account state and refreshes on its own reload).
void invalidateOwnerListings(WidgetRef ref) {
  ref
    ..invalidate(ownerListingsProvider)
    ..invalidate(ownerListingDetailProvider)
    ..invalidate(ownerDashboardProvider);
}

/// `POST /real-estate/owner/listings/{id}/publish`. One request, for the initiating account only
/// (see `runAsAccount`); the backend's publication gate decides.
Future<PropertyListing> publishListing(WidgetRef ref, String id) =>
    runAsAccount(
      ref,
      () => ref.read(realEstateApiProvider).publish(id),
      () => invalidateOwnerListings(ref),
    );

/// `POST /real-estate/owner/listings/{id}/unpublish`.
Future<PropertyListing> unpublishListing(WidgetRef ref, String id) =>
    runAsAccount(
      ref,
      () => ref.read(realEstateApiProvider).unpublish(id),
      () => invalidateOwnerListings(ref),
    );
