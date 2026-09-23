#!/usr/bin/env python3
"""Compare two APKs: zip entry diff, manifest delta, and dex class-set delta.

Usage:
    apk_diff.py BASE.apk MODIFIED.apk [--json out.json] [--limit N]

Designed to answer "what changed between these two builds?" without a JVM,
so it is cheap enough to run on every push.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile

try:
    from loguru import logger as _lg

    _lg.remove()
except Exception:  # pragma: no cover
    pass

from androguard.core.apk import APK  # noqa: E402


def entry_hashes(path: str) -> dict[str, str]:
    out = {}
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            h = hashlib.sha256(zf.read(info.filename)).hexdigest()
            out[info.filename] = h
    return out


def class_set(apk_path: str) -> set[str]:
    """All class descriptors across top-level and nested dex files."""
    apk = APK(apk_path)
    names: set[str] = set()
    for dex in apk.get_all_dex():
        try:
            from androguard.core.dex import DEX

            d = DEX(dex)
            names.update(d.get_classes_names())
        except Exception:
            continue
    return names


def zip_diff(base: dict[str, str], mod: dict[str, str]) -> dict:
    bk, mk = set(base), set(mod)
    return {
        "added": sorted(mk - bk),
        "removed": sorted(bk - mk),
        "modified": sorted(k for k in (bk & mk) if base[k] != mod[k]),
        "unchanged": len(bk & mk) - len([k for k in (bk & mk) if base[k] != mod[k]]),
    }


def manifest_delta(base_apk: APK, mod_apk: APK) -> dict:
    fields = {
        "package": lambda a: a.get_package(),
        "version_name": lambda a: a.get_androidversion_name(),
        "version_code": lambda a: a.get_androidversion_code(),
        "application_class": lambda a: a.get_attribute_value("application", "name"),
        "app_component_factory": lambda a: a.get_attribute_value(
            "application", "appComponentFactory"
        ),
        "min_sdk": lambda a: a.get_min_sdk_version(),
        "target_sdk": lambda a: a.get_target_sdk_version(),
        "main_activity": lambda a: a.get_main_activity(),
    }
    delta = {}
    for name, fn in fields.items():
        try:
            b, m = fn(base_apk), fn(mod_apk)
        except Exception:
            continue
        if b != m:
            delta[name] = {"base": b, "modified": m}

    for label, getter in (
        ("permissions", lambda a: set(a.get_permissions())),
        ("activities", lambda a: set(a.get_activities())),
        ("services", lambda a: set(a.get_services())),
        ("receivers", lambda a: set(a.get_receivers())),
        ("providers", lambda a: set(a.get_providers())),
    ):
        try:
            b, m = getter(base_apk), getter(mod_apk)
        except Exception:
            continue
        if b != m:
            delta[label] = {
                "added": sorted(m - b),
                "removed": sorted(b - m),
            }
    return delta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("modified")
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--limit", type=int, default=40, help="max entries listed per section")
    args = ap.parse_args()

    base_h = entry_hashes(args.base)
    mod_h = entry_hashes(args.modified)
    zd = zip_diff(base_h, mod_h)

    base_apk, mod_apk = APK(args.base), APK(args.modified)
    md = manifest_delta(base_apk, mod_apk)

    bc, mc = class_set(args.base), class_set(args.modified)
    cd = {
        "base_class_count": len(bc),
        "modified_class_count": len(mc),
        "added": sorted(mc - bc),
        "removed": sorted(bc - mc),
    }

    result = {"zip": zd, "manifest": md, "dex_classes": cd}

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, sort_keys=True)

    lim = args.limit
    print("=== ZIP entries ===")
    print(f"  base={len(base_h)} modified={len(mod_h)} unchanged={zd['unchanged']}")
    for label in ("added", "removed", "modified"):
        items = zd[label]
        print(f"  {label}: {len(items)}")
        for n in items[:lim]:
            print(f"    {n}")
        if len(items) > lim:
            print(f"    ... and {len(items) - lim} more")

    print("\n=== Manifest delta ===")
    if not md:
        print("  (no changes in tracked manifest fields)")
    for k, v in md.items():
        if "base" in v:
            print(f"  {k}: {v['base']!r} -> {v['modified']!r}")
        else:
            print(f"  {k}: +{len(v['added'])} / -{len(v['removed'])}")
            for n in v["added"][:lim]:
                print(f"    + {n}")
            for n in v["removed"][:lim]:
                print(f"    - {n}")

    print("\n=== DEX classes ===")
    print(f"  base={cd['base_class_count']} modified={cd['modified_class_count']}")
    print(f"  added: {len(cd['added'])}  removed: {len(cd['removed'])}")
    for n in cd["added"][:lim]:
        print(f"    + {n}")
    if len(cd["added"]) > lim:
        print(f"    ... and {len(cd['added']) - lim} more")
    for n in cd["removed"][:lim]:
        print(f"    - {n}")
    if len(cd["removed"]) > lim:
        print(f"    ... and {len(cd['removed']) - lim} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
