import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api_client import ApiClient
from app import App
from config_manager import ConfigManager
from sign_service import SignService


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.headers = {}
        self.cookies = {}
        self.posts = []
        self.gets = []

    def post(self, url, data="", headers=None, timeout=None):
        self.posts.append((url, data, headers, timeout))
        return FakeResponse(payload={"msgbox": "登录成功", "msg": "1"})

    def get(self, url, headers=None, timeout=None):
        self.gets.append((url, headers, timeout))
        return FakeResponse(text="<input id='hidUID' value='stu1'>")


class ConfigManagerTests(unittest.TestCase):
    def test_repairs_existing_empty_config_before_saving(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "duifenyi.ini"
            path.write_text("", encoding="utf-8")

            config = ConfigManager(str(path))
            config.save_cookie("a=b")
            config.save_countdown(7)

            self.assertEqual(config.load_cookie(), {"a": "b"})
            self.assertEqual(config.get_countdown(), 7)


class ApiClientTests(unittest.TestCase):
    def _config(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return ConfigManager(str(Path(tmp.name) / "duifenyi.ini"))

    def test_password_login_uses_structured_form_data(self):
        config = self._config()
        api = ApiClient(config)
        fake = FakeSession()
        api.session = fake

        api.login_by_password("u&role=x", "p=1&z=2")

        _, data, _, _ = fake.posts[-1]
        self.assertEqual(
            data,
            {
                "action": "loginmb",
                "loginname": "u&role=x",
                "password": "p=1&z=2",
            },
        )

    def test_wechat_login_rejects_malformed_code_parameter(self):
        config = self._config()
        api = ApiClient(config)

        link = "https://example.test/?code=1234567890123456789012345678901&state=1"

        self.assertIn("链接无效", api.login_by_wechat_link(link))

    def test_wechat_login_requires_verified_session(self):
        config = self._config()
        api = ApiClient(config)

        with patch.object(api, "_get", return_value=FakeResponse(status_code=200)), \
                patch.object(api, "check_login", return_value=False):
            msg = api.login_by_wechat_link(
                "https://example.test/?code=12345678901234567890123456789012&state=1"
            )

        self.assertIn("登录失败", msg)


class SignServiceTests(unittest.TestCase):
    def test_malformed_activity_is_reported_without_crashing_poll_loop(self):
        class FakeApi:
            def check_login(self):
                return True

            def check_sign_activity(self, class_id):
                return {
                    "type": "1",
                    "checkin_id": "id1",
                    "class_ids": ["c1"],
                    "seconds": "",
                    "code": "1234",
                    "longitude": "",
                    "latitude": "",
                }

        service = SignService(FakeApi())
        service._monitoring = True
        service._class_id = "c1"
        service._countdown = 10
        service._start_time = 10**20
        logs = []
        service.callback = lambda level, message: logs.append((level, message))

        service._tick_worker()

        self.assertTrue(any(level == "warn" and "活动数据不完整" in msg for level, msg in logs))
        self.assertFalse(any("轮询异常" in msg for _, msg in logs))


class AppHelperTests(unittest.TestCase):
    def test_countdown_must_be_non_negative_integer(self):
        self.assertEqual(App._parse_countdown("0"), 0)
        self.assertEqual(App._parse_countdown("25"), 25)

        for value in ("", "abc", "-1"):
            with self.assertRaises(ValueError):
                App._parse_countdown(value)

    def test_duplicate_course_names_get_distinct_labels(self):
        courses = [
            {"CourseName": "英语", "CourseID": "c1", "TClassID": "t1"},
            {"CourseName": "英语", "CourseID": "c2", "TClassID": "t2"},
        ]

        labels = App._build_course_labels(courses)

        self.assertEqual(labels, ["英语 (t1)", "英语 (t2)"])


if __name__ == "__main__":
    unittest.main()
