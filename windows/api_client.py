import random
import re
from urllib.parse import parse_qs, urlencode, urlparse

import requests
try:
    import lxml  # noqa: F401
    BS_PARSER = "lxml"
except ImportError:
    BS_PARSER = "html.parser"
from bs4 import BeautifulSoup
from config_manager import ConfigManager

HOST = "https://www.duifene.com"
UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
    "MicroMessenger/8.0.40(0x1800282a) NetType/WIFI Language/zh_CN"
)


class ApiClient:
    def __init__(self, config: ConfigManager):
        self.config = config
        self.session = requests.Session()
        self.session.headers["User-Agent"] = UA
        self.session.timeout = 15

        saved = config.load_cookie()
        for key, value in saved.items():
            self.session.cookies.set(key, value)

    def _post(self, url: str, data=None, extra_headers: dict = None) -> requests.Response:
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        if extra_headers:
            headers.update(extra_headers)
        return self.session.post(url, data=data or "", headers=headers, timeout=15)

    def _get(self, url: str, extra_headers: dict = None) -> requests.Response:
        return self.session.get(url, headers=extra_headers, timeout=15)

    @staticmethod
    def _safe_json(r: requests.Response) -> dict:
        try:
            return r.json()
        except Exception:
            return {}

    # ─── 登录 ───

    def login_by_password(self, username: str, password: str) -> str:
        self.session.cookies.clear()
        self._get(HOST)
        data = {
            "action": "loginmb",
            "loginname": username,
            "password": password,
        }
        headers = {"Referer": f"{HOST}/AppGate.aspx"}
        r = self._post(f"{HOST}/AppCode/LoginInfo.ashx", data, headers)
        if r.status_code == 200:
            resp = self._safe_json(r)
            msg = resp.get("msgbox", "未知错误")
            if msg == "登录成功":
                self._persist_cookie()
            return msg
        raise ConnectionError(f"登录请求失败，状态码: {r.status_code}")

    def login_by_wechat_link(self, link: str) -> str:
        code = self._extract_wechat_code(link)
        if not code:
            return "链接无效，未找到授权码"

        self.session.cookies.clear()
        query = urlencode({"authtype": "1", "code": code, "state": "1"})
        r = self._get(f"{HOST}/P.aspx?{query}")
        if r.status_code == 200:
            if self.check_login():
                self._persist_cookie()
                return "微信链接登录成功"
            return "微信链接登录失败，请确认链接未过期"
        raise ConnectionError(f"微信登录请求失败，状态码: {r.status_code}")

    @staticmethod
    def _extract_wechat_code(link: str) -> str:
        try:
            values = parse_qs(urlparse(link).query).get("code", [])
        except Exception:
            return ""
        if len(values) != 1:
            return ""
        code = values[0].strip()
        return code if re.fullmatch(r"[A-Za-z0-9_-]{32}", code) else ""

    # ─── 登录状态 ───

    def check_login(self) -> bool:
        headers = {
            "Referer": f"{HOST}/_UserCenter/PC/CenterStudent.aspx",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        r = self._post(
            f"{HOST}/AppCode/LoginInfo.ashx",
            {"Action": "checklogin"},
            headers,
        )
        return r.status_code == 200 and self._safe_json(r).get("msg") == "1"

    # ─── 课程 ───

    def get_course_list(self) -> list[dict]:
        r = self._post(
            f"{HOST}/_UserCenter/CourseInfo.ashx",
            {"action": "getstudentcourse", "classtypeid": "2"},
            {"Referer": f"{HOST}/_UserCenter/PC/CenterStudent.aspx"},
        )
        if r.status_code == 200:
            data = self._safe_json(r)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "msgbox" in data:
                raise PermissionError(data["msgbox"])
        return []

    # ─── 用户 ───

    def get_student_id(self) -> str:
        r = self._get(f"{HOST}/_UserCenter/MB/index.aspx")
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, BS_PARSER)
            el = soup.find(id="hidUID")
            if el:
                return el.get("value", "")
        return ""

    # ─── 进入课程 ───

    def enter_course(self, course_id: str) -> bool:
        headers = {"Referer": f"{HOST}/_UserCenter/MB/index.aspx"}
        r = self._get(f"{HOST}/_UserCenter/MB/Module.aspx?{urlencode({'data': course_id})}",
                       extra_headers=headers)
        return r.status_code == 200 and course_id in r.text

    # ─── 签到活动监控 ───

    def check_sign_activity(self, class_id: str) -> dict | None:
        query = urlencode({
            "classid": class_id,
            "temps": "0",
            "checktype": "1",
            "isrefresh": "0",
            "timeinterval": "0",
            "roomid": "0",
            "match": "",
        })
        url = f"{HOST}/_CheckIn/MB/TeachCheckIn.aspx?{query}"
        r = self._get(url)
        if r.status_code != 200:
            return None

        text = r.text
        if "HFChecktype" not in text:
            # 有签到活动时才会出现 HFChecktype，没有活动时这里返回 None 是正常的
            return None

        soup = BeautifulSoup(text, BS_PARSER)

        def val(elm_id: str) -> str:
            el = soup.find(id=elm_id)
            return el.get("value", "") if el else ""

        raw_ids = val("HFClassID")
        class_ids = [x.strip() for x in raw_ids.split(",") if x.strip()] if raw_ids else []

        activity = {
            "type": val("HFChecktype"),       # 1=数字 2=二维码 3=定位
            "checkin_id": val("HFCheckInID"),
            "class_ids": class_ids,
            "seconds": val("HFSeconds"),
            "code": val("HFCheckCodeKey"),
            "longitude": val("HFRoomLongitude"),
            "latitude": val("HFRoomLatitude"),
        }
        return activity if activity["type"] else None

    # ─── 签到执行 ───

    def do_code_signin(self, checkin_code: str) -> str:
        sid = self.get_student_id()
        data = {
            "action": "studentcheckin",
            "studentid": sid,
            "checkincode": checkin_code,
        }
        headers = {"Referer": f"{HOST}/_CheckIn/MB/CheckInStudent.aspx?moduleid=16&pasd="}
        r = self._post(f"{HOST}/_CheckIn/CheckIn.ashx", data, headers)
        if r.status_code == 200:
            return self._safe_json(r).get("msgbox", "未知响应")
        return f"签到码签到失败，状态码: {r.status_code}"

    def do_qrcode_signin(self, state: str) -> str:
        r = self._get(f"{HOST}/_CheckIn/MB/QrCodeCheckOK.aspx?{urlencode({'state': state})}")
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, BS_PARSER)
            el = soup.find(id="DivOK")
            if el:
                text = el.get_text()
                if "签到成功" in text:
                    return "签到成功！"
                return text
            return "非微信链接登录，二维码无法签到"
        return f"二维码签到失败，状态码: {r.status_code}"

    def do_location_signin(self, longitude: str, latitude: str) -> str:
        lng = round(float(longitude) + random.uniform(-0.000089, 0.000089), 8)
        lat = round(float(latitude) + random.uniform(-0.000089, 0.000089), 8)
        sid = self.get_student_id()
        data = {
            "action": "signin",
            "sid": sid,
            "longitude": lng,
            "latitude": lat,
        }
        headers = {"Referer": f"{HOST}/_CheckIn/MB/CheckInStudent.aspx?moduleid=16&pasd="}
        r = self._post(f"{HOST}/_CheckIn/CheckInRoomHandler.ashx", data, headers)
        if r.status_code == 200:
            return self._safe_json(r).get("msgbox", "未知响应")
        return f"定位签到失败，状态码: {r.status_code}"

    # ─── 辅助 ───

    def _persist_cookie(self):
        cookie_str = "; ".join(
            f"{k}={v}" for k, v in self.session.cookies.items()
        )
        if cookie_str:
            self.config.save_cookie(cookie_str)

    def clear_session(self):
        self.session.cookies.clear()
        self.config.clear_cookie()
