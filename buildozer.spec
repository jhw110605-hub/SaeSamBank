[app]
title = 새삼은행
package.name = saesambank
package.domain = org.saesam

source.dir = .
source.include_exts = py,kv,png,jpg,ttf
source.include_patterns = fonts/*
source.exclude_dirs = .github,bin,.buildozer

version = 0.1
requirements = python3,kivy==2.3.0

orientation = portrait
fullscreen = 0

android.api = 33
android.minapi = 21
android.archs = arm64-v8a
android.accept_sdk_license = True
android.permissions =

[buildozer]
log_level = 2
warn_on_root = 1
