"""对分易自动签到 — Android APK 版"""

import sys
import traceback
import os
import datetime

# ── crash handler ──────────────────────────────────────────

_CRASH_LOG = "crash.log"
_excepthook_installed = False


def _install_crash_handler():
    global _excepthook_installed
    if _excepthook_installed:
        return
    _excepthook_installed = True
    _orig = sys.excepthook

    def _handler(exc_type, exc_value, exc_tb):
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            with open(_CRASH_LOG, "w") as f:
                f.write(tb_str)
        except Exception:
            pass
        try:
            from kivy.uix.popup import Popup
            from kivy.uix.label import Label
            from kivy.app import App
            app = App.get_running_app()
            if app is not None:
                popup = Popup(
                    title="应用程序崩溃",
                    content=Label(text=tb_str[:800], font_size=11),
                    size_hint=(0.95, 0.8),
                    auto_dismiss=False,
                )
                popup.open()
                return
        except Exception:
            pass
        _orig(exc_type, exc_value, exc_tb)

    sys.excepthook = _handler


_install_crash_handler()

# ── imports ────────────────────────────────────────────────

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.spinner import Spinner
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.utils import platform
from kivy.metrics import dp
from kivy.graphics import Color, RoundedRectangle

from api_client import ApiClient
from sign_service import SignService

COOKIE_FILE = "cookie.txt"

# ── theme ──────────────────────────────────────────────────

# color palette
C1 = (0.26, 0.52, 0.96, 1)   # primary blue
C1_DIM = (0.18, 0.38, 0.75, 1)  # pressed blue
C_GREEN = (0.20, 0.72, 0.44, 1)
C_RED = (0.92, 0.30, 0.24, 1)
C_ORANGE = (0.98, 0.60, 0.04, 1)
C_BG = (0.94, 0.94, 0.95, 1)
C_CARD = (1, 1, 1, 1)
C_TEXT = (0.10, 0.10, 0.10, 1)
C_HINT = (0.55, 0.55, 0.58, 1)
C_BORDER = (0.82, 0.82, 0.85, 1)
C_DISABLED = (0.70, 0.70, 0.72, 1)

R = dp(10)      # corner radius
F_TITLE = dp(18)
F_BODY = dp(14)
F_SMALL = dp(12)


def _flat_btn(text, color=C1, text_color=(1, 1, 1, 1), font_size=F_BODY,
              height=dp(46), disabled=False, on_press=None):
    """Flat rounded button — cleaner than default gradient."""
    btn = Button(
        text=text, font_size=font_size, bold=True,
        size_hint_y=None, height=height,
        background_normal="", background_down="",
        color=text_color,
        background_color=C_DISABLED if disabled else color,
        on_press=on_press,
    )
    if disabled:
        btn.disabled = True
    # rounded corners via canvas
    btn.bind(pos=lambda i, _: _draw_round_rect(i), size=lambda i, _: _draw_round_rect(i))
    return btn


def _draw_round_rect(widget):
    widget.canvas.before.clear()
    with widget.canvas.before:
        Color(*widget.background_color[:3], 1)
        RoundedRectangle(pos=widget.pos, size=widget.size, radius=[dp(8)])


def _styled_input(hint, password=False, multiline=False, height=dp(46)):
    """Styled text input — simple flat style, no canvas to avoid GPU state leak."""
    return TextInput(
        hint_text=hint, multiline=multiline,
        password=password,
        font_size=F_BODY,
        size_hint_y=None, height=height,
        background_color=(0.96, 0.96, 0.97, 1),
        foreground_color=(0, 0, 0, 1),
        hint_text_color=C_HINT,
        cursor_color=C1,
        padding=[dp(12), dp(10), dp(12), dp(10)],
        cursor_width=dp(1.5),
    )


def _card(inner, padding=dp(12)):
    """Wrap a widget in a white rounded card."""
    from kivy.uix.anchorlayout import AnchorLayout
    anchor = AnchorLayout(size_hint_y=None, padding=padding)
    anchor.height = inner.height + padding * 2
    inner.bind(height=lambda i, h: setattr(anchor, 'height', h + padding * 2))
    anchor.add_widget(inner)
    anchor.bind(pos=lambda i, _: _draw_card_bg(anchor),
                size=lambda i, _: _draw_card_bg(anchor))
    return anchor


def _draw_card_bg(widget):
    widget.canvas.before.clear()
    with widget.canvas.before:
        Color(*C_CARD)
        RoundedRectangle(pos=widget.pos, size=widget.size, radius=[dp(12)])


def _section_label(text):
    return Label(
        text=text, font_size=F_SMALL + dp(1), bold=True,
        color=C_HINT, size_hint_y=None, height=dp(28),
        halign="left", valign="bottom",
        padding=[dp(4), 0],
    )


# ── main panel ─────────────────────────────────────────────

class SignPanel(BoxLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.orientation = "vertical"
        self.padding = [dp(12), dp(8)]
        self.spacing = dp(8)

        self.api = ApiClient(self._load_cookie())
        self.svc = SignService(self.api)
        self.svc.on_log = self._on_log
        self.svc.on_status = self._on_status

        self._courses = []
        self._selected_course = None
        self._monitoring = False

        self._build()

    # ─── cookie ────────────────────────────────────────────

    def _load_cookie(self) -> str:
        if os.path.exists(COOKIE_FILE):
            with open(COOKIE_FILE) as f:
                return f.read().strip()
        return ""

    def _save_cookie(self):
        with open(COOKIE_FILE, "w") as f:
            f.write(self.api.export_cookie())

    # ─── UI ────────────────────────────────────────────────

    def _build(self):
        # ── 头部 ──
        header = BoxLayout(orientation="vertical",
                          size_hint_y=None, height=dp(42), spacing=0)
        title = Label(
            text="对分易 自动签到", font_size=F_TITLE, bold=True,
            color=C1, size_hint_y=None, height=dp(30),
            halign="center", valign="middle",
        )
        header.add_widget(title)
        self.add_widget(header)

        # ── 登录区域 ──
        self._login_box = BoxLayout(orientation="vertical", spacing=dp(6),
                                    size_hint_y=None, height=dp(280))
        self._build_login_pwd()
        self.add_widget(self._login_box)

        # ── 课程 + 控制 ──
        self._ctrl_box = BoxLayout(orientation="vertical", spacing=dp(6),
                                   size_hint_y=None, height=dp(160))
        self._build_controls()
        self.add_widget(self._ctrl_box)

        # ── 日志 ──
        self.add_widget(_section_label("签到日志"))
        scroll = ScrollView(size_hint_y=1)
        self._log_label = Label(
            text="", font_size=F_SMALL, markup=True,
            size_hint_y=None, valign="top", halign="left",
            padding=[dp(6), dp(4)],
        )
        self._log_label.bind(texture_size=lambda i, s: setattr(i, 'height', s[1]))
        scroll.add_widget(self._log_label)
        self.add_widget(scroll)

    def _build_login_pwd(self):
        box = BoxLayout(orientation="vertical", spacing=dp(6), padding=[dp(4), 0])
        self._user_input = _styled_input("账号", height=dp(46))
        self._pwd_input = _styled_input("密码", password=True, height=dp(46))
        self._link_input = _styled_input("粘贴微信 OAuth 链接...", multiline=True, height=dp(72))

        btn_row = BoxLayout(orientation="horizontal", spacing=dp(8),
                           size_hint_y=None, height=dp(46))
        btn_row.add_widget(_flat_btn("密码登录", C1, on_press=lambda _: self._do_pwd_login()))
        btn_row.add_widget(_flat_btn("微信登录", (0.06, 0.75, 0.55, 1),
                                     on_press=lambda _: self._do_link_login()))

        box.add_widget(Label(
            text="密码登录 — 不支持二维码签到   微信登录 — 支持全部",
            font_size=F_SMALL - dp(1), color=C_HINT,
            size_hint_y=None, height=dp(18),
        ))
        box.add_widget(self._user_input)
        box.add_widget(self._pwd_input)
        box.add_widget(self._link_input)
        box.add_widget(btn_row)
        self._login_box.add_widget(box)

    def _build_controls(self):
        box = BoxLayout(orientation="vertical", spacing=dp(6), padding=[dp(4), 0])

        # 课程 + 倒计时
        row1 = BoxLayout(orientation="horizontal", spacing=dp(6),
                        size_hint_y=None, height=dp(44))
        row1.add_widget(Label(
            text="课程", font_size=F_BODY, color=C_TEXT,
            size_hint_x=0.18, halign="right", valign="middle",
        ))
        self._spinner = Spinner(
            text="请先登录", font_size=F_BODY,
            size_hint_x=0.55, background_normal="", background_down="",
            background_color=C_CARD, color=(0, 0, 0, 1),
        )
        self._spinner.bind(text=self._on_course_select)
        row1.add_widget(self._spinner)

        row1.add_widget(Label(
            text="提前(s)", font_size=F_SMALL, color=C_HINT,
            size_hint_x=0.12, halign="right", valign="middle",
        ))
        self._cd_input = TextInput(
            text="10", multiline=False, font_size=F_BODY,
            size_hint_x=0.15, input_filter="int",
            background_color=(0.96, 0.96, 0.97, 1),
            foreground_color=(0, 0, 0, 1),
            cursor_color=C1, padding=[dp(24), dp(10), 0, dp(10)],
            halign="center", cursor_width=dp(1.5),
        )
        row1.add_widget(self._cd_input)
        box.add_widget(row1)

        # 按钮
        row2 = BoxLayout(orientation="horizontal", spacing=dp(10),
                        size_hint_y=None, height=dp(46))
        self._btn_start = _flat_btn("开始监控", C1,
                                    on_press=lambda _: self._toggle())
        self._btn_stop = _flat_btn("停止", C_RED, disabled=True,
                                   on_press=lambda _: self._stop())
        row2.add_widget(self._btn_start)
        row2.add_widget(self._btn_stop)
        box.add_widget(row2)
        self._ctrl_box.add_widget(box)

    # ─── 登录 ──────────────────────────────────────────────

    def _do_pwd_login(self):
        user = self._user_input.text.strip()
        pwd = self._pwd_input.text.strip()
        if not user or not pwd:
            self._log("warn", "请输入账号和密码")
            return
        self._log("info", "正在登录...")
        try:
            msg = self.api.login_by_password(user, pwd)
            self._log("success" if "成功" in msg else "error", msg)
            if "成功" in msg:
                self._save_cookie()
                self._load_courses()
        except Exception as e:
            self._log("error", str(e))

    def _do_link_login(self):
        link = self._link_input.text.strip()
        if not link or "code=" not in link:
            self._log("warn", "链接无效，需包含 code 参数")
            return
        self._log("info", "正在登录...")
        try:
            msg = self.api.login_by_wechat_link(link)
            self._log("success" if "成功" in msg else "error", msg)
            if "成功" in msg:
                self._save_cookie()
                self._load_courses()
        except Exception as e:
            self._log("error", str(e))

    # ─── 课程 ──────────────────────────────────────────────

    def _load_courses(self):
        try:
            courses = self.api.get_course_list()
            if courses:
                self._courses = courses
                names = [c["CourseName"] for c in courses]
                self._spinner.values = names
                self._spinner.text = names[0]
                self._selected_course = courses[0]
                self._log("info", f"已加载 {len(courses)} 门课程")
            else:
                self._log("warn", "未获取到课程")
        except Exception as e:
            self._log("error", str(e))

    def _on_course_select(self, spinner, text):
        for c in self._courses:
            if c["CourseName"] == text:
                self._selected_course = c
                return

    # ─── 监控 ──────────────────────────────────────────────

    def _toggle(self):
        if self._monitoring:
            self._stop()
        else:
            self._start()

    def _start(self):
        if not self._selected_course:
            self._log("warn", "请先登录并选择课程")
            return

        try:
            cd = int(self._cd_input.text)
        except ValueError:
            cd = 10

        self._log_label.text = ""
        self._btn_start.disabled = True
        self._btn_start.background_color = C_DISABLED
        _draw_round_rect(self._btn_start)
        self._btn_stop.disabled = False
        self._btn_stop.background_color = C_RED
        _draw_round_rect(self._btn_stop)
        self._monitoring = True

        c = self._selected_course
        self.svc.start(
            course_id=c["CourseID"],
            class_id=c["TClassID"],
            class_name=c["CourseName"],
            countdown=cd,
        )

    def _stop(self):
        self.svc.stop()
        self._monitoring = False
        self._btn_start.disabled = False
        self._btn_start.background_color = C1
        _draw_round_rect(self._btn_start)
        self._btn_stop.disabled = True
        self._btn_stop.background_color = C_DISABLED
        _draw_round_rect(self._btn_stop)

    def _on_status(self, running: bool):
        if not running:
            self._monitoring = False
            self._btn_start.disabled = False
            self._btn_start.background_color = C1
            _draw_round_rect(self._btn_start)
            self._btn_stop.disabled = True
            self._btn_stop.background_color = C_DISABLED
            _draw_round_rect(self._btn_stop)

    # ─── 日志 ──────────────────────────────────────────────

    LOG_COLORS = {
        "info":    "7F8C8D",
        "success": "27AE60",
        "error":   "E74C3C",
        "warn":    "F39C12",
    }
    LOG_ICONS = {
        "info":    "i",
        "success": "✔",
        "error":   "✘",
        "warn":    "!",
    }

    @mainthread
    def _on_log(self, level: str, message: str):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        color = self.LOG_COLORS.get(level, "7F8C8D")
        icon = self.LOG_ICONS.get(level, "")
        text = self._log_label.text
        text += f"\n[color=#{color}][b]{icon}[/b] [{now}][/color] {message}"
        if len(text) > 6000:
            text = text[-5000:]
        self._log_label.text = text

    def _log(self, level: str, message: str):
        self._on_log(level, message)


# ── app ────────────────────────────────────────────────────

class SignApp(App):
    def _setup_font(self):
        import os as _os
        for _p in [
            "/system/fonts/NotoSansCJK-Regular.ttc",
            "/system/fonts/DroidSansFallback.ttf",
            "/system/fonts/NotoSansSC-Regular.otf",
            "/system/fonts/MiSans-Regular.ttf",
            "/system/fonts/HarmonyOS_Sans_SC_Regular.ttf",
        ]:
            if _os.path.exists(_p):
                from kivy.core.text import LabelBase
                try:
                    LabelBase.register(name="Roboto", fn_regular=_p)
                except Exception:
                    pass
                return

    def build(self):
        if platform == "android":
            self._setup_font()
        self.title = "对分易自动签到"
        return SignPanel()


if __name__ == "__main__":
    SignApp().run()
