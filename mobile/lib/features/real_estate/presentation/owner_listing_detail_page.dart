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
import '../application/real_estate_actions.dart';
import '../application/real_estate_providers.dart';
import '../data/real_estate_models.dart';
import 'listing_detail_page.dart';
import 'owner_listings_page.dart';
import 'real_estate_errors.dart';
import 'seller_gate.dart';

class OwnerListingDetailPage extends ConsumerWidget {
  const OwnerListingDetailPage({required this.listingId, super.key});
  final String listingId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    return SellerGate(
      title: l10n.ownerListingDetailTitle,
      child: _Detail(listingId: listingId),
    );
  }
}

class _Detail extends ConsumerStatefulWidget {
  const _Detail({required this.listingId});
  final String listingId;

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

  Future<void> _run(
    Future<PropertyListing> Function() action,
    String success,
  ) async {
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
        _message = realEstateErrorMessage(
          l10n,
          error,
          RealEstateAction.lifecycle,
        );
        _isError = true;
      });
      // The backend refused (or the state changed elsewhere): show what is true now.
      ref.invalidate(ownerListingDetailProvider);
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
      value: widget.listingId,
    );
    final detail = ref.watch(ownerListingDetailProvider(key));

    // Keyed by account; during a reload the last value stays so the page message survives.
    if (detail.hasValue) return _content(context, detail.requireValue);
    if (detail.hasError && !detail.isLoading) {
      final error = detail.error;
      return AppScaffold(
        title: l10n.ownerListingDetailTitle,
        scrollable: false,
        body: ErrorView(
          message: error is ApiException
              ? realEstateErrorMessage(l10n, error, RealEstateAction.load)
              : l10n.errorUnknown,
          onRetry: () async => ref.invalidate(ownerListingDetailProvider(key)),
        ),
      );
    }
    return AppScaffold(
      title: l10n.ownerListingDetailTitle,
      body: const LoadingView(),
    );
  }

  Widget _content(BuildContext context, PropertyListing listing) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final status = listing.publicationStatus;
    return ListingBody(
      title: l10n.ownerListingDetailTitle,
      listing: listing,
      top: [
        if (_message != null)
          Padding(
            padding: const EdgeInsets.only(bottom: RacheetaSpacing.md),
            child: Semantics(
              liveRegion: true,
              child: Text(
                _message!,
                key: const Key('listing-message'),
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
          child: Wrap(
            spacing: RacheetaSpacing.sm,
            children: ownerBadges(l10n, listing),
          ),
        ),
      ],
      bottom: [
        const SizedBox(height: RacheetaSpacing.xl),
        // The button follows the stored status (a hint); the backend's gate decides.
        if (status == 'DRAFT')
          PrimaryButton(
            key: const Key('listing-publish'),
            label: l10n.listingPublish,
            pendingLabel: l10n.listingPublishing,
            icon: Icons.publish,
            onPressed: _busy
                ? null
                : () => _run(
                    () => publishListing(ref, listing.id),
                    l10n.listingPublished,
                  ),
          )
        else if (status == 'PUBLISHED')
          SecondaryButton(
            key: const Key('listing-unpublish'),
            label: l10n.listingUnpublish,
            pendingLabel: l10n.listingUnpublishing,
            icon: Icons.unpublished_outlined,
            confirm: () => showConfirmDialog(
              context,
              title: l10n.confirmUnpublishTitle,
              message: l10n.confirmUnpublishBody,
              confirmLabel: l10n.listingUnpublish,
              cancelLabel: l10n.confirmKeepPublished,
            ),
            onPressed: _busy
                ? null
                : () => _run(
                    () => unpublishListing(ref, listing.id),
                    l10n.listingUnpublished,
                  ),
          ),
      ],
    );
  }
}
