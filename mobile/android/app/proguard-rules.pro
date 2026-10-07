# App-specific R8/ProGuard rules for release builds.
#
# Flutter's Gradle plugin and every Flutter plugin used here (firebase_messaging, firebase_core,
# flutter_secure_storage, shared_preferences) ship their own consumer rules, so no -keep rules are
# needed today. Add a rule here ONLY together with the failure it fixes (and note it in
# docs/MOBILE_RELEASE.md); never add a blanket -keep or -dontwarn to make a build pass.
