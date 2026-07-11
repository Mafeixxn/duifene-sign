import unittest
from urllib.parse import parse_qs, urlparse

from android.api_client import ApiClient


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


if __name__ == "__main__":
    unittest.main()
