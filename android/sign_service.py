import time
from collections.abc import Mapping


class SignService:
    """Platform-neutral check-in polling engine.

    Android-specific code owns the foreground-service lifecycle and supplies an
    Event-compatible stop object to ``run``.
    """

    COURSE_REFRESH_SECONDS = 10 * 60
    NORMAL_POLL_DELAY = 1
    NETWORK_ERROR_DELAY = 5

    def __init__(self, api, on_log=None, on_status=None):
        self.api = api
        self.on_log = on_log
        self.on_status = on_status
        self._running = False
        self._course_id = ""
        self._class_id = ""
        self._class_name = ""
        self._countdown = 10
        self._checked_ids = set()
        self._last_course_refresh = None
        self.next_poll_delay = self.NORMAL_POLL_DELAY

    @property
    def is_running(self):
        return self._running

    @property
    def class_name(self):
        return self._class_name

    def configure(self, course_id, class_id, class_name, countdown=10):
        self._course_id = str(course_id)
        self._class_id = str(class_id)
        self._class_name = str(class_name)
        try:
            self._countdown = int(countdown)
        except (TypeError, ValueError):
            self._countdown = 10
        self._checked_ids.clear()
        self._last_course_refresh = None
        self.next_poll_delay = self.NORMAL_POLL_DELAY

    def poll_once(self):
        """Poll once and return whether the caller should keep running."""
        self.next_poll_delay = self.NORMAL_POLL_DELAY
        try:
            if not self.api.check_login():
                self._emit_log("warn", "Login expired; polling stopped.")
                self._set_running(False)
                return False

            self._refresh_course_if_due()
            self._handle_activity(self.api.check_sign_activity(self._class_id))
        except Exception as exc:
            self.next_poll_delay = self.NETWORK_ERROR_DELAY
            self._emit_log("error", f"Polling request failed: {exc}")
        return True

    def run(self, stop_event):
        """Poll until stopped, using Event.wait so shutdown interrupts sleep."""
        self._set_running(True)
        try:
            while not stop_event.is_set() and self._running:
                if not self.poll_once():
                    break
                stop_event.wait(self.next_poll_delay)
        finally:
            self._set_running(False)

    def _refresh_course_if_due(self):
        now = time.monotonic()
        if (
            self._last_course_refresh is not None
            and now - self._last_course_refresh < self.COURSE_REFRESH_SECONDS
        ):
            return

        entered = self.api.enter_course(self._course_id)
        if not entered:
            self._emit_log("warn", "Unable to refresh course context.")
            return
        self._last_course_refresh = now

    def _handle_activity(self, activity):
        if not isinstance(activity, Mapping):
            return

        checkin_id = activity.get("checkin_id")
        class_ids = activity.get("class_ids")
        if checkin_id is None or not isinstance(class_ids, (list, tuple, set)):
            return

        checkin_id = str(checkin_id)
        if not checkin_id or self._class_id not in {str(value) for value in class_ids}:
            return
        if checkin_id in self._checked_ids:
            return

        try:
            seconds = int(activity.get("seconds"))
        except (TypeError, ValueError):
            self._emit_log("warn", "Ignored activity with invalid countdown.")
            return

        check_type = str(activity.get("type", ""))
        type_name = {
            "1": "签到码",
            "2": "二维码",
            "3": "定位",
        }.get(check_type)
        if type_name is None:
            return
        if seconds > self._countdown:
            self._emit_log(
                "info",
                f"检测到{type_name}签到，剩余 {seconds} 秒，等待中。",
            )
            return

        self._emit_log(
            "info",
            f"{type_name}签到剩余 {seconds} 秒，开始签到。",
        )
        if check_type == "1":
            code = activity.get("code")
            if code is None:
                return
            message = self.api.do_code_signin(str(code))
        elif check_type == "2":
            message = self.api.do_qrcode_signin(checkin_id)
        elif check_type == "3":
            longitude = activity.get("longitude")
            latitude = activity.get("latitude")
            if longitude is None or latitude is None:
                return
            message = self.api.do_location_signin(longitude, latitude)
        else:
            return

        if "成功" in str(message):
            self._checked_ids.add(checkin_id)
            self._emit_log("success", str(message))
        else:
            self._emit_log("error", str(message))

    def _set_running(self, running):
        if self._running == running:
            return
        self._running = running
        self._emit_status(running)

    def _emit_log(self, level, message):
        if self.on_log is None:
            return
        try:
            self.on_log(level, message)
        except Exception:
            pass

    def _emit_status(self, running):
        if self.on_status is None:
            return
        try:
            self.on_status(running)
        except Exception:
            pass
