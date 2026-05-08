import re
import random
import json
import ssl
import urllib.request
import urllib.error
import http.cookiejar
from html.parser import HTMLParser

import certifi

_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

HOST = "https://www.duifene.com"
UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
    "MicroMessenger/8.0.40(0x1800282a) NetType/WIFI Language/zh_CN"
)


class _AttrParser(HTMLParser):
    """Extract element values and text by id — minimal replacement for bs4."""

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
        self._cj = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cj),
            urllib.request.HTTPSHandler(context=_SSL_CONTEXT),
        )
        self._opener.addheaders = [("User-Agent", UA)]
        if cookie_str:
            self._load_cookie(cookie_str)

    # ─── cookie ───

    def _load_cookie(self, raw: str):
        for pair in raw.split("; "):
            if "=" in pair:
                k, v = pair.split("=", 1)
                ck = http.cookiejar.Cookie(
                    version=0, name=k, value=v,
                    port=None, port_specified=False,
                    domain=".duifene.com", domain_specified=True,
                    domain_initial_dot=True,
                    path="/", path_specified=True,
                    secure=False, expires=None, discard=False,
                    comment=None, comment_url=None, rest={}, rfc2109=False,
                )
                self._cj.set_cookie(ck)

    def export_cookie(self) -> str:
        return "; ".join(f"{c.name}={c.value}" for c in self._cj)

    # ─── HTTP ───

    def _send(self, url, data=None, extra_headers=None):
        headers = {}
        if extra_headers:
            headers.update(extra_headers)
        body = data.encode("utf-8") if isinstance(data, str) else data
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            resp = self._opener.open(req, timeout=15)
        except urllib.error.HTTPError as e:
            resp = e
        return resp

    def _post(self, url, data="", extra_headers=None):
        h = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
        if extra_headers:
            h.update(extra_headers)
        return self._send(url, data=data, extra_headers=h)

    def _get(self, url, extra_headers=None):
        return self._send(url, extra_headers=extra_headers)

    def _read(self, resp):
        charset = "utf-8"
        ct = resp.headers.get("Content-Type", "")
        if "charset=" in ct:
            charset = ct.split("charset=")[-1].split(";")[0].strip()
        return resp.read().decode(charset, errors="replace")

    @staticmethod
    def _safe_json(resp):
        try:
            return json.loads(resp.read())
        except Exception:
            return {}

    # ─── 登录 ───

    def login_by_password(self, username: str, password: str) -> str:
        self._cj.clear()
        self._get(HOST)
        data = f"action=loginmb&loginname={username}&password={password}"
        r = self._post(f"{HOST}/AppCode/LoginInfo.ashx", data,
                       {"Referer": f"{HOST}/AppGate.aspx"})
        if r.getcode() == 200:
            return self._safe_json(r).get("msgbox", "未知错误")
        raise ConnectionError(f"登录失败，状态码: {r.getcode()}")

    def login_by_wechat_link(self, link: str) -> str:
        code_match = re.search(r"(?<=code=)\S{32}", link)
        if not code_match:
            return "链接无效，未找到授权码"
        self._cj.clear()
        r = self._get(f"{HOST}/P.aspx?authtype=1&code={code_match[0]}&state=1")
        if r.getcode() == 200:
            return "微信链接登录成功"
        raise ConnectionError(f"微信登录失败，状态码: {r.getcode()}")

    def check_login(self) -> bool:
        headers = {
            "Referer": f"{HOST}/_UserCenter/PC/CenterStudent.aspx",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        r = self._post(f"{HOST}/AppCode/LoginInfo.ashx", "Action=checklogin", headers)
        return r.getcode() == 200 and self._safe_json(r).get("msg") == "1"

    # ─── 课程 ───

    def get_course_list(self) -> list:
        r = self._post(
            f"{HOST}/_UserCenter/CourseInfo.ashx",
            "action=getstudentcourse&classtypeid=2",
            {"Referer": f"{HOST}/_UserCenter/PC/CenterStudent.aspx"},
        )
        if r.getcode() == 200:
            data = self._safe_json(r)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "msgbox" in data:
                raise PermissionError(data["msgbox"])
        return []

    # ─── 用户 ───

    def get_student_id(self) -> str:
        r = self._get(f"{HOST}/_UserCenter/MB/index.aspx")
        if r.getcode() == 200:
            p = _AttrParser("hidUID")
            p.feed(self._read(r))
            return p.val("hidUID")
        return ""

    # ─── 进入课程 ───

    def enter_course(self, course_id: str) -> bool:
        r = self._get(
            f"{HOST}/_UserCenter/MB/Module.aspx?data={course_id}",
            extra_headers={"Referer": f"{HOST}/_UserCenter/MB/index.aspx"},
        )
        return r.getcode() == 200 and course_id in self._read(r)

    # ─── 签到活动监控 ───

    def check_sign_activity(self, class_id: str) -> dict | None:
        url = (
            f"{HOST}/_CheckIn/MB/TeachCheckIn.aspx"
            f"?classid={class_id}&temps=0&checktype=1&isrefresh=0"
            f"&timeinterval=0&roomid=0&match="
        )
        r = self._get(url)
        body = self._read(r)
        if r.getcode() != 200 or "HFChecktype" not in body:
            return None

        ids = [
            "HFChecktype", "HFCheckInID", "HFClassID", "HFSeconds",
            "HFCheckCodeKey", "HFRoomLongitude", "HFRoomLatitude",
        ]
        p = _AttrParser(*ids)
        p.feed(body)

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
        if r.getcode() == 200:
            return self._safe_json(r).get("msgbox", "未知响应")
        return f"签到码签到失败，状态码: {r.getcode()}"

    def do_qrcode_signin(self, state: str) -> str:
        r = self._get(f"{HOST}/_CheckIn/MB/QrCodeCheckOK.aspx?state={state}")
        if r.getcode() == 200:
            p = _AttrParser("DivOK")
            p.feed(self._read(r))
            text = p.text("DivOK")
            if text:
                return "签到成功！" if "签到成功" in text else text
            return "非微信链接登录，二维码无法签到"
        return f"二维码签到失败，状态码: {r.getcode()}"

    def do_location_signin(self, longitude: str, latitude: str) -> str:
        lng = round(float(longitude) + random.uniform(-0.000089, 0.000089), 8)
        lat = round(float(latitude) + random.uniform(-0.000089, 0.000089), 8)
        sid = self.get_student_id()
        data = f"action=signin&sid={sid}&longitude={lng}&latitude={lat}"
        r = self._post(
            f"{HOST}/_CheckIn/CheckInRoomHandler.ashx", data,
            {"Referer": f"{HOST}/_CheckIn/MB/CheckInStudent.aspx?moduleid=16&pasd="},
        )
        if r.getcode() == 200:
            return self._safe_json(r).get("msgbox", "未知响应")
        return f"定位签到失败，状态码: {r.getcode()}"
