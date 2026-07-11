import json
import tempfile
import unittest
from urllib.parse import parse_qs, urlparse

from android.api_client import ApiClient
from android.session_store import SessionStore
from android.sign_service import SignService
from android.service_state import ServiceState


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
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


if __name__ == "__main__":
    unittest.main()
