8-Bit Theater Reader - Android APK Project
===============================================

Files
-----
main.py
    The Kivy reader app.

buildozer.spec
    Android package settings.

.github/workflows/build-android.yml
    GitHub Actions workflow that builds the APK.

How the app accesses the comics
-------------------------------
This personal sideloaded build reads the existing folder:

/storage/emulated/0/Download/8BitTheater

On first launch Android will require "All files access".
Tap "Grant File Access", enable the permission for the app,
then return to the reader.

The app stores only its reading-position state inside its own
private app data. It does not modify the comic images.

Build
-----
Upload this project to a GitHub repository.

The included GitHub Actions workflow builds the APK on:
- every push to the main branch
- manual Workflow Dispatch

When the build finishes, open the Actions run and download the
artifact named:

8-Bit-Theater-Reader-APK

Extract the ZIP downloaded from GitHub Actions, then tap the APK
on the Samsung phone to install it.

Note
----
Android may show a warning when installing an APK downloaded
outside the Play Store. You may need to allow "Install unknown
apps" for the browser or file manager you use.

This project uses MANAGE_EXTERNAL_STORAGE because it is the
simplest way for this personal sideloaded app to read the comics
already stored in Downloads. This is intentionally a personal
sideload setup, not a Play Store configuration.
