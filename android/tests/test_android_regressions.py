import configparser
import datetime
import importlib
import inspect
import json
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from android.api_client import ApiClient
from android.session_store import SessionStore
from android.sign_service import SignService
from android.service_state import ServiceState
from android.service.main import (
    StopMarker,
    _append_event,
    load_monitor_config,
    parse_service_argument,
    resolve_private_app_dir,
    run_monitor,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeCookies(dict):
    def clear(self):
        super().clear()


class FakeSession:
    def __init__(self):
        self.headers = {}
        self.cookies = FakeCookies()
        self.posts = []
        self.gets = []

    def post(self, url, data=None, headers=None, timeout=None):
        self.posts.append((url, data, headers, timeout))
        return FakeResponse()

    def get(self, url, headers=None, timeout=None):
        self.gets.append((url, headers, timeout))
        return FakeResponse()


class ApiClientTests(unittest.TestCase):
    def setUp(self):
        self.api = ApiClient()
        self.session = FakeSession()
        self.api.session = self.session

    def test_extracts_oauth_code_from_query_parameters(self):
        code = "a" * 32

        self.assertEqual(
            self.api._extract_wechat_code(
                f"https://example.test/callback?state=keep&code={code}&other=value"
            ),
            code,
        )

    def test_rejects_malformed_or_duplicate_oauth_codes(self):
        valid_code = "a" * 32

        for link in (
            "https://example.test/callback?state=missing",
            "https://example.test/callback?code=too-short",
            f"https://example.test/callback?code={valid_code}&code={'b' * 32}",
        ):
            with self.subTest(link=link):
                self.assertIsNone(self.api._extract_wechat_code(link))

    def test_wechat_login_uses_encoded_query_and_requires_session_check(self):
        code = "a" * 32
        self.api.check_login = lambda: False

        message = self.api.login_by_wechat_link(
            f"https://example.test/callback?state=keep&code={code}"
        )

        self.assertIn("登录失败", message)
        request_url = self.session.gets[-1][0]
        self.assertEqual(
            parse_qs(urlparse(request_url).query),
            {"authtype": ["1"], "code": [code], "state": ["1"]},
        )

    def test_wechat_login_returns_exact_success_after_session_verification(self):
        code = "a" * 32
        self.api.check_login = lambda: True

        self.assertEqual(
            self.api.login_by_wechat_link(
                f"https://example.test/callback?state=keep&code={code}"
            ),
            "微信链接登录成功",
        )

    def test_check_login_raises_for_temporary_http_failures(self):
        for status_code in (429, 503):
            with self.subTest(status_code=status_code):
                self.session.post = lambda *args, **kwargs: FakeResponse(
                    status_code=status_code
                )
                with self.assertRaisesRegex(ConnectionError, str(status_code)):
                    self.api.check_login()

    def test_check_login_raises_for_malformed_json(self):
        self.session.post = lambda *args, **kwargs: FakeResponse(
            payload=ValueError("malformed")
        )

        with self.assertRaisesRegex(ValueError, "JSON"):
            self.api.check_login()

    def test_check_login_returns_false_only_for_explicit_expiry(self):
        self.session.post = lambda *args, **kwargs: FakeResponse(payload={"msg": "0"})

        self.assertFalse(self.api.check_login())

    def test_check_login_returns_true_for_valid_session(self):
        self.session.post = lambda *args, **kwargs: FakeResponse(payload={"msg": "1"})

        self.assertTrue(self.api.check_login())

    def test_form_values_with_reserved_characters_remain_structured(self):
        self.api.login_by_password("user&role=admin", "pass=word&token=abc")

        _, data, _, _ = self.session.posts[-1]
        self.assertEqual(
            data,
            {
                "action": "loginmb",
                "loginname": "user&role=admin",
                "password": "pass=word&token=abc",
            },
        )

    def test_query_values_with_reserved_characters_remain_structured(self):
        self.api.do_qrcode_signin("state=value&token=abc")

        request_url = self.session.gets[-1][0]
        self.assertEqual(
            parse_qs(urlparse(request_url).query),
            {"state": ["state=value&token=abc"]},
        )

    def test_normalizes_numeric_course_id_before_response_membership_check(self):
        self.session.get = lambda *args, **kwargs: FakeResponse(text="course=123")

        self.assertTrue(self.api.enter_course(123))


class FakeSignServiceApi:
    def __init__(self):
        self.logged_in = True
        self.activities = []
        self.entered_courses = []
        self.code_signins = []

    def check_login(self):
        return self.logged_in

    def enter_course(self, course_id):
        self.entered_courses.append(course_id)
        return True

    def check_sign_activity(self, class_id):
        if self.activities:
            activity = self.activities.pop(0)
            if isinstance(activity, Exception):
                raise activity
            return activity
        return None

    def do_code_signin(self, code):
        self.code_signins.append(code)
        return "签到成功"

    def do_qrcode_signin(self, checkin_id):
        return "签到成功"

    def do_location_signin(self, longitude, latitude):
        return "签到成功"


class SignServiceTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeSignServiceApi()
        self.service = SignService(self.api)
        self.service.configure(course_id=101, class_id=7, class_name="Physics")

    def test_matches_numeric_class_id_against_string_configuration(self):
        self.api.activities = [{
            "type": "1",
            "checkin_id": 42,
            "class_ids": [7],
            "seconds": "0",
            "code": "1234",
        }]

        self.assertTrue(self.service.poll_once())
        self.assertEqual(self.api.code_signins, ["1234"])

    def test_ignores_malformed_activity_countdown_and_class_fields(self):
        self.api.activities = [
            {"type": "1", "checkin_id": "bad-seconds", "class_ids": ["7"],
             "seconds": "not-a-number", "code": "1234"},
            {"type": "1", "checkin_id": "bad-classes", "class_ids": None,
             "seconds": "0", "code": "1234"},
        ]

        self.assertTrue(self.service.poll_once())
        self.assertTrue(self.service.poll_once())
        self.assertEqual(self.api.code_signins, [])
        self.assertEqual(self.service.next_poll_delay, 1)

    def test_suppresses_duplicate_checkins_after_success(self):
        activity = {
            "type": "1",
            "checkin_id": "duplicate",
            "class_ids": ["7"],
            "seconds": "0",
            "code": "1234",
        }
        self.api.activities = [activity, activity]

        self.service.poll_once()
        self.service.poll_once()

        self.assertEqual(self.api.code_signins, ["1234"])

    def test_uses_five_second_backoff_after_activity_timeout(self):
        self.api.activities = [TimeoutError("timed out")]

        self.assertTrue(self.service.poll_once())
        self.assertEqual(self.service.next_poll_delay, 5)

    def test_retries_course_refresh_after_unsuccessful_enter(self):
        self.api.enter_course = lambda course_id: (
            self.api.entered_courses.append(course_id) or False
        )

        self.service.poll_once()
        self.service.poll_once()

        self.assertEqual(self.api.entered_courses, ["101", "101"])

    def test_login_expiry_stops_running_loop_and_reports_status(self):
        statuses = []
        waits = []

        class StopAfterWait:
            def is_set(self):
                return False

            def wait(self, delay):
                waits.append(delay)
                return True

        self.service.on_status = statuses.append
        self.api.logged_in = False

        self.service.run(StopAfterWait())

        self.assertEqual(statuses, [True, False])
        self.assertEqual(waits, [])
        self.assertFalse(self.service.is_running)


class PrivateStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base_dir = self.temp_dir.name

    def test_missing_cookie_file_loads_as_signed_out(self):
        self.assertEqual(SessionStore(self.base_dir).load_cookie(), "")

    def test_cookie_round_trips_as_utf8(self):
        store = SessionStore(self.base_dir)
        cookie = "session=\u6d4b\u8bd5; name=\u771f\u5bfb"

        store.save_cookie(cookie)

        self.assertEqual(store.load_cookie(), cookie)

    def test_cookie_round_trips_with_leading_and_trailing_whitespace(self):
        store = SessionStore(self.base_dir)
        cookie = " \t session=\u6d4b\u8bd5; name=\u771f\u5bfb \n"

        store.save_cookie(cookie)

        self.assertEqual(store.load_cookie(), cookie)

    def test_clear_removes_saved_cookie(self):
        store = SessionStore(self.base_dir)
        store.save_cookie("session=active")

        store.clear()

        self.assertEqual(store.load_cookie(), "")

    def test_monitor_configuration_replaces_previous_json_atomically(self):
        state = ServiceState(self.base_dir)
        initial_config = {"course_id": "old", "countdown": 10}
        config = {"course_id": "new", "class_id": "7", "countdown": 0}
        state.write_config(initial_config)

        state.write_config(config)

        self.assertEqual(state.read_config(), config)
        self.assertEqual(
            json.loads((state.base_dir / state.CONFIG_FILE).read_text(encoding="utf-8")),
            config,
        )

    def test_stop_marker_can_be_requested_and_cleared(self):
        state = ServiceState(self.base_dir)

        self.assertFalse(state.stop_requested())
        state.request_stop()
        self.assertTrue(state.stop_requested())
        state.clear_stop()
        self.assertFalse(state.stop_requested())

    def test_timeout_marker_is_consumed_once_and_cleared_for_new_config(self):
        state = ServiceState(self.base_dir)

        state.request_timeout()
        self.assertTrue(state.timeout_requested())
        self.assertTrue(state.consume_timeout())
        self.assertFalse(state.consume_timeout())

        state.request_timeout()
        state.write_config({"course_id": "new"})
        self.assertFalse(state.timeout_requested())

    def test_event_reader_ignores_malformed_json_lines(self):
        state = ServiceState(self.base_dir)
        state.append_event({"level": "info", "message": "first"})
        with state.events_path.open("a", encoding="utf-8") as event_file:
            event_file.write("not json\n")
            event_file.write('["not", "an", "event"]\n')
        state.append_event({"level": "success", "message": "done"})

        self.assertEqual(
            state.read_events(),
            [
                {"level": "info", "message": "first"},
                {"level": "success", "message": "done"},
            ],
        )

    def test_event_log_retains_only_the_most_recent_bounded_events(self):
        state = ServiceState(self.base_dir)
        for index in range(state.MAX_EVENT_LINES + 2):
            state.append_event({"index": index})

        events = state.read_events()

        self.assertEqual(len(events), state.MAX_EVENT_LINES)
        self.assertEqual(events[0], {"index": 2})
        self.assertEqual(events[-1], {"index": state.MAX_EVENT_LINES + 1})

    def test_event_log_retains_json_strings_with_unicode_line_separators(self):
        state = ServiceState(self.base_dir)
        message = "first\u0085second"
        for index in range(state.MAX_EVENT_LINES + 1):
            event = {"index": index}
            if index == 1:
                event["message"] = message
            state.append_event(event)

        events = state.read_events()

        self.assertEqual(len(events), state.MAX_EVENT_LINES)
        self.assertEqual(events[0], {"index": 1, "message": message})
        self.assertEqual(events[-1], {"index": state.MAX_EVENT_LINES})

    def test_event_log_recovers_from_invalid_utf8_before_bounded_retention(self):
        state = ServiceState(self.base_dir)
        state.events_path.write_bytes(b'{"corrupt":"\xff"}\n')

        for index in range(state.MAX_EVENT_LINES + 2):
            state.append_event({"index": index})

        events = state.read_events()

        self.assertEqual(len(events), state.MAX_EVENT_LINES)
        self.assertEqual(events[0], {"index": 2})
        self.assertEqual(events[-1], {"index": state.MAX_EVENT_LINES + 1})


class ForegroundServiceTests(unittest.TestCase):
    def test_service_events_persist_unique_uuid_hex_event_ids(self):
        with tempfile.TemporaryDirectory() as base_dir:
            state = ServiceState(base_dir)

            _append_event(state, "info", "same physical payload")
            _append_event(state, "info", "same physical payload")

            events = state.read_events()

        event_ids = [event["event_id"] for event in events]
        self.assertEqual(len(event_ids), 2)
        self.assertEqual(len(set(event_ids)), 2)
        for event_id in event_ids:
            with self.subTest(event_id=event_id):
                self.assertEqual(len(event_id), 32)
                self.assertEqual(format(int(event_id, 16), "032x"), event_id)

    def test_buildozer_declares_android_15_data_sync_service_contract(self):
        parser = configparser.ConfigParser(interpolation=None)
        spec_path = Path(__file__).resolve().parents[1] / "buildozer.spec"
        parser.read(spec_path, encoding="utf-8")

        app = parser["app"]
        requirements = {item.strip() for item in app["requirements"].split(",")}
        permissions = {item.strip() for item in app["android.permissions"].split(",")}

        self.assertEqual(
            app["services"],
            "monitor:service/main.py:foreground:sticky:foregroundServiceType=dataSync",
        )
        self.assertEqual(app["android.api"], "35")
        self.assertEqual(app["android.minapi"], "29")
        self.assertEqual(app["android.archs"], "arm64-v8a")
        self.assertIn("kivy==2.3.1", requirements)
        self.assertIn("requests==2.34.2", requirements)
        self.assertTrue(
            {
                "INTERNET",
                "ACCESS_NETWORK_STATE",
                "FOREGROUND_SERVICE",
                "FOREGROUND_SERVICE_DATA_SYNC",
                "POST_NOTIFICATIONS",
            }.issubset(permissions)
        )

    def test_buildozer_omits_empty_gradle_dependencies(self):
        parser = configparser.ConfigParser(interpolation=None)
        spec_path = Path(__file__).resolve().parents[1] / "buildozer.spec"
        parser.read(spec_path, encoding="utf-8")

        self.assertNotIn("android.gradle_dependencies", parser["app"])

    def test_buildozer_uses_ndk_28c_disables_backup_and_registers_hook(self):
        parser = configparser.ConfigParser(interpolation=None)
        spec_path = Path(__file__).resolve().parents[1] / "buildozer.spec"
        parser.read(spec_path, encoding="utf-8")

        app = parser["app"]
        self.assertEqual(app["android.ndk"], "28c")
        self.assertEqual(app["android.allow_backup"], "False")
        self.assertEqual(app["p4a.hook"], "p4a_hook.py")

    def test_buildozer_excludes_only_private_runtime_test_and_build_files(self):
        parser = configparser.ConfigParser(interpolation=None)
        spec_path = Path(__file__).resolve().parents[1] / "buildozer.spec"
        parser.read(spec_path, encoding="utf-8")
        patterns = {
            item.strip()
            for item in parser["app"]["source.exclude_patterns"].split(",")
        }

        required = {
            "cookie.txt",
            "monitor.json",
            "monitor.stop",
            "monitor.timeout",
            "monitor-events.jsonl",
            "crash.log",
            "crash-*.log",
            ".cookie.txt.*.tmp",
            ".monitor.json.*.tmp",
            ".monitor.stop.*.tmp",
            ".monitor.timeout.tmp",
            ".monitor.timeout.*.tmp",
            ".monitor-events.jsonl.*.tmp",
            ".crash.log.*.tmp",
            ".crash-*.log.*.tmp",
            "tests/*",
            ".buildozer/*",
            "bin/*",
            "build/*",
            "dist/*",
            "**/__pycache__/*",
        }
        self.assertTrue(required.issubset(patterns))
        self.assertTrue({"*.png", "*.jpg", "main.py", "service/*"}.isdisjoint(patterns))

    def test_p4a_hook_patches_generated_service_idempotently(self):
        from android.p4a_hook import patch_service_java

        generated = """package org.example.duifene_sign;

public class ServiceMonitor extends org.kivy.android.PythonService {
    public static void start(android.content.Context context, String argument) {}
}
"""
        with tempfile.TemporaryDirectory() as base_dir:
            java_path = Path(base_dir) / "ServiceMonitor.java"
            java_path.write_text(generated, encoding="utf-8")

            self.assertTrue(patch_service_java(java_path))
            patched = java_path.read_text(encoding="utf-8")
            self.assertFalse(patch_service_java(java_path))
            self.assertEqual(java_path.read_text(encoding="utf-8"), patched)

        self.assertIn("public void onTimeout(int startId, int fgsType)", patched)
        self.assertIn('"monitor.timeout"', patched)
        self.assertIn("getFilesDir()", patched)
        self.assertIn("stopSelf(startId)", patched)
        self.assertIn("android.system.OsConstants.O_RDONLY", patched)
        self.assertNotIn("O_DIRECTORY", patched)
        self.assertIn("android.system.Os.open(", patched)
        self.assertIn("android.system.Os.fsync(directory)", patched)
        self.assertIn("android.system.Os.close(directory)", patched)
        self.assertNotIn("Cookie", patched)

    def test_p4a_hook_fails_closed_when_generated_service_is_missing_or_unrecognized(self):
        from android.p4a_hook import patch_service_java

        with tempfile.TemporaryDirectory() as base_dir:
            missing = Path(base_dir) / "ServiceMonitor.java"
            with self.assertRaises(FileNotFoundError):
                patch_service_java(missing)

            missing.write_text("public class Unexpected {}\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                patch_service_java(missing)

            missing.write_text(
                "public class ServiceMonitor extends PythonService {\n"
                "    public void onTimeout(int startId, int fgsType) {}\n"
                "}\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "timeout override"):
                patch_service_java(missing)

    def test_bootstrap_helpers_parse_argument_and_prefer_shared_monitor_state(self):
        self.assertEqual(parse_service_argument("not-json"), {})
        self.assertEqual(parse_service_argument("[]"), {})
        argument_config = {"cookie": "argument", "course_id": "1"}
        self.assertEqual(parse_service_argument(json.dumps(argument_config)), argument_config)

        with tempfile.TemporaryDirectory() as base_dir:
            state = ServiceState(base_dir)
            shared_config = {"cookie": "shared", "course_id": "2"}
            state.write_config(shared_config)

            self.assertEqual(load_monitor_config(state, json.dumps(argument_config)), shared_config)

    def test_stop_marker_and_private_directory_helpers_use_service_state_and_context(self):
        class FakeFilesDir:
            def getAbsolutePath(self):
                return "."

        class FakeContext:
            def getFilesDir(self):
                return FakeFilesDir()

        with tempfile.TemporaryDirectory() as base_dir:
            state = ServiceState(base_dir)
            marker = StopMarker(state)

            self.assertFalse(marker.is_set())
            state.request_stop()
            self.assertTrue(marker.is_set())

        self.assertEqual(resolve_private_app_dir(FakeContext()), str(Path(".").resolve()))

    def test_bootstrap_rejects_none_monitor_fields_before_constructing_api(self):
        with tempfile.TemporaryDirectory() as base_dir:
            state = ServiceState(base_dir)
            state.write_config(
                {
                    "cookie": None,
                    "course_id": "1",
                    "class_id": "2",
                    "class_name": "Physics",
                }
            )

            run_monitor(
                state,
                "",
                api_factory=lambda cookie: self.fail("API must not be constructed"),
            )

            self.assertEqual(state.read_events()[-1]["level"], "error")


class ActivityUiTests(unittest.TestCase):
    @staticmethod
    def _activity_module():
        return importlib.import_module("android.main")

    def test_countdown_helper_returns_nonnegative_integer(self):
        normalize_countdown = self._activity_module().normalize_countdown

        self.assertEqual(normalize_countdown("25"), 25)
        self.assertEqual(normalize_countdown("-4"), 0)
        self.assertEqual(normalize_countdown(""), 10)
        self.assertEqual(normalize_countdown("not-a-number"), 10)
        self.assertEqual(normalize_countdown(None, default=3), 3)

    def test_duplicate_course_labels_are_unique_and_stable(self):
        course_labels = self._activity_module().course_labels
        courses = [
            {"CourseName": "Physics"},
            {"CourseName": "Physics"},
            {"CourseName": "Chemistry"},
            {"CourseName": "Physics"},
        ]

        self.assertEqual(
            course_labels(courses),
            ["Physics", "Physics (2)", "Chemistry", "Physics (3)"],
        )
        self.assertEqual(
            course_labels([
                {"CourseName": "Physics"},
                {"CourseName": "Physics"},
                {"CourseName": "Physics (2)"},
            ]),
            ["Physics", "Physics (3)", "Physics (2)"],
        )

    def test_service_argument_json_contains_normalized_monitor_config(self):
        service_argument_json = self._activity_module().service_argument_json
        course = {"CourseID": 12, "TClassID": 34, "CourseName": "Physics"}

        payload = service_argument_json("sid=test", course, "-2")

        self.assertEqual(
            json.loads(payload),
            {
                "cookie": "sid=test",
                "course_id": "12",
                "class_id": "34",
                "class_name": "Physics",
                "countdown": 0,
            },
        )
        self.assertNotIn(" ", payload)

    def test_worker_helper_starts_daemon_thread(self):
        start_daemon_worker = self._activity_module().start_daemon_worker
        completed = threading.Event()

        worker = start_daemon_worker(completed.set, name="activity-test")

        self.assertTrue(worker.daemon)
        self.assertEqual(worker.name, "activity-test")
        self.assertTrue(completed.wait(1))
        worker.join(1)

    def test_vertical_stack_height_includes_children_spacing_and_padding(self):
        vertical_stack_height = self._activity_module().vertical_stack_height

        self.assertEqual(vertical_stack_height([18, 42, 42]), 136)
        self.assertEqual(vertical_stack_height([42, 42]), 111)
        self.assertEqual(vertical_stack_height([]), 20)

    def test_monitoring_state_uses_only_explicit_service_lifecycle_messages(self):
        module = self._activity_module()
        stopped_messages = (
            "Monitoring stopped.",
            "Monitoring stopped before service startup.",
            "Monitoring configuration is unavailable.",
            "Monitoring service failed: boom",
        )

        self.assertTrue(module.lifecycle_monitoring_state("Monitoring started."))
        for message in stopped_messages:
            with self.subTest(message=message):
                self.assertFalse(module.lifecycle_monitoring_state(message))
        for message in (
            "Polling request failed: timed out",
            "Session expired while polling; retrying.",
            "Course unavailable; polling continues.",
            "Worker stopped responding briefly.",
        ):
            with self.subTest(message=message):
                self.assertIsNone(module.lifecycle_monitoring_state(message))

    def test_restored_monitoring_state_ignores_transient_failures(self):
        restored_monitoring_state = self._activity_module().restored_monitoring_state
        events = [
            {"message": "Monitoring started."},
            {"message": "Polling request failed: timed out"},
        ]

        self.assertTrue(restored_monitoring_state(True, False, events))
        events.append({"message": "Monitoring configuration is unavailable."})
        self.assertFalse(restored_monitoring_state(True, False, events))

    def test_polled_lifecycle_events_update_monitoring_state_immediately(self):
        apply_lifecycle_events = self._activity_module().apply_lifecycle_events

        self.assertFalse(apply_lifecycle_events(True, [
            {"message": "Monitoring stopped before service startup."},
        ]))
        self.assertFalse(apply_lifecycle_events(True, [
            {"message": "Monitoring service failed: broken config"},
        ]))
        self.assertTrue(apply_lifecycle_events(False, [
            {"message": "Monitoring started."},
        ]))

    def test_timeout_marker_records_visible_terminal_event_and_stops_restored_state(self):
        module = self._activity_module()
        with tempfile.TemporaryDirectory() as base_dir:
            state = ServiceState(base_dir)
            state.write_config({"course_id": "1"})
            state.request_timeout()

            event = module.consume_timeout_termination(state)

            self.assertEqual(event["level"], "error")
            self.assertEqual(event["message"], module.TIMEOUT_EVENT_MESSAGE)
            self.assertFalse(state.timeout_requested())
            self.assertEqual(state.read_events()[-1], event)
            self.assertFalse(module.lifecycle_monitoring_state(event["message"]))
            self.assertFalse(module.restored_monitoring_state(
                True, False, state.read_events(), timeout_requested=True
            ))

    def test_login_worker_helper_uses_verified_oauth_result_without_second_check(self):
        module = self._activity_module()

        class FakeApi:
            def __init__(self):
                self.check_calls = 0

            def login_by_wechat_link(self, link):
                self.link = link
                return "微信链接登录成功"

            def check_login(self):
                self.check_calls += 1
                return True

            def export_cookie(self):
                return "sid=verified"

            def get_course_list(self):
                return [{"CourseID": 1}]

        class FakeStore:
            def save_cookie(self, cookie):
                self.cookie = cookie

        api = FakeApi()
        store = FakeStore()
        result = module.complete_wechat_login(lambda: api, store, "oauth-link")

        self.assertEqual(result, (api, [{"CourseID": 1}], "微信链接登录成功", True))
        self.assertEqual(api.check_calls, 0)
        self.assertEqual(store.cookie, "sid=verified")


    def test_event_identity_tracker_survives_rollover_and_pause_with_bounded_memory(self):
        module = self._activity_module()
        tracker = module.EventIdentityTracker(max_seen=400)
        initial = [
            {"timestamp": index, "level": "info", "message": f"event {index}"}
            for index in range(200)
        ]

        self.assertEqual(tracker.unseen(initial), initial)
        rolled = initial[1:] + [
            {"timestamp": 200, "level": "info", "message": "event 200"},
        ]
        self.assertEqual(tracker.unseen(rolled), [rolled[-1]])

        after_pause = [
            {"timestamp": index, "level": "info", "message": f"event {index}"}
            for index in range(201, 401)
        ]
        self.assertEqual(tracker.unseen(after_pause), after_pause)
        self.assertLessEqual(tracker.seen_count, 400)

    def test_event_identity_tracker_processes_physical_duplicates_with_distinct_ids(self):
        tracker = self._activity_module().EventIdentityTracker(max_seen=10)
        common = {"timestamp": 1, "level": "info", "message": "same"}
        events = [
            {**common, "event_id": "event-a"},
            {**common, "event_id": "event-b"},
        ]

        self.assertEqual(tracker.unseen(events), events)
        self.assertEqual(tracker.unseen(events), [])

    def test_event_id_identity_memory_remains_bounded(self):
        tracker = self._activity_module().EventIdentityTracker(max_seen=3)
        events = [
            {"event_id": f"event-{index}", "timestamp": 1,
             "level": "info", "message": "same"}
            for index in range(5)
        ]

        self.assertEqual(tracker.unseen(events), events)
        self.assertEqual(tracker.seen_count, 3)
        self.assertEqual(tracker.unseen([events[-1]]), [])

    def test_legacy_event_identity_uses_timestamp_level_and_message(self):
        tracker = self._activity_module().EventIdentityTracker(max_seen=10)
        events = [
            {"timestamp": 1, "level": "info", "message": "same"},
            {"timestamp": 1, "level": "warn", "message": "same"},
            {"timestamp": 2, "level": "info", "message": "same"},
        ]

        self.assertEqual(tracker.unseen(events), events)
        self.assertEqual(tracker.unseen(events), [])

        duplicate = {"timestamp": 3, "level": "info", "message": "legacy"}
        self.assertEqual(tracker.unseen([duplicate, dict(duplicate)]), [duplicate])

    def test_malformed_overflow_timestamp_uses_current_time_fallback(self):
        event_moment = self._activity_module().event_moment
        fallback = datetime.datetime(2026, 7, 12, 8, 30, 0)

        self.assertEqual(event_moment("1e309", now=lambda: fallback), fallback)

    def test_activity_module_is_desktop_importable_without_kivy(self):
        module = self._activity_module()

        self.assertIsInstance(module.KIVY_AVAILABLE, bool)
        self.assertTrue(callable(module.normalize_countdown))

    def test_activity_source_has_no_password_login_surface(self):
        source = inspect.getsource(self._activity_module()).lower()

        self.assertNotIn("login_by_password", source)
        self.assertNotIn("password=true", source.replace(" ", ""))
        self.assertNotIn("_pwd", source)

    def test_sign_panel_smoke_has_no_password_widgets_when_kivy_is_available(self):
        module = self._activity_module()
        if not module.KIVY_AVAILABLE:
            self.skipTest("Kivy is not installed on this host")

        with tempfile.TemporaryDirectory() as base_dir:
            panel = module.SignPanel(base_dir=base_dir, auto_restore=False)
            visible_copy = " ".join(
                str(getattr(widget, attribute, ""))
                for widget in panel.walk()
                for attribute in ("text", "hint_text")
            ).lower()

        self.assertNotIn("password", visible_copy)
        self.assertNotIn("密码", visible_copy)


class CrashReporterTests(unittest.TestCase):
    def test_crash_report_is_atomic_unicode_and_excludes_sensitive_values(self):
        from android.crash_reporter import write_crash

        with tempfile.TemporaryDirectory() as base_dir:
            sensitive_cookie = "cookie=do-not-record"
            try:
                raise RuntimeError(f"测试崩溃 {sensitive_cookie}")
            except RuntimeError:
                report_path = write_crash(base_dir, *sys.exc_info())

            report = report_path.read_text(encoding="utf-8")
            leftovers = list(Path(base_dir).glob(".crash.log.*.tmp"))

        self.assertIn("测试崩溃", report)
        self.assertIn("Traceback", report)
        self.assertNotIn("do-not-record", report)
        self.assertNotIn("sensitive_cookie", report)
        self.assertEqual(leftovers, [])

    def test_crash_hooks_write_then_delegate_to_original_hooks(self):
        from android.crash_reporter import install_crash_hooks

        delegated = []
        fake_sys = types.SimpleNamespace(
            excepthook=lambda *args: delegated.append(("sys", args))
        )
        fake_threading = types.SimpleNamespace(
            excepthook=lambda args: delegated.append(("thread", args))
        )

        with tempfile.TemporaryDirectory() as base_dir:
            install_crash_hooks(
                base_dir, sys_module=fake_sys, threading_module=fake_threading
            )
            try:
                raise ValueError("线程异常")
            except ValueError:
                exc_info = sys.exc_info()
            fake_sys.excepthook(*exc_info)
            thread_args = types.SimpleNamespace(
                exc_type=exc_info[0],
                exc_value=exc_info[1],
                exc_traceback=exc_info[2],
                thread=None,
            )
            fake_threading.excepthook(thread_args)
            report = (Path(base_dir) / "crash.log").read_text(encoding="utf-8")

        self.assertEqual([kind for kind, _args in delegated], ["sys", "thread"])
        self.assertIn("线程异常", report)

    def test_activity_and_service_wire_crash_reporting_after_private_dir_exists(self):
        activity_source = inspect.getsource(importlib.import_module("android.main"))
        service_module = importlib.import_module("android.service.main")
        service_source = inspect.getsource(service_module)

        self.assertIn("install_crash_hooks(base_dir)", activity_source)
        self.assertIn("install_crash_hooks(state.base_dir)", service_source)
        self.assertIn("write_crash(state.base_dir", service_source)


class DocumentationTests(unittest.TestCase):
    def test_readme_says_notification_denial_prevents_monitor_start(self):
        readme_path = Path(__file__).resolve().parents[2] / "README.md"
        readme = readme_path.read_text(encoding="utf-8")

        self.assertIn("拒绝通知权限后，应用不会启动监听", readme)

if __name__ == "__main__":
    unittest.main()
