[app]
title = 对分易签到
package.name = duifene_sign
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,txt
version = 1.1
requirements = python3,kivy==2.3.1,requests==2.34.2
services = monitor:service/main.py:foreground:sticky:foregroundServiceType=dataSync
orientation = portrait
osx.python_version = 3
osx.kivy_version = 2.3.0
fullscreen = 0
android.permissions = INTERNET, ACCESS_NETWORK_STATE, FOREGROUND_SERVICE, FOREGROUND_SERVICE_DATA_SYNC, POST_NOTIFICATIONS
android.api = 35
android.minapi = 29
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = True
android.presplash_color = #2196F3
android.icons = 96
p4a.bootstrap = sdl2
ios.kivy_ios_url = https://github.com/kivy/kivy-ios
ios.kivy_ios_branch = master
ios.ios_deploy_version = 12
ios.ios_project_name = duifene_sign

[buildozer]
log_level = 2
warn_on_root = 0
