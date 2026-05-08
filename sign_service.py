import threading
import time
from datetime import datetime
from api_client import ApiClient


class SignService:
    def __init__(self, api: ApiClient):
        self.api = api
        self._running = False
        self._thread = None
        self._course_id = ""
        self._class_id = ""
        self._class_name = ""
        self._countdown = 10
        self._checked_ids: set = set()
        self._heartbeat = 0
        self.on_log = None          # callback(level, message)
        self.on_status = None       # callback(running: bool)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def class_name(self) -> str:
        return self._class_name

    def start(self, course_id: str, class_id: str,
              class_name: str, countdown: int = 10):
        self._course_id = course_id
        self._class_id = class_id
        self._class_name = class_name
        self._countdown = countdown
        self._checked_ids.clear()
        self._heartbeat = 0

        if not self.api.enter_course(course_id):
            self._emit_log("warn", "进入课程页面失败，请重新登录")
            return

        self._running = True
        self._emit_log("info",
            f"开始监听【{class_name}】\nCourseID: {course_id}\nTClassID: {class_id}")
        if self.on_status:
            self.on_status(True)

        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._emit_log("info", "监控已停止")
        if self.on_status:
            self.on_status(False)

    def _loop(self):
        while self._running:
            try:
                self._tick()
            except Exception as e:
                self._emit_log("error", f"轮询异常: {e}")
            time.sleep(1)

    def _tick(self):
        if not self.api.check_login():
            self._emit_log("warn", "登录状态已失效，请重新登录")
            self._running = False
            if self.on_status:
                self.on_status(False)
            return

        activity = self.api.check_sign_activity(self._class_id)
        if activity is None:
            self._heartbeat += 1
            if self._heartbeat % 30 == 0:
                self._emit_log("info",
                    f"[{datetime.now().strftime('%H:%M:%S')}] 监控中...")
            return
        self._heartbeat = 0

        checkin_id = activity["checkin_id"]
        class_ids = activity["class_ids"]

        if self._class_id not in class_ids:
            return

        if checkin_id in self._checked_ids:
            return

        check_type = activity["type"]
        seconds = int(activity["seconds"])
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if seconds > self._countdown:
            tname = {"1": "签到码", "2": "二维码", "3": "定位"}.get(check_type, "未知")
            self._emit_log("info",
                f"[{now}] {tname}签到 倒计时{seconds}秒，等待中...")
            return

        self._emit_log("info",
            f"\n{'='*30}\n[{now}] 检测到签到 ID:{checkin_id}")

        if check_type == "1":
            code = activity["code"]
            self._emit_log("info", f"类型: 签到码 ({code})")
            msg = self.api.do_code_signin(code)
        elif check_type == "2":
            self._emit_log("info", "类型: 二维码")
            msg = self.api.do_qrcode_signin(checkin_id)
        elif check_type == "3":
            lng, lat = activity["longitude"], activity["latitude"]
            self._emit_log("info", f"类型: 定位 ({lng}, {lat})")
            msg = self.api.do_location_signin(lng, lat)
        else:
            return

        if "成功" in msg:
            self._emit_log("success", f"✅ {msg}")
            self._checked_ids.add(checkin_id)
        else:
            self._emit_log("error", f"❌ {msg}")
        self._emit_log("info", f"{'='*30}\n")

    def _emit_log(self, level: str, message: str):
        if self.on_log:
            self.on_log(level, message)
