import java.io.File

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// 버전 단일 소스: 00__build/src/pc/yamp/version.py (PC 와 같은 값) — rootDir(src/android) 의 상위(src) 기준
//   형식 v<type><major>.<minor>.<patch>.<build3><upgrade>  예) vr0.1.0.002, vt0.0.0.001, vr0.1.2.345+
val verPy = File(rootDir.parentFile, "pc/yamp/version.py").let { if (it.exists()) it.readText() else "" }
fun verVal(k: String): String = Regex("""(?m)^$k = "?([^"\r\n]*)"?""").find(verPy)?.groupValues?.get(1)?.trim() ?: ""
val vType = verVal("VER_TYPE").ifEmpty { "t" }
val vMajor = verVal("VER_MAJOR").toIntOrNull() ?: 0
val vMinor = verVal("VER_MINOR").toIntOrNull() ?: 0
val vPatch = verVal("VER_PATCH").toIntOrNull() ?: 0
val vBuild = verVal("VER_BUILD").toIntOrNull() ?: 0
val vUp = verVal("VER_UPGRADE")
val verName: String = "v$vType$vMajor.$vMinor.$vPatch.${"%03d".format(vBuild)}$vUp"
val verCode: Int = maxOf(1, vMajor * 10_000_000 + vMinor * 100_000 + vPatch * 1_000 + vBuild)
val appName = "yMp3Player"
// 빌드 시각: build.sh 가 YAMP_BUILD_TIME 으로 한 번 정해 exe/apk 같은 값 사용
val buildTime: String = System.getenv("YAMP_BUILD_TIME")?.takeIf { it.isNotBlank() } ?: "dev"

android {
    namespace = "com.ascen.yamp"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.ascen.yamp"
        minSdk = 26
        targetSdk = 35
        versionCode = verCode
        versionName = verName
        buildConfigField("String", "BUILD_TIME", "\"$buildTime\"")
        buildConfigField("String", "APP_NAME", "\"$appName\"")
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            // 개인 설치용: 디버그 키로 서명 (스토어 배포 시 별도 keystore 지정)
            signingConfig = signingConfigs.getByName("debug")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    // 첫 빌드 안정성: release lint 경고로 빌드가 멈추지 않게
    lint {
        checkReleaseBuilds = false
        abortOnError = false
    }
    // apk 이름: yMp3Player_<버전>.apk (build.sh apk 가 dist 로 복사)
    applicationVariants.all {
        val variant = this
        outputs.all {
            (this as com.android.build.gradle.internal.api.BaseVariantOutputImpl).outputFileName =
                "${appName}_${verName}" + (if (variant.buildType.name == "debug") "_debug" else "") + ".apk"
        }
    }
    packaging { resources.excludes += "/META-INF/{AL2.0,LGPL2.1}" }
}

dependencies {
    val media3 = "1.4.1"
    implementation(platform("androidx.compose:compose-bom:2024.10.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.media3:media3-exoplayer:$media3")
    implementation("androidx.media3:media3-session:$media3")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-guava:1.8.1")
    testImplementation("junit:junit:4.13.2")
}
