# Pine + LGL template

A self-contained scaffold for hooking **your own** app so you can see what the
loader architecture actually does at runtime. Nothing here targets a
third-party APK, and there is no anti-tamper or detection-evasion code.

Two layers:

- `java/.../Hooks.java` — Pine hooks into your own Java/Kotlin methods. This is
  the part PHub uses via its `Application` swap; here it runs as a normal
  Application class in your own app.
- `cpp/native_entry.cpp` — the native `System.loadLibrary` + constructor-thread
  pattern LGL uses, so you can attach native hooks and a menu to it.

## Why the two layers line up

PHub's loader does roughly this, and you can reproduce each step transparently
in your own app:

| Loader step | What it is | Template equivalent |
|---|---|---|
| `application` set to `actionmods.loader.core` | Runs loader code before your app code | `HookApp` in `AndroidManifest.xml` |
| `appComponentFactory` swapped | Intercepts class loading for injection | not included; not needed for self-hooking |
| `actionmods/dex/classes.dex` | Hook code, dynamically loaded | your own `Hooks` class, loaded normally |
| `actionmods/lib/arm64.so` + `lib...so` | Native hooks and menu | `native_entry.cpp` + `System.loadLibrary` |
| `actionmods/origin.apk` | Untouched original, loaded via classloader | not applicable — you own the source |
| `libfancy-bypass.so` | anti-frida / anti-debug / integrity defeat | **deliberately excluded** |

The first four are ordinary app architecture. The last one is the part that
only exists to hide from a check, and it has no place in your own build.

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
