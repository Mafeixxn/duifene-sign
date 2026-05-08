<p align="center">
  <h1 align="center">对分易自动签到</h1>
  <p align="center">自动监控对分易教学平台签到，支持数字码 / 二维码 / GPS 三种签到类型。</p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20Android-lightgrey.svg" alt="Platform">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs">
</p>

---

## 快速下载

| 版本 | 适用平台 | 下载 |
|------|---------|------|
| Android APK | Android 7.0+ | [duifene_sign.apk](android/duifene_sign.apk) |
| Windows 桌面版 | Windows 10/11 | 克隆仓库运行源码 |

## 功能

- **微信链接登录** — 粘贴 OAuth 链接即可登录，支持全部签到类型
- **账号密码登录** — 直接输入对分易账号密码（不支持二维码签到）
- **会话保持** — 自动保存 Cookie，下次启动恢复登录
- **多课程切换** — 自动拉取课程列表，选择目标课程
- **倒计时提前** — 可设置提前签到秒数
- **系统通知** — 签到结果桌面弹窗提醒（Windows 版）

## 签到类型支持

| 类型 | Windows 版 | Android 版 | 说明 |
|------|:---:|:---:|------|
| 数字签到码 (1) | ✅ | ✅ | 自动发送签到码 |
| 二维码 (2) | ✅ | ✅ | 仅微信链接登录支持 |
| GPS 定位 (3) | ✅ | ✅ | 自动按老师坐标签到 |

## 目录结构

```
├── android/              # Android Kivy 版
│   ├── main.py           # Kivy UI 主程序
│   ├── api_client.py     # 对分易 API 封装
│   ├── sign_service.py   # 签到监控逻辑
│   ├── buildozer.spec    # Buildozer 打包配置
│   ├── build_apk.ipynb   # Google Colab 构建脚本
│   └── duifene_sign.apk  # 预构建 APK 安装包
├── windows/              # Windows tkinter 桌面版
│   ├── main.py           # 程序入口
│   ├── app.py            # tkinter 图形界面
│   ├── api_client.py     # 对分易 API 封装
│   ├── sign_service.py   # 签到监控逻辑
│   ├── config_manager.py # 配置存取
│   └── duifenyi.ini      # 配置文件模板
└── LICENSE
```

## Windows 桌面版使用

### 安装

```bash
git clone https://github.com/Mafeixxn/duifene-sign.git
cd duifene-sign/windows
pip install -r requirements.txt
```

### 运行

```bash
python main.py
```

或双击 `对分易签到.pyw`（无控制台窗口）。

### 登录方式

**微信链接登录（推荐）：**
1. 电脑端微信打开以下链接（发到文件传输助手）：
   ```
   https://open.weixin.qq.com/connect/oauth2/authorize?appid=wx1b5650884f657981&redirect_uri=https://www.duifene.com/_FileManage/PdfView.aspx&response_type=code&scope=snsapi_base&state=1#wechat_redirect
   ```
2. 点击右上角 ⋯ → 复制链接
3. 粘贴到程序输入框，点击登录

**账号密码登录：**
- 直接输入对分易账号和密码
- ⚠️ 此方式不支持二维码签到

### 签到流程

1. 登录后在课程下拉框选择目标课程
2. 设置倒计时提前量（秒）
3. 点击「开始监听签到」
4. 等待老师发布签到，程序自动完成

## Android 版使用

### 直接安装

下载 [duifene_sign.apk](android/duifene_sign.apk) 安装到手机即可。

### 自行构建

使用 [Google Colab notebook](android/build_apk.ipynb) 自行构建：

1. 将 `android/build_apk.ipynb` 上传到 [Google Colab](https://colab.research.google.com/)
2. 全部运行 → 授权 Google Drive
3. 等待 15-25 分钟构建
4. APK 自动保存到 Google Drive 根目录

### 本地开发调试

```bash
cd android
pip install -r requirements.txt
python main.py
```

## 依赖

| 包 | 用途 |
|------|------|
| requests | HTTP 请求 |
| beautifulsoup4 | HTML 解析 |
| lxml (Windows) / html.parser (Android) | 解析引擎 |
| tkinter (Windows 内置) | 桌面 GUI |
| kivy + buildozer (Android) | 移动端 GUI + 打包 |
| plyer (Windows) | 桌面通知 |

## 致谢

本项目参考了 [liuzhijie443/duifene_auto_sign](https://github.com/liuzhijie443/duifene_auto_sign) 的实现思路。

## 免责声明

本项目仅供学习交流使用，请遵守学校相关规定。使用者自行承担一切责任。

## License

[MIT](LICENSE)
