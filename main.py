"""对分易自动签到 — Android APK 版 (KivyMD Material Design)"""

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

from kivy.clock import Clock, mainthread
from kivy.utils import platform
from kivy.metrics import dp
from kivy.core.window import Window

from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDRoundFlatButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.snackbar import Snackbar
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.scrollview import MDScrollView

from api_client import ApiClient
from sign_service import SignService

COOKIE_FILE = "cookie.txt"


# ── main panel ─────────────────────────────────────────────

class SignPanel(MDBoxLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.orientation = "vertical"
        self.md_bg_color = (0.95, 0.95, 0.96, 1)
        self.spacing = dp(10)
        self.padding = [dp(14), dp(10)]

        self.api = ApiClient(self._load_cookie())
        self.svc = SignService(self.api)
        self.svc.on_log = self._on_log
        self.svc.on_status = self._on_status

        self._courses = []
        self._selected_course = None
        self._monitoring = False
        self._login_mode = "pwd"  # "pwd" | "wechat"

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
        # ── Top bar ──
        toolbar = MDTopAppBar(
            title="对分易 自动签到",
            elevation=2,
            md_bg_color=(0.19, 0.45, 0.91, 1),
            specific_text_color=(1, 1, 1, 1),
            pos_hint={"top": 1},
        )
        toolbar.right_action_items = [["refresh", lambda x: self._load_courses()]]
        self.add_widget(toolbar)

        # ── Login card ──
        self._login_card = MDCard(
            orientation="vertical",
            padding=[dp(14), dp(12)],
            spacing=dp(10),
            size_hint_y=None,
            height=dp(270),
            elevation=3,
            radius=[dp(14)],
        )
        self._login_card.md_bg_color = (1, 1, 1, 1)
        self._build_login_section()
        self.add_widget(self._login_card)

        # ── Control card ──
        self._ctrl_card = MDCard(
            orientation="vertical",
            padding=[dp(14), dp(12)],
            spacing=dp(10),
            size_hint_y=None,
            height=dp(170),
            elevation=3,
            radius=[dp(14)],
        )
        self._ctrl_card.md_bg_color = (1, 1, 1, 1)
        self._build_control_section()
        self.add_widget(self._ctrl_card)

        # ── Log area ──
        header_row = MDBoxLayout(
            orientation="horizontal",
            size_hint_y=None, height=dp(30),
            spacing=dp(6),
        )
        header_row.add_widget(MDLabel(
            text="签到日志", font_style="Caption", bold=True,
            theme_text_color="Hint", adaptive_height=True,
        ))
        self.add_widget(header_row)

        self._log_scroll = MDScrollView(size_hint_y=1)
        self._log_label = MDLabel(
            text="", font_style="Caption",
            adaptive_height=True,
            markup=True,
            padding=[dp(8), dp(4)],
        )
        self._log_scroll.add_widget(self._log_label)
        self.add_widget(self._log_scroll)

    def _build_login_section(self):
        self._login_box = MDBoxLayout(orientation="vertical", spacing=dp(10))

        # login mode toggle
        toggle = MDBoxLayout(orientation="horizontal", spacing=0,
                            size_hint_y=None, height=dp(38))
        self._btn_pwd_mode = MDRaisedButton(
            text="密码登录", font_style="Button",
            size_hint_x=0.5, md_bg_color=(0.19, 0.45, 0.91, 1),
            on_release=lambda _: self._switch_login("pwd"),
        )
        self._btn_wx_mode = MDFlatButton(
            text="微信登录", font_style="Button",
            size_hint_x=0.5, text_color=(0.5, 0.5, 0.5, 1),
            on_release=lambda _: self._switch_login("wechat"),
        )
        toggle.add_widget(self._btn_pwd_mode)
        toggle.add_widget(self._btn_wx_mode)
        self._login_box.add_widget(toggle)

        # password fields
        self._pwd_section = MDBoxLayout(orientation="vertical", spacing=dp(8))
        self._user_input = MDTextField(
            hint_text="账号", mode="rectangle",
            size_hint_x=1, font_size=F_BODY,
        )
        self._pwd_input = MDTextField(
            hint_text="密码", mode="rectangle",
            size_hint_x=1, password=True, font_size=F_BODY,
        )
        self._pwd_section.add_widget(self._user_input)
        self._pwd_section.add_widget(self._pwd_input)

        # wechat field
        self._wx_section = MDBoxLayout(orientation="vertical", spacing=dp(8))
        self._link_input = MDTextField(
            hint_text="粘贴微信 OAuth 完整链接...", mode="rectangle",
            size_hint_x=1, multiline=True, font_size=F_BODY,
            max_height=dp(80),
        )
        self._wx_section.add_widget(self._link_input)
        self._wx_section.opacity = 0
        self._wx_section.height = 0

        self._login_box.add_widget(self._pwd_section)
        self._login_box.add_widget(self._wx_section)

        # login button
        btn_row = MDBoxLayout(orientation="horizontal", spacing=dp(10),
                             size_hint_y=None, height=dp(44))
        self._login_btn = MDRaisedButton(
            text="登  录", font_style="Button",
            size_hint_x=1, md_bg_color=(0.19, 0.45, 0.91, 1),
            on_release=lambda _: self._do_login(),
        )
        btn_row.add_widget(self._login_btn)
        self._login_box.add_widget(btn_row)

        self._hint_label = MDLabel(
            text="密码登录不支持二维码签到",
            font_style="Caption", theme_text_color="Hint",
            adaptive_height=True, halign="center",
        )
        self._login_box.add_widget(self._hint_label)

        self._login_card.add_widget(self._login_box)

    def _switch_login(self, mode):
        self._login_mode = mode
        if mode == "pwd":
            self._btn_pwd_mode.md_bg_color = (0.19, 0.45, 0.91, 1)
            self._btn_pwd_mode.text_color = (1, 1, 1, 1)
            self._btn_wx_mode.md_bg_color = (0, 0, 0, 0)
            self._btn_wx_mode.text_color = (0.5, 0.5, 0.5, 1)
            self._pwd_section.opacity = 1
            self._pwd_section.height = dp(100)
            self._wx_section.opacity = 0
            self._wx_section.height = 0
            self._hint_label.text = "密码登录不支持二维码签到"
            self._login_card.height = dp(270)
        else:
            self._btn_wx_mode.md_bg_color = (0.19, 0.45, 0.91, 1)
            self._btn_wx_mode.text_color = (1, 1, 1, 1)
            self._btn_pwd_mode.md_bg_color = (0, 0, 0, 0)
            self._btn_pwd_mode.text_color = (0.5, 0.5, 0.5, 1)
            self._pwd_section.opacity = 0
            self._pwd_section.height = 0
            self._wx_section.opacity = 1
            self._wx_section.height = dp(86)
            self._hint_label.text = "微信登录 — 支持全部签到类型"
            self._login_card.height = dp(260)

    def _build_control_section(self):
        box = MDBoxLayout(orientation="vertical", spacing=dp(10))

        # course selector
        course_row = MDBoxLayout(orientation="horizontal", spacing=dp(8),
                                size_hint_y=None, height=dp(44))
        course_row.add_widget(MDLabel(
            text="课程", font_style="Body1",
            theme_text_color="Primary", size_hint_x=0.15,
            halign="right", adaptive_height=True,
        ))

        self._course_btn = MDFlatButton(
            text="请先登录", font_style="Body1",
            size_hint_x=0.58, theme_text_color="Primary",
            on_release=lambda _: self._open_course_menu(),
        )
        course_row.add_widget(self._course_btn)

        course_row.add_widget(MDLabel(
            text="提前(s)", font_style="Caption",
            theme_text_color="Hint", size_hint_x=0.13,
            halign="right", adaptive_height=True,
        ))
        self._cd_input = MDTextField(
            text="10", mode="rectangle", font_size=F_BODY,
            size_hint_x=0.14, input_filter="int",
            halign="center",
        )
        course_row.add_widget(self._cd_input)
        box.add_widget(course_row)

        # action buttons
        btn_row = MDBoxLayout(orientation="horizontal", spacing=dp(10),
                             size_hint_y=None, height=dp(44))
        self._btn_start = MDRaisedButton(
            text="开始监控", font_style="Button",
            size_hint_x=0.5, md_bg_color=(0.19, 0.45, 0.91, 1),
            on_release=lambda _: self._toggle(),
        )
        self._btn_stop = MDRaisedButton(
            text="停止", font_style="Button",
            size_hint_x=0.5, md_bg_color=(0.92, 0.30, 0.24, 1),
            disabled=True,
            on_release=lambda _: self._stop(),
        )
        btn_row.add_widget(self._btn_start)
        btn_row.add_widget(self._btn_stop)
        box.add_widget(btn_row)

        self._ctrl_card.add_widget(box)

    def _open_course_menu(self):
        if not self._courses:
            return
        items = [
            {
                "text": c["CourseName"],
                "viewclass": "OneLineListItem",
                "on_release": lambda x=c: self._on_course_pick(x),
            }
            for c in self._courses
        ]
        self._course_menu = MDDropdownMenu(
            caller=self._course_btn,
            items=items,
            width_mult=4,
        )
        self._course_menu.open()

    def _on_course_pick(self, course):
        self._selected_course = course
        self._course_btn.text = course["CourseName"]
        self._course_menu.dismiss()

    # ─── login ─────────────────────────────────────────────

    def _do_login(self):
        if self._login_mode == "pwd":
            self._do_pwd_login()
        else:
            self._do_link_login()

    def _do_pwd_login(self):
        user = self._user_input.text.strip()
        pwd = self._pwd_input.text.strip()
        if not user or not pwd:
            self._snack("请输入账号和密码", "warn")
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
            self._snack("链接无效，需包含 code 参数", "warn")
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

    def _snack(self, text, level="info"):
        try:
            Snackbar(text=text, duration=2).open()
        except Exception:
            self._log(level, text)

    # ─── course ────────────────────────────────────────────

    def _load_courses(self):
        try:
            courses = self.api.get_course_list()
            if courses:
                self._courses = courses
                self._selected_course = courses[0]
                self._course_btn.text = courses[0]["CourseName"]
                self._log("info", f"已加载 {len(courses)} 门课程")
            else:
                self._log("warn", "未获取到课程")
        except Exception as e:
            self._log("error", str(e))

    # ─── monitor ───────────────────────────────────────────

    def _toggle(self):
        if self._monitoring:
            self._stop()
        else:
            self._start()

    def _start(self):
        if not self._selected_course:
            self._snack("请先登录并选择课程", "warn")
            return
        try:
            cd = int(self._cd_input.text)
        except ValueError:
            cd = 10

        self._log_label.text = ""
        self._btn_start.disabled = True
        self._btn_start.md_bg_color = (0.7, 0.7, 0.72, 1)
        self._btn_stop.disabled = False
        self._btn_stop.md_bg_color = (0.92, 0.30, 0.24, 1)
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
        self._on_status(False)

    def _on_status(self, running: bool):
        self._monitoring = running
        self._btn_start.disabled = running
        self._btn_start.md_bg_color = (0.7, 0.7, 0.72, 1) if running else (0.19, 0.45, 0.91, 1)
        self._btn_stop.disabled = not running
        self._btn_stop.md_bg_color = (0.92, 0.30, 0.24, 1) if running else (0.7, 0.7, 0.72, 1)

    # ─── log ───────────────────────────────────────────────

    LOG_COLORS = {
        "info": "7F8C8D", "success": "27AE60",
        "error": "E74C3C", "warn": "F39C12",
    }

    @mainthread
    def _on_log(self, level: str, message: str):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        color = self.LOG_COLORS.get(level, "7F8C8D")
        icon = {"success": "✔", "error": "✘", "warn": "!", "info": "i"}.get(level, "")
        text = self._log_label.text
        text += f"\n[color=#{color}][b]{icon}[/b] [{now}][/color] {message}"
        if len(text) > 6000:
            text = text[-5000:]
        self._log_label.text = text
        # scroll to bottom
        if self._log_scroll.children:
            self._log_scroll.scroll_y = 0

    def _log(self, level: str, message: str):
        self._on_log(level, message)


# ── app ────────────────────────────────────────────────────

FONT_BODY = dp(14)


class SignApp(MDApp):
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

        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.accent_palette = "Teal"
        self.theme_cls.theme_style = "Light"

        return SignPanel()


if __name__ == "__main__":
    SignApp().run()
