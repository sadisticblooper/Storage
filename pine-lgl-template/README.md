# Pine + LGL template

A self-contained scaffold for hooking **your own** app so you can see what the
loader architecture actually does at runtime. Nothing here targets a
third-party APK, and there is no anti-tamper or detection-evasion code.

The menu dex is embedded in the `.so` and loaded at runtime, the way the
actionmods loader does it. See `ANALYSIS-loader.md` for the mechanism and for
what I verified versus what I could not.

## Layout

Two native modules compiled into one `.so`, plus a Java layer:

```
tools/
  embed_dex.py         dex -> generated headers (also reads out its signatures)
app/src/main/
  java/com/example/hooktemplate/
    HookApp.java       Application entry — loads native, starts menu on UI thread
    Hooks.java         Pine hooks into your Java/Kotlin methods
    ScoreBoard.java    stand-in for your game logic
  cpp/
    lgl/
      lgl.h            orientation only; the real signatures are generated
      dex_loader.h/.cpp  decode dex -> InMemoryDexClassLoader -> RegisterNatives
      embedded_dex.h     GENERATED - the menu dex as hex
      lgl_bindings.h     GENERATED - extern "C" decls + JNINativeMethod table
      lgl_descriptors.h  GENERATED - class name and JNI descriptors
      impl.cpp         the only file that knows LGL exists
    mod/
      mod_api.h        the seam: features + values the mod exposes
      features.cpp     descriptor table + interaction routing
      native_entry.cpp load/thread/wait, then install hooks
```

The dependency points one way: `lgl/` includes `mod/mod_api.h`, never the
reverse. Verified — `mod/` compiles cleanly with the `lgl/` directory deleted,
so swapping menu libraries never touches your feature code.

## Swapping the menu dex

Never hand-edit the three generated headers. Point the tool at a dex and rerun:

```
python3 tools/embed_dex.py menu.dex --out app/src/main/cpp/lgl
```

It prints the constructor and `Changes` descriptors it found. That is not
decoration — LGL variants disagree about whether `Changes` takes a `long lvalue`,
and a wrong descriptor means the menu silently does nothing. Generating avoids
the guesswork.

## How the pieces connect

Adding a feature is two edits and nothing else:

1. One line in `kFeatures` in `mod/features.cpp` — its array index becomes the
   `featNum` you receive back.
2. One `case` in `on_feature_changed()`, storing into a `mod::g_*` global.
3. Read that global at your hook site in `native_entry.cpp`.

The menu writes a value, the hook reads it. That is the whole contract.


The values are plain `bool`/`int` globals. They are written on the menu thread
and read on the game thread, so there is no ordering guarantee — a value can
change mid-frame. That is fine for a toggle. If a torn read would matter, snap
it into a local at the top of the hook.

## Why this shape matches the loader

PHub's loader does roughly this, and you can reproduce each step transparently:

| Loader step | What it is | Template equivalent |
|---|---|---|
| `application` set to `actionmods.loader.core` | Runs loader code before your app code | `HookApp` in `AndroidManifest.xml` |
| `appComponentFactory` swapped | Intercepts class loading for injection | not included; not needed for self-hooking |
| `.so` fetched from `action-mods.com` at runtime | Payload never sits in the APK | not applicable — you build your own `.so` |
| menu dex hex-coded inside that `.so` | One artifact carries its own UI | `tools/embed_dex.py` + `lgl/dex_loader.cpp` |
| natives registered by hand | Child-classloader classes are not auto-resolved | `RegisterNatives` in `lgl/dex_loader.cpp` |
| `libfancy-bypass.so` | anti-frida / anti-debug / integrity defeat | **deliberately excluded** |

The dex-embedding and hand-registration rows are the mechanism this template
copies, because they are ordinary technique that works for anyone. The last row
only exists to hide from a check and has no place in your own build.

One detail worth carrying over: the loader's `.so` exports **only `JNI_OnLoad`**,
with no `Java_*` symbols at all. That is the fingerprint of a library that
registers its natives explicitly rather than relying on name lookup — which it
must, because its menu class is defined by a child classloader. `tools/embed_dex.py`
generates the same kind of table from the dex it embeds.

## Loading the mod: two paths, and which to pick

If you compile the mod *into* the target APK (the case here), `System.loadLibrary`
runs it via `JNI_OnLoad` and the `__attribute__((constructor))`. Because your
`HookApp` is the app's own Application class, you are already resident before
most code you would want to hook runs.

If instead you ship the mod as a *separate* app that loads a prebuilt `.so` into
another process, you need a handle to that process and the module is loaded by
the loader, not by `System.loadLibrary` in the target. That is a different
deployment and a different set of problems — it is not what this template
builds, and it is outside the "hook your own app" scope.

The reason the `lgl`/`mod` split exists is that the second case needs a frozen
ABI: a `.so` built elsewhere must call into a stable surface. `mod_api.h` is that
surface — plain C++ types, no JNI in the mod's own signature, one-way include.


## Pine hooks

Add the dependency (verify the current version on Maven Central):

```groovy
implementation 'top.canyie.pine:core:0.3.0'
```

Then hook anything in your process:

```java
PineConfig.debug = true;
PineConfig.debuggable = BuildConfig.DEBUG;

Method m = MyGame.class.getDeclaredMethod("getScore");
Pine.hook(m, new MethodHook() {
    @Override public void beforeCall(Pine.CallFrame cf) {
        cf.thisObject.getClass();          // receiver
    }
    @Override public void afterCall(Pine.CallFrame cf) {
        cf.setResult(9999);                // replace the return value
    }
});
```

Useful pieces of the real API:

- `Pine.hook(Method, MethodHook)` — before/after callbacks.
- `MethodReplacement.DO_NOTHING` / `REPLACE_METHOD` / pass a callback — replace
  the method body outright.
- `Pine.CallFrame` exposes `thisObject`, `args`, `result`, `throwable`, and
  `setResult()`.
- `ReflectionHelper.getMethod(cls, "name", argTypes...)` — get a `Method`
  without the checked-exception noise.
- `PineEnhances.enableDelayHook()` (from `top.canyie.pine:enhances`) lets you
  hook static methods without initializing the declaring class.

Hooks only apply to the current process. There is no cross-process magic; if you
need another process you inject into it yourself.

## Native side

`native_entry.cpp` follows the LGL shape: a `__attribute__((constructor))`
runs on `loadLibrary`, spawns a thread, and waits for your target library to be
mapped before touching it. Waiting matters — the library is usually not loaded
when your constructor runs.

```cpp
extern "C" JNIEXPORT jint JNI_OnLoad(JavaVM *vm, void *) {
    env = vm;  // cache for callbacks
    return JNI_VERSION_1_6;
}
```

Add Dobby for native hooks (it is what LGL uses under the hood):

```
# CMakeLists.txt
add_subdirectory(dobby)
target_link_libraries(${CMAKE_PROJECT_NAME} dobby)
```

Then:

```cpp
HOOK_LIB("libyourgame.so", "0x123456", my_hook, orig_my_hook);
```

## Android version support

Short answer: **not reliably on Android 16, and not at all on 16 KB-page
devices without a rebuild.** Two separate problems, both currently open upstream.

### 1. `libpine.so` is not 16 KB-page aligned

Verified by inspecting the published artifact, not by reading the changelog:

```
$ readelf -lW jni/arm64-v8a/libpine.so | grep LOAD
  LOAD  0x000000 0x0000000000000000 ... Align 0x1000
  LOAD  0x010770 0x0000000000011770 ... Align 0x1000   <-- not 0x4000
```

Segments are 4 KB aligned and the second starts at vaddr `0x11770`, which is not
a multiple of 16 KB. On a 16 KB-page kernel the loader refuses to map it and the
app dies at startup with an unsatisfied link. Tracked upstream as
[canyie/pine#107](https://github.com/canyie/pine/issues/107), still open.

This matters more than it looks: since **1 November 2025** Google Play requires
16 KB support for apps targeting Android 15+. Any device with 16 KB pages —
increasingly common on newer arm64 hardware — cannot load the stock AAR.

### 2. Hidden-API policy handling broke on Android 16

Pine disables the hidden-API policy on init so hooks can reach non-SDK members.
On Android 16 that path fails; the library logs `Method.getAccessFlags not found`
and falls back to defaults. Tracked as
[canyie/pine#110](https://github.com/canyie/pine/issues/110), open, reported
against a vivo Android 16 build.

Practical effect: hooks on public methods are fine, hooks on hidden APIs are not.
If your hook targets something not in the SDK, assume it will not work.

### What the project state actually says

Latest commit is November 2025 (`[core] Fix incorrect log in elf image parser`).
The last *release* is 0.3.0, from **July 2024** — over a year of fixes are on
`master` but unpublished. Last explicit version-support fix was Feb 2025 for
Android 15 QPR1.

So: the maintainer is still active, but the released artifact lags the source,
and neither has 16 KB support.

### What to do

- **Android 14 and below, 4 KB pages** — the published 0.3.0 AAR works. This is
  the safe target.
- **Android 15** — works; QPR1 needed the Feb 2025 fix, which is only on
  `master`, so build Pine from source rather than using the AAR.
- **Android 16** — expect hidden-API hooks to fail. Build from source and test
  the specific method you need; do not assume.
- **16 KB pages** — you must build Pine from source with an NDK that emits 16 KB
  alignment (`-Wl,-z,max-page-size=16384`). The AAR cannot be fixed by
  configuration alone.

Building from source:

```bash
git clone https://github.com/canyie/pine
cd pine && ./gradlew :core:assembleRelease
# then depend on the local module instead of the Maven artifact
```

Worth confirming which page size your target device uses before debugging
anything else — `adb shell getconf PAGE_SIZE` returning `16384` means the stock
AAR will not load at all.

## Building

This is a reference scaffold, not a ready-built APK. To use it:

1. Copy `java/` and `cpp/` into your app module (or start a new project and drop
   them in).
2. Set your own `applicationId` and package name — the ones here are placeholders.
3. Point `TARGET_LIB` in `native_entry.cpp` at your own `.so`.
4. Replace the example hook in `Hooks.java` with a real method from your game.

## LGL menu

`cpp/lgl_features.cpp` implements the two functions LGL calls: `GetFeatureList`
returns the descriptors, `Changes` receives every user interaction. The overlay,
themes and preference storage are upstream LGL's job — it is a few thousand
lines, so it is not vendored here.

Upstream: https://github.com/LGLTeam/Android-Mod-Menu

The descriptor format (from LGL's `Main.cpp`) is `<Number>_<Type>_<Name>_<args>`:

| Type | Meaning |
|---|---|
| `Toggle_`, `CheckBox_` | on/off; prefix `True_` to default on |
| `Button_`, `ButtonOnOff_` | one-shot / latching action |
| `SeekBar_<name>_<min>_<max>` | slider, value delivered as int |
| `Spinner_<name>_<a,b,c>` | dropdown |
| `InputValue_`, `InputText_` | text entry |
| `RadioButton_<name>_<a,b,c>` | exclusive choice |
| `Category_`, `Collapse_`/`CollapseAdd_` | grouping, not counted as features |
| `ButtonLink_`, `RichTextView_`, `RichWebView_` | non-interactive, not counted |

Your callback receives `(featNum, featName, value, lvalue, boolean, text)` where
`featNum` is the descriptor index unless you assigned an explicit number.

## Scope

Hook your own app, or an app you have written permission to modify. Hooking a
third-party app to defeat its checks is a different thing, and that is the line
this template stays on the right side of.
