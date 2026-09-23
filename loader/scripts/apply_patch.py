#!/usr/bin/env python3
"""Apply a declarative patch spec to an apktool-decoded APK directory.

The point of a spec file is that every change is reviewable in the repo
instead of being hidden inside a rebuild. Supported operations:

  manifest:            set application-level manifest attributes
  manifest_component:  add/remove entries from a component list
  copy:                replace/add a file (dex, so, asset) from a source path
  delete:              remove a file from the decoded tree
  strings:             find/replace inside decoded smali/xml text files

Usage:
    apply_patch.py <decoded_dir> <patch.yml|patch.json> [--dry-run]

Example spec is in patches/example.yml.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from xml.etree import ElementTree as ET

ANDROID_NS = "http://schemas.android.com/apk/res/android"


def load_spec(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if path.endswith((".yml", ".yaml")):
        try:
            import yaml
        except ImportError:
            print("[x] PyYAML required for .yml specs: pip install pyyaml", file=sys.stderr)
            raise SystemExit(2)
        return yaml.safe_load(text)
    return json.loads(text)


def q(attr: str) -> str:
    return f"{{{ANDROID_NS}}}{attr}"


def set_manifest_attrs(manifest_path: str, attrs: dict, dry: bool, report: list) -> None:
    """Set <manifest> root attributes (package, versionName, versionCode...)."""
    ET.register_namespace("android", ANDROID_NS)
    tree = ET.parse(manifest_path)
    root = tree.getroot()
    for key, value in attrs.items():
        old = root.get(key) or root.get(q(key))
        if old == value:
            report.append(f"  = manifest@{key} already {value!r}")
            continue
        report.append(f"  ~ manifest@{key}: {old!r} -> {value!r}")
        if not dry:
            if value is None:
                root.attrib.pop(key, None)
                root.attrib.pop(q(key), None)
            else:
                # keep the android: prefix for namespaced attrs, plain for
                # package/versionName/versionCode which are un-namespaced
                if key in ("package", "versionName", "versionCode",
                           "platformBuildVersionCode", "platformBuildVersionName"):
                    root.set(key, str(value))
                else:
                    root.set(q(key), str(value))
    if not dry:
        tree.write(manifest_path, encoding="utf-8", xml_declaration=True)


def set_application_attrs(manifest_path: str, attrs: dict, dry: bool, report: list) -> None:
    """Set <application> attributes (name, label, appComponentFactory...)."""
    ET.register_namespace("android", ANDROID_NS)
    tree = ET.parse(manifest_path)
    root = tree.getroot()
    app = root.find("application")
    if app is None:
        raise SystemExit("manifest has no <application> element")
    for key, value in attrs.items():
        old = app.get(q(key))
        if old == value:
            report.append(f"  = application@{key} already {value!r}")
            continue
        report.append(f"  ~ application@{key}: {old!r} -> {value!r}")
        if not dry:
            if value is None:
                app.attrib.pop(q(key), None)
            else:
                app.set(q(key), str(value))
    if not dry:
        tree.write(manifest_path, encoding="utf-8", xml_declaration=True)


def edit_components(manifest_path: str, spec: dict, dry: bool, report: list) -> None:
    ET.register_namespace("android", ANDROID_NS)
    tree = ET.parse(manifest_path)
    root = tree.getroot()
    app = root.find("application")
    if app is None:
        raise SystemExit("manifest has no <application> element")

    for kind in ("activity", "service", "receiver", "provider"):
        rules = spec.get(kind)
        if not rules:
            continue
        existing = {e.get(q("name")) for e in app.findall(kind)}
        for name in rules.get("remove", []) or []:
            for e in list(app.findall(kind)):
                if e.get(q("name")) == name:
                    report.append(f"  - {kind} {name}")
                    if not dry:
                        app.remove(e)
        for name in rules.get("add", []) or []:
            if name in existing:
                report.append(f"  = {kind} {name} already present")
                continue
            report.append(f"  + {kind} {name}")
            if not dry:
                el = ET.SubElement(app, kind)
                el.set(q("name"), name)
    if not dry:
        tree.write(manifest_path, encoding="utf-8", xml_declaration=True)


def copy_files(decoded: str, rules: list, dry: bool, report: list) -> None:
    for rule in rules or []:
        src, dst = rule["from"], rule["to"]
        target = os.path.join(decoded, dst)
        if not os.path.isfile(src):
            raise SystemExit(f"copy source not found: {src}")
        report.append(f"  > {src} -> {dst}")
        if not dry:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(src, target)


def delete_files(decoded: str, rules: list, dry: bool, report: list) -> None:
    for rel in rules or []:
        target = os.path.join(decoded, rel)
        if not os.path.exists(target):
            report.append(f"  = {rel} not present, skipping")
            continue
        report.append(f"  - {rel}")
        if not dry:
            if os.path.isdir(target):
                shutil.rmtree(target)
            else:
                os.remove(target)


def apply_strings(decoded: str, rules: list, dry: bool, report: list) -> None:
    exts = (".smali", ".xml")
    for rule in rules or []:
        find, repl = rule["find"], rule["replace"]
        glob_pat = re.compile(rule.get("path_regex", r".*"))
        changed = 0
        for dirpath, _, files in os.walk(decoded):
            for fn in files:
                if not fn.endswith(exts):
                    continue
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, decoded)
                if not glob_pat.search(rel):
                    continue
                with open(full, encoding="utf-8", errors="surrogateescape") as fh:
                    text = fh.read()
                if find not in text:
                    continue
                n = text.count(find)
                changed += n
                report.append(f"  ~ {rel}: {n}x {find!r} -> {repl!r}")
                if not dry:
                    with open(full, "w", encoding="utf-8", errors="surrogateescape") as fh:
                        fh.write(text.replace(find, repl))
        if changed == 0:
            report.append(f"  = no match for {find!r}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("decoded_dir")
    ap.add_argument("spec")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(args.decoded_dir):
        raise SystemExit(f"decoded dir not found: {args.decoded_dir}")

    spec = load_spec(args.spec)
    manifest = os.path.join(args.decoded_dir, "AndroidManifest.xml")
    report: list[str] = []

    print(f"spec: {args.spec}{'  (DRY RUN)' if args.dry_run else ''}")
    print("=== manifest root attributes ===")
    report: list[str] = []
    if spec.get("manifest"):
        set_manifest_attrs(manifest, spec["manifest"], args.dry_run, report)
    print("\n".join(report) or "  (none)")

    report = []
    print("=== application attributes ===")
    if spec.get("application"):
        set_application_attrs(manifest, spec["application"], args.dry_run, report)
    print("\n".join(report) or "  (none)")

    report = []
    print("=== manifest components ===")
    edit_components(manifest, spec, args.dry_run, report)
    print("\n".join(report) or "  (none)")

    report = []
    print("=== files copied ===")
    copy_files(args.decoded_dir, spec.get("copy"), args.dry_run, report)
    print("\n".join(report) or "  (none)")

    report = []
    print("=== files deleted ===")
    delete_files(args.decoded_dir, spec.get("delete"), args.dry_run, report)
    print("\n".join(report) or "  (none)")

    report = []
    print("=== string replacements ===")
    apply_strings(args.decoded_dir, spec.get("strings"), args.dry_run, report)
    print("\n".join(report) or "  (none)")

    print("\npatch applied" + (" (dry run, nothing written)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
