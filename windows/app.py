import queue
import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime

from config_manager import ConfigManager
from api_client import ApiClient
from sign_service import SignService


class App:
    def __init__(self):
        self.config = ConfigManager()
        self.api = ApiClient(self.config)
        self.service = SignService(self.api)
        self.service.callback = self._on_service_message
        self.service.state_callback = self._on_service_state

        self._root = tk.Tk()
        self._root.title("对分易自动签到")
        self._root.resizable(False, False)
        self._root.geometry("700x580")

        self._ui_queue = queue.Queue()
        self._login_in_flight = False
        self._restore_in_flight = False
        self._monitor_starting = False
        self._course_list: list[dict] = []
        self._selected_course = None
        self._monitoring = False
        self._build_ui()
        self._root.after(100, self._drain_ui_queue)
        self._root.after(0, self._try_restore_session)

    # ─── UI 构建 ───

    def _build_ui(self):
        # 顶部 notebook（登录区）
        self._notebook = ttk.Notebook(self._root)
        self._notebook.pack(fill=tk.X, padx=10, pady=(10, 0))

        self._tab_link = ttk.Frame(self._notebook)
        self._tab_pwd = ttk.Frame(self._notebook)
        self._notebook.add(self._tab_link, text="微信链接登录")
        self._notebook.add(self._tab_pwd, text="账号密码登录")
        self._notebook.bind("<<NotebookTabChanged>>", self._on_tab_change)

        self._build_link_tab()
        self._build_pwd_tab()

        # 中间控制栏
        ctrl = ttk.Frame(self._root)
        ctrl.pack(fill=tk.X, padx=10, pady=(10, 0))

        ttk.Label(ctrl, text="选择课程:").pack(side=tk.LEFT)
        self._combo_var = tk.StringVar()
        self._combo = ttk.Combobox(ctrl, textvariable=self._combo_var,
                                   state="readonly", width=25)
        self._combo.bind("<<ComboboxSelected>>", self._on_course_select)
        self._combo.pack(side=tk.LEFT, padx=(5, 0))

        ttk.Label(ctrl, text="  提前(秒):").pack(side=tk.LEFT)
        self._countdown_var = tk.StringVar(value=str(self.config.get_countdown()))
        self._countdown_entry = ttk.Entry(ctrl, textvariable=self._countdown_var, width=5)
        self._countdown_entry.pack(side=tk.LEFT, padx=(2, 0))

        self._btn_toggle = ttk.Button(ctrl, text="开始监听签到",
                                      command=self._toggle_monitor)
        self._btn_toggle.pack(side=tk.RIGHT, padx=(10, 0))

        # 日志区域
        log_frame = ttk.Frame(self._root)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))

        self._log_text = scrolledtext.ScrolledText(
            log_frame, width=80, height=20,
            font=("Microsoft YaHei UI", 9), state=tk.DISABLED,
        )
        self._log_text.pack(fill=tk.BOTH, expand=True)
        self._log_text.tag_config("success", foreground="#228B22")
        self._log_text.tag_config("error", foreground="#DC143C")
        self._log_text.tag_config("warn", foreground="#FF8C00")
        self._log_text.tag_config("info", foreground="#1E1E1E")

        # 状态栏
        self._status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(self._root, textvariable=self._status_var,
                               relief=tk.SUNKEN, anchor=tk.W, padding=(5, 2))
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # 初始显示链接登录页的说明
        self._show_link_help()

    def _build_link_tab(self):
        f = ttk.Frame(self._tab_link)
        f.pack(fill=tk.X, pady=(20, 5))

        ttk.Label(f, text="将微信OAuth链接粘贴到下方，点击登录",
                  font=("Microsoft YaHei UI", 9)).pack(pady=(0, 8))

        self._link_var = tk.StringVar()
        link_entry = ttk.Entry(f, textvariable=self._link_var,
                               font=("Microsoft YaHei UI", 10))
        link_entry.pack(fill=tk.X, padx=20, pady=(0, 10))

        self._btn_link_login = ttk.Button(f, text="微信链接登录",
                                          command=self._do_link_login)
        self._btn_link_login.pack()

    def _build_pwd_tab(self):
        f = ttk.Frame(self._tab_pwd)
        f.pack(fill=tk.X, pady=(20, 5))

        row1 = ttk.Frame(f)
        row1.pack(fill=tk.X, padx=20, pady=4)
        ttk.Label(row1, text="账号", width=6,
                  font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT)
        self._user_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self._user_var,
                  font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT,
                                                         fill=tk.X, expand=True)

        row2 = ttk.Frame(f)
        row2.pack(fill=tk.X, padx=20, pady=4)
        ttk.Label(row2, text="密码", width=6,
                  font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT)
        self._pwd_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self._pwd_var, show="*",
                  font=("Microsoft YaHei UI", 10)).pack(side=tk.LEFT,
                                                        fill=tk.X, expand=True)

        ttk.Label(f, text="⚠ 账号密码登录不支持二维码签到",
                  font=("Microsoft YaHei UI", 8),
                  foreground="#888").pack(pady=(10, 5))

        self._btn_pwd_login = ttk.Button(f, text="账号登录",
                                         command=self._do_pwd_login)
        self._btn_pwd_login.pack(pady=(0, 10))

    # ─── 线程与 UI 调度 ───

    def _post_ui(self, func, *args, **kwargs):
        self._ui_queue.put((func, args, kwargs))

    def _drain_ui_queue(self):
        while True:
            try:
                func, args, kwargs = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                func(*args, **kwargs)
            except Exception as e:
                self._append_log(f"界面更新异常: {e}", "error")
        self._root.after(100, self._drain_ui_queue)

    def _run_bg(self, worker):
        threading.Thread(target=worker, daemon=True).start()

    def _refresh_controls(self):
        login_state = tk.DISABLED if self._login_in_flight or self._restore_in_flight or self._monitoring or self._monitor_starting else tk.NORMAL
        if hasattr(self, "_btn_link_login"):
            self._btn_link_login.configure(state=login_state)
        if hasattr(self, "_btn_pwd_login"):
            self._btn_pwd_login.configure(state=login_state)
        if hasattr(self, "_btn_toggle"):
            toggle_state = tk.DISABLED if self._login_in_flight or self._restore_in_flight else tk.NORMAL
            self._btn_toggle.configure(state=toggle_state)

    def _set_login_busy(self, busy: bool):
        self._login_in_flight = busy
        if busy:
            self._status_var.set("登录中，请稍候...")
        self._refresh_controls()

    # ─── 事件处理 ───

    def _on_tab_change(self, event):
        idx = self._notebook.index(self._notebook.select())
        if idx == 0:
            self._show_link_help()

    def _show_link_help(self):
        self._append_log(
            "\n微信链接获取方法：\n"
            "1. 在电脑端微信中，将以下链接发给文件传输助手并打开\n"
            "   https://open.weixin.qq.com/connect/oauth2/authorize"
            "?appid=wx1b5650884f657981&redirect_uri="
            "https://www.duifene.com/_FileManage/PdfView.aspx?...\n"
            "2. 点击右上角 ⋯ → 复制链接\n"
            "3. 粘贴到左侧输入框，点击登录\n",
            "info"
        )

    def _do_link_login(self):
        if self._login_in_flight or self._restore_in_flight:
            return
        if self._monitoring or self._monitor_starting:
            messagebox.showwarning("提示", "请先停止监听再重新登录")
            return
        link = self._link_var.get().strip()
        if not link or "code=" not in link:
            messagebox.showerror("错误", "请输入包含 code 参数的微信链接")
            return

        self._set_login_busy(True)

        def worker():
            msg = None
            courses = None
            error = None
            stage = "login"
            try:
                msg = self.api.login_by_wechat_link(link)
                if "成功" in msg:
                    stage = "course"
                    courses = self.api.get_course_list()
            except Exception as e:
                error = e
            self._post_ui(self._finish_login, "link", msg, courses, error, stage)

        self._run_bg(worker)

    def _do_pwd_login(self):
        if self._login_in_flight or self._restore_in_flight:
            return
        if self._monitoring or self._monitor_starting:
            messagebox.showwarning("提示", "请先停止监听再重新登录")
            return
        user = self._user_var.get().strip()
        pwd = self._pwd_var.get().strip()
        if not user or not pwd:
            messagebox.showerror("错误", "请输入账号和密码")
            return

        self._set_login_busy(True)

        def worker():
            msg = None
            courses = None
            error = None
            stage = "login"
            try:
                msg = self.api.login_by_password(user, pwd)
                if "成功" in msg:
                    stage = "course"
                    courses = self.api.get_course_list()
            except Exception as e:
                error = e
            self._post_ui(self._finish_login, "pwd", msg, courses, error, stage)

        self._run_bg(worker)

    def _finish_login(self, login_type: str, msg: str | None,
                      courses: list[dict] | None, error: Exception | None,
                      stage: str):
        self._set_login_busy(False)
        if error:
            if msg and "成功" in msg:
                self._append_log(f"{msg}\n", "success")
            if isinstance(error, PermissionError):
                self._append_log(f"会话过期: {error}\n", "warn")
                messagebox.showwarning("登录状态失效", str(error))
            else:
                title = "获取课程失败" if stage == "course" else "登录失败"
                messagebox.showerror(title, str(error))
            self._status_var.set("就绪")
            return

        if not msg:
            self._status_var.set("就绪")
            return

        if "成功" in msg:
            self._append_log(f"{msg}\n", "success")
            self._finish_load_courses(courses, restored=False)
        else:
            if login_type == "link":
                self._append_log(f"登录失败: {msg}\n", "error")
            else:
                self._append_log(f"{msg}\n", "error")
            self._status_var.set("就绪")

    def _load_courses(self):
        self._status_var.set("正在获取课程...")

        def worker():
            courses = None
            error = None
            try:
                courses = self.api.get_course_list()
            except Exception as e:
                error = e
            self._post_ui(self._finish_courses, courses, error)

        self._run_bg(worker)

    def _finish_courses(self, courses: list[dict] | None, error: Exception | None):
        if error:
            if isinstance(error, PermissionError):
                self._append_log(f"会话过期: {error}\n", "warn")
                messagebox.showwarning("登录状态失效", str(error))
            else:
                messagebox.showerror("获取课程失败", str(error))
            self._status_var.set("就绪")
            return
        self._finish_load_courses(courses, restored=False)

    def _finish_load_courses(self, courses: list[dict] | None, restored: bool):
        if not courses:
            if not restored:
                messagebox.showwarning("提示", "未获取到课程列表")
            self._status_var.set("就绪")
            return
        self._course_list = courses
        names = [c["CourseName"] for c in courses]
        self._combo["values"] = tuple(names)
        self._combo.set(names[0])
        self._on_course_select(None)
        if restored:
            self._status_var.set("已恢复登录会话")
            self._append_log("已恢复上次登录会话\n", "info")
        else:
            self._status_var.set("登录成功 — 请选择课程并开始监听")
            messagebox.showinfo("提示", "登录成功")

    def _try_restore_session(self):
        saved = self.config.load_cookie()
        if not saved:
            return
        self._restore_in_flight = True
        self._status_var.set("正在恢复登录会话...")
        self._refresh_controls()

        def worker():
            courses = None
            error = None
            try:
                courses = self.api.get_course_list()
            except Exception as e:
                error = e
                self.api.clear_session()
            self._post_ui(self._finish_restore_session, courses, error)

        self._run_bg(worker)

    def _finish_restore_session(self, courses: list[dict] | None, error: Exception | None):
        self._restore_in_flight = False
        self._refresh_controls()
        if error:
            self._status_var.set("就绪")
            return
        self._finish_load_courses(courses, restored=True)

    def _on_course_select(self, event):
        if not self._course_list:
            return
        name = self._combo_var.get()
        for c in self._course_list:
            if c["CourseName"] == name:
                self._selected_course = c
                return
        self._selected_course = self._course_list[0]

    def _toggle_monitor(self):
        if self._monitoring or self._monitor_starting:
            self._stop_monitor()
        else:
            self._start_monitor()

    def _start_monitor(self):
        if self._login_in_flight or self._restore_in_flight:
            return
        if not self._selected_course:
            messagebox.showerror("错误", "请先登录并选择课程")
            return

        try:
            countdown = int(self._countdown_var.get())
        except ValueError:
            messagebox.showerror("错误", "倒计时秒数请输入整数")
            return

        self.config.save_countdown(countdown)

        course = self._selected_course
        self._log_text.configure(state=tk.NORMAL)
        self._log_text.delete("1.0", tk.END)
        self._log_text.configure(state=tk.DISABLED)

        self._monitor_starting = True
        self._btn_toggle.configure(text="取消启动")
        self._status_var.set("正在启动监控...")
        self._refresh_controls()

        self.service.start_monitoring(
            course_id=course["CourseID"],
            class_id=course["TClassID"],
            class_name=course["CourseName"],
            countdown=countdown,
            root=self._root,
            post_ui=self._post_ui,
        )

    def _stop_monitor(self):
        self.service.stop_monitoring()
        self._monitoring = False
        self._monitor_starting = False
        self._btn_toggle.configure(text="开始监听签到")
        self._status_var.set("监控已停止")
        self._refresh_controls()

    def _on_service_state(self, state: str):
        if state == "started":
            self._monitor_starting = False
            self._monitoring = True
            self._btn_toggle.configure(text="停止监听")
            self._status_var.set(f"监控中 — {self.service.class_name}")
        elif state == "failed":
            self._monitor_starting = False
            self._monitoring = False
            self._btn_toggle.configure(text="开始监听签到")
            self._status_var.set("监控启动失败")
        elif state == "stopped":
            self._monitor_starting = False
            self._monitoring = False
            self._btn_toggle.configure(text="开始监听签到")
            self._status_var.set("监控已停止")
        self._refresh_controls()

    def _on_service_message(self, level: str, message: str):
        self._append_log(message, level)

        if level == "success":
            self._notify(f"签到成功 - {self.service.class_name}", message)
        elif level == "warn":
            self._notify("签到提醒", message)

    def _append_log(self, text: str, tag: str = "info"):
        self._log_text.configure(state=tk.NORMAL)
        timestamp = datetime.now().strftime("[%H:%M:%S] ")
        if not text.startswith("\n") and not text.startswith("["):
            text = timestamp + text
        self._log_text.insert(tk.END, text + "\n", tag)
        self._log_text.see(tk.END)
        self._log_text.configure(state=tk.DISABLED)

    def _notify(self, title: str, message: str):
        try:
            from plyer import notification
            notification.notify(
                title=title,
                message=message[:120],
                app_name="对分易自动签到",
                timeout=5,
            )
        except Exception:
            pass

    def run(self):
        self._root.mainloop()
