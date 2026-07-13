# Task 6 Report: Documentation and Packaging

## Status

Documentation and packaging-ignore work is complete on `codex/rebuild-android-app`.
APK construction and device verification remain outstanding because this Windows
host has no installed WSL distribution, Buildozer, or ADB.

Committed task-owned repository changes: `6daf66f` (`Document Android foreground monitoring`).

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

Run from `F:\成品\安卓版签到`:

| Command | Result |
| --- | --- |
| `python -m unittest android.tests.test_android_regressions -v` | PASS: 44 tests ran; 43 passed and 1 expected skip because Kivy is not installed on this host. |
| `python -m compileall -q android` | Initial direct run was blocked by sandbox permission errors while writing existing repository `__pycache__` directories. Re-ran with `PYTHONPYCACHEPREFIX=$env:TEMP`; PASS with exit code 0. |
| `git -c safe.directory='F:/成品/安卓版签到' diff --check` | PASS with exit code 0. Git emitted only existing LF-to-CRLF conversion warnings for `.gitignore` and `README.md`. |
| `wsl -l -v` | BLOCKED: `wsl.exe` is installed, but no Linux distribution is installed. |
| `Get-Command buildozer` | BLOCKED: unavailable. |
| `Get-Command adb` | BLOCKED: unavailable. |

## Blockers

- No installed Linux/WSL distribution with JDK, Android SDK, Android NDK, and
  Buildozer. `buildozer android debug` was not run, so no rebuilt APK path or
  SHA256 can be recorded.
- No ADB executable or connected target. Installation, notification permission
  grant, background/lock foreground-notification verification, and continued
  event-output verification are outstanding.
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
