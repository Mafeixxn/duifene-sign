"""对分易自动签到 — Android APK 版"""

import os
from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.spinner import Spinner
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.checkbox import CheckBox
from kivy.uix.popup import Popup
from kivy.utils import platform

from api_client import ApiClient
from sign_service import SignService

COOKIE_FILE = "cookie.txt"


class SignPanel(BoxLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.orientation = "vertical"
        self.padding = [10, 5]
        self.spacing = 6

        # API & service
        self.api = ApiClient(self._load_cookie())
        self.svc = SignService(self.api)
        self.svc.on_log = self._on_log
        self.svc.on_status = self._on_status

        self._courses = []
        self._selected_course = None
        self._monitoring = False

        self._build()

    # ─── cookie ───

    def _load_cookie(self) -> str:
        if os.path.exists(COOKIE_FILE):
            with open(COOKIE_FILE) as f:
                return f.read().strip()
        return ""

    def _save_cookie(self):
        with open(COOKIE_FILE, "w") as f:
            f.write(self.api.export_cookie())

    # ─── UI ───

    def _build(self):
        # ── 登录标签页 ──
        tabs = TabbedPanel(size_hint_y=0.45)

        # 账号密码登录
        tab_pwd = TabbedPanelItem(text="密码登录")
        box_pwd = BoxLayout(orientation="vertical", spacing=5, padding=[8, 10])
        self._user_input = TextInput(hint_text="账号", multiline=False,
                                      font_size=16, size_hint_y=None, height=44)
        self._pwd_input = TextInput(hint_text="密码", multiline=False,
                                     password=True, font_size=16,
                                     size_hint_y=None, height=44)
        box_pwd.add_widget(Label(text="密码登录不支持二维码签到",
                                  font_size=12, color=(0.6, 0.6, 0.6, 1),
                                  size_hint_y=None, height=20))
        box_pwd.add_widget(self._user_input)
        box_pwd.add_widget(self._pwd_input)
        box_pwd.add_widget(Button(text="登录", size_hint_y=None, height=44,
                                   on_press=lambda _: self._do_pwd_login()))
        tab_pwd.content = box_pwd
        tabs.add_widget(tab_pwd)

        # 微信链接登录
        tab_link = TabbedPanelItem(text="微信登录")
        box_link = BoxLayout(orientation="vertical", spacing=5, padding=[8, 10])
        self._link_input = TextInput(hint_text="粘贴微信OAuth链接...",
                                      multiline=True, font_size=14,
                                      size_hint_y=None, height=80)
        box_link.add_widget(Label(text="支持全部签到类型",
                                  font_size=12, color=(0.6, 0.6, 0.6, 1),
                                  size_hint_y=None, height=20))
        box_link.add_widget(self._link_input)
        box_link.add_widget(Button(text="登录", size_hint_y=None, height=44,
                                    on_press=lambda _: self._do_link_login()))
        tab_link.content = box_link
        tabs.add_widget(tab_link)

        tabs.default_tab = tab_pwd
        self.add_widget(tabs)

        # ── 课程选择 + 控制 ──
        ctrl = BoxLayout(orientation="vertical", spacing=6,
                         size_hint_y=None, height=130, padding=[10, 5])

        row1 = BoxLayout(orientation="horizontal", spacing=6,
                         size_hint_y=None, height=40)
        row1.add_widget(Label(text="课程:", size_hint_x=0.2,
                               font_size=15, halign="right"))
        self._spinner = Spinner(text="请先登录", size_hint_x=0.6,
                                 font_size=14)
        self._spinner.bind(text=self._on_course_select)
        row1.add_widget(self._spinner)

        row1.add_widget(Label(text="提前:", size_hint_x=0.1,
                               font_size=14))
        self._cd_input = TextInput(text="10", multiline=False,
                                    size_hint_x=0.1, font_size=14,
                                    input_filter="int")
        row1.add_widget(self._cd_input)
        ctrl.add_widget(row1)

        row2 = BoxLayout(orientation="horizontal", spacing=10,
                         size_hint_y=None, height=44)
        self._btn_start = Button(text="开始监控", size_hint_x=0.5,
                                  on_press=lambda _: self._toggle())
        self._btn_stop = Button(text="停止", size_hint_x=0.5,
                                 disabled=True,
                                 on_press=lambda _: self._stop())
        row2.add_widget(self._btn_start)
        row2.add_widget(self._btn_stop)
        ctrl.add_widget(row2)

        self.add_widget(ctrl)

        # ── 日志 ──
        self.add_widget(Label(text="签到日志:", size_hint_y=None,
                               height=22, font_size=14,
                               halign="left"))
        scroll = ScrollView(size_hint_y=1)
        self._log_label = Label(
            text="", font_size=13, markup=True,
            size_hint_y=None, valign="top", halign="left",
            padding=[6, 4]
        )
        self._log_label.bind(texture_size=lambda instance, size:
            setattr(instance, 'height', size[1]))
        scroll.add_widget(self._log_label)
        self.add_widget(scroll)

    # ─── 登录 ───

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

    # ─── 课程 ───

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

    # ─── 监控 ───

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
        self._btn_stop.disabled = False
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
        self._btn_stop.disabled = True

    def _on_status(self, running: bool):
        if not running:
            self._monitoring = False
            self._btn_start.disabled = False
            self._btn_stop.disabled = True

    # ─── 日志 ───

    COLORS = {
        "info": "cccccc", "success": "4caf50",
        "error": "f44336", "warn": "ff9800",
    }

    @mainthread
    def _on_log(self, level: str, message: str):
        color = self.COLORS.get(level, "cccccc")
        text = self._log_label.text
        text += f"\n[color=#{color}]{message}[/color]"
        # keep last ~5000 chars
        if len(text) > 5000:
            text = text[-4000:]
        self._log_label.text = text

    def _log(self, level: str, message: str):
        self._on_log(level, message)


class SignApp(App):
    def build(self):
        self.title = "对分易自动签到"
        return SignPanel()


if __name__ == "__main__":
    SignApp().run()
