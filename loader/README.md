# loader

Tooling for analysing an APK, applying a declared set of changes to it, and
rebuilding it. Everything lives under this folder so it stays out of the way of
the rest of the repo.

Two workflows drive it:

| Workflow | What it does |
|---|---|
| `.github/workflows/apk-analyze.yml` | Reads an APK and produces a report: metadata, manifest facts, zip/dex/manifest diff against a baseline, native-library triage. |
| `.github/workflows/apk-repack.yml` | Decodes an APK, applies a patch spec, rebuilds, aligns, signs, and uploads the result. |

Both are `workflow_dispatch` (Actions tab -> Run workflow). Analyze also runs on
push when a file under `loader/input/` changes.

## Layout

```
loader/
  input/            APKs you want to work on (gitignored by default)
  patches/          patch specs, one file per set of changes
  scripts/          the tooling
    apk_info.py     metadata + permissions + components + native libs
    apk_diff.py     zip / manifest / dex-class diff between two APKs
    native_triage.py ELF symbols, imports, interesting strings
    apply_patch.py  applies a patch spec to a decoded tree
    repack.sh       apktool build + zipalign + apksigner
  tools/            apktool.jar is fetched here at runtime
```

## Quick start

1. Put your APK in `loader/input/` (or anywhere; the workflow takes a path).
2. Actions -> **APK Analyze** -> Run workflow, set `apk_path`.
   Optionally set `baseline_path` to a second APK to diff against.
3. For changes: copy `patches/example.yml`, edit it, then run **APK Repack**
   with `patch_spec` pointing at your file. Use `dry_run: true` first to see
   what would change without building.

## Patch spec format

See `patches/example.yml` for a documented template. Supported keys:

```yaml
manifest:          # <manifest> root attrs: package, versionName, versionCode
  versionName: "1.2.7.10-custom"

application:       # <application> attrs: name, label, appComponentFactory
  label: "My Build"

activity:          # also service / receiver / provider
  add: [com.example.ExtraActivity]
  remove: [com.example.OldActivity]

copy:              # replace or add files in the decoded tree
  - from: patches/assets/mylib.so
    to:   lib/arm64-v8a/mylib.so

delete:            # remove paths from the decoded tree
  - lib/armeabi-v7a

strings:           # text find/replace inside decoded .smali / .xml
  - find: "old text"
    replace: "new text"
    path_regex: "res/values/strings\\.xml"
```

## Signing

`repack.sh` signs with a throwaway debug keystore generated at runtime, so the
output is installable for testing but carries no identity. To use a real
keystore, add repo secrets and pass `--keystore` / `--alias` / `--pass`.

A debug-signed APK cannot be published or used to update an installed app
signed with a different key.

## Known issues

- **`attribute android:X not found` during build.** apktool's bundled framework
  lags the newest platform attributes. `android:pageSizeCompat` (API 36) is a
  common one. Pass `strip_attrs` (default `pageSizeCompat`) to have it removed
  before building. Removing an attribute can change behaviour, so check whether
  the app relied on it.
- **No `jarsigner` on PATH.** The script looks next to `java` as a fallback. If
  neither apksigner nor jarsigner is found it fails rather than emitting an
  unsigned APK.
- **v1-only signing** (jarsigner fallback) is rejected by many Android 11+
  targets. Install `apksigner` for v2/v3.

## Why Ghidra/radare2 instead of IDA

`native_triage.py` uses pyelftools and needs no native toolchain, which is what
you want for per-push CI. For deeper disassembly:

- **IDA Pro** is commercial and its headless mode (`idat`) is not installable on
  a hosted runner. **IDA Free** is GUI-only and not redistributable.
- **Ghidra headless** (`analyzeHeadless`) is the CI-friendly equivalent,
  Apache-2.0 licensed, and scriptable.
- **radare2 / rabin2** is lighter if you only need symbols and strings.

`native_triage.py` output is a good input for either: it already lists the
largest exported symbols and filtered strings worth disassembling.

## Legal note

Analysing and repackaging an APK you have the right to modify is normal
engineering. Redistributing someone else's application, or shipping something
that defeats another app's anti-tamper or anti-cheat protections, is a
different matter and can breach the target's terms of service or local law.
Keep patched builds local, and check what you are allowed to change before you
publish anything.
