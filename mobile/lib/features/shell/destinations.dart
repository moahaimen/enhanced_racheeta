import 'package:flutter/material.dart';

import '../../l10n/generated/app_localizations.dart';
import '../auth/data/auth_models.dart';

/// One entry of the signed-in navigation. Later subphases (11B–11E) append their destinations
/// here; each declares who may see it. Availability is derived from the account returned by
/// `/me` (role and backend capability codes), never from hardcoded assumptions about the user.
/// It only decides what is *shown*: the backend re-checks every action.
class ShellDestination {
  const ShellDestination({
    required this.id,
    required this.path,
    required this.icon,
    required this.selectedIcon,
    required this.label,
    this.isAvailableFor = _always,
  });

  final String id;
  final String path;
  final IconData icon;
  final IconData selectedIcon;
  final String Function(AppLocalizations l10n) label;
  final bool Function(Account account) isAvailableFor;

  static bool _always(Account _) => true;
}

/// Destinations that exist in 11A. No unfinished feature is listed.
final List<ShellDestination> coreDestinations = <ShellDestination>[
  ShellDestination(
    id: 'home',
    path: '/',
    icon: Icons.home_outlined,
    selectedIcon: Icons.home,
    label: (l10n) => l10n.navHome,
  ),
  ShellDestination(
    id: 'account',
    path: '/account',
    icon: Icons.person_outline,
    selectedIcon: Icons.person,
    label: (l10n) => l10n.navAccount,
  ),
];

List<ShellDestination> destinationsFor(
  Account account, {
  List<ShellDestination>? registry,
}) => (registry ?? coreDestinations)
    .where((destination) => destination.isAvailableFor(account))
    .toList(growable: false);
