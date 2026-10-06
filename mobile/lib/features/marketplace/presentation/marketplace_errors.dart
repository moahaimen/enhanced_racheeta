import '../../../core/api/api_exception.dart';
import '../../../core/api/error_messages.dart';
import '../../../l10n/generated/app_localizations.dart';

enum MarketplaceAction { browse, companyLoad, lifecycle }

/// Localised, user-safe text for a failed marketplace call. Raw server text is never shown; typed
/// codes are checked before the generic status classes.
String marketplaceErrorMessage(
  AppLocalizations l10n,
  ApiException error,
  MarketplaceAction action,
) {
  switch (error.code) {
    case 'company_not_verified':
      return l10n.errorCompanyNotVerified;
    case 'category_unavailable':
      return l10n.errorCategoryUnavailable;
    case 'invalid_transition' || 'invalid_product':
      return l10n.errorProductTransition;
  }
  if (error.kind == ApiErrorKind.forbidden) {
    return switch (action) {
      MarketplaceAction.browse => l10n.errorMarketplaceBrowse,
      MarketplaceAction.companyLoad => l10n.companyProfileMissing,
      MarketplaceAction.lifecycle => l10n.errorForbidden,
    };
  }
  if (action == MarketplaceAction.lifecycle &&
      error.kind == ApiErrorKind.validation) {
    return l10n.errorProductTransition;
  }
  return apiErrorMessage(l10n, error);
}
