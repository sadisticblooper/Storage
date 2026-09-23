#!/usr/bin/env python3
"""Static native-library triage: ELF headers, exported symbols, imports, strings.

Usage:
    native_triage.py <lib.so> [--json out.json] [--strings-limit N]

Pure-Python (pyelftools + regex) so it works with no native toolchain.
For deeper work, Ghidra headless or radare2 can consume the same ELF.

Why not IDA: IDA Pro is commercial and cannot be installed on a hosted
runner; IDA Free is GUI-only and non-redistributable. Ghidra headless
(analyzeHeadless) is the CI-friendly equivalent and is Apache-2.0.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter

try:
    from elftools.elf.elffile import ELFFile
except ImportError:  # pragma: no cover
    print("[x] pyelftools is required: pip install pyelftools", file=sys.stderr)
    raise SystemExit(2)


PRINTABLE = re.compile(rb"[\x20-\x7e]{6,}")

# Strings worth surfacing in a triage report.
INTERESTING = re.compile(
    rb"(\.so$|\.dex$|\.dat$|\.apk$|/data/|/system/|"
    rb"JNI_OnLoad|RegisterNatives|GetEnv|AttachCurrentThread|"
    rb"hook|Hook|inline|PLT|dlsym|dlopen|"
    rb"java/|Ljava/|Landroid/|"
    rb"art::|ArtMethod|dex2oat|oat|"
    rb"ptrace|frida|magisk|xposed|substrate|"
    rb"anti|bypass|detect|integrity|root|emulator|debugger)",
)


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def triage(path: str, strings_limit: int) -> dict:
    with open(path, "rb") as fh:
        elf = ELFFile(fh)
        exported, imported = [], []
        for sec in elf.iter_sections():
            if sec.name == ".dynsym":
                for sym in sec.iter_symbols():
                    if not sym.name:
                        continue
                    if sym["st_shndx"] == "SHN_UNDEF":
                        imported.append(sym.name)
                    else:
                        exported.append(
                            {
                                "name": sym.name,
                                "size": sym["st_size"],
                                "type": str(sym["st_info"]["type"]),
                            }
                        )
        needed = []
        for sec in elf.iter_sections():
            if sec.name == ".dynamic":
                for tag in sec.iter_tags():
                    if tag.entry.d_tag == "DT_NEEDED":
                        needed.append(tag.needed)

        arch = elf.get_machine_arch()
        bits = elf.elfclass

    with open(path, "rb") as fh:
        raw = fh.read()

    all_strings = [m.group().decode("ascii", "ignore") for m in PRINTABLE.finditer(raw)]
    interesting = sorted(
        {s for s in all_strings if INTERESTING.search(s.encode("ascii", "ignore"))}
    )

    return {
        "path": path,
        "sha256": sha256(path),
        "arch": arch,
        "bits": bits,
        "needed": sorted(set(needed)),
        "exported_symbols": sorted(exported, key=lambda s: -s["size"]),
        "exported_count": len(exported),
        "imported_count": len(set(imported)),
        "imported_sample": sorted(set(imported))[:60],
        "interesting_strings": interesting[:strings_limit],
        "interesting_string_count": len(interesting),
    }


def triage_from_apk(apk_path: str, strings_limit: int, out_dir: str | None) -> list[dict]:
    """Triage every lib/*.so inside an APK, without needing unzip on PATH."""
    import os
    import tempfile
    import zipfile

    results = []
    with zipfile.ZipFile(apk_path) as zf:
        libs = [n for n in zf.namelist() if n.startswith("lib/") and n.endswith(".so")]
        if not libs:
            return []
        tmpdir = out_dir or tempfile.mkdtemp()
        os.makedirs(tmpdir, exist_ok=True)
        for name in sorted(libs):
            slug = name.replace("/", "_")
            dest = os.path.join(tmpdir, slug)
            with zf.open(name) as src, open(dest, "wb") as dst:
                dst.write(src.read())
            info = triage(dest, strings_limit)
            info["apk_entry"] = name
            results.append(info)
            os.remove(dest)
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("lib", help="an .so file, or an .apk to scan all lib/*.so")
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--strings-limit", type=int, default=80)
    args = ap.parse_args()

    if args.lib.endswith(".apk"):
        reports = triage_from_apk(args.lib, args.strings_limit, None)
        if not reports:
            print("no native libraries found in this APK")
            if args.json_out:
                with open(args.json_out, "w", encoding="utf-8") as fh:
                    json.dump([], fh)
            return 0
        if args.json_out:
            with open(args.json_out, "w", encoding="utf-8") as fh:
                json.dump(reports, fh, indent=2, sort_keys=True)
        for info in reports:
            print(f"\n=== {info['apk_entry']} ===")
            print(f"  sha256  : {info['sha256']}")
            print(f"  arch    : {info['arch']} ({info['bits']}-bit)")
            print(f"  needed  : {', '.join(info['needed']) or '(none)'}")
            print(f"  exports : {info['exported_count']}  imports: {info['imported_count']}")
            for s in info["exported_symbols"][:15]:
                print(f"    {s['size']:>8}  {s['type']:<8} {s['name']}")
            if info["interesting_strings"]:
                print("  interesting strings:")
                for s in info["interesting_strings"]:
                    print(f"    {s[:110]}")
        return 0

    info = triage(args.lib, args.strings_limit)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(info, fh, indent=2, sort_keys=True)

    print(f"file     : {info['path']}")
    print(f"sha256   : {info['sha256']}")
    print(f"arch     : {info['arch']} ({info['bits']}-bit)")
    print(f"needed   : {', '.join(info['needed']) or '(none)'}")
    print(f"exports  : {info['exported_count']}  imports: {info['imported_count']}")

    print("\n=== Largest exported symbols ===")
    for s in info["exported_symbols"][:25]:
        print(f"  {s['size']:>8}  {s['type']:<8} {s['name']}")

    print(f"\n=== Interesting strings ({info['interesting_string_count']}) ===")
    for s in info["interesting_strings"]:
        print(f"  {s[:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
