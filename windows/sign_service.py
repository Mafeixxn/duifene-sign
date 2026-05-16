import threading
from datetime import datetime
from api_client import ApiClient


class SignService:
    def __init__(self, api: ApiClient):
        self.api = api
        self._monitoring = False
        self._after_id: str | None = None
        self._class_id = ""
        self._class_name = ""
        self._countdown = 10
        self._checked_ids: set[str] = set()
        self._request_in_flight = False
        self._post_ui = None
        # 回调: (level, message)   level: "info" | "success" | "error" | "warn"
        self.callback = None
        self.state_callback = None

    @property
    def is_monitoring(self) -> bool:
        return self._monitoring

    @property
    def class_name(self) -> str:
        return self._class_name

    def start_monitoring(self, course_id: str, class_id: str,
                         class_name: str, countdown: int, root,
                         post_ui=None):
        self._course_id = course_id
        self._class_id = class_id
        self._class_name = class_name
        self._countdown = countdown
        self._checked_ids.clear()
        self._heartbeat = 0
        self._request_in_flight = False
        self._monitoring = True
        self._root = root
        self._post_ui = post_ui or self._after_ui

        threading.Thread(target=self._enter_course_worker, daemon=True).start()

    def _enter_course_worker(self):
        ok = False
        error = None
        try:
            ok = self.api.enter_course(self._course_id)
        except Exception as e:
            error = e

        if not self._monitoring:
            return

        if error:
            self._log("error", f"进入课程页面异常: {error}")
            self._monitoring = False
            self._emit_state("failed")
            return

        if not ok:
            self._log("warn", "进入课程页面失败，请重新登录")
            self._monitoring = False
            self._emit_state("failed")
            return

        self._log("info", f'开始监听【{self._class_name}】的签到活动 (CourseID: {self._course_id}, TClassID: {self._class_id})')
        self._emit_state("started")
        self._post_ui(self._poll)

    def stop_monitoring(self):
        was_monitoring = self._monitoring
        self._monitoring = False
        if self._after_id:
            try:
                self._root.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        if was_monitoring:
            self._log("info", "监控已停止")
        self._emit_state("stopped")

    def _poll(self):
        if not self._monitoring or self._request_in_flight:
            return
        self._request_in_flight = True
        threading.Thread(target=self._tick_worker, daemon=True).start()

    def _tick_worker(self):
        try:
            self._tick()
        except Exception as e:
            self._log("error", f"轮询异常: {e}")
        finally:
            if self._post_ui:
                self._post_ui(self._finish_tick)

    def _finish_tick(self):
        self._request_in_flight = False
        if self._monitoring:
            self._after_id = self._root.after(1000, self._poll)

    def _tick(self):
        if not self._monitoring:
            return

        if not self.api.check_login():
            if self._monitoring:
                self._log("warn", "登录状态已失效，请重新登录")
                self._post_ui(self.stop_monitoring)
            return

        if not self._monitoring:
            return

        activity = self.api.check_sign_activity(self._class_id)
        if not self._monitoring:
            return

        if activity is None:
            self._heartbeat += 1
            if self._heartbeat % 30 == 0:
                self._log("info", "监控中... (未检测到签到活动)")
            return
        self._heartbeat = 0

        checkin_id = activity["checkin_id"]
        class_ids = activity["class_ids"]

        if self._class_id not in class_ids:
            type_names = {"1": "签到码", "2": "二维码", "3": "定位"}
            tname = type_names.get(activity["type"], "未知")
            self._log("info", f"检测到{tname}签到，但不是本班 (本班ID:{self._class_id}, 活动班级:{','.join(class_ids)})")
            return

        if checkin_id in self._checked_ids:
            return

        check_type = activity["type"]
        seconds = int(activity["seconds"])
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if seconds > self._countdown:
            type_names = {"1": "签到码", "2": "二维码", "3": "定位"}
            tname = type_names.get(check_type, "未知")
            self._log("info", f"[{now}] {tname}签到 倒计时{seconds}秒，等待中...")
            return

        try:
            if not self._monitoring:
                return
            if check_type == "1":
                code = activity["code"]
                self._log("info", f"\n{now} 签到ID:{checkin_id} 开始签到码签到\t码:{code}")
                msg = self.api.do_code_signin(code)
            elif check_type == "2":
                self._log("info", f"\n{now} 签到ID:{checkin_id} 开始二维码签到")
                msg = self.api.do_qrcode_signin(checkin_id)
            elif check_type == "3":
                lng = activity["longitude"]
                lat = activity["latitude"]
                self._log("info", f"\n{now} 签到ID:{checkin_id} 开始定位签到")
                msg = self.api.do_location_signin(lng, lat)
            else:
                return

            if not self._monitoring:
                return
            if "成功" in msg:
                self._log("success", f"签到结果: {msg}")
                self._checked_ids.add(checkin_id)
            else:
                self._log("error", f"签到结果: {msg}")

        except Exception as e:
            self._log("error", f"签到异常: {e}")

    def _after_ui(self, func, *args, **kwargs):
        self._root.after(0, lambda: func(*args, **kwargs))

    def _log(self, level: str, message: str):
        if self.callback and self._post_ui:
            self._post_ui(self.callback, level, message)
        elif self.callback:
            self.callback(level, message)

    def _emit_state(self, state: str):
        if self.state_callback and self._post_ui:
            self._post_ui(self.state_callback, state)
        elif self.state_callback:
            self.state_callback(state)
