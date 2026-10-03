import '../../l10n/generated/app_localizations.dart';
import '../auth/data/auth_models.dart';

/// Localised name of a backend role code (unknown future roles degrade to a neutral label).
String roleLabel(AppLocalizations l10n, String code) {
  switch (AccountRole.tryParse(code)) {
    case AccountRole.patient:
      return l10n.roleLabelPatient;
    case AccountRole.provider:
      return l10n.roleLabelProvider;
    case AccountRole.medicalCompany:
      return l10n.roleLabelMedicalCompany;
    case AccountRole.realEstateSeller:
      return l10n.roleLabelRealEstateSeller;
    case AccountRole.admin:
      return l10n.roleLabelAdmin;
    case null:
      return l10n.roleLabelUnknown;
  }
}
