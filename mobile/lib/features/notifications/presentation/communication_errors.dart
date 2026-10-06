import '../../../core/api/api_exception.dart';
import '../../../core/api/error_messages.dart';
import '../../../l10n/generated/app_localizations.dart';

/// Safe text for a failed notification / chat call. Server messages are never shown (a validation
/// message could carry user content); typed kinds map to fixed localized text, and a 404 is the
/// same generic "not found" whether the thing is missing or belongs to someone else.
String communicationErrorMessage(AppLocalizations l10n, ApiException error) =>
    error.kind == ApiErrorKind.validation
    ? l10n.errorUnknown
    : apiErrorMessage(l10n, error);
