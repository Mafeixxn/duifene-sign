# Task 6 Report: Documentation and Packaging

## Status

Documentation, packaging-ignore work, and the Android APK build are complete on
`codex/rebuild-android-app`. The APK was built successfully with Buildozer 1.6.0
on Ubuntu 22.04; the build log contains `BUILD SUCCESSFUL` and `APK available`.
The original successful `buildozer android debug` transcript that generated the
current APK is retained at [`.superpowers/sdd/task-6-build.log`](task-6-build.log).
Device installation and background/lock-screen verification remain outstanding
because Windows PATH has no `adb` and there is no connected ADB target.

Task 6 commits: `6daf66f` (`Document Android foreground monitoring`), `527b2d5`
(`docs: localize Android usage notes heading`), `7dfe927`
(`fix(android): omit empty Gradle dependencies`), and `6b7503a`
(`build(android): record verified debug APK`) for `android/duifene_sign.apk`.

## Changed Files

- `README.md`
  - Updated the Android APK minimum version from Android 7.0+ to Android 10+
    (API 29).
  - Added Android 10+ usage notes covering OAuth-only login, the foreground
    notification, continued monitoring while backgrounded or locked,
    Android 13+ notification permission, and battery-management caveats.
  - Preserved all pre-existing README content.
- `android/.gitignore`
  - Ignores private session and service IPC files (`cookie.txt`, `monitor.json`,
    `monitor.stop`, and `monitor-events.jsonl`) plus their temporary writes.
  - Ignores local crash diagnostics and Buildozer output directories.
- `.superpowers/sdd/progress.md`
  - Recorded Task 6 documentation/desktop-verification completion and the
    remaining environment-dependent validation.

## Verification

### Android APK Build Evidence

| Item | Result |
| --- | --- |
| Build environment | Ubuntu 22.04; Buildozer 1.6.0 |
| Build command | `buildozer android debug` |
| Build log | PASS: [`.superpowers/sdd/task-6-build.log`](task-6-build.log), the original successful `buildozer android debug` transcript for the current APK; it contains `BUILD SUCCESSFUL`, `Android packaging done`, and `APK available` |
| APK | `android/duifene_sign.apk` |
| Size | 21,085,355 bytes |
| SHA256 | `AA52140FBDF29BF72BEC944603C2FD80036420F389C5A16F05D6A429E217363A` |
| Package metadata | `org.example.duifene_sign`, versionCode `1029101`, version `1.1`, minSdk `29`, targetSdk `35`, ABI `arm64-v8a` |
| Permissions and service | `INTERNET`, `ACCESS_NETWORK_STATE`, `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_DATA_SYNC`, and `POST_NOTIFICATIONS`; `ServiceMonitor` foreground service type `dataSync` |
| Signature | `apksigner` verification PASS: v2 debug signature |

The following commands were used from an Ubuntu Android SDK/build-tools
environment to review the committed APK; their output recorded the values
above:

```sh
aapt dump badging android/duifene_sign.apk
# package: name='org.example.duifene_sign' versionCode='1029101' versionName='1.1'
# sdkVersion:'29'; targetSdkVersion:'35'; native-code: 'arm64-v8a'
# uses-permission: INTERNET, ACCESS_NETWORK_STATE, FOREGROUND_SERVICE,
#   FOREGROUND_SERVICE_DATA_SYNC, POST_NOTIFICATIONS
aapt dump xmltree android/duifene_sign.apk AndroidManifest.xml
# ServiceMonitor has android:foregroundServiceType="dataSync"
apksigner verify --verbose --print-certs android/duifene_sign.apk
# Verified using v2 scheme (APK Signature Scheme v2: true)
```

Run from `F:\成品\安卓版签到`:

| Command | Result |
| --- | --- |
| `python -m unittest android.tests.test_android_regressions -v` | PASS: 45 tests ran; 44 passed and 1 expected Kivy skip because Kivy is not installed on this host. |
| `python -m compileall -q android` | Initial direct run was blocked by sandbox permission errors while writing existing repository `__pycache__` directories. Re-ran with `PYTHONPYCACHEPREFIX=$env:TEMP`; PASS with exit code 0. |
| `git -c safe.directory='F:/成品/安卓版签到' diff --check` | PASS with exit code 0. Git emitted only existing LF-to-CRLF conversion warnings for `.gitignore` and `README.md`. |
| `Get-Command adb`; `adb devices` | OUTSTANDING: Windows PATH has no `adb`, and no connected ADB target is available for device verification. |

## Blockers

- Windows PATH has no `adb`, and there is no connected ADB target. Installation,
  notification-permission grant, background/lock foreground-notification
  verification, and continued event-output verification are outstanding.
- Kivy is not installed on this host, so the Kivy-only widget construction
  smoke test is skipped; the complete desktop regression suite otherwise passes.

## Review Fix Verification

| Command | Result |
| --- | --- |
| `git diff --check -- README.md .superpowers/sdd/task-6-report.md` | PASS: exit code 0. |

## Buildozer Empty Dependency Regression Fix

Root cause: Buildozer 1.6.0 translates an empty
`android.gradle_dependencies =` declaration to the p4a argument `--depend ''`,
which causes Gradle to reject the empty module notation.

### RED

| Command | Result |
| --- | --- |
| `python -m unittest android.tests.test_android_regressions.ForegroundServiceTests.test_buildozer_omits_empty_gradle_dependencies -v` | Expected FAIL: `AssertionError: 'android.gradle_dependencies' unexpectedly found in <Section: app>`; 1 test ran, 1 failure. |

### GREEN

| Command | Result |
| --- | --- |
| `python -m unittest android.tests.test_android_regressions.ForegroundServiceTests.test_buildozer_omits_empty_gradle_dependencies -v` | PASS: 1 test ran, exit code 0. |
| `python -m unittest android.tests.test_android_regressions -v` | PASS: 45 tests ran, 44 passed and 1 expected skip because Kivy is not installed on this host; exit code 0. |

The fix removes only the empty `android.gradle_dependencies` line. The added
regression test requires the option to be absent whenever there are no Gradle
dependencies.
