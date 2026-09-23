# Architecture and handoff

Everything verified in this project, in one place, so it can be picked up cold.

**Scope boundary, stated first.** This covers the menu template and the loader's
generic mechanics. It does not cover making a menu act on a live online match in
a game someone else operates, and that is not a gap that later filling in is
expected. Anything about target offsets, per-feature flag addresses, or handler
threads is out of scope here and stays out of scope.

---

## 1. What this project is

A mod-menu template. Three independent pieces that meet at exactly one file:

| Piece | Location | Responsibility |
|---|---|---|
| Hooks | `app/src/main/java/.../Hooks.java` | Pine hooks, on methods in this app |
| Menu loader | `app/src/main/cpp/lgl/` | decode dex, stage it, bind natives, start menu |
| Your features | `app/src/main/cpp/mod/` | what features exist and what each value does |

Nothing under `mod/` includes anything from `lgl/`. The dependency points one
way, so the menu library is replaceable without touching feature code.

---

## 2. Layout

```
pine-lgl-template/
  app/src/main/cpp/
    lgl/                    menu layer - usually not touched
      embedded_dex.h        GENERATED - the menu dex, hex encoded
      lgl_descriptors.h     GENERATED - parsed out of that dex
      lgl_bindings.h        GENERATED - JNI signatures read from that dex
      dex_loader.cpp        the load pipeline
      impl.cpp              the native entry points the menu calls
    mod/                    your code
      mod_api.h             the seam
      features.cpp          feature list + routing
      native_entry.cpp      JNI_OnLoad, thread, wait-for-lib
  app/src/main/java/com/example/hooktemplate/
    HookApp.java            Application, loads the native lib
    MainActivity.java       host activity, starts the menu
    Hooks.java              Pine hook examples
    ScoreBoard.java         stand-in for your own logic
  tools/
    embed_dex.py            dex -> the three generated headers
    check_descriptors.py    validates the feature grammar
```

---

## 3. Build and verify

```
./gradlew :app:assembleDebug
python3 tools/check_descriptors.py
```

The wrapper is committed. `check_descriptors.py` ports the menu's real parser
out of the decompiled `Menu.java` and asserts that every descriptor is
understood, uniquely numbered, and delivers the number it declares. It is the
fastest way to catch the two traps in section 6.

---

## 4. The seam

`mod/mod_api.h` declares:

```c
const char *const *feature_descriptors(int *count_out);
void on_feature_changed(int featNum, int value, bool enabled, const char *text);
```

`lgl/impl.cpp` implements the JNI entry points and forwards to those two.
`mod/features.cpp` implements them. That is the whole contract.

## 5. Descriptor grammar

Read straight out of the decompiled `Menu.java`, not guessed:

```
[<number>_]<Type>_<Name>[_<arg>...][_True]
```

The parser, in order:

1. if the string contains `_True`, strip it once and mark the row enabled by
   default
2. if it contains `CollapseAdd_`, strip it once
3. split on `_`. If the first token is numeric (or a negative digit run), that is
   the `featNum` and it is removed; otherwise the `featNum` is the internal
   counter and that counter is incremented
4. the next token is the widget type, the one after it is the label
5. `Collapse`, `CollapseAdd`, `Category`, `ButtonLink`, `RichTextView`,
   `RichWebView` additionally bump the internal counter

Widget types: `Toggle`, `SeekBar`, `Button`, `ButtonOnOff`, `Spinner`,
`InputText`, `InputValue`, `CheckBox`, `RadioButton`, `Collapse`, `ButtonLink`,
`Category`, `RichTextView`, `RichWebView`.

## 6. The two traps

**Trap one — always write the leading number.** Without an explicit number the
menu falls back to its internal counter. That counter also advances for
`Category`, `Collapse` and friends, which never call back for a `featNum`, so the
counter drifts out of step with the rows the moment a heading or a collapsible
group appears. The menu renders perfectly and every feature after the heading
writes to the wrong slot. Explicit numbering makes it immune and costs nothing.

**Trap two — route on `featNum`, not on the name.** For `Spinner` and
`RadioButton` the menu does not send your label back; it sends the *selected
item* (`spinner.getSelectedItem().toString()`). For every other type it sends the
label. The name field is therefore not a stable key, and any feature that routes
on it silently misbehaves for those two widget types only — which is a nasty bug
to find by inspection.

## 7. What the callback arguments carry

| Type | `value` | `enabled` | `text` |
|---|---|---|---|
| `Toggle`, `CheckBox` | unused | the state | null |
| `SeekBar`, `InputValue` | the number | unused | null |
| `Spinner`, `RadioButton` | selected index | unused | null |
| `Button`, `ButtonOnOff` | unused | unused | null |
| `InputText` | unused | unused | the string |

## 8. Non-obvious requirements

**`Icon()` must return a real Base64 PNG.** The menu Base64-decodes the return of
`Icon()` and hands the bytes to `BitmapFactory` while constructing. Return null
and construction fails.

**`SYSTEM_ALERT_WINDOW` is mandatory.** The menu is an overlay added to the
`WindowManager`. Without the permission declared, attaching throws. On API 23+
there is no runtime dialog for it, so the user must be routed to Settings —
`MainActivity` does this.

**`Menu.CreateMenu(Context)` is the entry point, not the constructor.**
Constructing `Menu` directly builds the view tree and stops. Attaching is
`SetWindowManagerActivity()` plus `ShowMenu()`, and the static
`CreateMenu(Context)` does both. This is the single easiest way to get a menu
that loads with no error and never appears.

## 9. The load pipeline

`lgl/dex_loader.cpp`, in order, and why each step is load-bearing:

1. **decode** the hex in `embedded_dex.h` into raw dex bytes
2. **wrap** them in a `java.nio.ByteBuffer`
3. **`dalvik.system.InMemoryDexClassLoader`** over that buffer — needs API 26+,
   guarded at runtime; on 24–25 it logs and returns rather than crashing
4. **`FindClass`** on the menu class out of that loader. Note: the class must be
   resolved *through* the loader, not by `FindClass` on the system class loader,
   which has never seen it
5. **`RegisterNatives`** on the menu's declared natives
6. **`CreateMenu`**

Step 5 is mandatory rather than optional. The menu's own static initialiser calls
its natives, so if they are not bound before the class is first touched, the
class throws `UnsatisfiedLinkError` during initialisation. There is no order that
avoids this.

The natives, as declared by the embedded dex:

```
Changes, GetFeatureList, Icon, IconWebViewData, Init, SettingsList
```

`Changes` signature in the embedded build:

```
(Landroid/content/Context;ILjava/lang/String;IZLjava/lang/String;)V
```

No `long lvalue` parameter. This matters — see section 10.

## 10. Why the signatures are generated, not hardcoded

LGL ships variants whose signatures disagree. The commonly-copied tutorial
`Changes` has a `long lvalue` argument; this build does not. Hardcoding the
tutorial signature leaves the method unbound, and the failure mode is silent:
no build error, no load error, menu does nothing.

So `tools/embed_dex.py` reads the class and the signatures *out of the dex you
actually embed* and emits `lgl_bindings.h` and `lgl_descriptors.h` from them.
Regenerate whenever the dex changes:

```
python3 tools/embed_dex.py your-menu.dex --out app/src/main/cpp/lgl
```

The three generated headers are byte-reproducible; regenerating from the same
dex produces identical output, which is how you confirm they are in sync.

## 11. Native entry choreography

`native_entry.cpp` follows the LGL pattern, and the shape is the point:

- a constructor runs when `System.loadLibrary` executes
- it must not do heavy work on that thread — it is the thread starting your app
- it spawns a thread and does setup there, waiting for the target library to be
  mapped before touching it
- library readiness is polled via `/proc/self/maps`

## 12. Pine

Pine rewrites the ART entry point of a target method in the current process.

Known limits, worth stating because they are the usual source of "my hook does
nothing":

- cannot hook `final`, private, or framework methods
- stock `libpine.so` is **not** built for 16 KB pages, which breaks it on Android
  15+ devices with 16 KB pages. The template's own lib is built correctly:
  `-Wl,-z,max-page-size=16384`, and every `LOAD` segment lands on a `0x4000`
  boundary
- `PineConfig.debuggable` should track `BuildConfig.DEBUG`; the app must be
  debuggable for the debug hook path

## 13. Adding a feature

Two edits, both in `mod/features.cpp`:

```c
"12_Toggle_Infinite ammo",        // in kFeatures
```
```c
case 12: g_infinite_ammo = enabled; break;   // in on_feature_changed
```

Then read the global at the hook site. No menu code is involved. Run
`check_descriptors.py` after editing.

## 14. Symptom to cause

| Symptom | Likely cause |
|---|---|
| Builds, loads, nothing appears | `CreateMenu` not used, or overlay permission missing |
| Menu appears, features do nothing | descriptor numbers missing, so `featNum` drifted (section 6) |
| Only `Spinner`/`RadioButton` misbehave | routing on name instead of `featNum` |
| `UnsatisfiedLinkError` at class touch | natives not registered before first use |
| Crash on construction | `Icon()` returned null |
| Works on old device, fails on new | 16 KB page alignment |

---

## 15. The reference loader — what was established

About the actionmods loader, checked against the binaries:

- It **fetches its library from `https://action-mods.com` at runtime**; the `.so`
  is not inside the APK. That is why the APK looks inert on inspection.
- The library carries the menu dex inline. `libsf4.so` holds the entire
  `payload.dex` as **119,856 ASCII hex characters at offset `0x701c9`**, and the
  decoded bytes hash identical to `payload.dex`
  (`ecabe3e5566c879e927bc078d6a6767fbf11a8fcde1c5b7f35764d1f4c6cdea1`). The
  earlier "these are from a different sample" claim was wrong because the search
  looked for raw dex magic and compressed streams, never a hex encoding.
- The loader's process model is a **parallel-space host**
  (`com.sherrytse.parallel`, `libparallelhub.so`), which virtualises the target
  into the loader's own process.
- **The app picker is not a scan.** It is a hardcoded allowlist of exactly four
  package names, built in the static initialiser of `Lwc/c;`:
  `com.nekki.shadowfight`, `com.nekki.shadowfight3`, `com.nekki.shadowfightarena`,
  `com.google.android.play.games`. `Lwc/i;` enumerates installed packages and
  keeps only names that are `contains()`-members of that set, plus a system-app
  check. Three icons appeared because three of the four names were installed.
  There is no discovery, no heuristic, and no registry — the IDs are literals
  that someone typed. This is the direct answer to why only three apps showed.

Free Fire packages (`com.dts.freefireth`, `com.dts.freefiremax`) appear elsewhere
in the loader dex but are not in that allowlist.

## 16. Not verified

- The template has never been run on a device. Native side compiles clean under
  `-Werror -Wall -Wextra`, generated headers are reproducible, the descriptor
  checker passes, and page alignment is correct. Rendering is unproven.
- The 48 KB encrypted region in the reference library is **unresolved**. An
  earlier note in the session described a zlib attempt as recovering "the key";
  that characterisation was wrong and should not be propagated. What the region
  is, is unknown.
- `lgl_mod_menu_re_hardcore.zip` in the repo root is a reverse-engineering report
  over the reference library, one `.md` per menu entry, with per-feature handler
  offsets and flag addresses. Its structure is as described; those offsets are
  deliberately not reproduced here, per the scope note at the top.
