plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

val releaseStorePath = System.getenv("RACHEETA_ANDROID_KEYSTORE_PATH")
val releaseStorePassword = System.getenv("RACHEETA_ANDROID_STORE_PASSWORD")
val releaseKeyAlias = System.getenv("RACHEETA_ANDROID_KEY_ALIAS")
val releaseKeyPassword = System.getenv("RACHEETA_ANDROID_KEY_PASSWORD")
val hasReleaseSigning = listOf(
    releaseStorePath,
    releaseStorePassword,
    releaseKeyAlias,
    releaseKeyPassword,
).all { !it.isNullOrBlank() }

// Debug/profile work without production credentials. A release task fails closed instead of ever
// falling back to the debug key.
val releaseRequested = gradle.startParameter.taskNames.any {
    it.contains("release", ignoreCase = true)
}
if (releaseRequested && !hasReleaseSigning) {
    throw GradleException(
        "Android release signing is required. Set RACHEETA_ANDROID_KEYSTORE_PATH, " +
            "RACHEETA_ANDROID_STORE_PASSWORD, RACHEETA_ANDROID_KEY_ALIAS and " +
            "RACHEETA_ANDROID_KEY_PASSWORD."
    )
}

android {
    namespace = "app.racheeta.racheeta_mobile"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // Stable store identity. Changing this after publication creates a different application.
        applicationId = "app.racheeta.racheeta_mobile"
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        if (hasReleaseSigning) {
            create("release") {
                storeFile = file(releaseStorePath!!)
                storePassword = releaseStorePassword
                keyAlias = releaseKeyAlias
                keyPassword = releaseKeyPassword
            }
        }
    }

    buildTypes {
        release {
            signingConfig = if (hasReleaseSigning) {
                signingConfigs.getByName("release")
            } else {
                null
            }
        }
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
