import 'package:flutter/material.dart';

import '../../l10n/generated/app_localizations.dart';
import '../auth/data/auth_models.dart';
import '../jobs/provider_capability.dart';
import '../marketplace/provider_capability.dart';
import '../real_estate/provider_capability.dart';

/// One entry point on the Home screen's *Explore* section. The bottom bar stays small; everything
/// the account may use beyond it is reachable from here. Availability follows the account's `/me`
/// capabilities and, for recruiters (whose membership is not a capability), the server's dashboard
/// index. It only decides what is *shown*: the backend authorizes every call.
class ExploreEntry {
  const ExploreEntry({
    required this.id,
    required this.path,
    required this.icon,
    required this.label,
    required this.isAvailableFor,
  });

  final String id;
  final String path;
  final IconData icon;
  final String Function(AppLocalizations l10n) label;
  final bool Function(Account account, Set<String> dashboards) isAvailableFor;
}

final List<ExploreEntry> exploreEntries = <ExploreEntry>[
  ExploreEntry(
    id: 'jobs',
    path: '/jobs',
    icon: Icons.work_outline,
    label: (l10n) => l10n.jobsTitle,
    isAvailableFor: (account, dashboards) => true,
  ),
  ExploreEntry(
    id: 'recruiter-workspace',
    path: '/recruiter',
    icon: Icons.groups_outlined,
    label: (l10n) => l10n.recruiterWorkspaceTitle,
    isAvailableFor: (account, dashboards) =>
        dashboards.contains(recruiterDashboardKey),
  ),
  ExploreEntry(
    id: 'marketplace',
    path: '/marketplace',
    icon: Icons.storefront_outlined,
    label: (l10n) => l10n.marketplaceTitle,
    isAvailableFor: (account, dashboards) =>
        account.hasPermission(marketplaceBrowseCapability),
  ),
  ExploreEntry(
    id: 'company-workspace',
    path: '/company',
    icon: Icons.business_center_outlined,
    label: (l10n) => l10n.companyWorkspaceTitle,
    isAvailableFor: (account, dashboards) =>
        account.hasPermission(marketplaceCompanyCapability),
  ),
  ExploreEntry(
    id: 'real-estate',
    path: '/real-estate',
    icon: Icons.apartment,
    label: (l10n) => l10n.realEstateTitle,
    isAvailableFor: (account, dashboards) => true,
  ),
  ExploreEntry(
    id: 'seller-workspace',
    path: '/seller',
    icon: Icons.real_estate_agent_outlined,
    label: (l10n) => l10n.sellerWorkspaceTitle,
    isAvailableFor: (account, dashboards) =>
        account.hasPermission(realEstateSellerCapability),
  ),
];

List<ExploreEntry> exploreFor(
  Account account,
  Set<String> dashboards, {
  List<ExploreEntry>? registry,
}) => (registry ?? exploreEntries)
    .where((entry) => entry.isAvailableFor(account, dashboards))
    .toList(growable: false);
