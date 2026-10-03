import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../l10n/generated/app_localizations.dart';
import '../auth/application/providers.dart';
import '../auth/application/session_state.dart';
import 'destinations.dart';

/// Authenticated frame: bottom navigation on phones, a rail on wide screens. The destination list
/// comes from the signed-in account (`destinationsFor`), so role-specific screens added in later
/// subphases appear only for the accounts the backend says may use them.
class AppShell extends ConsumerWidget {
  const AppShell({required this.location, required this.child, super.key});

  final String location;
  final Widget child;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionControllerProvider);
    final l10n = AppLocalizations.of(context);
    if (session is! SessionAuthenticated) {
      return child; // router redirects away momentarily
    }

    final destinations = destinationsFor(session.account);
    final selected = _selectedIndex(destinations, location);
    void go(int index) => context.go(destinations[index].path);

    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 720;
        if (wide) {
          return Scaffold(
            body: SafeArea(
              child: Row(
                children: [
                  NavigationRail(
                    selectedIndex: selected,
                    onDestinationSelected: go,
                    labelType: NavigationRailLabelType.all,
                    destinations: [
                      for (final d in destinations)
                        NavigationRailDestination(
                          icon: Icon(d.icon),
                          selectedIcon: Icon(d.selectedIcon),
                          label: Text(d.label(l10n)),
                        ),
                    ],
                  ),
                  const VerticalDivider(width: 1),
                  Expanded(child: child),
                ],
              ),
            ),
          );
        }
        return Scaffold(
          body: child,
          bottomNavigationBar: Semantics(
            label: l10n.navigationLabel,
            container: true,
            child: NavigationBar(
              selectedIndex: selected,
              onDestinationSelected: go,
              destinations: [
                for (final d in destinations)
                  NavigationDestination(
                    icon: Icon(d.icon),
                    selectedIcon: Icon(d.selectedIcon),
                    label: d.label(l10n),
                  ),
              ],
            ),
          ),
        );
      },
    );
  }

  int _selectedIndex(List<ShellDestination> destinations, String location) {
    var best = 0;
    var bestLength = -1;
    for (var i = 0; i < destinations.length; i++) {
      final path = destinations[i].path;
      final matches = path == '/' ? location == '/' : location.startsWith(path);
      if (matches && path.length > bestLength) {
        best = i;
        bestLength = path.length;
      }
    }
    return best;
  }
}
