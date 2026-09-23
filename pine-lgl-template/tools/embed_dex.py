#!/usr/bin/env python3
"""Turn a menu .dex into the sources that bind it: bytes + native signatures.

Why this exists
---------------
The obvious way to embed a dex is to hardcode the JNI signatures you expect. That
is exactly how hand-rolled loaders break. LGL alone ships variants that do not
agree:

    canonical LGL       Changes(Context, int featNum, String featName,
                                int value, long lvalue, boolean bl, String text)
    the variant in this Changes(Context, int featNum, String featName,
    repo's lib          int value, boolean bl, String text)

A `long` that is or is not there changes the JNI descriptor. Register the wrong
one and the method never binds: nothing fails at build time, nothing fails at
load time, the menu just silently does nothing. So read the dex instead of
assuming.

Emits three headers:
    embedded_dex.h       the dex as ASCII hex, so it can live in .rodata
    lgl_bindings.h       extern "C" declarations matching that dex exactly
    lgl_descriptors.h    class name + JNI descriptors for the reflection calls

Usage:
    python3 tools/embed_dex.py menu.dex --out app/src/main/cpp/lgl
"""

import argparse
import os
import struct
import sys

TYPE_MAP = {
    "I": "jint", "Z": "jboolean", "B": "jbyte", "C": "jchar", "S": "jshort",
    "J": "jlong", "F": "jfloat", "D": "jdouble", "V": "void",
}

# Natives the menu calls back into. We declare whatever the dex actually has.
INTERESTING = ("Changes", "GetFeatureList", "SettingsList", "Init",
               "Icon", "IconWebViewData")

CHUNK = 4000


class Dex:
    def __init__(self, data: bytes):
        if data[:4] != b"dex\n":
            raise ValueError(f"not a dex: magic {data[:4]!r}")
        self.d = data
        # All header fields are (size, offset) pairs; we want the offsets.
        _, self.string_off = struct.unpack_from("<II", data, 0x38)
        _, self.type_off = struct.unpack_from("<II", data, 0x40)
        _, self.proto_off = struct.unpack_from("<II", data, 0x48)
        _, self.method_off = struct.unpack_from("<II", data, 0x58)
        self.class_def_size, self.class_def_off = struct.unpack_from(
            "<II", data, 0x60)

    def _uleb(self, off):
        result = shift = 0
        while True:
            byte = self.d[off]
            off += 1
            result |= (byte & 0x7F) << shift
            if not byte & 0x80:
                return result, off
            shift += 7

    def string(self, idx):
        off = struct.unpack_from("<I", self.d, self.string_off + idx * 4)[0]
        length, pos = self._uleb(off)
        end = self.d.index(b"\x00", pos + min(length, 512))
        return self.d[pos:end].decode("utf-8", "replace")

    def type_name(self, idx):
        return self.string(
            struct.unpack_from("<I", self.d, self.type_off + idx * 4)[0])

    def proto(self, idx):
        shorty_idx, ret_idx, params_off = struct.unpack_from(
            "<III", self.d, self.proto_off + idx * 12)
        params = []
        if params_off:
            count = struct.unpack_from("<I", self.d, params_off)[0]
            for k in range(count):
                params.append(self.type_name(struct.unpack_from(
                    "<H", self.d, params_off + 4 + 2 * k)[0]))
        return self.string(shorty_idx), self.type_name(ret_idx), params

    def classes(self):
        for i in range(self.class_def_size):
            off = self.class_def_off + i * 32
            yield off, self.type_name(struct.unpack_from("<I", self.d, off)[0])

    def methods(self, class_def_off):
        class_data_off = struct.unpack_from("<I", self.d, class_def_off + 24)[0]
        if not class_data_off:
            return
        pos = class_data_off
        static_fields, pos = self._uleb(pos)
        instance_fields, pos = self._uleb(pos)
        direct_methods, pos = self._uleb(pos)
        virtual_methods, pos = self._uleb(pos)
        for _ in range(static_fields + instance_fields):
            _, pos = self._uleb(pos)
            _, pos = self._uleb(pos)
        for kind, count in (("direct", direct_methods),
                            ("virtual", virtual_methods)):
            idx = 0
            for _ in range(count):
                delta, pos = self._uleb(pos)
                access, pos = self._uleb(pos)
                _, pos = self._uleb(pos)
                idx += delta
                _, proto_idx, name_idx = struct.unpack_from(
                    "<HHI", self.d, self.method_off + idx * 8)
                _, ret, params = self.proto(proto_idx)
                yield {
                    "name": self.string(name_idx),
                    "ret": ret,
                    "params": params,
                    "native": bool(access & 0x100),
                    "static": bool(access & 0x8),
                }


def to_cpp(jni_type: str) -> str:
    if jni_type.startswith("["):
        return "jarray"
    if jni_type.startswith("L"):
        return "jobject"
    return TYPE_MAP[jni_type]


def jni_desc(params, ret):
    return "(" + "".join(params) + ")" + ret


def emit_dex_header(dex_bytes: bytes) -> str:
    hexed = dex_bytes.hex()
    lines = [
        "// Generated by tools/embed_dex.py - do not edit by hand.",
        "//",
        f"// {len(dex_bytes)} dex bytes, {len(hexed)} hex characters.",
        "// Decoded at runtime by dexload::decode_embedded_dex().",
        "",
        "#pragma once",
        "",
        "static const char kLglDexHex[] =",
    ]
    for i in range(0, len(hexed), CHUNK):
        lines.append(f'    "{hexed[i:i + CHUNK]}"')
    lines.append("    ;")
    lines.append("")
    lines.append(f"static const unsigned int kLglDexHexLen = {len(hexed)};")
    lines.append("")
    return "\n".join(lines)


def emit_descriptor_header(menu_class, ctor_desc, native_names, changes) -> str:
    lines = [
        "// Generated by tools/embed_dex.py - do not edit by hand.",
        "//",
        "// Class name and JNI descriptors read from the embedded dex, so the",
        "// loader's reflection lookups cannot drift from the bytes.",
        "",
        "#pragma once",
        "",
        f'static const char kLglMenuClass[] = "{menu_class}";',
        f'static const char kLglMenuCtorDesc[] = "{ctor_desc}";',
        "",
    ]
    if changes:
        lines.append("// Interaction callback, as this dex declares it.")
        lines.append(f'static const char kLglChangesDesc[] = "{changes["desc"]}";')
        lines.append("static const bool kLglChangesStatic = "
                     f'{"true" if changes["static"] else "false"};')
        lines.append("")
    lines.append("// Natives this dex declares. A name missing here means this build")
    lines.append("// of the menu does not have it, and nothing should assume it does.")
    lines.append("static const char *const kLglNatives[] = {")
    for n in native_names:
        lines.append(f'    "{n}",')
    lines.append("};")
    lines.append(f"static const unsigned int kLglNativeCount = {len(native_names)};")
    lines.append("")
    return "\n".join(lines)


def emit_bindings_header(natives, changes) -> str:
    lines = [
        "// Generated by tools/embed_dex.py - do not edit by hand.",
        "//",
        '// extern "C" declarations matching the embedded dex exactly, plus the',
        "// JNINativeMethod table that binds them.",
        "//",
        "// Why a table instead of plain Java_* symbols: JNI resolves a native by",
        "// name AND descriptor, and it resolves it against the classloader that",
        "// DEFINED the class. The menu class here is defined by our own",
        "// InMemoryDexClassLoader, not by the loader that ran System.loadLibrary,",
        "// so there is nothing for the automatic lookup to find. RegisterNatives",
        "// sidesteps that entirely: we hand ART the (name, descriptor, function)",
        "// triples for the class we just loaded. This is also why the reference",
        "// libraries export only JNI_OnLoad and no Java_* symbols at all.",
        "",
        "#pragma once",
        "",
        "#include <jni.h>",
        "",
        'extern "C" {',
        "",
    ]
    for m in natives:
        params = ["JNIEnv *env",
                  "jclass clazz" if m["static"] else "jobject thiz"]
        params += [to_cpp(p) for p in m["params"]]
        ret = "void" if m["ret"] == "V" else to_cpp(m["ret"])
        lines.append(f'// {"".join(m["params"])}{m["ret"]}')
        lines.append(f'{ret} {m["name"]}({", ".join(params)});')
        lines.append("")

    lines.append('}  // extern "C"')
    lines.append("")
    lines.append("// Descriptors and function pointers, kept adjacent so the two cannot")
    lines.append("// drift apart. Registered in lgl/impl.cpp.")
    lines.append("struct LglNativeBinding {")
    lines.append("    const char *name;")
    lines.append("    const char *descriptor;")
    lines.append("    void *function;")
    lines.append("};")
    lines.append("")
    lines.append("static const LglNativeBinding kLglNativeBindings[] = {")
    for m in natives:
        desc = jni_desc(m["params"], m["ret"])
        lines.append(f'    {{"{m["name"]}", "{desc}", '
                     f'reinterpret_cast<void *>(&{m["name"]})}},')
    lines.append("};")
    lines.append("static const unsigned int kLglNativeBindingCount = "
                 f"{len(natives)};")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dex")
    ap.add_argument("--out", default=".", help="directory for generated headers")
    ap.add_argument("--menu-class", default="com/android/support/Menu",
                    help="dotted class name to bind")
    args = ap.parse_args()

    with open(args.dex, "rb") as fh:
        raw = fh.read()
    dex = Dex(raw)
    wanted = "L" + args.menu_class.replace(".", "/") + ";"

    found = None
    for off, name in dex.classes():
        if name == wanted:
            found = off
            break
    if found is None:
        print(f"{args.menu_class} not present in {args.dex}", file=sys.stderr)
        return 1

    ctor_desc = None
    changes = {}
    natives = []
    for m in dex.methods(found):
        if m["name"] == "<init>":
            ctor_desc = jni_desc(m["params"], m["ret"])
        elif m["name"] == "Changes":
            changes = {"desc": jni_desc(m["params"], m["ret"]),
                       "static": m["static"]}
        if m["native"] and m["name"] in INTERESTING:
            natives.append(m)

    if ctor_desc is None:
        print("no <init> on the menu class", file=sys.stderr)
        return 1
    if not changes:
        print("no Changes method - is this an LGL menu dex?", file=sys.stderr)
        return 1

    os.makedirs(args.out, exist_ok=True)
    outputs = {
        "embedded_dex.h": emit_dex_header(raw),
        "lgl_descriptors.h": emit_descriptor_header(
            args.menu_class, ctor_desc, [n["name"] for n in natives], changes),
        "lgl_bindings.h": emit_bindings_header(natives, changes),
    }
    for name, text in outputs.items():
        path = os.path.join(args.out, name)
        with open(path, "w") as fh:
            fh.write(text)
        print(f"wrote {path}")

    print(f"\nmenu class   {args.menu_class}")
    print(f"constructor  {ctor_desc}")
    print(f"Changes      {changes['desc']}")
    print(f"natives      {', '.join(n['name'] for n in natives)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
