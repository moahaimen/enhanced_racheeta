import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// ---------------------------------------------------------------------------------------------
// Release signing (docs/MOBILE_RELEASE.md). NO key material and NO password is in the repository.
//
// Credentials come from `android/key.properties` (git-ignored; template: key.properties.example)
// or from the environment (CI secrets): RACHEETA_KEYSTORE_PATH, RACHEETA_KEYSTORE_PASSWORD,
// RACHEETA_KEY_ALIAS, RACHEETA_KEY_PASSWORD.
//
// A release build WITHOUT credentials FAILS (never silently debug-signed). The only escape hatch is
// the explicit smoke switch `-PracheetaAllowDebugSignedRelease=true` (or the environment variable
// ORG_GRADLE_PROJECT_racheetaAllowDebugSignedRelease=true), which signs with the debug key so CI can
// verify that the release configuration compiles. Such an artifact is NOT a production build.
// ---------------------------------------------------------------------------------------------
val keyProperties = Properties().apply {
    val file = rootProject.file("key.properties")
    if (file.exists()) file.inputStream().use { load(it) }
}

fun signingValue(propertyName: String, envName: String): String? =
    (keyProperties.getProperty(propertyName) ?: System.getenv(envName))?.takeIf { it.isNotBlank() }

val releaseStoreFile = signingValue("storeFile", "RACHEETA_KEYSTORE_PATH")
val releaseStorePassword = signingValue("storePassword", "RACHEETA_KEYSTORE_PASSWORD")
val releaseKeyAlias = signingValue("keyAlias", "RACHEETA_KEY_ALIAS")
val releaseKeyPassword = signingValue("keyPassword", "RACHEETA_KEY_PASSWORD")
val hasReleaseSigning =
    releaseStoreFile != null &&
        releaseStorePassword != null &&
        releaseKeyAlias != null &&
        releaseKeyPassword != null
val allowDebugSignedRelease =
    (project.findProperty("racheetaAllowDebugSignedRelease") as String?) == "true"

android {
    namespace = "app.racheeta.racheeta_mobile"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // The application id is permanent once published on Google Play: it is an owner decision
        // recorded in docs/MOBILE_RELEASE.md (release blocker until confirmed).
        applicationId = "app.racheeta.racheeta_mobile"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        if (hasReleaseSigning) {
            create("release") {
                storeFile = rootProject.file(releaseStoreFile!!)
                storePassword = releaseStorePassword
                keyAlias = releaseKeyAlias
                keyPassword = releaseKeyPassword
            }
        }
    }

    buildTypes {
        release {
            signingConfig =
                when {
                    hasReleaseSigning -> signingConfigs.getByName("release")
                    allowDebugSignedRelease -> signingConfigs.getByName("debug")
                    else -> null
                }
            // R8: shrink code and resources. Flutter and the plugins ship their own consumer rules;
            // app-specific rules (none needed today) belong in proguard-rules.pro.
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }
}

// Fail closed: building a release artifact without production signing credentials is an error,
// unless the explicit smoke switch above is set.
gradle.taskGraph.whenReady {
    val buildsRelease =
        allTasks.any { task ->
            task.project == project &&
                (task.name.startsWith("assembleRelease") ||
                    task.name.startsWith("bundleRelease") ||
                    task.name.startsWith("packageRelease"))
        }
    if (buildsRelease && !hasReleaseSigning && !allowDebugSignedRelease) {
        throw GradleException(
            "Release signing is not configured. Provide android/key.properties (see " +
                "android/key.properties.example) or the RACHEETA_KEYSTORE_PATH / " +
                "RACHEETA_KEYSTORE_PASSWORD / RACHEETA_KEY_ALIAS / RACHEETA_KEY_PASSWORD " +
                "environment variables. For a NON-production compile check only, set " +
                "-PracheetaAllowDebugSignedRelease=true. See docs/MOBILE_RELEASE.md.",
        )
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
