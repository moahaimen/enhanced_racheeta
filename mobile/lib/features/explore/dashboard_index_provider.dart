import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/paging/paged_notifier.dart';
import '../provider/application/provider_providers.dart';

/// The dashboards the server says this account may open right now (`GET /dashboards/`), keyed by
/// account so one account's answer is never used for another. The Explore section uses it to decide
/// whether the account is a recruiter (membership is not a `/me` capability). A failed request
/// simply yields no extra entries: Home never shows a technical error for it.
final dashboardIndexProvider = FutureProvider.autoDispose
    .family<Set<String>, String?>((ref, accountId) async {
      if (accountId == null) return const <String>{};
      final token = CancelToken();
      ref.onDispose(() => token.cancel('disposed'));
      final index = await ref
          .watch(providerApiProvider)
          .dashboardIndex(cancelToken: token);
      return index.dashboards.toSet();
    }, retry: noRetry);
