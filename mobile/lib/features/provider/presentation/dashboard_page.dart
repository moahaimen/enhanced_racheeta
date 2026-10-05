import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/time/time_providers.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/format/formatters.dart';
import '../../../shared/format/labels.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/states.dart';
import '../../auth/application/account_scope.dart';
import '../../reservations/presentation/reservations_page.dart';
import '../application/provider_providers.dart';
import '../data/provider_models.dart';
import 'provider_errors.dart';
import 'provider_gate.dart';

/// The provider/facility home: exactly the figures `GET /dashboards/doctor|facility` returns. The
/// server decides which dashboard applies (`GET /dashboards/`).
class WorkspacePage extends ConsumerWidget {
  const WorkspacePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    return ProviderGate(title: l10n.dashboardTitle, child: const _Dashboard());
  }
}

class _Dashboard extends ConsumerWidget {
  const _Dashboard();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final accountId = ref.watch(accountIdProvider);
    final provider = providerDashboardProvider(accountId);
    final dashboard = ref.watch(provider);

    Future<void> refresh() async {
      ref.invalidate(provider);
      try {
        await ref.read(provider.future);
      } on Object {
        // the error view below reports it
      }
    }

    // Keyed by account, so a value here always belongs to the signed-in account.
    if (dashboard.isLoading && !dashboard.hasValue) {
      return AppScaffold(title: l10n.dashboardTitle, body: const LoadingView());
    }
    if (dashboard.hasError && !dashboard.hasValue) {
      final error = dashboard.error;
      return AppScaffold(
        title: l10n.dashboardTitle,
        scrollable: false,
        body: ErrorView(
          message: error is ApiException
              ? providerErrorMessage(l10n, error, ProviderAction.load)
              : l10n.errorUnknown,
          onRetry: () async => ref.invalidate(provider),
        ),
      );
    }
    final data = dashboard.value;
    if (data == null) {
      return AppScaffold(
        title: l10n.dashboardTitle,
        scrollable: false,
        body: EmptyView(
          icon: Icons.assignment_ind_outlined,
          title: l10n.providerProfileMissing,
        ),
      );
    }
    return AppScaffold(
      title: l10n.dashboardTitle,
      scrollable: false,
      body: RefreshIndicator(
        onRefresh: refresh,
        child: ListView(
          children: [
            _ProfileCard(data: data),
            const SizedBox(height: RacheetaSpacing.lg),
            _ReservationsCard(data: data),
            const SizedBox(height: RacheetaSpacing.lg),
            _UpcomingCard(data: data),
            const SizedBox(height: RacheetaSpacing.lg),
            _ReviewsCard(summary: data.reviews),
            const SizedBox(height: RacheetaSpacing.lg),
            _OffersCard(summary: data.offers),
            const SizedBox(height: RacheetaSpacing.lg),
            _UnreadCard(summary: data.unread),
            if (data.memberships != null) ...[
              const SizedBox(height: RacheetaSpacing.lg),
              _MembershipsCard(summary: data.memberships!),
            ],
          ],
        ),
      ),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({required this.title, required this.children, super.key});
  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(RacheetaSpacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Semantics(
            header: true,
            child: Text(title, style: Theme.of(context).textTheme.titleMedium),
          ),
          const SizedBox(height: RacheetaSpacing.sm),
          ...children,
        ],
      ),
    ),
  );
}

class _Stat extends StatelessWidget {
  const _Stat(this.label, this.value);
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: RacheetaSpacing.xs),
    child: Row(
      children: [
        Expanded(child: Text(label)),
        Text(value, style: Theme.of(context).textTheme.titleSmall),
      ],
    ),
  );
}

class _ProfileCard extends StatelessWidget {
  const _ProfileCard({required this.data});
  final ProviderDashboard data;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final profile = data.profile;
    return _Section(
      key: const Key('dashboard-profile'),
      title: profile.displayName,
      children: [
        Text(providerTypeLabel(l10n, profile.providerType)),
        _Stat(
          l10n.dashboardVerification,
          verificationLabel(l10n, profile.verificationStatus),
        ),
        Text(
          profile.isVisible ? l10n.dashboardVisible : l10n.dashboardHidden,
          style: TextStyle(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
      ],
    );
  }
}

class _ReservationsCard extends StatelessWidget {
  const _ReservationsCard({required this.data});
  final ProviderDashboard data;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return _Section(
      key: const Key('dashboard-reservations'),
      title: l10n.dashboardReservations,
      children: [
        _Stat(l10n.dashboardTotal, '${data.total}'),
        _Stat(l10n.dashboardUpcoming, '${data.upcomingCount}'),
        const Divider(),
        for (final entry in data.byStatus.entries)
          _Stat(reservationStatusLabel(l10n, entry.key), '${entry.value}'),
      ],
    );
  }
}

class _UpcomingCard extends ConsumerWidget {
  const _UpcomingCard({required this.data});
  final ProviderDashboard data;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final wallClock = ref.watch(wallClockProvider);
    return _Section(
      key: const Key('dashboard-upcoming'),
      title: l10n.dashboardUpcomingList,
      children: [
        if (data.upcoming.isEmpty)
          Text(l10n.dashboardNoUpcoming)
        else
          for (final item in data.upcoming)
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(item.patientName),
              subtitle: Text(
                '${item.serviceTitle}\n${formatDateTime(item.startsAt, wallClock, locale)}',
              ),
              isThreeLine: true,
              trailing: StatusChip(status: item.status, l10n: l10n),
              onTap: () => context.push('/workspace/reservations/${item.id}'),
            ),
        const SizedBox(height: RacheetaSpacing.xs),
        Text(
          l10n.bookingTimezoneNote,
          style: Theme.of(context).textTheme.bodySmall,
        ),
      ],
    );
  }
}

class _ReviewsCard extends StatelessWidget {
  const _ReviewsCard({required this.summary});
  final ReviewSummary summary;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final average = summary.average;
    return _Section(
      key: const Key('dashboard-reviews'),
      title: l10n.dashboardReviews,
      children: [
        if (average == null || summary.count == 0)
          Text(l10n.noReviews)
        else
          Text(
            l10n.ratingSummary(formatRating(average, locale), summary.count),
          ),
        if (summary.count > 0)
          for (var stars = 5; stars >= 1; stars--)
            _Stat('$stars ★', '${summary.distribution[stars] ?? 0}'),
      ],
    );
  }
}

class _OffersCard extends StatelessWidget {
  const _OffersCard({required this.summary});
  final OfferSummary summary;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return _Section(
      key: const Key('dashboard-offers'),
      title: l10n.dashboardOffers,
      children: [
        _Stat(l10n.offersTotal, '${summary.total}'),
        _Stat(l10n.offersRunning, '${summary.runningNow}'),
        _Stat(l10n.offersScheduled, '${summary.scheduled}'),
      ],
    );
  }
}

class _UnreadCard extends StatelessWidget {
  const _UnreadCard({required this.summary});
  final UnreadSummary summary;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return _Section(
      key: const Key('dashboard-unread'),
      title: l10n.dashboardUnread,
      children: [
        _Stat(l10n.unreadNotifications, '${summary.notifications}'),
        _Stat(l10n.unreadMessages, '${summary.messages}'),
      ],
    );
  }
}

class _MembershipsCard extends StatelessWidget {
  const _MembershipsCard({required this.summary});
  final MembershipSummary summary;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return _Section(
      key: const Key('dashboard-practitioners'),
      title: l10n.dashboardPractitioners,
      children: [
        _Stat(l10n.practitionersActive, '${summary.active}'),
        _Stat(l10n.practitionersIncoming, '${summary.incomingRequests}'),
        _Stat(l10n.practitionersOutgoing, '${summary.outgoingInvitations}'),
      ],
    );
  }
}
