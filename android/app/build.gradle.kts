plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.aicompanion.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.aicompanion.app"
        minSdk = 24
        targetSdk = 34
        versionCode = 4
        versionName = "1.3"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    // WebSocket 客户端 + JSON（界面仍然用系统 WebView，不引入 UI 库）
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
}
