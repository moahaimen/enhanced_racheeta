import '../../../core/api/api_exception.dart';
import '../../../core/api/error_messages.dart';
import '../../../l10n/generated/app_localizations.dart';

enum JobsAction { browse, apply, withdraw, recruiterLoad, close }

/// Localised, user-safe text for a failed jobs call. Raw server text is never shown; typed codes
/// are checked before the generic status classes (a 409/400 may carry the same kind as others).
String jobsErrorMessage(
  AppLocalizations l10n,
  ApiException error,
  JobsAction action,
) {
  switch (error.code) {
    case 'job_not_open':
      return l10n.errorJobNotOpen;
    case 'deadline_passed':
      return l10n.errorDeadlinePassed;
    case 'already_applied':
      return l10n.errorAlreadyApplied;
    case 'contact_information_not_allowed':
      return l10n.errorContactNotAllowed;
    case 'entitlement_required' || 'usage_limit_reached':
      return l10n.errorApplicationLimit;
    case 'membership_inactive':
      return l10n.errorMembershipInactive;
    case 'application_closed':
      return l10n.errorApplicationTransition;
    case 'invalid_transition':
      return action == JobsAction.close
          ? l10n.errorJobTransition
          : l10n.errorApplicationTransition;
  }
  if (error.kind == ApiErrorKind.forbidden) {
    return switch (action) {
      // The apply endpoint answers 403 when the account has no job-seeker profile yet.
      JobsAction.apply || JobsAction.withdraw => l10n.errorProfileRequired,
      JobsAction.recruiterLoad ||
      JobsAction.close => l10n.recruiterProfileMissing,
      JobsAction.browse => l10n.errorForbidden,
    };
  }
  return apiErrorMessage(l10n, error);
}
