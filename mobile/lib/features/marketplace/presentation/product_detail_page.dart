import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/states.dart';
import '../../auth/application/account_scope.dart';
import '../../discovery/data/discovery_models.dart' show Place;
import '../application/marketplace_providers.dart';
import '../data/marketplace_models.dart';
import 'marketplace_errors.dart';
import 'product_tile.dart';
import '../../../shared/widgets/selectable_value.dart';

/// One catalogue product exactly as the API exposes it (including the supplier's public contact
/// details the B2B schema carries). Websites are shown as text: the app opens no external links.
class ProductDetailPage extends ConsumerWidget {
  const ProductDetailPage({required this.productId, super.key});
  final String productId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final key = (account: ref.watch(accountIdProvider), value: productId);
    final detail = ref.watch(productDetailProvider(key));
    if (detail.hasValue) {
      return ProductBody(
        title: l10n.productDetailTitle,
        product: detail.requireValue,
      );
    }
    if (detail.hasError && !detail.isLoading) {
      final error = detail.error;
      return AppScaffold(
        title: l10n.productDetailTitle,
        scrollable: false,
        body: ErrorView(
          message: error is ApiException
              ? marketplaceErrorMessage(l10n, error, MarketplaceAction.browse)
              : l10n.errorUnknown,
          onRetry: () async => ref.invalidate(productDetailProvider(key)),
        ),
      );
    }
    return AppScaffold(
      title: l10n.productDetailTitle,
      body: const LoadingView(),
    );
  }
}

/// The product card shared by the catalogue detail and the company's own detail.
class ProductBody extends StatelessWidget {
  const ProductBody({
    required this.title,
    required this.product,
    this.top = const [],
    this.bottom = const [],
    super.key,
  });

  final String title;
  final Product product;
  final List<Widget> top;
  final List<Widget> bottom;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final theme = Theme.of(context);
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
          SelectableValue(value),
        ],
      ),
    );
    final company = product.company;
    String place(Place? city, Place? governorate) => [
      city?.name(locale),
      governorate?.name(locale),
    ].whereType<String>().where((n) => n.isNotEmpty).join('، ');

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
                      product.title,
                      style: theme.textTheme.headlineSmall,
                    ),
                  ),
                  const SizedBox(height: RacheetaSpacing.sm),
                  Text(
                    productPrice(l10n, product, locale),
                    key: const Key('product-price'),
                    style: theme.textTheme.titleLarge,
                  ),
                  const SizedBox(height: RacheetaSpacing.md),
                  row(l10n.categoryLabel, product.category.name(locale)),
                  if (product.brand.isNotEmpty)
                    row(l10n.brandLabel, product.brand),
                  if (product.modelName.isNotEmpty)
                    row(l10n.modelLabel, product.modelName),
                ],
              ),
            ),
          ),
          if (product.description.isNotEmpty) ...[
            const SizedBox(height: RacheetaSpacing.lg),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(RacheetaSpacing.lg),
                child: SelectableValue(product.description),
              ),
            ),
          ],
          if (company != null) ...[
            const SizedBox(height: RacheetaSpacing.lg),
            Card(
              key: const Key('product-supplier'),
              child: Padding(
                padding: const EdgeInsets.all(RacheetaSpacing.lg),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    row(l10n.supplierLabel, company.name),
                    if (place(company.city, company.governorate).isNotEmpty)
                      row(
                        l10n.detailLocation,
                        place(company.city, company.governorate),
                      ),
                    if (company.phone.isNotEmpty)
                      row(l10n.detailPhone, company.phone),
                    if (company.publicEmail.isNotEmpty)
                      row(l10n.detailEmail, company.publicEmail),
                    if (company.website.isNotEmpty)
                      row(l10n.detailWebsite, company.website),
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

/// Used by the company's own list/detail.
String productStatusText(AppLocalizations l10n, bool? active) =>
    active == true ? l10n.productStatusActive : l10n.productStatusInactive;
