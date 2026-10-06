import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../auth/application/account_scope.dart';
import '../data/marketplace_models.dart';
import 'marketplace_providers.dart';

/// After a lifecycle change the company's list, opened details and dashboard are reloaded from the
/// backend (the provider catalogue is targeted data and refreshes on its own reload).
void invalidateCompanyProducts(WidgetRef ref) {
  ref
    ..invalidate(companyProductsProvider)
    ..invalidate(companyProductDetailProvider)
    ..invalidate(companyDashboardProvider);
}

/// `POST /marketplace/company/products/{id}/activate`: one request for the initiating account
/// only (see `runAsAccount`); the backend's publication gate decides.
Future<Product> activateProduct(WidgetRef ref, String id) => runAsAccount(
  ref,
  () => ref.read(marketplaceApiProvider).activate(id),
  () => invalidateCompanyProducts(ref),
);

/// `POST /marketplace/company/products/{id}/deactivate`.
Future<Product> deactivateProduct(WidgetRef ref, String id) => runAsAccount(
  ref,
  () => ref.read(marketplaceApiProvider).deactivate(id),
  () => invalidateCompanyProducts(ref),
);
