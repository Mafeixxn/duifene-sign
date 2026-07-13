# Android Application Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a responsive Android 10+ Kivy client with verified WeChat login and foreground-service monitoring that continues while backgrounded or locked.

**Architecture:** Platform-neutral API and polling modules are covered by desktop unit tests. The Kivy activity performs login and course loading in worker threads, stores sessions in its private data directory, and starts a python-for-android foreground `dataSync` service. The service owns monitoring and exchanges JSON-line state with the visible activity through private files.

**Tech Stack:** Python 3, Kivy 2.3.x, requests, pyjnius, python-for-android 2026.05+, Buildozer, unittest

## Global Constraints

- Minimum Android API is 29 and target API is 35.
- Only arm64-v8a is packaged.
- Password login is not exposed.
- All HTTP requests use a 15 second timeout and structured parameters.
- The UI thread never performs network requests or blocking joins.
- Foreground monitoring is user-initiated and stops cleanly; Android 15 `dataSync` service duration limits are not bypassed.

---

### Task 1: Harden the Android API Client

**Files:**
- Modify: `android/api_client.py`
- Create: `android/tests/test_android_regressions.py`
- Create: `android/tests/__init__.py`

**Interfaces:**
- Produces: `ApiClient(cookie_str="")`, `_extract_wechat_code(link)`, `login_by_wechat_link(link)`, `check_login()`, `get_course_list()`, activity and sign-in methods.

- [ ] Write failing tests proving OAuth codes are parsed with `urlparse`/`parse_qs`, malformed or duplicate codes are rejected, login success requires `check_login()`, and form/query data remains structured when values contain `&` or `=`.
- [ ] Run `python -m unittest android.tests.test_android_regressions.ApiClientTests -v` from the repository root and confirm the current client fails those assertions.
- [ ] Replace string-built request bodies and URLs with dictionaries and `urlencode`; validate exactly one 32-character OAuth code and verify the session before returning success.
- [ ] Normalize `course_id` before response membership checks and retain the lightweight `HTMLParser` implementation.
- [ ] Run the targeted API tests and confirm PASS.

### Task 2: Replace the Polling Engine

**Files:**
- Modify: `android/sign_service.py`
- Test: `android/tests/test_android_regressions.py`

**Interfaces:**
- Produces: `SignService(api, on_log=None, on_status=None)`, `configure(...)`, `poll_once()`, `run(stop_event)`, and `next_poll_delay`.

- [ ] Add failing tests for numeric/string class ID equality, malformed countdown/activity fields, duplicate check-in suppression, request timeout backoff to five seconds, and login-expiry termination.
- [ ] Run the SignService test class and confirm failures match the missing behavior.
- [ ] Implement a platform-neutral engine with string-normalized IDs, guarded activity parsing, ten-minute course refresh, one-second normal polling, five-second network-error backoff, and interruptible `Event.wait(delay)` sleeping.
- [ ] Keep all callback invocations exception-safe and ensure one failed activity cannot terminate the loop.
- [ ] Run targeted service tests and confirm PASS.

### Task 3: Add Private Storage and Service IPC

**Files:**
- Create: `android/session_store.py`
- Create: `android/service_state.py`
- Test: `android/tests/test_android_regressions.py`

**Interfaces:**
- Produces: `SessionStore(base_dir)` with `load_cookie`, `save_cookie`, and `clear`; `ServiceState(base_dir)` with atomic config/stop writes and JSON-line event append/read.

- [ ] Add failing temporary-directory tests for missing files, UTF-8 cookie round trips, clear behavior, atomic monitor configuration, stop markers, and ignoring malformed event lines.
- [ ] Implement storage with `pathlib`, temporary-file replacement, restricted app-private paths, and bounded event-log retention.
- [ ] Run storage/IPC tests and confirm PASS.

### Task 4: Build the Foreground Monitoring Service

**Files:**
- Create: `android/service/main.py`
- Create: `android/service/__init__.py`
- Modify: `android/buildozer.spec`

**Interfaces:**
- Consumes: monitor JSON from `ServiceState`, `ApiClient`, and `SignService`.
- Produces: foreground service `monitor:service/main.py:foreground:sticky:foregroundServiceType=dataSync`.

- [ ] Implement service bootstrap that reads `PYTHON_SERVICE_ARGUMENT`, resolves the private app directory, creates API/engine objects, writes service events, and exits on the stop marker.
- [ ] Use python-for-android's generated foreground service notification rather than creating a second notification implementation.
- [ ] Update Buildozer to API 35, min API 29, current Kivy and requests requirements, `arm64-v8a`, and permissions `INTERNET`, `ACCESS_NETWORK_STATE`, `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_DATA_SYNC`, and `POST_NOTIFICATIONS`.
- [ ] Add a configuration test that parses `buildozer.spec` and asserts the service declaration, API levels, architecture, and required permissions.

### Task 5: Rebuild the Kivy Activity UI

**Files:**
- Replace: `android/main.py`
- Test: `android/tests/test_android_regressions.py`

**Interfaces:**
- Produces: `SignPanel` with link login, course selection, countdown validation, foreground-service start/stop, event tailing, and explicit busy states.

- [ ] Add pure helper tests for non-negative countdown parsing, duplicate course labels, and service argument JSON generation.
- [ ] Build a one-screen card layout with a compact header/status badge, OAuth field/button, course/countdown controls, one start/stop button, and flexible timestamped log.
- [ ] Run login, restore, and course loading in daemon worker threads; marshal all Kivy changes through `Clock.schedule_once` or `@mainthread`.
- [ ] Store cookies under `App.user_data_dir`, validate restored sessions, and clear invalid cookies.
- [ ] On Android 13+, request `POST_NOTIFICATIONS` before service start. Start the generated service from the visible activity via PyJNIus; stop it through its generated class plus the stop marker.
- [ ] Poll service JSON-line events only while the activity is visible and restore current monitoring state after returning from background.
- [ ] Add a desktop smoke test guarded by Kivy availability that constructs `SignPanel` and confirms password fields/buttons are absent.

### Task 6: Documentation and Packaging

**Files:**
- Modify: `README.md`
- Modify: `android/.gitignore`

- [ ] Update Android requirements to Android 10+, document the foreground notification/background behavior, notification permission, OAuth-only login, and battery-management caveat without removing unrelated README content.
- [ ] Ignore private session, service state, event, crash, and Buildozer output files.
- [ ] Run `python -m unittest android.tests.test_android_regressions -v` and confirm all Android tests pass.
- [ ] Run `python -m compileall -q android` and `git diff --check`.
- [ ] Run `buildozer android debug` in a Linux/WSL environment with JDK, SDK, and NDK available; record the APK path and SHA256.
- [ ] If an ADB target is available, install the APK, grant notifications, start monitoring, background and lock the device, then verify the foreground notification and continued event output. Otherwise report device verification as outstanding rather than claiming it passed.
