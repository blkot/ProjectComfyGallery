import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

val privateConnection = Properties().apply {
    val source = rootProject.file("private-connection.properties")
    if (source.exists()) source.reader(Charsets.UTF_8).use { load(it) }
}
fun javaString(value: String): String = "\"" + buildString {
    value.forEach { char ->
        when (char) {
            '\\' -> append("\\\\")
            '"' -> append("\\\"")
            '\n' -> append("\\n")
            '\r' -> append("\\r")
            '\t' -> append("\\t")
            else -> if (char.code < 32) append("\\u%04x".format(char.code)) else append(char)
        }
    }
} + "\""

android {
    namespace = "com.comfygallery.quest"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.comfygallery.quest"
        minSdk = 34
        targetSdk = 34
        versionCode = 3
        versionName = "0.3.0"
        buildConfigField("String", "GALLERY_URL", "\"\"")
        buildConfigField("String", "GALLERY_TOKEN", "\"\"")
        ndk { abiFilters += "arm64-v8a" }
    }
    buildFeatures { compose = true; buildConfig = true }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildTypes {
        debug {
            buildConfigField("String", "GALLERY_URL", javaString(privateConnection.getProperty("gallery.url", "").trim()))
            buildConfigField("String", "GALLERY_TOKEN", javaString(privateConnection.getProperty("gallery.token", "").trim()))
        }
        release { isMinifyEnabled = false }
    }
    packaging { resources.excludes += "/META-INF/{AL2.0,LGPL2.1}" }
    lint {
        // Private Horizon APK, following Meta's current Android 14 target baseline.
        disable += "ExpiredTargetSdkVersion"
    }
}

dependencies {
    implementation(libs.spatial.base)
    implementation(libs.spatial.vr)
    implementation(libs.spatial.toolkit)
    implementation(libs.spatial.compose)
    implementation(libs.spatial.isdk)
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.material3)
    implementation(libs.activity.compose)
    implementation(libs.lifecycle)
    implementation(libs.media3.exoplayer)
    implementation(libs.media3.okhttp)
    implementation(libs.coroutines)
    implementation(libs.serialization)
    implementation(libs.okhttp)
    implementation(libs.coil)
    testImplementation(libs.junit)
    testImplementation(libs.mockwebserver)
    testImplementation(libs.coroutines.test)
}
