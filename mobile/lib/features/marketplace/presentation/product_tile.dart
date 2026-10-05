import 'package:flutter/material.dart';

import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/format/formatters.dart';
import '../../../shared/theme/app_theme.dart';
import '../data/marketplace_models.dart';

/// "250,000 IQD" or "Price on request" from the backend's amount and currency (no conversion).
String productPrice(AppLocalizations l10n, Product product, String locale) =>
    product.price == null
    ? l10n.priceOnRequest
    : formatMoney(product.price!, product.currency, locale);

class ProductTile extends StatelessWidget {
  const ProductTile({
    required this.product,
    required this.onTap,
    this.badges = const [],
    super.key,
  });

  final Product product;
  final VoidCallback onTap;
  final List<Widget> badges;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final theme = Theme.of(context);
    final subtitle = [
      product.brand,
      product.modelName,
    ].where((text) => text.isNotEmpty).join(' · ');
    return Card(
      key: Key('product-${product.id}'),
      margin: const EdgeInsets.only(bottom: RacheetaSpacing.md),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(RacheetaSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(product.title, style: theme.textTheme.titleMedium),
              if (subtitle.isNotEmpty) Text(subtitle),
              Text(
                product.category.name(locale),
                style: TextStyle(color: theme.colorScheme.primary),
              ),
              if (product.company != null) Text(product.company!.name),
              const SizedBox(height: RacheetaSpacing.xs),
              Text(
                productPrice(l10n, product, locale),
                style: theme.textTheme.titleSmall,
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
