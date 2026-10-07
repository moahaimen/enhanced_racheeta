#!/usr/bin/env python3
"""Verifies the security-relevant properties of a built Android release APK.

Usage: tool/verify_release_apk.py <app-release.apk> [--aapt2 <path>] [--package <id>]

Checks (each failure is printed and the exit code is 1):
  * the application id;
  * the permission list is a subset of the audited allow-list;
  * allowBackup=false, usesCleartextTraffic=false, not debuggable;
  * every exported component is the launcher activity or is protected by a permission;
  * the Dart snapshot does not embed the development API fallback (http://10.0.2.2 / localhost).

It reads the compiled manifest with aapt2 (Android SDK build-tools); it never needs signing keys.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import subprocess
import sys
import zipfile

ALLOWED_PERMISSIONS = {
    "android.permission.INTERNET",  # API access
    "android.permission.POST_NOTIFICATIONS",  # Android 13+ runtime permission (push, optional)
    "android.permission.WAKE_LOCK",  # firebase_messaging
    "android.permission.ACCESS_NETWORK_STATE",  # firebase_messaging
    "com.google.android.c2dm.permission.RECEIVE",  # FCM
}
# androidx signature permission added by the support libraries for non-exported dynamic receivers.
ALLOWED_PERMISSION_SUFFIX = ".DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION"


def find_aapt2(explicit: str | None) -> str:
    if explicit:
        return explicit
    home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or ""
    candidates = sorted(glob.glob(os.path.join(home, "build-tools", "*", "aapt2")))
    if not candidates:
        sys.exit("aapt2 not found: set ANDROID_HOME or pass --aapt2")
    return candidates[-1]


def run(aapt2: str, *args: str) -> str:
    return subprocess.run([aapt2, *args], check=True, capture_output=True, text=True).stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("apk")
    parser.add_argument("--aapt2")
    parser.add_argument("--package", default="app.racheeta.racheeta_mobile")
    args = parser.parse_args()
    aapt2 = find_aapt2(args.aapt2)
    errors: list[str] = []

    badging = run(aapt2, "dump", "badging", args.apk)
    package = re.search(r"package: name='([^']+)'", badging)
    if not package or package.group(1) != args.package:
        errors.append(f"application id is {package.group(1) if package else None}, expected {args.package}")

    permissions = set(re.findall(r"uses-permission: name='([^']+)'", badging))
    for permission in sorted(permissions):
        if permission not in ALLOWED_PERMISSIONS and not permission.endswith(ALLOWED_PERMISSION_SUFFIX):
            errors.append(f"unexpected permission: {permission}")
    for required in ("android.permission.INTERNET",):
        if required not in permissions:
            errors.append(f"missing permission: {required}")

    tree = run(aapt2, "dump", "xmltree", "--file", "AndroidManifest.xml", args.apk)
    if "allowBackup(0x01010280)=false" not in tree:
        errors.append("android:allowBackup is not false")
    if "usesCleartextTraffic(0x010104ec)=false" not in tree:
        errors.append("android:usesCleartextTraffic is not false")
    if re.search(r"debuggable\(0x0101000f\)=(true|\(type 0x12\)0xffffffff)", tree):
        errors.append("the application is debuggable")

    # Walk the element tree: an exported component must be the launcher or permission-protected.
    current: dict | None = None
    components: list[dict] = []
    for line in tree.splitlines():
        element = re.match(r"\s*E: (activity|service|receiver|provider|activity-alias) ", line)
        if element:
            current = {"kind": element.group(1), "exported": False, "permission": False, "name": ""}
            components.append(current)
            continue
        if current is None:
            continue
        if re.match(r"\s*E: ", line) and not re.match(r"\s*E: (intent-filter|action|category|data|meta-data) ", line):
            current = None
            continue
        if "android:exported" in line and line.rstrip().endswith("=true"):
            current["exported"] = True
        if re.search(r"android:permission\(", line):
            current["permission"] = True
        name = re.search(r'android:name\(0x01010003\)="([^"]+)"', line)
        if name and not current["name"]:
            current["name"] = name.group(1)
    for component in components:
        if not component["exported"]:
            continue
        if component["kind"] == "activity" and component["name"].endswith("MainActivity"):
            continue
        if not component["permission"]:
            errors.append(f"exported {component['kind']} without a permission: {component['name']}")

    with zipfile.ZipFile(args.apk) as apk:
        for name in apk.namelist():
            if name.endswith("libapp.so"):
                data = apk.read(name)
                for needle in (b"http://10.0.2.2", b"http://localhost", b"http://127.0.0.1"):
                    if needle in data:
                        errors.append(f"{name} embeds a development URL: {needle.decode()}")

    if errors:
        print("RELEASE APK CHECK FAILED")
        for error in errors:
            print(" -", error)
        return 1
    print(f"release APK ok: {args.package}, {len(permissions)} permissions, {len(components)} components")
    return 0


if __name__ == "__main__":
    sys.exit(main())
