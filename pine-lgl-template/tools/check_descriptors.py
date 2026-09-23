"""Check the mod's feature descriptors against the menu's real parser.

This ports featureList() out of the decompiled Menu.java rather than guessing at
the grammar, then asserts that every descriptor the mod emits is understood and
that the featNum the menu will hand back matches the number in the descriptor.
"""

import re
import subprocess
import sys

# ---- the menu's parser, ported from Menu.java featureList() ------------------
#
# Faithful to the original, including the counter behaviour, because the counter
# is exactly what we are testing against.

TYPES_NEEDING_INDEX_BUMP = {"Collapse", "ButtonLink", "Category",
                            "RichTextView", "RichWebView"}


def parse(entries):
    """Return list of (featNum, type, name, payload) as the menu would build it."""
    out = []
    counter = 0
    for raw in entries:
        s = raw
        enabled = False
        if "_True" in s:
            enabled = True
            s = s.replace("_True", "", 1)
        if "CollapseAdd_" in s:
            s = s.replace("CollapseAdd_", "", 1)

        parts = s.split("_")
        first = parts[0]
        if first.isdigit() or re.fullmatch(r"-[0-9]*", first or ""):
            feat_num = int(first)
            s = s.replace(first + "_", "", 1)
            counter += 1
        else:
            feat_num = counter
            counter += 1

        parts = s.split("_")
        widget = parts[0]
        name = parts[1] if len(parts) > 1 else ""
        out.append((feat_num, widget, name, parts, enabled))

        if widget in TYPES_NEEDING_INDEX_BUMP:
            counter += 1
    return out


def extract_descriptors():
    """Pull kFeatures[] strings straight out of features.cpp."""
    src = open(
        "/workspace/project/Storage/pine-lgl-template/"
        "app/src/main/cpp/mod/features.cpp").read()
    body = re.search(r"kFeatures\[\]\s*=\s*\{(.*?)\};", src, re.S).group(1)
    return re.findall(r'"((?:[^"\\]|\\.)*)"', body)


KNOWN_TYPES = {"Toggle", "SeekBar", "Button", "ButtonOnOff", "Spinner",
               "InputText", "InputValue", "CheckBox", "RadioButton", "Collapse",
               "ButtonLink", "Category", "RichTextView", "RichWebView"}

descriptors = extract_descriptors()
print(f"descriptors: {len(descriptors)}")
for d in descriptors:
    print(f"  {d}")

parsed = parse(descriptors)

failures = []
for (feat_num, widget, name, parts, enabled), raw in zip(parsed, descriptors):
    if widget not in KNOWN_TYPES:
        failures.append(f"unknown widget type {widget!r} in {raw!r}")
    declared = int(raw.split("_")[0]) if raw.split("_")[0].lstrip("-").isdigit() else None
    if declared is None:
        failures.append(f"missing explicit index in {raw!r}")
    elif declared != feat_num:
        failures.append(
            f"{raw!r}: declared {declared} but menu will deliver {feat_num}")

# feature numbers must be unique, or two features share a slot
nums = [p[0] for p in parsed]
if len(set(nums)) != len(nums):
    failures.append(f"duplicate featNums: {nums}")

# every widget the mod routes on must exist in the descriptor set
src = open(
    "/workspace/project/Storage/pine-lgl-template/"
    "app/src/main/cpp/mod/features.cpp").read()
cases = set(int(m) for m in re.findall(r"case\s+(\d+):", src))
for c in sorted(cases):
    if c not in nums:
        failures.append(f"case {c} handles a featNum no descriptor declares")
print(f"\nrouted cases: {sorted(cases)}")
print(f"declared nums: {sorted(nums)}")

print()
if failures:
    print("FAIL")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print("PASS: every descriptor parses, is uniquely numbered, and the number the "
      "menu delivers matches the number declared.")
