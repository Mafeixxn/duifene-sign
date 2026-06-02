# Windows 版 UI 现代化 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 sv_ttk 主题替换原生 tkinter 样式，实现极简浅色现代化 UI，零功能改动。

**Architecture:** 仅修改 `windows/app.py` 和 `windows/requirements.txt`。在 `App.__init__` 中 `_build_ui()` 之前注入 sv_ttk 主题，再通过 ttk.Style 覆写局部配色。ScrolledText（tk 原生组件）手动调色以匹配。

**Tech Stack:** Python 3.8+, tkinter, sv_ttk

---

### Task 1: 添加 sv_ttk 依赖并安装

**Files:**
- Modify: `windows/requirements.txt`

- [ ] **Step 1: 在 requirements.txt 中添加 sv_ttk**

```diff
 requests>=2.31.0
 beautifulsoup4>=4.12.0
 lxml>=5.0.0
 plyer>=2.0.0
+sv_ttk>=2.3.0
```

- [ ] **Step 2: 安装依赖**

```bash
pip install sv_ttk
```

Expected: `Successfully installed sv_ttk-x.x.x`

- [ ] **Step 3: 提交**

```bash
git add windows/requirements.txt
git commit -m "deps: add sv_ttk for UI theming"
```

---

### Task 2: 在 app.py 中注入 sv_ttk 主题 + 统一字体

**Files:**
- Modify: `windows/app.py`

- [ ] **Step 1: 添加导入和主题调用**

在 `App.__init__` 中，`tk.Tk()` 创建之后、`_build_ui()` 之前插入 sv_ttk 初始化和字体设置：

```python
# 文件顶部 import 区，在 from sign_service import SignService 之后添加：
import sv_ttk

# App.__init__ 中，在 self._root.geometry("700x580") 之后、self._ui_queue 之前插入：
        self._root.option_add("*Font", ("Microsoft YaHei UI", 9))
        sv_ttk.set_theme("light")

        style = ttk.Style()
        style.configure(".", font=("Microsoft YaHei UI", 9))
        style.configure("TNotebook.Tab", font=("Microsoft YaHei UI", 9))
        style.configure("TButton", font=("Microsoft YaHei UI", 9))
        style.configure("TLabel", font=("Microsoft YaHei UI", 9))
        style.configure("TEntry", font=("Microsoft YaHei UI", 9))
        style.configure("TCombobox", font=("Microsoft YaHei UI", 9))
```

- [ ] **Step 2: 调整控件 padding**

在同样位置（`_build_ui` 之前的 style 配置块中）增加间距：

```python
        style.configure("TButton", padding=(12, 6))
        style.configure("TEntry", padding=(8, 6))
        style.configure("TNotebook.Tab", padding=(16, 6))
```

- [ ] **Step 3: 提交**

```bash
git add windows/app.py
git commit -m "feat: enable sv_ttk light theme with unified fonts"
```

---

### Task 3: 覆写日志区与配色以匹配极简浅色

**Files:**
- Modify: `windows/app.py`

sv_ttk 不会动 `ScrolledText`（它是 tk 原生组件），需要手动调整其背景色和文字色来匹配浅色主题。同时将 log tag 颜色统一到极简浅色调色板。

- [ ] **Step 1: 调整 ScrolledText 的配色**

`_build_ui` 中 `_log_text` 所在地（第77-85行），改字体和背景色：

```python
        self._log_text = scrolledtext.ScrolledText(
            log_frame, width=80, height=20,
            font=("Microsoft YaHei UI", 9), state=tk.DISABLED,
            bg="#FAFBFC", fg="#1F2937",
            relief=tk.FLAT, borderwidth=0,
            padx=10, pady=8,
        )
```

- [ ] **Step 2: 更新 log tag 颜色**

```python
        self._log_text.tag_config("success", foreground="#22A861")
        self._log_text.tag_config("error", foreground="#DC143C")
        self._log_text.tag_config("warn", foreground="#EB7D00")
        self._log_text.tag_config("info", foreground="#1F2937")
```

- [ ] **Step 3: 调整状态栏样式**

将状态栏的 `relief=tk.SUNKEN` 改为更现代化的扁平样式：

```python
        status_bar = ttk.Label(self._root, textvariable=self._status_var,
                               anchor=tk.W, padding=(10, 4),
                               background="#ECEFF4", foreground="#6B7280")
```

- [ ] **Step 4: 调整各标签的 padding 使整体更透气**

- `_build_link_tab`: 将 `f.pack(fill=tk.X, pady=(20, 5))` 改为 `pady=(15, 8)`
- `_build_pwd_tab`: 将 `f.pack(fill=tk.X, pady=(20, 5))` 改为 `pady=(15, 8)`
- 控制栏: 将 `ctrl.pack(fill=tk.X, padx=10, pady=(10, 0))` 改为 `padx=12, pady=(12, 0)`
- 日志区: 将 `log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))` 改为 `padx=12, pady=(10, 4)`

- [ ] **Step 5: 调整窗口尺寸以容纳新 padding**

将 `self._root.geometry("700x580")` 改为 `"720x600"`

- [ ] **Step 6: 提交**

```bash
git add windows/app.py
git commit -m "style: adjust colors, spacing, and log area for modern look"
```

---

### Task 4: 视觉验证

**目标：** 启动程序，确认 UI 正常渲染、无崩溃、所有功能可用。

- [ ] **Step 1: 启动程序进行冒烟测试**

```bash
cd windows && python main.py
```

肉眼检查：
- [ ] 窗口正常显示，标题栏正确
- [ ] Notebook 两个 tab 正常切换
- [ ] 微信链接登录 tab：说明文本 + 链接完整显示 + 输入框 + 按钮
- [ ] 账号密码登录 tab：账号/密码输入框 + 警告文本 + 登录按钮
- [ ] 控制栏：课程下拉框 + 提前秒数输入 + 按钮
- [ ] 日志区：背景色匹配主题、文字颜色正确
- [ ] 状态栏：底部扁平风格、文字居中
- [ ] 字体统一为 Microsoft YaHei UI
- [ ] 按钮有圆角效果（sv_ttk 自带）

- [ ] **Step 2: 交互测试**

- [ ] 切换 tab 时日志区显示正确帮助信息
- [ ] 未输入内容点登录，弹窗正常
- [ ] 日志文字滚动正常

- [ ] **Step 3: 无崩溃确认**

程序启动后停留 2 分钟，无卡死、无崩溃、无异常日志。

---

### Task 5: 提交最终结果

- [ ] **Step 1: 如有遗留改动，提交**

```bash
git add windows/app.py
git commit -m "style: final polish — padding, colors, status bar"
```

- [ ] **Step 2: 查看最终状态**

```bash
git log --oneline -5
```

确认所有改动已提交。
