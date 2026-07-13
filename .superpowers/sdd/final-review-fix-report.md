# Android Final Review Fix Report

Date: 2026-07-13
Branch: `codex/rebuild-android-app`

## Final Build Resolution

The final APK was rebuilt cleanly with NDK `28c`; this is the final recorded
APK build evidence.
`buildozer android debug` succeeded, including generated Java compilation and
Gradle packaging. The final artifact is `android/duifene_sign.apk`:

| Item | Value |
| --- | --- |
| Size | `21,433,319` bytes |
| Windows SHA256 | `4E5ED6161D3CCE4474B2DA0BAE893FD4DDE9EDDC8FB8EC118080A141ABB21336` |
| Package | `org.example.duifene_sign` |
| Version | versionCode `1029101`; versionName `1.1` |
| SDK | minSdk `29`; targetSdk `35` |
| ABI | `arm64-v8a` |

## Generated Service Timeout Hook

The clean build generated `ServiceMonitor.java` with
`onTimeout(int startId, int fgsType)`. The override atomically writes
`monitor.timeout`, fsyncs the file and parent directory, and invokes
`stopSelf(startId)` in `finally`. Javac and Gradle completed successfully.

## Final APK Inspection

- `aapt` reports `allowBackup=false`, the five required permissions, and
  `ServiceMonitor` with foreground-service type `dataSync`.
- `apksigner` verifies the APK Signature Scheme v2 signature.
- `zipalign -c -P 16 -v 4` succeeds.
- Individual `llvm-readelf` checks show `0x4000` LOAD alignment for every true
  ELF. `libpybundle.so` is gzip data and is therefore not an ELF candidate.
- `private.tar` excludes cookie, monitor, event, crash, test, build, and
  `p4a_hook` files; it contains only required runtime content such as `.pyc`.

## Build Log Hygiene

The complete successful `buildozer android debug` transcript is recorded in
`.superpowers/sdd/task-6-build.log`. Its ANSI control sequences were removed
while retaining the full log. A scan for common password, token, secret, API
key, authorization, and session patterns found no credentials.

## Residual Risk

There is no connected ADB target. Real-device installation, notification
permission handling, and foreground monitoring while backgrounded or locked
remain outstanding. The Android 15 `dataSync` timeout is system-managed and
needs API 35 device/system validation for full runtime coverage.
