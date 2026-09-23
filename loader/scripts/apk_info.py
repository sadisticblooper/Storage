#!/usr/bin/env python3
"""Extract APK metadata: manifest facts, permissions, components, native libs, signatures.

Usage: apk_info.py <apk> [--json out.json]

Uses androguard only (no JVM needed) so it runs fast in CI.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile

try:
    from loguru import logger as _lg

    _lg.remove()  # androguard is chatty on stderr
except Exception:  # pragma: no cover
    pass

from androguard.core.apk import APK  # noqa: E402


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect(apk_path: str) -> dict:
    apk = APK(apk_path)
    zf = zipfile.ZipFile(apk_path)

    native = {}
    for name in zf.namelist():
        if name.startswith("lib/") and name.endswith(".so"):
            native.setdefault(name.split("/")[1], []).append(name.split("/")[-1])
    for arch in native:
        native[arch].sort()

    dex_entries = sorted(
        n for n in zf.namelist() if n.endswith(".dex") and "/" not in n
    )

    return {
        "path": apk_path,
        "sha256": sha256(apk_path),
        "size_bytes": zf.fp.seek(0, 2) if False else None,
        "package": apk.get_package(),
        "app_name": apk.get_app_name(),
        "version_name": apk.get_androidversion_name(),
        "version_code": apk.get_androidversion_code(),
        "min_sdk": apk.get_min_sdk_version(),
        "target_sdk": apk.get_target_sdk_version(),
        "application_class": apk.get_attribute_value("application", "name"),
        "app_component_factory": apk.get_attribute_value(
            "application", "appComponentFactory"
        ),
        "debuggable": apk.get_attribute_value("application", "debuggable"),
        "permissions": sorted(apk.get_permissions()),
        "activities": sorted(apk.get_activities()),
        "services": sorted(apk.get_services()),
        "receivers": sorted(apk.get_receivers()),
        "providers": sorted(apk.get_providers()),
        "main_activity": apk.get_main_activity(),
        "dex_files": dex_entries,
        "native_libs": native,
        "is_signed_v1": apk.is_signed_v1(),
        "is_signed_v2": apk.is_signed_v2(),
        "is_signed_v3": apk.is_signed_v3(),
        "certificates": sorted(apk.get_certificates_der_v3() or []) and "v3" or (
            "v2" if apk.is_signed_v2() else ("v1" if apk.is_signed_v1() else "unsigned")
        ),
        "zip_entries": len(zf.namelist()),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("apk")
    ap.add_argument("--json", dest="json_out")
    args = ap.parse_args()

    info = collect(args.apk)
    info["size_bytes"] = __import__("os").path.getsize(args.apk)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(info, fh, indent=2, sort_keys=True)

    print(f"package        : {info['package']}")
    print(f"app name       : {info['app_name']}")
    print(f"version        : {info['version_name']} (code {info['version_code']})")
    print(f"sdk            : min={info['min_sdk']} target={info['target_sdk']}")
    print(f"application    : {info['application_class']}")
    print(f"appCompFactory : {info['app_component_factory']}")
    print(f"main activity  : {info['main_activity']}")
    print(f"sha256         : {info['sha256']}")
    print(f"signed         : v1={info['is_signed_v1']} v2={info['is_signed_v2']} v3={info['is_signed_v3']}")
    print(f"zip entries    : {info['zip_entries']}")
    print(f"permissions    : {len(info['permissions'])}")
    print(f"activities     : {len(info['activities'])}")
    print(f"services       : {len(info['services'])}")
    print(f"receivers      : {len(info['receivers'])}")
    print(f"providers      : {len(info['providers'])}")
    print(f"dex files      : {', '.join(info['dex_files']) or '(none)'}")
    for arch, libs in sorted(info["native_libs"].items()):
        print(f"  lib/{arch}: {', '.join(libs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
