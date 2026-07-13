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
| Size | `21,433,319` bytes |
| Windows SHA256 | `4E5ED6161D3CCE4474B2DA0BAE893FD4DDE9EDDC8FB8EC118080A141ABB21336` |
| Java/Gradle | Generated `ServiceMonitor.java` includes `onTimeout(int startId, int fgsType)`; Javac and Gradle completed successfully |

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
`onTimeout(int startId, int fgsType)`. It atomically writes `monitor.timeout`,
fsyncs the temporary file and parent directory, and calls `stopSelf(startId)`
in `finally`. Javac and Gradle success during the clean build verify the
generated Java compiles and packages.

## Remaining Device Risk

No connected ADB target is available. Installation, notification-permission
grant, and real-device foreground behavior while backgrounded or locked remain
to be verified. Android's approximately six-hour `dataSync` timeout is
system-managed and also requires an API 35 device/system test for full runtime
coverage.
