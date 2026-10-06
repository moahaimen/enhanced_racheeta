import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';

import 'push_source.dart';

/// The public Firebase *client* configuration (project id, app id, sender id, API key). These are
/// identifiers, not server secrets, but they are build-time inputs (`--dart-define`) rather than
/// committed values: a build without them has push disabled. No service-account or Admin
/// credential ever belongs in the app.
class FirebaseConfig {
  const FirebaseConfig({
    required this.apiKey,
    required this.appId,
    required this.messagingSenderId,
    required this.projectId,
  });

  /// Null when any value is missing.
  static FirebaseConfig? fromEnvironment() {
    const apiKey = String.fromEnvironment('FIREBASE_API_KEY');
    const appId = String.fromEnvironment('FIREBASE_APP_ID');
    const senderId = String.fromEnvironment('FIREBASE_MESSAGING_SENDER_ID');
    const projectId = String.fromEnvironment('FIREBASE_PROJECT_ID');
    if (apiKey.isEmpty ||
        appId.isEmpty ||
        senderId.isEmpty ||
        projectId.isEmpty) {
      return null;
    }
    return const FirebaseConfig(
      apiKey: apiKey,
      appId: appId,
      messagingSenderId: senderId,
      projectId: projectId,
    );
  }

  final String apiKey;
  final String appId;
  final String messagingSenderId;
  final String projectId;

  FirebaseOptions toOptions() => FirebaseOptions(
    apiKey: apiKey,
    appId: appId,
    messagingSenderId: messagingSenderId,
    projectId: projectId,
  );
}

/// Initialises Firebase from [config] and returns the real source, or the disabled one when the
/// build has no configuration or initialisation fails (push is then simply unavailable).
Future<PushSource> createPushSource(FirebaseConfig? config) async {
  if (config == null) return const DisabledPushSource();
  try {
    await Firebase.initializeApp(options: config.toOptions());
    return FirebasePushSource(FirebaseMessaging.instance);
  } on Object {
    return const DisabledPushSource();
  }
}

PushPermission _map(AuthorizationStatus status) => switch (status) {
  AuthorizationStatus.authorized ||
  AuthorizationStatus.provisional => PushPermission.granted,
  AuthorizationStatus.denied ||
  AuthorizationStatus.deniedPermanently => PushPermission.denied,
  AuthorizationStatus.notDetermined => PushPermission.notDetermined,
};

PushMessageData _data(RemoteMessage message) => PushMessageData(
  messageId: message.messageId,
  data: {for (final entry in message.data.entries) entry.key: '${entry.value}'},
);

class FirebasePushSource implements PushSource {
  FirebasePushSource(this._messaging);
  final FirebaseMessaging _messaging;

  @override
  bool get isAvailable => true;

  @override
  Future<PushPermission> permission() async =>
      _map((await _messaging.getNotificationSettings()).authorizationStatus);

  @override
  Future<PushPermission> requestPermission() async =>
      _map((await _messaging.requestPermission()).authorizationStatus);

  @override
  Future<String?> token() => _messaging.getToken();

  @override
  Stream<String> get tokenRefreshes => _messaging.onTokenRefresh;

  @override
  Stream<PushMessageData> get foregroundMessages =>
      FirebaseMessaging.onMessage.map(_data);

  @override
  Stream<PushMessageData> get openedMessages =>
      FirebaseMessaging.onMessageOpenedApp.map(_data);

  @override
  Future<PushMessageData?> initialMessage() async {
    final message = await _messaging.getInitialMessage();
    return message == null ? null : _data(message);
  }
}
