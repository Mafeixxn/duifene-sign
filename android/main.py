"""One-screen Kivy activity for OAuth login and foreground monitoring."""

import datetime
import json
import threading
import time
from collections import Counter, deque
from uuid import uuid4

try:
    from .api_client import ApiClient
    from .crash_reporter import install_crash_hooks
    from .service_state import ServiceState
    from .session_store import SessionStore
except ImportError:  # python-for-android runs this file as a top-level module.
    from api_client import ApiClient
    from crash_reporter import install_crash_hooks
    from service_state import ServiceState
    from session_store import SessionStore


DEFAULT_COUNTDOWN = 10
SERVICE_CLASS = "org.example.duifene_sign.ServiceMonitor"
WECHAT_LOGIN_SUCCESS = "微信链接登录成功"
TIMEOUT_EVENT_MESSAGE = "监控已停止：Android 前台服务达到系统时限。"


def normalize_countdown(value, default=DEFAULT_COUNTDOWN):
    """Return an integer countdown, falling back and clamping below zero."""
    try:
        countdown = int(value)
    except (TypeError, ValueError):
        try:
            countdown = int(default)
        except (TypeError, ValueError):
            countdown = DEFAULT_COUNTDOWN
    return max(0, countdown)


def course_labels(courses):
    """Return stable unique labels while preserving the incoming course order."""
    names = [str(course.get("CourseName") or "Unnamed course") for course in courses]
    reserved = set(names)
    seen = Counter()
    used = set()
    labels = []
    for name in names:
        seen[name] += 1
        if seen[name] == 1 and name not in used:
            label = name
        else:
            suffix = max(2, seen[name])
            label = f"{name} ({suffix})"
            while label in used or label in reserved:
                suffix += 1
                label = f"{name} ({suffix})"
        used.add(label)
        labels.append(label)
    return labels


def service_argument_json(cookie, course, countdown=DEFAULT_COUNTDOWN):
    """Serialize the exact foreground-service monitor configuration."""
    config = {
        "cookie": str(cookie),
        "course_id": str(course["CourseID"]),
        "class_id": str(course["TClassID"]),
        "class_name": str(course["CourseName"]),
        "countdown": normalize_countdown(countdown),
    }
    return json.dumps(config, ensure_ascii=False, separators=(",", ":"))


def start_daemon_worker(target, *args, name="activity-worker", **kwargs):
    """Start background work without allowing it to keep the activity alive."""
    worker = threading.Thread(
        target=target,
        args=args,
        kwargs=kwargs,
        name=name,
        daemon=True,
    )
    worker.start()
    return worker


def complete_wechat_login(api_factory, session_store, link):
    """Complete one OAuth login whose API method already verifies the session."""
    api = api_factory()
    message = str(api.login_by_wechat_link(link))
    if message != WECHAT_LOGIN_SUCCESS:
        return None, [], message, False
    session_store.save_cookie(api.export_cookie())
    courses = api.get_course_list()
    return api, courses, message, True


def vertical_stack_height(child_heights, spacing=7, padding=10):
    """Return a fixed vertical layout height without clipping its children."""
    heights = list(child_heights)
    gaps = max(0, len(heights) - 1)
    return sum(heights) + gaps * spacing + padding * 2


def lifecycle_monitoring_state(message):
    """Return the monitoring state represented by an explicit lifecycle message."""
    message = str(message)
    if message == "Monitoring started.":
        return True
    if message in {
        "Monitoring stopped.",
        "Monitoring stopped before service startup.",
        "Monitoring configuration is unavailable.",
        TIMEOUT_EVENT_MESSAGE,
    } or message.startswith("Monitoring service failed:"):
        return False
    return None


def apply_lifecycle_events(monitoring, events):
    """Apply lifecycle events in emission order and return the resulting state."""
    monitoring = bool(monitoring)
    for event in events:
        state = lifecycle_monitoring_state(event.get("message", ""))
        if state is not None:
            monitoring = state
    return monitoring


def restored_monitoring_state(
    config_available, stop_requested, events, timeout_requested=False
):
    """Infer service state without allowing stale events to revive invalid config."""
    monitoring = (
        bool(config_available)
        and not bool(stop_requested)
        and not bool(timeout_requested)
    )
    if not monitoring:
        return False
    return apply_lifecycle_events(monitoring, events)


def consume_timeout_termination(state):
    """Consume Java's timeout marker and persist one user-visible terminal event."""
    if not state.consume_timeout():
        return None
    event = {
        "event_id": uuid4().hex,
        "level": "error",
        "message": TIMEOUT_EVENT_MESSAGE,
        "timestamp": int(time.time()),
    }
    state.append_event(event)
    return event


class EventIdentityTracker:
    """Deduplicate retained service events by ID with legacy tuple fallback."""

    def __init__(self, max_seen=400):
        self.max_seen = max(1, int(max_seen))
        self._order = deque()
        self._seen = set()

    @staticmethod
    def identity(event):
        if "event_id" in event:
            return "event_id", str(event["event_id"])
        return (
            "legacy",
            *(str(event.get(field, "")) for field in ("timestamp", "level", "message")),
        )

    @property
    def seen_count(self):
        return len(self._seen)

    def unseen(self, events):
        unseen_events = []
        for event in events:
            identity = self.identity(event)
            if identity in self._seen:
                continue
            self._seen.add(identity)
            self._order.append(identity)
            unseen_events.append(event)
            while len(self._order) > self.max_seen:
                self._seen.remove(self._order.popleft())
        return unseen_events


def event_moment(timestamp, now=datetime.datetime.now):
    """Convert a service timestamp, falling back safely for malformed values."""
    if timestamp is not None:
        try:
            return datetime.datetime.fromtimestamp(float(timestamp))
        except (TypeError, ValueError, OverflowError, OSError):
            pass
    return now()


try:
    from kivy.app import App
    from kivy.clock import Clock, mainthread
    from kivy.graphics import Color, RoundedRectangle
    from kivy.metrics import dp
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.label import Label
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.spinner import Spinner
    from kivy.uix.textinput import TextInput
    from kivy.utils import escape_markup, platform

    KIVY_AVAILABLE = True
except ModuleNotFoundError as exc:
    if not (exc.name or "").startswith("kivy"):
        raise
    KIVY_AVAILABLE = False


class AndroidServiceBridge:
    """Control p4a's generated service class from the visible activity."""

    REQUEST_CODE = 4105

    @staticmethod
    def _android_runtime():
        from jnius import autoclass

        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        service = autoclass(SERVICE_CLASS)
        sdk_int = autoclass("android.os.Build$VERSION").SDK_INT
        return activity, service, sdk_int

    def start(self, argument, callback):
        if not KIVY_AVAILABLE or platform != "android":
            callback(False, "Foreground monitoring is available on Android only.")
            return
        try:
            activity, service, sdk_int = self._android_runtime()
            if sdk_int >= 33:
                from android.permissions import (
                    Permission,
                    check_permission,
                    request_permissions,
                )

                permission = Permission.POST_NOTIFICATIONS
                if not check_permission(permission):
                    def permission_result(_permissions, _grants):
                        if check_permission(permission):
                            self._start_generated(service, activity, argument, callback)
                        else:
                            callback(False, "Notification permission is required.")

                    request_permissions([permission], permission_result)
                    return
            self._start_generated(service, activity, argument, callback)
        except Exception as exc:
            callback(False, f"Unable to start monitor: {exc}")

    @staticmethod
    def _start_generated(service, activity, argument, callback):
        try:
            service.start(activity, argument)
        except Exception as exc:
            callback(False, f"Unable to start monitor: {exc}")
            return
        callback(True, "Monitoring started.")

    def stop(self, callback):
        if not KIVY_AVAILABLE or platform != "android":
            callback(False, "Foreground monitoring is available on Android only.")
            return
        try:
            activity, service, _sdk_int = self._android_runtime()
            service.stop(activity)
        except Exception as exc:
            callback(False, f"Unable to stop monitor: {exc}")
            return
        callback(True, "Monitoring stopped.")


if KIVY_AVAILABLE:
    C_BG = (0.95, 0.96, 0.97, 1)
    C_CARD = (1, 1, 1, 1)
    C_PRIMARY = (0.12, 0.42, 0.82, 1)
    C_DANGER = (0.82, 0.20, 0.18, 1)
    C_TEXT = (0.10, 0.12, 0.15, 1)
    C_MUTED = (0.40, 0.44, 0.50, 1)
    C_SUCCESS = (0.12, 0.58, 0.34, 1)
    C_WARNING = (0.88, 0.50, 0.08, 1)
    C_DISABLED = (0.67, 0.69, 0.72, 1)

    def _paint(widget, color, radius=8):
        widget.canvas.before.clear()
        with widget.canvas.before:
            Color(*color)
            RoundedRectangle(pos=widget.pos, size=widget.size, radius=[dp(radius)])

    def _card(height=None):
        card = BoxLayout(
            orientation="vertical",
            padding=dp(10),
            spacing=dp(7),
            size_hint_y=None if height else 1,
            height=dp(height) if height else 100,
        )
        card.bind(pos=lambda widget, _value: _paint(widget, C_CARD))
        card.bind(size=lambda widget, _value: _paint(widget, C_CARD))
        return card

    def _button(text, color=C_PRIMARY):
        button = Button(
            text=text,
            bold=True,
            font_size=dp(14),
            size_hint_y=None,
            height=dp(42),
            background_normal="",
            background_down="",
            background_color=color,
            color=(1, 1, 1, 1),
        )
        return button

    def _input(**kwargs):
        return TextInput(
            multiline=False,
            font_size=dp(14),
            size_hint_y=None,
            height=dp(42),
            padding=[dp(10), dp(10), dp(10), dp(8)],
            background_normal="",
            background_active="",
            background_color=(0.96, 0.97, 0.98, 1),
            foreground_color=C_TEXT,
            hint_text_color=C_MUTED,
            cursor_color=C_PRIMARY,
            **kwargs,
        )


    class SignPanel(BoxLayout):
        EVENT_INTERVAL = 1.0

        def __init__(
            self,
            base_dir,
            api_factory=ApiClient,
            service_bridge=None,
            auto_restore=True,
            **kwargs,
        ):
            super().__init__(**kwargs)
            install_crash_hooks(base_dir)
            self.orientation = "vertical"
            self.padding = [dp(12), dp(9)]
            self.spacing = dp(8)
            self.api_factory = api_factory
            self.bridge = service_bridge or AndroidServiceBridge()
            self.session_store = SessionStore(base_dir)
            self.service_state = ServiceState(base_dir)
            self.api = None
            self._courses = []
            self._course_by_label = {}
            self._selected_course = None
            self._auth_busy = False
            self._service_busy = False
            self._monitoring = False
            self._visible = False
            self._event_timer = None
            self._event_tracker = EventIdentityTracker()
            self.bind(pos=lambda widget, _value: _paint(widget, C_BG, 0))
            self.bind(size=lambda widget, _value: _paint(widget, C_BG, 0))
            self._build()
            self._sync_controls()
            if auto_restore:
                self._begin_restore()

        def _build(self):
            header = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(8))
            title = Label(
                text="对分易签到",
                bold=True,
                font_size=dp(20),
                color=C_TEXT,
                halign="left",
                valign="middle",
            )
            title.bind(size=lambda widget, value: setattr(widget, "text_size", value))
            self.status_badge = Label(
                text="未登录",
                bold=True,
                font_size=dp(12),
                color=C_MUTED,
                size_hint_x=None,
                width=dp(86),
            )
            header.add_widget(title)
            header.add_widget(self.status_badge)
            self.add_widget(header)

            auth_card = _card(vertical_stack_height([18, 42, 42]))
            auth_card.add_widget(Label(
                text="微信 OAuth 链接",
                bold=True,
                font_size=dp(13),
                color=C_TEXT,
                size_hint_y=None,
                height=dp(18),
                halign="left",
            ))
            self.oauth_input = _input(hint_text="粘贴包含 code 参数的授权链接")
            self.oauth_button = _button("登录并加载课程")
            self.oauth_button.bind(on_press=self._on_login_press)
            auth_card.add_widget(self.oauth_input)
            auth_card.add_widget(self.oauth_button)
            self.add_widget(auth_card)

            control_card = _card(vertical_stack_height([42, 42]))
            row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(7))
            self.course_spinner = Spinner(
                text="登录后选择课程",
                values=(),
                font_size=dp(14),
                size_hint_x=0.72,
                background_normal="",
                background_color=(0.96, 0.97, 0.98, 1),
                color=C_TEXT,
            )
            self.course_spinner.bind(text=self._on_course_select)
            self.countdown_input = _input(text=str(DEFAULT_COUNTDOWN), input_filter="int")
            self.countdown_input.size_hint_x = 0.28
            row.add_widget(self.course_spinner)
            row.add_widget(self.countdown_input)
            self.monitor_button = _button("开始监控")
            self.monitor_button.bind(on_press=self._on_monitor_press)
            control_card.add_widget(row)
            control_card.add_widget(self.monitor_button)
            self.add_widget(control_card)

            log_card = _card()
            log_card.add_widget(Label(
                text="运行记录",
                bold=True,
                font_size=dp(13),
                color=C_TEXT,
                size_hint_y=None,
                height=dp(20),
                halign="left",
            ))
            scroll = ScrollView(do_scroll_x=False)
            self.log_label = Label(
                text="",
                markup=True,
                font_size=dp(12),
                color=C_TEXT,
                size_hint_y=None,
                valign="top",
                halign="left",
                padding=[dp(2), dp(3)],
            )
            self.log_label.bind(width=lambda widget, value: setattr(widget, "text_size", (value, None)))
            self.log_label.bind(texture_size=lambda widget, value: setattr(widget, "height", value[1]))
            scroll.add_widget(self.log_label)
            log_card.add_widget(scroll)
            self.add_widget(log_card)

        def _schedule(self, callback, *args):
            Clock.schedule_once(lambda _dt: callback(*args), 0)

        def _begin_restore(self):
            self._set_auth_busy(True, "恢复登录中")
            start_daemon_worker(self._restore_worker, name="restore-session")

        def _restore_worker(self):
            cookie = self.session_store.load_cookie()
            if not cookie:
                self._schedule(self._finish_restore, None, [], "", False)
                return
            try:
                api = self.api_factory(cookie)
                if not api.check_login():
                    self.session_store.clear()
                    self._schedule(self._finish_restore, None, [], "登录已失效，请重新授权。", True)
                    return
                courses = api.get_course_list()
            except Exception as exc:
                self._schedule(self._finish_restore, None, [], f"恢复登录失败: {exc}", False)
                return
            self._schedule(self._finish_restore, api, courses, "已恢复登录。", False)

        @mainthread
        def _finish_restore(self, api, courses, message, invalid_cookie):
            self.api = api
            self._set_auth_busy(False)
            self._apply_courses(courses)
            if message:
                self._append_log("warn" if invalid_cookie else "info", message)
            self._restore_monitoring_state()

        def _on_login_press(self, _button):
            link = self.oauth_input.text.strip()
            if not link:
                self._append_log("warn", "请粘贴微信 OAuth 链接。")
                return
            self._set_auth_busy(True, "登录中")
            start_daemon_worker(self._login_worker, link, name="oauth-login")

        def _login_worker(self, link):
            try:
                result = complete_wechat_login(
                    self.api_factory, self.session_store, link
                )
            except Exception as exc:
                self._schedule(self._finish_login, None, [], f"登录失败: {exc}", False)
                return
            self._schedule(self._finish_login, *result)

        @mainthread
        def _finish_login(self, api, courses, message, success):
            self.api = api if success else None
            self._set_auth_busy(False)
            self._apply_courses(courses)
            self._append_log("success" if success else "error", message)

        @mainthread
        def _apply_courses(self, courses):
            self._courses = list(courses or [])
            labels = course_labels(self._courses)
            self._course_by_label = dict(zip(labels, self._courses))
            self.course_spinner.values = labels
            if labels:
                configured = self.service_state.read_config() or {}
                configured_id = str(configured.get("course_id", ""))
                selected_label = next(
                    (
                        label for label, course in self._course_by_label.items()
                        if str(course.get("CourseID", "")) == configured_id
                    ),
                    labels[0],
                )
                self.course_spinner.text = selected_label
                self._selected_course = self._course_by_label[selected_label]
            else:
                self.course_spinner.text = "暂无课程" if self.api else "登录后选择课程"
                self._selected_course = None
            self._sync_controls()

        def _on_course_select(self, _spinner, label):
            self._selected_course = self._course_by_label.get(label)
            self._sync_controls()

        def _on_monitor_press(self, _button):
            if self._service_busy:
                return
            if self._monitoring:
                self._stop_monitoring()
            else:
                self._start_monitoring()

        def _start_monitoring(self):
            if self.api is None or self._selected_course is None:
                self._append_log("warn", "请先登录并选择课程。")
                return
            cookie = self.api.export_cookie()
            argument = service_argument_json(cookie, self._selected_course, self.countdown_input.text)
            self.service_state.clear_timeout()
            self.service_state.write_config(json.loads(argument))
            self._set_service_busy(True, "启动中")
            self.bridge.start(
                argument,
                lambda success, message: self._schedule(
                    self._finish_service_start, success, message
                ),
            )

        @mainthread
        def _finish_service_start(self, success, message):
            self._monitoring = bool(success)
            if not success:
                self.service_state.request_stop()
            self._set_service_busy(False)
            self._append_log("success" if success else "error", message)

        def _stop_monitoring(self):
            self.service_state.request_stop()
            self._monitoring = False
            self._set_service_busy(True, "停止中")
            self.bridge.stop(
                lambda success, message: self._schedule(
                    self._finish_service_stop, success, message
                )
            )

        @mainthread
        def _finish_service_stop(self, success, message):
            self._monitoring = False
            self._set_service_busy(False)
            self._append_log("info" if success else "warn", message)

        @mainthread
        def _set_auth_busy(self, busy, status=None):
            self._auth_busy = bool(busy)
            if status:
                self.status_badge.text = status
                self.status_badge.color = C_WARNING
            self._sync_controls()

        @mainthread
        def _set_service_busy(self, busy, status=None):
            self._service_busy = bool(busy)
            if status:
                self.status_badge.text = status
                self.status_badge.color = C_WARNING
            self._sync_controls()

        def _sync_controls(self):
            logged_in = self.api is not None
            blocked = self._auth_busy or self._service_busy
            self.oauth_input.disabled = blocked or self._monitoring
            self.oauth_button.disabled = blocked or self._monitoring
            self.course_spinner.disabled = blocked or self._monitoring or not self._courses
            self.countdown_input.disabled = blocked or self._monitoring or not logged_in
            self.monitor_button.disabled = blocked or (not self._monitoring and self._selected_course is None)
            self.monitor_button.text = "停止监控" if self._monitoring else "开始监控"
            self.monitor_button.background_color = C_DANGER if self._monitoring else C_PRIMARY
            if blocked:
                self.monitor_button.background_color = C_DISABLED
            elif self._monitoring:
                self.status_badge.text = "监控中"
                self.status_badge.color = C_SUCCESS
            elif logged_in:
                self.status_badge.text = "已登录"
                self.status_badge.color = C_PRIMARY
            else:
                self.status_badge.text = "未登录"
                self.status_badge.color = C_MUTED

        def on_visible(self):
            self._visible = True
            self._restore_monitoring_state()
            self._poll_events(0)
            if self._event_timer is None:
                self._event_timer = Clock.schedule_interval(
                    self._poll_events, self.EVENT_INTERVAL
                )

        def on_hidden(self):
            self._visible = False
            if self._event_timer is not None:
                self._event_timer.cancel()
                self._event_timer = None

        @mainthread
        def _restore_monitoring_state(self):
            config = self.service_state.read_config()
            self._monitoring = restored_monitoring_state(
                bool(config),
                self.service_state.stop_requested(),
                self.service_state.read_events(),
                timeout_requested=self.service_state.timeout_requested(),
            )
            self._sync_controls()

        def _poll_events(self, _dt):
            if not self._visible:
                return False
            consume_timeout_termination(self.service_state)
            events = self.service_state.read_events()
            new_events = self._event_tracker.unseen(events)
            lifecycle_seen = False
            for event in new_events:
                self._append_log(
                    str(event.get("level", "info")),
                    str(event.get("message", "")),
                    event.get("timestamp"),
                )
                state = lifecycle_monitoring_state(event.get("message", ""))
                if state is not None:
                    self._monitoring = state
                    lifecycle_seen = True
            if lifecycle_seen:
                self._service_busy = False
                self._sync_controls()
            return True

        @mainthread
        def _append_log(self, level, message, timestamp=None):
            colors = {
                "info": "4B647A",
                "success": "16834A",
                "warn": "B56708",
                "error": "B52822",
            }
            moment = event_moment(timestamp)
            line = (
                f"[color=#{colors.get(level, '4B647A')}]"
                f"[{moment:%H:%M:%S}][/color] {escape_markup(str(message))}"
            )
            lines = (self.log_label.text.splitlines() + [line])[-160:]
            self.log_label.text = "\n".join(lines)


    class SignApp(App):
        def build(self):
            self.title = "对分易签到"
            self.panel = SignPanel(base_dir=self.user_data_dir)
            Clock.schedule_once(lambda _dt: self.panel.on_visible(), 0)
            return self.panel

        def on_pause(self):
            self.panel.on_hidden()
            return True

        def on_resume(self):
            self.panel.on_visible()

        def on_stop(self):
            self.panel.on_hidden()


else:
    class SignPanel:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("Kivy is required to construct SignPanel")


    class SignApp:
        def run(self):
            raise RuntimeError("Kivy is required to run SignApp")


if __name__ == "__main__":
    SignApp().run()
