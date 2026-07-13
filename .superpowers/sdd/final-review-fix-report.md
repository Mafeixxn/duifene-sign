# Android Final Review Fix Report

Date: 2026-07-13
Branch: `codex/rebuild-android-app`

## RED

- Baseline before new regressions: `python -m unittest android.tests.test_android_regressions -v` ran 45 tests successfully with 1 Kivy smoke test skipped because Kivy is not installed on this host.
- After adding the requested regression coverage and before production changes, the full command ran 60 tests and failed as expected with 6 assertion failures, 8 missing-interface errors, and 1 environment skip. The failures covered temporary HTTP and malformed login responses, duplicate OAuth verification, timeout marker/UI behavior, missing fail-closed p4a hook, crash reporting, Buildozer NDK/backup/exclusions, and README permission wording.
- During exclusion review, a focused RED run caught the Java hook's fixed `.monitor.timeout.tmp` name missing from `source.exclude_patterns`: 1 test ran and failed.

## GREEN

- Authentication/OAuth focused run: 12 tests passed.
- Timeout hook/marker/UI focused run: 5 tests passed.
- Crash reporter focused run: 3 tests passed.
- Buildozer/README focused run: 3 tests passed.
- Java timeout temporary-file exclusion RED was followed by a focused GREEN run: 1 test passed.
- Full regression run after implementation: 60 tests total, with 59 passed and 1 Kivy smoke test skipped because Kivy is unavailable on this host.
- Final required verification commands and their exit status are recorded below after the final run.

## Changes

- Added a repeatable, fail-closed `p4a.hook` that patches only the expected generated `ServiceMonitor.java` in `before_apk_assemble`. The Android 15 `onTimeout(int startId, int fgsType)` override writes `monitor.timeout` below `filesDir` using fsync plus an atomic same-filesystem rename, fsyncs the directory, never includes authentication data, and always calls `stopSelf(startId)`.
- Added timeout marker creation, one-shot consumption, and stale-marker clearing to `ServiceState`. Activity polling consumes the marker, persists a bounded user-visible terminal event, clears busy/monitoring state through the existing lifecycle path, and refuses to restore a timed-out monitor as running.
- Changed `ApiClient.check_login` so only a parsed `msg=0` response means expired login. `msg=1` remains valid; 429/503, malformed JSON, and ambiguous payloads raise explicit exceptions for the existing five-second `SignService` retry path.
- Removed the Android login worker's second `check_login` request. It now accepts only the exact success result already established by `login_by_wechat_link`, then saves the cookie and loads courses.
- Added an app-private, latest-only atomic `crash.log` reporter. It records UTF-8 traceback frames without source lines or locals, redacts common cookie/session/token forms, delegates both process and threading hooks to their originals, installs after private directories are known, and records service top-level exceptions.
- Updated `buildozer.spec` to NDK `28c`, `android.allow_backup = False`, the p4a hook, and precise runtime-secret/temp/test/build exclusions without broad resource patterns.
- Updated README wording to state that denying Android 13+ notification permission prevents monitoring from starting while preserving the existing warning about later system/background restrictions.
- `android/duifene_sign.apk` was not modified or staged.

## Residual Risk

- Per instruction, no APK was rebuilt. The hook was tested against representative current p4a-generated Java and its fail-closed/idempotent behavior, but Gradle/Javac packaging and an Android 15 device timeout must be verified on the controller's rebuilt APK.
- The desktop host does not have Kivy installed, so the existing Kivy widget smoke test remains skipped; platform-neutral Activity state helpers and source wiring are covered.
- Android's approximately six-hour `dataSync` timeout is system-managed and impractical to exercise in the host unit suite. The rebuilt APK should be inspected for the injected override and tested on API 35 with system/device tooling where available.

## Final Verification

- `python -m unittest android.tests.test_android_regressions -v`: exit 0; 60 tests total, with 59 passed and 1 Kivy smoke test skipped because Kivy is not installed.
- `python -m compileall -q android` with `PYTHONPYCACHEPREFIX` directed to the host temporary directory: exit 0.
- `git diff --check`: exit 0. Git emitted only existing line-ending and inaccessible global-ignore warnings, with no whitespace errors.

## NDK 28c Controller Build Follow-up

### RED

- The controller's clean NDK 28c build reached `compileDebugJavaWithJavac` and failed because Android SDK's `android.system.OsConstants` does not expose `O_DIRECTORY`.
- Added a minimal generated-source regression requiring `O_RDONLY`, forbidding `O_DIRECTORY`, and retaining parent-directory `Os.open`, `Os.fsync`, and `Os.close` calls.
- Target command: `python -m unittest android.tests.test_android_regressions.ForegroundServiceTests.test_p4a_hook_patches_generated_service_idempotently -v`.
- RED result: 1 test ran and failed at `assertNotIn("O_DIRECTORY", patched)` against the generated Java.

### GREEN

- Changed only the generated parent-directory open flags from `O_RDONLY | O_DIRECTORY` to Android SDK-compatible `O_RDONLY`.
- Preserved temporary-file fsync, atomic `android.system.Os.rename`, parent-directory `open/fsync/finally close`, and `stopSelf(startId)` in the outer `finally`.
- Target command: exit 0; 1 test passed.
- Full regression command: exit 0; 60 tests total, with 59 passed and 1 existing Kivy smoke test skipped.
- `python -m compileall -q android` with a temporary `PYTHONPYCACHEPREFIX`: exit 0.
- `git diff --check`: exit 0 with no whitespace errors.

## APK private.tar Hook Exclusion Follow-up

### RED

- Controller inspection found build-only `p4a_hook.pyc` inside the APK's `private.tar`; all previously listed sensitive, test, and build files were already absent.
- Extended the existing Buildozer exclusion regression to require the exact `p4a_hook.py` pattern and to reject broad `*.py` or `**/*.py` exclusions.
- Target command: `python -m unittest android.tests.test_android_regressions.ForegroundServiceTests.test_buildozer_excludes_only_private_runtime_test_and_build_files -v`.
- RED result: 1 test ran and failed because `p4a_hook.py` was not in `source.exclude_patterns`.

### GREEN

- Added only `p4a_hook.py` to `source.exclude_patterns`; normal application Python sources remain included.
- Target command: exit 0; 1 test passed.
- Full regression command: exit 0; 60 tests total, with 59 passed and 1 existing Kivy smoke test skipped.
- `python -m compileall -q android` with a temporary `PYTHONPYCACHEPREFIX`: exit 0.
- `git diff --check`: exit 0 with no whitespace errors.
