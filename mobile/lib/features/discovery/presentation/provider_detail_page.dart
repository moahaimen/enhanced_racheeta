import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/error_messages.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/time/time_providers.dart';
import '../../../l10n/generated/app_localizations.dart';
import '../../../shared/format/formatters.dart';
import '../../../shared/format/labels.dart';
import '../../../shared/theme/app_theme.dart';
import '../../../shared/widgets/app_scaffold.dart';
import '../../../shared/widgets/states.dart';
import '../../auth/application/providers.dart';
import '../../auth/application/session_state.dart';
import '../application/discovery_providers.dart';
import '../data/discovery_models.dart';
import 'provider_card_tile.dart';

/// Capability code that enables the booking entry point (shown only when `/me` lists it; the
/// backend still enforces PATIENT on every reservation endpoint).
const bookingCapability = 'reservations.create_own';

class ProviderDetailPage extends ConsumerWidget {
  const ProviderDetailPage({required this.providerId, super.key});
  final String providerId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final detail = ref.watch(providerDetailProvider(providerId));
    return detail.when(
      loading: () =>
          AppScaffold(title: l10n.providerTitle, body: const LoadingView()),
      error: (error, _) => AppScaffold(
        title: l10n.providerTitle,
        scrollable: false,
        body: ErrorView(
          message: error is ApiException
              ? apiErrorMessage(l10n, error)
              : l10n.errorUnknown,
          onRetry: () async =>
              ref.invalidate(providerDetailProvider(providerId)),
        ),
      ),
      data: (provider) => _Detail(provider: provider),
    );
  }
}

class _Detail extends ConsumerWidget {
  const _Detail({required this.provider});
  final ProviderPublic provider;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final language = Localizations.localeOf(context).languageCode;
    final wallClock = ref.watch(wallClockProvider);
    final session = ref.watch(sessionControllerProvider);
    final canBook =
        session is SessionAuthenticated &&
        session.account.hasPermission(bookingCapability);
    final card = provider.card;
    final place = placeSummary(card, language);
    final specialties = card.specialties
        .map((s) => s.name(language))
        .where((name) => name.isNotEmpty)
        .join('، ');

    return AppScaffold(
      title: card.displayName,
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(RacheetaSpacing.lg),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Semantics(
                    header: true,
                    child: Text(
                      card.displayName,
                      style: theme.textTheme.headlineSmall,
                    ),
                  ),
                  Text(
                    [
                      providerTypeLabel(l10n, card.providerType),
                      providerKindLabel(l10n, card.kind),
                    ].where((t) => t.isNotEmpty).join(' · '),
                    style: TextStyle(color: theme.colorScheme.primary),
                  ),
                  if (provider.verifiedAt != null)
                    Padding(
                      padding: const EdgeInsets.only(top: RacheetaSpacing.xs),
                      child: Row(
                        children: [
                          const Icon(Icons.verified_outlined, size: 18),
                          const SizedBox(width: RacheetaSpacing.xs),
                          Text(
                            l10n.verifiedSince(
                              formatDate(
                                provider.verifiedAt!,
                                wallClock,
                                language,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  const SizedBox(height: RacheetaSpacing.sm),
                  Text(ratingText(l10n, card, language)),
                ],
              ),
            ),
          ),
          if (provider.about.isNotEmpty)
            _Section(title: l10n.detailAbout, child: Text(provider.about)),
          if (specialties.isNotEmpty)
            _Section(title: l10n.detailSpecialties, child: Text(specialties)),
          if (place.isNotEmpty || provider.address.isNotEmpty)
            _Section(
              title: l10n.detailLocation,
              child: Text(
                [place, provider.address].where((t) => t.isNotEmpty).join('\n'),
              ),
            ),
          if (provider.phone.isNotEmpty ||
              provider.publicEmail.isNotEmpty ||
              provider.website.isNotEmpty)
            _Section(
              title: l10n.detailContact,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (provider.phone.isNotEmpty)
                    _Line(l10n.detailPhone, provider.phone),
                  if (provider.publicEmail.isNotEmpty)
                    _Line(l10n.detailEmail, provider.publicEmail),
                  if (provider.website.isNotEmpty)
                    _Line(l10n.detailWebsite, provider.website),
                ],
              ),
            ),
          _Section(
            title: l10n.detailServices,
            child: provider.services.isEmpty
                ? Text(l10n.noServices)
                : Column(
                    children: [
                      for (final service in provider.services)
                        _ServiceTile(
                          service: service,
                          canBook: canBook,
                          onBook: () => context.push(
                            '/providers/${card.id}/book/${service.id}',
                          ),
                        ),
                    ],
                  ),
          ),
          if (provider.relatedProviders.isNotEmpty)
            _Section(
              title: l10n.detailRelated,
              child: Column(
                children: [
                  for (final related in provider.relatedProviders)
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(related.displayName),
                      subtitle: Text(
                        providerTypeLabel(l10n, related.providerType),
                      ),
                      onTap: () => context.push('/providers/${related.id}'),
                    ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({required this.title, required this.child});
  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: RacheetaSpacing.lg),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Semantics(
          header: true,
          child: Text(title, style: Theme.of(context).textTheme.titleMedium),
        ),
        const SizedBox(height: RacheetaSpacing.sm),
        child,
      ],
    ),
  );
}

class _Line extends StatelessWidget {
  const _Line(this.label, this.value);
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: RacheetaSpacing.xs),
    child: Text.rich(
      TextSpan(
        children: [
          TextSpan(
            text: '$label: ',
            style: TextStyle(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
          TextSpan(text: value),
        ],
      ),
    ),
  );
}

class _ServiceTile extends StatelessWidget {
  const _ServiceTile({
    required this.service,
    required this.canBook,
    required this.onBook,
  });
  final PublicService service;
  final bool canBook;
  final VoidCallback onBook;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final details = [
      formatMoney(service.price, service.currency, locale),
      if (service.durationMinutes != null)
        l10n.serviceDuration(service.durationMinutes!),
    ].join(' · ');
    return Card(
      margin: const EdgeInsets.only(bottom: RacheetaSpacing.sm),
      child: Padding(
        padding: const EdgeInsets.all(RacheetaSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(service.title, style: Theme.of(context).textTheme.titleSmall),
            if (service.description.isNotEmpty) Text(service.description),
            const SizedBox(height: RacheetaSpacing.xs),
            Text(details),
            // A service without a duration cannot have appointment slots, so booking is not offered.
            if (canBook && service.durationMinutes != null) ...[
              const SizedBox(height: RacheetaSpacing.sm),
              Align(
                alignment: AlignmentDirectional.centerEnd,
                child: FilledButton(
                  onPressed: onBook,
                  child: Text(l10n.bookService),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
