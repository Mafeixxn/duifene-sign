<p align="center">
  <h1 align="center">对分易自动签到</h1>
  <p align="center">自动监控对分易教学平台签到，支持数字码、二维码和 GPS 定位签到。</p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20Android-lightgrey.svg" alt="Platform">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/github/v/release/Mafeixxn/duifene-sign" alt="Release">
  <img src="https://img.shields.io/github/stars/Mafeixxn/duifene-sign?style=social" alt="Stars">
</p>

---

## 目录

- [项目简介](#-项目简介)
- [快速下载](#-快速下载)
- [功能特性](#-功能特性)
- [签到类型支持](#-签到类型支持)
- [Windows 桌面版使用](#windows-桌面版使用)
- [Android 版使用](#-android-版使用)
- [目录结构](#-目录结构)
- [自动构建](#-自动构建)
- [主要依赖](#-主要依赖)
- [免责声明](#免责声明)

---

## 📖 项目简介

对分易自动签到是一款用于学习和交流的自动签到工具，提供 Windows 桌面版和 Android 移动版。程序可以登录对分易账号、读取课程列表、监听签到任务，并在老师发布签到后自动完成签到，即使是二维码签到也不用去到教室

本项目支持两种登录方式：

| 登录方式 | 支持能力 | 备注 |
|----------|----------|------|
| 微信 OAuth 链接登录 | 数字码、二维码、GPS 三种签到类型 | 推荐使用 |

> [!WARNING]
> - 经过测试,有一部分手机无法使用,具体原因未知
> - 监听签到期间请关闭代理/VPN 软件，否则有概率导致签到请求连接超时，错过签到
> - 使用前务必先创一个课程测试一下,有问题就反馈一下,后续我可能会改进
  
## 📥 快速下载

| 版本 | 适用平台 | 获取方式 | 适合场景 |
|------|----------|----------|----------|
| Android APK | Android 10+ (API 29) | 下载 [`android/duifene_sign.apk`](android/duifene_sign.apk) | 手机直接安装使用 |
| Windows 桌面版 | Windows 10 / 11 | [GitHub Releases](../../releases) 下载 exe，或克隆仓库运行源码 | 桌面监听、调试和打包 |

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| 微信链接登录 | 粘贴微信 OAuth 回调链接即可登录。 |
| 会话保持 | 自动保存 Cookie，下次启动可恢复登录状态。 |
| 配置保护 | Windows 版使用本地 `duifenyi.ini` 保存运行配置，仓库仅保留 `duifenyi.example.ini` 模板。 |
| 课程选择 | 自动拉取课程列表，支持切换目标课程。 |
| 提前签到 | 可设置倒计时提前量，提前尝试完成签到。 |
| 签到通知 | Windows 版支持桌面通知提醒签到结果。 |
| 多端支持 | 提供 Windows tkinter 桌面版和 Android Kivy 版。 |

## 📋 签到类型支持

| 签到类型 | Windows 版 | Android 版 | 说明 |
|----------|:----------:|:----------:|------|
| 数字签到码 | 支持 | 支持 | 自动提交签到码 |
| 二维码签到 | 支持 | 支持 | 仅微信链接登录支持 |
| GPS 定位签到 | 支持 | 支持 | 自动按老师发布的坐标签到 |

## 🖥️ Windows 桌面版使用

> [!IMPORTANT]
> 如果直接下载 exe，可以跳过“安装依赖”和“启动程序”，直接从“登录方式”开始。

### 1. 安装依赖

> [!TIP]
> Windows 源码运行建议使用 Python 3.10 及以上版本。

```bash
git clone https://github.com/Mafeixxn/duifene-sign.git
cd duifene-sign/windows
pip install -r requirements.txt
```

### 2. 启动程序

```bash
python main.py
```

也可以双击 `对分易签到.pyw` 启动无控制台窗口版本

> [!NOTE]
> 程序首次运行会在本地生成或更新 `duifenyi.ini`。该文件可能包含用于恢复登录状态的 Cookie，请不要提交到 Git，也不要分享给他人。

### 3. 登录方式

#### 微信链接登录（推荐）

1. 在电脑端微信中打开下面的链接，可以先发送到文件传输助手：

   ```text
   https://open.weixin.qq.com/connect/oauth2/authorize?appid=wx1b5650884f657981&redirect_uri=https%3A%2F%2Fwww.duifene.com%2F_FileManage%2FPdfView.aspx&response_type=code&scope=snsapi_base&state=1#wechat_redirect
   ```

2. 打开后点击右上角菜单，复制当前链接
3. 将复制到的链接粘贴到程序输入框，点击登录

### 4. 开始签到

1. 登录成功后，在课程下拉框中选择需要监听的课程
2. 设置倒计时提前量，单位为秒
3. 点击「开始监听签到」
4. 等待老师发布签到，程序会自动尝试完成签到

## 📱 Android 版使用

### 直接安装

下载 [`android/duifene_sign.apk`](android/duifene_sign.apk) 并安装到 Android 手机即可

具体步骤

1.在微信将上面链接发到聊天里面(或者收藏),然后点开,出现一个PDF文件预览画面(无内容)

2.点开右上角三个点,在浏览器打开

3.然后复制浏览器里面的链接

4.将链接粘贴到本软件的oauth链接输入框,点微信登录


### 自行构建 APK

可以使用 [`android/build_apk.ipynb`](android/build_apk.ipynb) 在 Google Colab 中构建 APK：

1. 将 `android/build_apk.ipynb` 上传到 [Google Colab](https://colab.research.google.com/)
2. 全部运行 Notebook，并按提示授权 Google Drive
3. 等待约 15-25 分钟完成构建
4. 生成的 APK 会自动保存到 Google Drive 根目录

### 本地开发调试

```bash
cd android
pip install -r requirements.txt
python main.py
```

## 📁 目录结构

```text
├── android/              # Android Kivy 版
│   ├── main.py           # Kivy UI 主程序
│   ├── api_client.py     # 对分易 API 封装
│   ├── sign_service.py   # 签到监控逻辑
│   ├── buildozer.spec    # Buildozer 打包配置
│   ├── requirements.txt  # 依赖清单
│   ├── build_apk.ipynb   # Google Colab 构建脚本
│   └── duifene_sign.apk  # 预构建 APK 安装包
├── windows/              # Windows tkinter 桌面版
│   ├── main.py              # 程序入口
│   ├── app.py               # tkinter 图形界面
│   ├── api_client.py        # 对分易 API 封装
│   ├── sign_service.py      # 签到监控逻辑
│   ├── config_manager.py    # 配置存取
│   ├── duifenyi.example.ini # 配置模板，实际运行使用本地 duifenyi.ini
│   ├── requirements.txt     # 依赖清单
│   └── 对分易签到.pyw        # 无控制台启动入口
├── LICENSE
└── README.md
```

## 🔧 自动构建

推送版本标签（`v*`）后，GitHub Actions 会自动构建 Windows exe 并发布到 [Releases](../../releases)，同时附带预构建的 Android APK

> [!TIP]
> 发布前建议确认：
>
> - Windows 依赖已安装完整。
> - `duifenyi.ini` 没有被提交或打包进源码仓库。
> - Release 页面中的 exe 与当前标签版本一致。

## 📦 主要依赖

| 依赖 | 用途 |
|------|------|
| requests | HTTP 请求（双平台） |
| beautifulsoup4 | Windows 版 HTML 解析 |
| lxml | Windows 版 HTML 解析引擎 |
| tkinter | Windows 桌面 GUI |
| plyer | Windows 桌面通知 |
| kivy | Android 移动端 GUI |
| buildozer | Android APK 打包 |

## 效果截图
二维码签到
<img width="1886" height="816" alt="Snipaste_2026-06-02_12-44-26" src="https://github.com/user-attachments/assets/88b0d6f6-f292-43b4-b80b-7996cc8b24f5" />

定位签到
<img width="1762" height="1071" alt="Snipaste_2026-06-02_12-40-17" src="https://github.com/user-attachments/assets/c2519d74-142b-4a8e-9b45-1e538590e286" />

签到码签到
<img width="1742" height="669" alt="Snipaste_2026-06-02_12-42-56" src="https://github.com/user-attachments/assets/8d5019af-ec6b-4b48-b785-6852b5177839" />


## 🙏 致谢

本项目参考了 [liuzhijie443/duifene_auto_sign](https://github.com/liuzhijie443/duifene_auto_sign) 的实现思路

## ⚠️ 免责声明

本项目仅供学习交流和技术研究使用，请遵守学校、课程和平台的相关规定。因使用本项目产生的任何后果由使用者自行承担

## 📄 License

[![MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## Android 10+ Usage Notes

Android 版本需要 **Android 10（API 29）或更高版本**，仅支持通过微信 OAuth 回调链接登录。程序不提供账号、密码登录入口；请按上文步骤将微信中复制的 OAuth 链接粘贴到应用中。

开始监听后，应用会启动一个前台服务并显示持续通知。这使监听在应用转入后台或设备锁屏后仍能继续；请保留该通知，并不要从系统设置中强行停止应用。

Android 13 及更高版本在首次开始监听前会请求「通知」权限，请选择允许。若权限被拒绝、通知被关闭，或系统限制了后台活动，监听可能会被中断。

> [!TIP]
> 为获得较可靠的后台行为，请将本应用设为允许后台运行，并在手机的电池优化、节电、自启动、任务清理等设置中排除或允许它。不同厂商的系统策略不同，无法保证在所有设备上都不会被系统停止。
