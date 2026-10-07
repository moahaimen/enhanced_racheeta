import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/api/page.dart';
import '../../../core/paging/paged_notifier.dart';
import '../../auth/application/account_scope.dart';
import '../../auth/application/providers.dart';
import '../data/chat_api.dart';
import '../data/chat_models.dart';

final Provider<ChatApi> chatApiProvider = Provider<ChatApi>(
  (ref) => ChatApi(ref.watch(apiClientProvider)),
);

/// The signed-in account's conversations (backend-scoped, latest activity first). Rebuilt on an
/// account change, so another account's list is never shown.
class ConversationsController extends PagedNotifier<Conversation> {
  @override
  PagedState<Conversation> build() {
    ref.watch(accountIdProvider);
    return start();
  }

  @override
  Future<Page<Conversation>> fetchPage(int page, CancelToken token) => ref
      .read(chatApiProvider)
      .conversations(
        page: page,
        pageSize: PagedNotifier.pageSize,
        cancelToken: token,
      );
}

final conversationsProvider =
    NotifierProvider<ConversationsController, PagedState<Conversation>>(
      ConversationsController.new,
      retry: noRetry,
    );

/// The authoritative unread chat count, keyed by the account.
final chatUnreadProvider = FutureProvider.autoDispose.family<int, String?>((
  ref,
  accountId,
) {
  if (accountId == null) return 0;
  final token = CancelToken();
  ref.onDispose(() => token.cancel('disposed'));
  return ref.watch(chatApiProvider).unreadCount(cancelToken: token);
}, retry: noRetry);

/// The messages of one conversation, oldest first. Page 1 is the latest page; older pages are
/// prepended (never reordered on the device: `sequence` decides and duplicates are dropped by id).
@immutable
class ChatMessagesState {
  const ChatMessagesState({
    this.phase = PagedPhase.loading,
    this.messages = const [],
    this.nextOlderPage,
    this.loadingOlder = false,
    this.error,
    this.loadOlderError,
  });

  final PagedPhase phase;
  final List<ChatMessage> messages;

  /// The page number holding the next-older messages; null when the oldest page was loaded.
  final int? nextOlderPage;
  final bool loadingOlder;
  final ApiException? error;
  final ApiException? loadOlderError;

  bool get hasOlder => nextOlderPage != null;
}

List<ChatMessage> _merge(List<ChatMessage> a, List<ChatMessage> b) {
  final byId = <String, ChatMessage>{
    for (final message in a) message.id: message,
    for (final message in b) message.id: message,
  };
  return byId.values.toList()..sort((x, y) => x.sequence.compareTo(y.sequence));
}

/// Keyed by `(account, conversationId)`: another account's thread is never handed to this one
/// (a new key starts from loading), and the controller rebuilds — cancelling requests and
/// dropping late answers — whenever the signed-in account changes.
class ChatMessagesController extends Notifier<ChatMessagesState> {
  ChatMessagesController(this.key);
  final AccountScoped<String> key;

  int _epoch = 0;
  CancelToken? _token;
  int _markedThrough = 0;

  @override
  ChatMessagesState build() {
    ref.watch(accountIdProvider);
    _epoch++;
    _markedThrough = 0;
    _token?.cancel('superseded');
    final token = _token = CancelToken();
    ref.onDispose(() => token.cancel('disposed'));
    final epoch = _epoch;
    unawaited(Future<void>.microtask(() => _loadLatest(epoch, token)));
    return const ChatMessagesState();
  }

  bool _current(int epoch) =>
      ref.mounted &&
      epoch == _epoch &&
      ref.read(accountIdProvider) == key.account;

  Future<void> _loadLatest(int epoch, CancelToken token) async {
    try {
      final page = await ref
          .read(chatApiProvider)
          .messages(
            key.value,
            pageSize: PagedNotifier.pageSize,
            cancelToken: token,
          );
      if (!_current(epoch)) return;
      state = ChatMessagesState(
        phase: PagedPhase.ready,
        messages: _merge(state.messages, page.results),
        nextOlderPage: state.messages.isEmpty
            ? (page.hasNext ? 2 : null)
            : state.nextOlderPage,
      );
      _markReadIfNeeded(epoch);
    } on StaleSessionException {
      // The session ended; the account change rebuilds this controller.
    } on ApiException catch (error) {
      if (!_current(epoch) || error.kind == ApiErrorKind.cancelled) return;
      if (state.messages.isEmpty) {
        state = ChatMessagesState(phase: PagedPhase.error, error: error);
      }
    }
  }

  /// Re-reads the latest page and merges it (a push said something arrived, or pull-to-refresh).
  Future<void> refresh() async {
    final token = _token;
    if (token == null || token.isCancelled) return;
    await _loadLatest(_epoch, token);
  }

  /// Retries after a first-page failure.
  void reload() => ref.invalidateSelf();

  /// Loads the next-older page and prepends it; a failure keeps what is shown.
  Future<void> loadOlder() async {
    final page = state.nextOlderPage;
    final token = _token;
    if (page == null ||
        state.loadingOlder ||
        state.phase != PagedPhase.ready ||
        token == null) {
      return;
    }
    final epoch = _epoch;
    state = ChatMessagesState(
      phase: PagedPhase.ready,
      messages: state.messages,
      nextOlderPage: page,
      loadingOlder: true,
    );
    try {
      final result = await ref
          .read(chatApiProvider)
          .messages(
            key.value,
            page: page,
            pageSize: PagedNotifier.pageSize,
            cancelToken: token,
          );
      if (!_current(epoch)) return;
      state = ChatMessagesState(
        phase: PagedPhase.ready,
        messages: _merge(result.results, state.messages),
        nextOlderPage: result.hasNext ? page + 1 : null,
      );
    } on StaleSessionException {
      // see above
    } on ApiException catch (error) {
      if (!_current(epoch) || error.kind == ApiErrorKind.cancelled) return;
      state = ChatMessagesState(
        phase: PagedPhase.ready,
        messages: state.messages,
        nextOlderPage: page,
        loadOlderError: error,
      );
    }
  }

  /// Adds a message the backend just confirmed (our own send), keeping `sequence` order.
  void add(ChatMessage message) {
    if (state.phase != PagedPhase.ready) return;
    state = ChatMessagesState(
      phase: PagedPhase.ready,
      messages: _merge(state.messages, [message]),
      nextOlderPage: state.nextOlderPage,
    );
  }

  /// The server's read semantics: reading is a separate `POST .../read/` carrying the highest
  /// sequence this screen actually loaded (opening or fetching a conversation does not mark it).
  /// One attempt per newly observed sequence, never retried in a loop; a failure leaves the
  /// messages unread on the server and the next refresh may try again.
  void _markReadIfNeeded(int epoch) {
    final messages = state.messages;
    if (messages.isEmpty) return;
    final newest = messages.last.sequence;
    final unreadFromOthers = messages.any(
      (m) => !m.isMine && m.sequence > _markedThrough,
    );
    if (!unreadFromOthers || newest <= _markedThrough) return;
    final previous = _markedThrough;
    _markedThrough = newest;
    unawaited(_markRead(epoch, newest, previous));
  }

  Future<void> _markRead(int epoch, int through, int previous) async {
    try {
      await ref.read(chatApiProvider).markRead(key.value, through);
      if (!_current(epoch)) return;
      ref
        ..invalidate(conversationsProvider)
        ..invalidate(chatUnreadProvider);
    } on Object {
      if (_current(epoch)) _markedThrough = previous;
    }
  }
}

final chatMessagesProvider = NotifierProvider.autoDispose
    .family<ChatMessagesController, ChatMessagesState, AccountScoped<String>>(
      ChatMessagesController.new,
      retry: noRetry,
    );
