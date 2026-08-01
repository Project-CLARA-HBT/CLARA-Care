plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.theclaracare.app"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "com.theclaracare.app"
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    val releaseStoreFile = providers.gradleProperty("CLARA_RELEASE_STORE_FILE").orNull
    val releaseStorePassword = providers.gradleProperty("CLARA_RELEASE_STORE_PASSWORD").orNull
    val releaseKeyAlias = providers.gradleProperty("CLARA_RELEASE_KEY_ALIAS").orNull
    val releaseKeyPassword = providers.gradleProperty("CLARA_RELEASE_KEY_PASSWORD").orNull
    val releaseSigningReady = listOf(
        releaseStoreFile,
        releaseStorePassword,
        releaseKeyAlias,
        releaseKeyPassword,
    ).all { !it.isNullOrBlank() }

    if (releaseSigningReady) {
        signingConfigs.create("release") {
            storeFile = file(requireNotNull(releaseStoreFile))
            storePassword = requireNotNull(releaseStorePassword)
            keyAlias = requireNotNull(releaseKeyAlias)
            keyPassword = requireNotNull(releaseKeyPassword)
        }
    }

    buildTypes {
        release {
            // Never fall back to the debug keystore. CI verifies signing inputs
            // before build; a local release without them is deliberately
            // unsigned and cannot be mistaken for a distributable artifact.
            if (releaseSigningReady) {
                signingConfig = signingConfigs.getByName("release")
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
