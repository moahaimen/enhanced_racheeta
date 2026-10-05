import '../../../core/api/api_exception.dart';
import '../../../core/api/error_messages.dart';
import '../../../l10n/generated/app_localizations.dart';

enum RealEstateAction { load, lifecycle }

/// Localised, user-safe text for a failed real-estate call. Raw server text is never shown; a
/// validation refusal of a lifecycle action (the publication gate) becomes one fixed message.
String realEstateErrorMessage(
  AppLocalizations l10n,
  ApiException error,
  RealEstateAction action,
) {
  if (action == RealEstateAction.lifecycle) {
    // Typed codes first (a 400 `invalid_transition` is also "validation" by status).
    if (error.code == 'seller_not_eligible') return l10n.errorSellerNotEligible;
    if (error.code == 'invalid_transition') return l10n.errorListingTransition;
    if (error.kind == ApiErrorKind.validation) {
      return l10n.errorListingNotPublishable;
    }
  }
  // The owner endpoints answer 403 when the account has no seller profile yet.
  if (error.kind == ApiErrorKind.forbidden && error.code != 'throttled') {
    return error.code == 'seller_not_eligible'
        ? l10n.errorSellerNotEligible
        : l10n.sellerProfileMissing;
  }
  return apiErrorMessage(l10n, error);
}
