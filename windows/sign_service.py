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
        # 回调: (level, message)   level: "info" | "success" | "error" | "warn"
        self.callback = None

    @property
    def is_monitoring(self) -> bool:
        return self._monitoring

    @property
    def class_name(self) -> str:
        return self._class_name

    def start_monitoring(self, course_id: str, class_id: str,
                         class_name: str, countdown: int, root):
        self._course_id = course_id
        self._class_id = class_id
        self._class_name = class_name
        self._countdown = countdown
        self._checked_ids.clear()
        self._heartbeat = 0
        self._monitoring = True
        self._root = root

        # 先进入课程页面（原版 go_sign 的必要步骤）
        if not self.api.enter_course(course_id):
            self._log("warn", "进入课程页面失败，请重新登录")
            self._monitoring = False
            return

        self._log("info", f'开始监听【{class_name}】的签到活动 (CourseID: {course_id}, TClassID: {class_id})')
        self._poll()

    def stop_monitoring(self):
        self._monitoring = False
        if self._after_id:
            try:
                self._root.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self._log("info", "监控已停止")

    def _poll(self):
        if not self._monitoring:
            return

        try:
            self._tick()
        except Exception as e:
            self._log("error", f"轮询异常: {e}")

        if self._monitoring:
            self._after_id = self._root.after(1000, self._poll)

    def _tick(self):
        if not self.api.check_login():
            self._log("warn", "登录状态已失效，请重新登录")
            self.stop_monitoring()
            return

        activity = self.api.check_sign_activity(self._class_id)
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

        # 执行签到
        try:
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

            if "成功" in msg:
                self._log("success", f"签到结果: {msg}")
                self._checked_ids.add(checkin_id)
            else:
                self._log("error", f"签到结果: {msg}")

        except Exception as e:
            self._log("error", f"签到异常: {e}")

    def _log(self, level: str, message: str):
        if self.callback:
            self.callback(level, message)
