# Windows 版 UI 现代化设计

## 目标

在不改动功能和布局的前提下，美化 Windows 版的视觉外观，使其更现代化。同时确保零闪退、零功能回归。

## 方案

使用 `sv_ttk` (Sun Valley ttk 主题) 替换原生 tkinter 控件样式，搭配少量配色覆写。

**选型理由：** sv_ttk 是纯 ttk 主题定义，不 hook 任何 tkinter 底层行为，兼容性最高，不会引入崩溃风险。

## 改动范围

| 文件 | 改动 |
|------|------|
| `windows/requirements.txt` | 新增 `sv_ttk` 依赖 |
| `windows/app.py` | 导入 sv_ttk、设置主题、调整配色/字体/Padding |
| `windows/main.py` | 不改 |
| `windows/api_client.py` | 不改 |
| `windows/sign_service.py` | 不改 |
| `windows/config_manager.py` | 不改 |

## 具体改动

### 1. 引入 sv_ttk 主题

```python
import sv_ttk
sv_ttk.set_theme("light")
```

在 `App.__init__` 中、`_build_ui` 之前调用。

### 2. 配色覆写

```python
COLORS = {
    "bg":        "#FAFBFC",
    "fg":        "#1F2937",
    "accent":    "#4F6EF7",
    "success":   "#22A861",
    "error":     "#DC143C",
    "warn":      "#EB7D00",
}
```

- ttk.Style 覆写按钮色、标签色等
- 日志 tag 颜色使用新配色
- 状态栏背景调为浅色

### 3. 字体统一

全局默认字体设为 `Microsoft YaHei UI` 9pt，等宽日志字体保持 `Microsoft YaHei UI`。

### 4. 间距优化

- 控件 padding 从默认值增加到 6-10px
- notebook tab padding 调整

### 5. 初始提示文案修正

将 `_show_link_help` 中拆分截断的微信 OAuth 链接替换为完整 URL 编码版本。

## 不改的内容

- resizable=False
- 所有控件布局、层级结构
- 所有事件回调、线程模型、UI 队列
- 日志消息内容（除初始帮助文案的链接修正）

## 风险

- sv_ttk 只依赖 tkinter 标准库，无 C 扩展
- 改动限定在一个文件，回退只需 `git checkout windows/app.py`
- sv_ttk "light" 主题在 Windows 7/10/11 上表现一致
