import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/async_action_button.dart';
import '../../../shared/widgets/confirm_dialog.dart';
import '../../../shared/widgets/states.dart';
import '../../auth/application/account_scope.dart';
import '../application/marketplace_actions.dart';
import '../application/marketplace_providers.dart';
import '../data/marketplace_models.dart';
import 'company_gate.dart';
import 'marketplace_errors.dart';
import 'product_detail_page.dart';

class CompanyProductDetailPage extends ConsumerWidget {
  const CompanyProductDetailPage({required this.productId, super.key});
  final String productId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    return CompanyGate(
      title: l10n.companyProductDetailTitle,
      child: _Detail(productId: productId),
    );
  }
}

class _Detail extends ConsumerStatefulWidget {
  const _Detail({required this.productId});
  final String productId;

  @override
  ConsumerState<_Detail> createState() => _DetailState();
}

class _DetailState extends ConsumerState<_Detail> {
  String? _message;
  bool _isError = false;
  bool _busy = false;

  /// Messages and the busy flag belong to one account.
  void _resetForAccountChange() => setState(() {
    _message = null;
    _isError = false;
    _busy = false;
  });

  Future<void> _run(Future<Product> Function() action, String success) async {
    final l10n = AppLocalizations.of(context);
    final accountId = ref.read(accountIdProvider);
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      await action();
      if (!mounted || ref.read(accountIdProvider) != accountId) return;
      setState(() {
        _busy = false;
        _message = success;
        _isError = false;
      });
    } on StaleSessionException {
      // The account changed while this was running: its result is never shown to the new one.
    } on ApiException catch (error) {
      if (!mounted || ref.read(accountIdProvider) != accountId) return;
      setState(() {
        _busy = false;
        _message = marketplaceErrorMessage(
          l10n,
          error,
          MarketplaceAction.lifecycle,
        );
        _isError = true;
      });
      // The backend refused (or the state changed elsewhere): show what is true now.
      ref.invalidate(companyProductDetailProvider);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    ref.listen<String?>(accountIdProvider, (previous, next) {
      if (previous != next) _resetForAccountChange();
    });
    final key = (
      account: ref.watch(accountIdProvider),
      value: widget.productId,
    );
    final detail = ref.watch(companyProductDetailProvider(key));

    // Keyed by account; during a reload the last value stays so the page message survives.
    if (detail.hasValue) return _content(context, detail.requireValue);
    if (detail.hasError && !detail.isLoading) {
      final error = detail.error;
      return AppScaffold(
        title: l10n.companyProductDetailTitle,
        scrollable: false,
        body: ErrorView(
          message: error is ApiException
              ? marketplaceErrorMessage(
                  l10n,
                  error,
                  MarketplaceAction.companyLoad,
                )
              : l10n.errorUnknown,
          onRetry: () async =>
              ref.invalidate(companyProductDetailProvider(key)),
        ),
      );
    }
    return AppScaffold(
      title: l10n.companyProductDetailTitle,
      body: const LoadingView(),
    );
  }

  Widget _content(BuildContext context, Product product) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    return ProductBody(
      title: l10n.companyProductDetailTitle,
      product: product,
      top: [
        if (_message != null)
          Padding(
            padding: const EdgeInsets.only(bottom: RacheetaSpacing.md),
            child: Semantics(
              liveRegion: true,
              child: Text(
                _message!,
                key: const Key('product-message'),
                style: TextStyle(
                  color: _isError
                      ? theme.colorScheme.error
                      : RacheetaColors.success,
                ),
              ),
            ),
          ),
        Padding(
          padding: const EdgeInsets.only(bottom: RacheetaSpacing.md),
          child: Chip(
            label: Text(productStatusText(l10n, product.isActive)),
            visualDensity: VisualDensity.compact,
          ),
        ),
      ],
      bottom: [
        const SizedBox(height: RacheetaSpacing.xl),
        // The button follows the stored state (a hint); the backend's gate decides.
        if (product.isActive == false)
          PrimaryButton(
            key: const Key('product-activate'),
            label: l10n.productActivate,
            pendingLabel: l10n.productActivating,
            icon: Icons.publish,
            onPressed: _busy
                ? null
                : () => _run(
                    () => activateProduct(ref, product.id),
                    l10n.productActivated,
                  ),
          )
        else if (product.isActive == true)
          SecondaryButton(
            key: const Key('product-deactivate'),
            label: l10n.productDeactivate,
            pendingLabel: l10n.productDeactivating,
            icon: Icons.unpublished_outlined,
            confirm: () => showConfirmDialog(
              context,
              title: l10n.confirmDeactivateTitle,
              message: l10n.confirmDeactivateBody,
              confirmLabel: l10n.productDeactivate,
              cancelLabel: l10n.confirmKeepActive,
            ),
            onPressed: _busy
                ? null
                : () => _run(
                    () => deactivateProduct(ref, product.id),
                    l10n.productDeactivated,
                  ),
          ),
      ],
    );
  }
}
