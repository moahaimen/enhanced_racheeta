import '../../l10n/generated/app_localizations.dart';
import 'api_exception.dart';

/// Localised, user-safe text for a failure. Raw exception text, stack traces and server internals
/// are never shown; the machine `code` decides, with the server's (already localised) message used
/// only for validation errors it wrote for the user.
String apiErrorMessage(AppLocalizations l10n, ApiException error) {
  if (error.code == 'no_active_account') return l10n.errorInvalidCredentials;
  switch (error.kind) {
    case ApiErrorKind.network:
      return l10n.errorNetwork;
    case ApiErrorKind.timeout:
      return l10n.errorTimeout;
    case ApiErrorKind.throttled:
      return l10n.errorThrottled;
    case ApiErrorKind.forbidden:
      return l10n.errorForbidden;
    case ApiErrorKind.server:
      return l10n.errorServer;
    case ApiErrorKind.unauthorized:
      return l10n.sessionExpired;
    case ApiErrorKind.validation:
    case ApiErrorKind.rejected:
    case ApiErrorKind.notFound:
      return error.message.isNotEmpty ? error.message : l10n.errorUnknown;
    case ApiErrorKind.cancelled:
      return l10n.errorUnknown;
  }
}
