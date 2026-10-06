import 'package:flutter/foundation.dart';

/// What the OS says about showing notifications to this app.
enum PushPermission { granted, denied, notDetermined }

/// A push the app received or was opened by: only the opaque `data` map the backend sends
/// (`type`, `notification_id`, `event_type`, `conversation_id`) and Firebase's message id. The
/// notification text is never read or logged.
@immutable
class PushMessageData {
  const PushMessageData({required this.data, this.messageId});
  final Map<String, String> data;
  final String? messageId;
}

/// The Firebase Messaging surface the app needs, behind an interface so token/lifecycle/routing
/// logic is tested without Firebase.
abstract class PushSource {
  /// False when Firebase is not configured in this build (nothing below is then ever called).
  bool get isAvailable;

  Future<PushPermission> permission();

  /// Shows the OS prompt (Android 13+); returns the resulting state.
  Future<PushPermission> requestPermission();

  /// This installation's FCM token, or null when none can be issued.
  Future<String?> token();

  /// Emits when FCM rotates the token.
  Stream<String> get tokenRefreshes;

  /// A push that arrived while the app was in the foreground.
  Stream<PushMessageData> get foregroundMessages;

  /// A notification tapped while the app was in the background.
  Stream<PushMessageData> get openedMessages;

  /// The notification that launched the app from the terminated state (once).
  Future<PushMessageData?> initialMessage();
}

/// The default: no Firebase configuration, so no push. The app is fully usable; persistent
/// notifications and chat come from the backend.
class DisabledPushSource implements PushSource {
  const DisabledPushSource();

  @override
  bool get isAvailable => false;

  @override
  Future<PushPermission> permission() async => PushPermission.denied;

  @override
  Future<PushPermission> requestPermission() async => PushPermission.denied;

  @override
  Future<String?> token() async => null;

  @override
  Stream<String> get tokenRefreshes => const Stream<String>.empty();

  @override
  Stream<PushMessageData> get foregroundMessages =>
      const Stream<PushMessageData>.empty();

  @override
  Stream<PushMessageData> get openedMessages =>
      const Stream<PushMessageData>.empty();

  @override
  Future<PushMessageData?> initialMessage() async => null;
}
