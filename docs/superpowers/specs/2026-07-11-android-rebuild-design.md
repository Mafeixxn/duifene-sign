# Android Application Rebuild

## Goal

Replace the existing Android client with a modern Kivy application that uses
WeChat OAuth login only, remains responsive during network operations, and can
continue monitoring while the app is backgrounded or the device is locked.

## Platform

- Minimum Android version: Android 10 (API 29).
- Target Android version: Android 15 (API 35).
- UI framework: Kivy 2.3.x.
- Packaging: Buildozer and python-for-android SDL2 bootstrap.
- CPU target: arm64-v8a.

## User Experience

The app uses one portrait screen with four vertical regions:

1. A compact header containing the product name and a status badge.
2. A WeChat OAuth login card with a multiline link field and one primary login
   button. Saved sessions are validated and restored automatically.
3. A monitoring card containing course selection, a non-negative countdown
   field, and a single start/stop action.
4. A flexible log panel showing timestamped status, warning, error, and success
   messages.

Password login is not exposed. Controls show explicit busy and disabled states.
Long work never runs on Kivy's UI thread.

## Architecture

### API Client

`api_client.py` owns one `requests.Session`, structured form/query encoding,
strict WeChat OAuth code parsing, verified login, course retrieval, activity
parsing, and the three sign-in methods. All requests use a 15 second timeout.

### Session Storage

`session_store.py` stores the exported cookie in Kivy's private `user_data_dir`
using UTF-8. Missing, empty, or invalid files are treated as a signed-out state.
Invalid restored sessions are cleared.

### Foreground Monitoring Service

`service/main.py` is a python-for-android service entry point. The UI starts it
with JSON arguments containing cookie, course ID, class ID, course name, and
countdown. The service creates a foreground notification immediately and owns
the polling loop until stopped.

The service writes compact JSON-line events to an app-private log/state file.
The UI tails that file while visible. This avoids relying on an in-process
thread after Android suspends the activity. Starting a new monitor replaces the
previous state; a stop marker causes the service to exit and remove its
notification.

### Monitoring Engine

`sign_service.py` contains platform-neutral polling logic used by the Android
service and unit tests. It normalizes IDs to strings, validates malformed
activity data, prevents duplicate sign-in, backs off to five seconds after
network errors, and refreshes the course session every ten minutes.

## Android Integration

- Declare `INTERNET`, `ACCESS_NETWORK_STATE`, `FOREGROUND_SERVICE`, and
  `POST_NOTIFICATIONS` permissions.
- Request notification permission at runtime on Android 13 and newer.
- Use a generic data-sync foreground-service notification category.
- Keep secrets in application-private storage and exclude session files from
  packaged sources and version control.

## Error Handling

- Login and course failures return to an enabled UI with a clear log message.
- Network timeouts never stop monitoring; they trigger bounded backoff.
- Expired login stops monitoring and records an actionable warning.
- Malformed activities are reported and skipped without terminating the loop.
- Crash reports are written to the application-private directory.

## Verification

- Unit tests cover structured requests, OAuth validation, verified sessions,
  numeric/string class ID compatibility, malformed activities, duplicate
  course labels, countdown validation, and network backoff.
- Desktop Kivy smoke tests verify widget construction and busy-state behavior
  when Kivy is available.
- Buildozer configuration is checked for API levels, permissions, service
  declaration, source files, and requirements.
- The final APK must build successfully; device installation and background
  lock-screen behavior require an Android device or emulator for final proof.
