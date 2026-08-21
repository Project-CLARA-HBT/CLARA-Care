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

    val defaultKeystore = file("clara-release.jks")
    val releaseStoreFile = providers.gradleProperty("CLARA_RELEASE_STORE_FILE").orNull
        ?: if (defaultKeystore.exists()) defaultKeystore.absolutePath else null
    val releaseStorePassword = providers.gradleProperty("CLARA_RELEASE_STORE_PASSWORD").orNull ?: "claracare2026"
    val releaseKeyAlias = providers.gradleProperty("CLARA_RELEASE_KEY_ALIAS").orNull ?: "claracare"
    val releaseKeyPassword = providers.gradleProperty("CLARA_RELEASE_KEY_PASSWORD").orNull ?: "claracare2026"

    signingConfigs {
        create("release") {
            if (releaseStoreFile != null && file(releaseStoreFile).exists()) {
                storeFile = file(releaseStoreFile)
                storePassword = releaseStorePassword
                keyAlias = releaseKeyAlias
                keyPassword = releaseKeyPassword
            } else {
                val debugConfig = getByName("debug")
                storeFile = debugConfig.storeFile
                storePassword = debugConfig.storePassword
                keyAlias = debugConfig.keyAlias
                keyPassword = debugConfig.keyPassword
            }
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("release")
            isMinifyEnabled = false
            isShrinkResources = false
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
