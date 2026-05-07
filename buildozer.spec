[app]
title = 对分易签到
package.name = duifene_sign
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,txt
version = 1.0
requirements = python3,kivy>=2.3.0,requests,beautifulsoup4,lxml,android
orientation = portrait
osx.python_version = 3
osx.kivy_version = 2.3.0
fullscreen = 0
android.permissions = INTERNET
android.api = 34
android.minapi = 24
android.ndk = 25b
android.sdk = 34
android.gradle_dependencies =
android.arch = arm64-v8a
android.allow_backup = True
android.presplash_color = #2196F3
android.icons = 96
p4a.branch = develop
p4a.bootstrap = sdl2
ios.kivy_ios_url = https://github.com/kivy/kivy-ios
ios.kivy_ios_branch = master
ios.ios_deploy_version = 12
ios.ios_project_name = duifene_sign

[buildozer]
log_level = 2
warn_on_root = 0
