import re
import random
import json
import requests
from html.parser import HTMLParser

HOST = "https://www.duifene.com"
UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
    "MicroMessenger/8.0.40(0x1800282a) NetType/WIFI Language/zh_CN"
)


class _AttrParser(HTMLParser):
    """Extract element values and text by id — replaces bs4 for our limited needs."""

    def __init__(self, *target_ids):
        super().__init__()
        self._targets = set(target_ids)
        self._values = {}
        self._texts = {}
        self._cur = None
        self._buf = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        eid = attrs.get("id", "")
        if eid in self._targets:
            self._cur = eid
            self._buf = []
            val = attrs.get("value", "")
            if val:
                self._values[eid] = val

    def handle_data(self, data):
        if self._cur is not None:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if self._cur is not None:
            self._texts[self._cur] = "".join(self._buf).strip()
        self._cur = None
        self._buf = None

    def val(self, eid, default=""):
        return self._values.get(eid, default)

    def text(self, eid, default=""):
        return self._texts.get(eid, default)


class ApiClient:
    def __init__(self, cookie_str: str = ""):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = UA
        if cookie_str:
            self._load_cookie(cookie_str)

    # ─── cookie ───

    def _load_cookie(self, raw: str):
        for pair in raw.split("; "):
            if "=" in pair:
                k, v = pair.split("=", 1)
                self.session.cookies.set(k, v)

    def export_cookie(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self.session.cookies.items())

    # ─── HTTP ───

    def _post(self, url: str, data: str = "", extra_headers: dict = None):
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
        if extra_headers:
            headers.update(extra_headers)
        return self.session.post(url, data=data, headers=headers, timeout=15)

    def _get(self, url: str, extra_headers: dict = None):
        return self.session.get(url, headers=extra_headers, timeout=15)

    @staticmethod
    def _safe_json(r):
        try:
            return r.json()
        except Exception:
            return {}

    @staticmethod
    def _parse_html(html: str, *ids):
        p = _AttrParser(*ids)
        p.feed(html)
        return p

    # ─── 登录 ───

    def login_by_password(self, username: str, password: str) -> str:
        self.session.cookies.clear()
        self._get(HOST)
        data = f"action=loginmb&loginname={username}&password={password}"
        r = self._post(f"{HOST}/AppCode/LoginInfo.ashx", data,
                       {"Referer": f"{HOST}/AppGate.aspx"})
        if r.status_code == 200:
            return self._safe_json(r).get("msgbox", "未知错误")
        raise ConnectionError(f"登录失败，状态码: {r.status_code}")

    def login_by_wechat_link(self, link: str) -> str:
        code_match = re.search(r"(?<=code=)\S{32}", link)
        if not code_match:
            return "链接无效，未找到授权码"
        self.session.cookies.clear()
        r = self._get(f"{HOST}/P.aspx?authtype=1&code={code_match[0]}&state=1")
        if r.status_code == 200:
            return "微信链接登录成功"
        raise ConnectionError(f"微信登录失败，状态码: {r.status_code}")

    def check_login(self) -> bool:
        headers = {
            "Referer": f"{HOST}/_UserCenter/PC/CenterStudent.aspx",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        r = self.session.get(
            f"{HOST}/AppCode/LoginInfo.ashx",
            data="Action=checklogin",
            headers=headers,
            timeout=15,
        )
        return r.status_code == 200 and self._safe_json(r).get("msg") == "1"

    # ─── 课程 ───

    def get_course_list(self) -> list:
        r = self._post(
            f"{HOST}/_UserCenter/CourseInfo.ashx",
            "action=getstudentcourse&classtypeid=2",
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
            p = self._parse_html(r.text, "hidUID")
            return p.val("hidUID")
        return ""

    # ─── 进入课程 ───

    def enter_course(self, course_id: str) -> bool:
        r = self._get(
            f"{HOST}/_UserCenter/MB/Module.aspx?data={course_id}",
            extra_headers={"Referer": f"{HOST}/_UserCenter/MB/index.aspx"},
        )
        return r.status_code == 200 and course_id in r.text

    # ─── 签到活动监控 ───

    def check_sign_activity(self, class_id: str) -> dict | None:
        url = (
            f"{HOST}/_CheckIn/MB/TeachCheckIn.aspx"
            f"?classid={class_id}&temps=0&checktype=1&isrefresh=0"
            f"&timeinterval=0&roomid=0&match="
        )
        r = self._get(url)
        if r.status_code != 200 or "HFChecktype" not in r.text:
            return None

        ids = [
            "HFChecktype", "HFCheckInID", "HFClassID", "HFSeconds",
            "HFCheckCodeKey", "HFRoomLongitude", "HFRoomLatitude",
        ]
        p = self._parse_html(r.text, *ids)

        raw_ids = p.val("HFClassID")
        class_ids = [x.strip() for x in raw_ids.split(",") if x.strip()] if raw_ids else []

        activity = {
            "type": p.val("HFChecktype"),
            "checkin_id": p.val("HFCheckInID"),
            "class_ids": class_ids,
            "seconds": p.val("HFSeconds"),
            "code": p.val("HFCheckCodeKey"),
            "longitude": p.val("HFRoomLongitude"),
            "latitude": p.val("HFRoomLatitude"),
        }
        return activity if activity["type"] else None

    # ─── 签到执行 ───

    def do_code_signin(self, checkin_code: str) -> str:
        sid = self.get_student_id()
        data = f"action=studentcheckin&studentid={sid}&checkincode={checkin_code}"
        r = self._post(
            f"{HOST}/_CheckIn/CheckIn.ashx", data,
            {"Referer": f"{HOST}/_CheckIn/MB/CheckInStudent.aspx?moduleid=16&pasd="},
        )
        if r.status_code == 200:
            return self._safe_json(r).get("msgbox", "未知响应")
        return f"签到码签到失败，状态码: {r.status_code}"

    def do_qrcode_signin(self, state: str) -> str:
        r = self._get(f"{HOST}/_CheckIn/MB/QrCodeCheckOK.aspx?state={state}")
        if r.status_code == 200:
            p = self._parse_html(r.text, "DivOK")
            text = p.text("DivOK")
            if text:
                return "签到成功！" if "签到成功" in text else text
            return "非微信链接登录，二维码无法签到"
        return f"二维码签到失败，状态码: {r.status_code}"

    def do_location_signin(self, longitude: str, latitude: str) -> str:
        lng = round(float(longitude) + random.uniform(-0.000089, 0.000089), 8)
        lat = round(float(latitude) + random.uniform(-0.000089, 0.000089), 8)
        sid = self.get_student_id()
        data = f"action=signin&sid={sid}&longitude={lng}&latitude={lat}"
        r = self._post(
            f"{HOST}/_CheckIn/CheckInRoomHandler.ashx", data,
            {"Referer": f"{HOST}/_CheckIn/MB/CheckInStudent.aspx?moduleid=16&pasd="},
        )
        if r.status_code == 200:
            return self._safe_json(r).get("msgbox", "未知响应")
        return f"定位签到失败，状态码: {r.status_code}"
