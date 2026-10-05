import '../../../core/api/api_exception.dart';
import '../../../core/api/error_messages.dart';
import '../../../l10n/generated/app_localizations.dart';

/// The same backend code means different things per action (`slot_conflict` is an overlap when
/// creating, `slot_unavailable` is "a live reservation uses it" when removing), so provider errors
/// are mapped with their action.
enum ProviderAction { load, createSlot, deactivateSlot, transition }

/// Localised, user-safe text for a failed provider call. Raw exception text and server internals
/// are never shown; an unknown code falls back to the shared mapping.
String providerErrorMessage(
  AppLocalizations l10n,
  ApiException error,
  ProviderAction action,
) {
  switch (action) {
    case ProviderAction.createSlot:
      switch (error.code) {
        case 'slot_conflict':
          return l10n.errorSlotOverlap;
        case 'invalid_availability':
          return l10n.errorSlotPast;
        case 'service_unavailable':
          return l10n.errorSlotService;
      }
    case ProviderAction.deactivateSlot:
      if (error.code == 'slot_unavailable') return l10n.errorSlotInUse;
    case ProviderAction.transition:
      if (error.code == 'invalid_transition') {
        return l10n.errorTransitionRefused;
      }
    case ProviderAction.load:
      break;
  }
  // The provider endpoints answer 403 when the account has no provider profile yet.
  if (error.kind == ApiErrorKind.forbidden) return l10n.providerProfileMissing;
  return apiErrorMessage(l10n, error);
}
