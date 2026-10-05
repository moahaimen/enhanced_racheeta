import 'package:flutter/material.dart';

import '../../l10n/generated/app_localizations.dart';
import '../auth/data/auth_models.dart';
import '../provider/provider_capability.dart';

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

final ShellDestination _home = ShellDestination(
  id: 'home',
  path: '/',
  icon: Icons.home_outlined,
  selectedIcon: Icons.home,
  label: (l10n) => l10n.navHome,
);

final ShellDestination _account = ShellDestination(
  id: 'account',
  path: '/account',
  icon: Icons.person_outline,
  selectedIcon: Icons.person,
  label: (l10n) => l10n.navAccount,
);

/// Destinations every signed-in account has (11A).
final List<ShellDestination> coreDestinations = <ShellDestination>[
  _home,
  _account,
];

/// 11B patient destinations, shown only to accounts whose `/me` lists the capability.
final ShellDestination discoverDestination = ShellDestination(
  id: 'discover',
  path: '/providers',
  icon: Icons.search,
  selectedIcon: Icons.manage_search,
  label: (l10n) => l10n.navDiscover,
  isAvailableFor: (account) =>
      account.hasPermission('providers.search') &&
      account.role == AccountRole.patient,
);

final ShellDestination reservationsDestination = ShellDestination(
  id: 'reservations',
  path: '/reservations',
  icon: Icons.event_note_outlined,
  selectedIcon: Icons.event_note,
  label: (l10n) => l10n.navReservations,
  isAvailableFor: (account) => account.hasPermission('reservations.create_own'),
);

/// 11C provider / facility destinations, shown only to accounts whose `/me` lists the provider
/// capability (the backend still requires a provider profile on every call).
final ShellDestination workspaceDestination = ShellDestination(
  id: 'workspace',
  path: '/workspace',
  icon: Icons.dashboard_outlined,
  selectedIcon: Icons.dashboard,
  label: (l10n) => l10n.navWorkspace,
  isAvailableFor: (account) => account.hasPermission(providerCapability),
);

final ShellDestination scheduleDestination = ShellDestination(
  id: 'schedule',
  path: '/workspace/availability',
  icon: Icons.edit_calendar_outlined,
  selectedIcon: Icons.edit_calendar,
  label: (l10n) => l10n.navSchedule,
  isAvailableFor: (account) => account.hasPermission(providerCapability),
);

final ShellDestination providerBookingsDestination = ShellDestination(
  id: 'provider-bookings',
  path: '/workspace/reservations',
  icon: Icons.assignment_outlined,
  selectedIcon: Icons.assignment,
  label: (l10n) => l10n.navBookings,
  isAvailableFor: (account) => account.hasPermission(providerCapability),
);

/// Everything the shell can show, in display order. Later subphases append here.
final List<ShellDestination> appDestinations = <ShellDestination>[
  _home,
  discoverDestination,
  reservationsDestination,
  workspaceDestination,
  scheduleDestination,
  providerBookingsDestination,
  _account,
];

List<ShellDestination> destinationsFor(
  Account account, {
  List<ShellDestination>? registry,
}) => (registry ?? appDestinations)
    .where((destination) => destination.isAvailableFor(account))
    .toList(growable: false);
