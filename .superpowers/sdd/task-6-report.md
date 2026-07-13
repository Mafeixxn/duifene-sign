# Task 6 Report: Final Android Packaging

## Status

The final debug APK was rebuilt cleanly with NDK 28c on
`codex/rebuild-android-app`. `buildozer android debug` completed successfully;
the complete successful transcript is retained at
[`.superpowers/sdd/task-6-build.log`](task-6-build.log). ANSI terminal control
sequences were removed from that retained transcript without removing its build
content. A scan for common credential forms found no passwords, tokens, API
keys, authorization values, or session values.

`android/duifene_sign.apk` is the final NDK 28c APK. There is no connected ADB
target, so physical-device background and lock-screen behavior remains
outstanding.

## Final Artifact

| Item | Result |
| --- | --- |
| Build command | `buildozer android debug` |
| Build result | PASS: `BUILD SUCCESSFUL`, `Android packaging done`, and APK availability recorded in the build log |
| NDK | Clean NDK `28c` build |
| APK | `android/duifene_sign.apk` |
| Size | `21,435,435` bytes |
| Windows SHA256 | `A9A9D67CB70EA13F5370020F780A09F773D0EBCA98099C9926C73E4894075706` |
| Java/Gradle | Generated `ServiceMonitor.java` includes UUID-token `onTimeout(int startId, int fgsType)`; Javac and Gradle completed successfully |

## APK Verification

- `aapt` confirms package `org.example.duifene_sign`, versionCode `1029101`,
  versionName `1.1`, minSdk `29`, targetSdk `35`, and ABI `arm64-v8a`.
- The manifest has the five required permissions: `INTERNET`,
  `ACCESS_NETWORK_STATE`, `FOREGROUND_SERVICE`,
  `FOREGROUND_SERVICE_DATA_SYNC`, and `POST_NOTIFICATIONS`.
- `aapt` confirms `allowBackup=false` and the `ServiceMonitor` `dataSync`
  foreground-service declaration.
- `apksigner verify` confirms the v2 signature.
- `zipalign -c -P 16 -v 4` succeeds.
- Every genuine ELF inspected individually with `llvm-readelf` has LOAD
  alignment `0x4000`. `libpybundle.so` is gzip data, not an ELF file.
- `private.tar` contains only required runtime material such as `.pyc`; it
  excludes cookie, monitor, event, crash, test, build, and `p4a_hook` files.

## Timeout Hook Verification

The generated `ServiceMonitor.java` hook implements
`onTimeout(int startId, int fgsType)` with one stable UUID token per service
lifetime. It atomically writes the token-bearing `monitor.timeout`, fsyncs the
temporary file and parent directory, and calls `stopSelf(startId)` in `finally`.
Javac and Gradle success during the clean build verify the generated Java
compiles and packages. The fail-open fault-injection window was fixed by
retaining timeout evidence until the terminal event has been durably recorded
and acknowledged.

## Regression Verification

The final regression suite ran `63` tests: `62` passed and `1` Kivy smoke test
was skipped because Kivy is not installed on this host. The UUID fail-closed
fault-injection cases cover failed event append, acknowledgement retry,
marker replacement during acknowledgement, and stable token generation.

## Remaining Device Risk

No connected ADB target is available. Installation, notification-permission
grant, and real-device foreground behavior while backgrounded or locked remain
to be verified. Android's approximately six-hour `dataSync` timeout is
system-managed and also requires an API 35 device/system test for full runtime
coverage.
