import unittest
from urllib.parse import parse_qs, urlparse

from android.api_client import ApiClient
from android.sign_service import SignService


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


if __name__ == "__main__":
    unittest.main()
