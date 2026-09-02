[app]

title = 8-Bit Theater Reader
package.name = eightbittheaterreader
package.domain = org.offlinereader

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json

version = 1.0.0

requirements = python3,kivy,pyjnius

orientation = portrait
fullscreen = 0

# This permission is used so the sideloaded app can read the existing
# /storage/emulated/0/Download/8BitTheater folder directly.
android.permissions = MANAGE_EXTERNAL_STORAGE

# The permission API used by this project was added in Android 11.
android.minapi = 30

# Modern Samsung phones are ARM64.
android.archs = arm64-v8a

android.private_storage = True
android.accept_sdk_license = True
android.debug_artifact = apk


# Use python-for-android with the July 30, 2026 fix for
# temporary pip/venv corruption during dependency installation.
p4a.branch = develop
p4a.commit = 0382d27

[buildozer]

log_level = 2
warn_on_root = 1
