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
| Size | `21,435,435` bytes |
| Windows SHA256 | `A9A9D67CB70EA13F5370020F780A09F773D0EBCA98099C9926C73E4894075706` |
| Package | `org.example.duifene_sign` |
| Version | versionCode `1029101`; versionName `1.1` |
| SDK | minSdk `29`; targetSdk `35` |
| ABI | `arm64-v8a` |

## Generated Service Timeout Hook

The clean NDK 28c build generated `ServiceMonitor.java` with UUID-token
`onTimeout(int startId, int fgsType)`. The override retains one stable UUID for
the service lifetime, atomically writes `monitor.timeout`, fsyncs the file and
parent directory, and invokes `stopSelf(startId)` in `finally`. Javac and
Gradle completed successfully.

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

## Final UUID Fail-Closed Timeout Evidence Fix

The final review found a fail-open, consume-before-append failure window: deleting
`monitor.timeout` before persisting its terminal event could lose the only
timeout evidence and restore the UI to a monitoring state after an `OSError`
or process interruption.

### RED

Five focused tests were added and run before the implementation. The run
failed as expected with one assertion failure and four errors: the generated
Java lacked a UUID token, `ServiceState.request_timeout` did not accept a
token, and the non-destructive read/expected-token acknowledgement APIs did
not exist. The injected cases cover append failure, retry after successful
append but failed acknowledgement, marker replacement during acknowledgement,
and stable Java UUID generation.

### GREEN

- Focused timeout suite: `5` tests passed.
- Full regression suite: `63` tests run, `62` passed, `1` skipped because Kivy
  is not installed on this host.
- `python -m compileall -q android`: passed with `PYTHONPYCACHEPREFIX` directed
  to a temporary directory.
- `git diff --check`: passed.

### Design

- The generated service owns one UUID timeout token for its lifetime and
  reuses it when atomically replacing `monitor.timeout` on repeated callbacks.
- Python reads timeout evidence without deleting it and derives a stable UUID5
  event ID from the token. An existing matching event is treated as confirmed
  persistence, so retries do not append indefinitely.
- The marker is acknowledged only after the event can be read back. The
  expected-token acknowledgement first atomically claims the marker and keeps
  mismatched or deletion-failed claims as pending evidence, preventing a newer
  token from being deleted.
- Pending primary or claimed evidence forces restored and live UI state to
  stopped. Starting a new monitor continues to clear stale timeout evidence.

### Residual Risk Update

The fault windows are covered with platform-neutral tests, and the final APK
was rebuilt cleanly with NDK 28c after the fix. Javac/Gradle packaging,
`apksigner` v2, `zipalign -c -P 16 -v 4`, true-ELF `0x4000` LOAD alignment, and
the `private.tar` exclusions all passed. Final validation of Android framework
callback timing and filesystem behavior still requires an API 35 device.
