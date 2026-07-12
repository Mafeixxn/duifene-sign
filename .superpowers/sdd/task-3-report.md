# Task 3 Report: Add Private Storage and Service IPC

## Status

Completed on `codex/rebuild-android-app`.

## Scope

Task-owned implementation and regression-test changes:

- `android/session_store.py`
- `android/service_state.py`
- `android/tests/test_android_regressions.py`

This report is the requested additional artifact. Unrelated changes already
present in `.gitignore`, `.claude/`, `_codex_payload.json`, and
`windows/.claude/` were left untouched.

## RED

Added temporary-directory tests before creating either production module. The
new coverage specifies:

1. A missing cookie file loads as a signed-out empty string.
2. Cookies round-trip as UTF-8 and `clear()` removes the saved session.
3. Monitor configuration replaces prior JSON state, and stop markers can be
   requested and cleared.
4. JSONL readers skip malformed and non-object lines.
5. Event retention keeps only the most recent bounded entries.

Ran from the repository root:

```text
PYTHONDONTWRITEBYTECODE=1 python -m unittest \
  android.tests.test_android_regressions.PrivateStorageTests -v
```

The run failed as expected before implementation during test-module import:

```text
ModuleNotFoundError: No module named 'android.session_store'
```

That failure demonstrated the requested storage API did not exist yet.

## GREEN

Implemented `SessionStore(base_dir)` with fixed `cookie.txt` storage below the
given private directory. It creates the private directory when needed, reads
UTF-8 safely as an empty signed-out state on missing or invalid files, replaces
cookies through a same-directory temporary file plus `Path.replace()`, and
removes saved sessions idempotently.

Implemented `ServiceState(base_dir)` with fixed private paths for
`monitor.json`, `monitor.stop`, and `monitor-events.jsonl`:

- Configuration and stop-marker writes use same-directory temporary files and
  atomic replacement.
- Replacing monitor configuration clears an earlier stop marker.
- JSONL event appends use UTF-8 and fsync; the log retains at most 200 recent
  lines, replacing the file atomically during rollover.
- Event reads tolerate missing files, malformed JSON, and JSON values that are
  not event objects.

Focused verification after the implementation:

```text
PYTHONDONTWRITEBYTECODE=1 python -m unittest \
  android.tests.test_android_regressions.PrivateStorageTests -v
Ran 7 tests in 2.438s
OK
```

## Full Regression Verification

Ran once from the repository root:

```text
PYTHONDONTWRITEBYTECODE=1 python -m unittest \
  android.tests.test_android_regressions -v
Ran 20 tests in 0.408s
OK
```

`git diff --check` also completed with exit code 0. Git reported pre-existing
CRLF and global-ignore permission warnings only; it reported no whitespace
errors.

## Self-Review

- Confirmed that callers cannot choose a filename: all session, config, stop,
  and event paths are fixed children of the resolved `base_dir`.
- Confirmed that both atomic writers create temporary files in that same
  private directory before replacement, preventing cross-filesystem moves.
- Confirmed missing, invalid, empty, and malformed persisted state degrades to
  safe signed-out or absent-state results rather than crashing the UI/service
  boundary.
- Confirmed retention keeps the newest entries after rollover and readers skip
  an incomplete line that could be observed while another process is writing.
- Confirmed only the task-owned Android modules, regression tests, and this
  required report are staged for the task commit.

## Concern

The event log is designed for the planned single foreground-service writer and
visible-activity reader. Concurrent event writers are outside this task's IPC
contract and would require a cross-process lock to avoid lost rollover writes.

## Review Follow-up Fixes

### RED

Added two regressions to `PrivateStorageTests` before changing the production
code:

1. A saved UTF-8 cookie with leading and trailing whitespace must load exactly
   as written.
2. A JSONL file beginning with invalid UTF-8 bytes must recover when valid
   events are appended, and must still retain only the newest 200 events.

Ran:

```text
PYTHONDONTWRITEBYTECODE=1 python -m unittest \
  android.tests.test_android_regressions.PrivateStorageTests -v
```

The expected failures were observed:

```text
FAIL: test_cookie_round_trips_with_leading_and_trailing_whitespace
AssertionError: 'session=...'
             != ' \t session=... \n'

FAIL: test_event_log_recovers_from_invalid_utf8_before_bounded_retention
AssertionError: 0 != 200
```

### GREEN

`SessionStore.load_cookie()` now returns successfully decoded text verbatim;
missing, invalid, and genuinely empty files still produce the signed-out empty
string. `ServiceState.append_event()` now atomically replaces an invalid UTF-8
event file with the incoming valid JSONL line before later appends and normal
retention resume.

Focused storage/IPC verification:

```text
PYTHONDONTWRITEBYTECODE=1 python -m unittest \
  android.tests.test_android_regressions.PrivateStorageTests -v
Ran 9 tests in 0.372s
OK
```

Full Android regression verification:

```text
PYTHONDONTWRITEBYTECODE=1 python -m unittest \
  android.tests.test_android_regressions -v
Ran 22 tests in 0.364s
OK
```
