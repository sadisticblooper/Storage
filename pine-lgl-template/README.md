# pine-lgl-template

A working mod-menu template: hooks in your own app, plus an LGL menu loaded from
a hex-embedded dex at runtime.

## Build it

```
./gradlew :app:assembleDebug
```

That is the whole thing. The wrapper is committed, so no local Gradle needed.

## What it does

Three independent pieces:

| Piece | Where | Job |
|---|---|---|
| Hooks | `Hooks.java` | Pine hooks on your own methods |
| Menu loader | `lgl/dex_loader.cpp` | Decode dex -> load class -> register natives -> start menu |
| Your mod | `mod/features.cpp` | Feature list and what each value does |

They meet at exactly one place: `mod_api.h`. Nothing under `mod/` includes
anything from `lgl/`, so you can swap the menu library and your features do not
change.

## Adding a feature

Two edits, both in `mod/features.cpp`.

1. Add a line to `kFeatures`:

```c
"12_Toggle_Infinite ammo",
```

2. Add a case to `on_feature_changed`:

```c
case 12:
    g_infinite_ammo = enabled;
    break;
```

Then read `g_infinite_ammo` wherever your hook needs it.

## The descriptor grammar

This is the menu's grammar, and it is fussy:

```
[<number>_]<Type>_<Name>[_<arg>...][_True]
```

Types: `Toggle`, `SeekBar`, `Button`, `ButtonOnOff`, `Spinner`, `InputText`,
`InputValue`, `CheckBox`, `RadioButton`, `Collapse`, `ButtonLink`, `Category`,
`RichTextView`, `RichWebView`.

**Always write the leading number.** It is the `featNum` your `case` matches on.
Without it the menu falls back to an internal counter that also advances for
`Category` and `Collapse` — widgets that never call back — so the numbers drift
the moment you add a heading and your features write to the wrong slots. This is
the single easiest way to get a menu that renders perfectly and does nothing.

Run `python3 tools/check_descriptors.py` after editing. It ports the menu's
actual parser out of the decompiled `Menu.java` and checks that every descriptor
parses, is uniquely numbered, and that the number delivered matches the number
declared.

## What `value` means per type

| Type | `value` | `enabled` | `text` |
|---|---|---|---|
| Toggle, CheckBox | unused | the state | null |
| SeekBar, InputValue | the number | unused | null |
| Spinner, RadioButton | selected index | unused | null |
| Button, ButtonOnOff | unused | unused | null |
| InputText | unused | unused | the string |

Route on `featNum`, not on the name. For `Spinner` and `RadioButton` the menu
sends the *selected item* as the name field rather than your label, so it is not
a stable key. Full detail in `mod_api.h`.

## Requirements

- `SYSTEM_ALERT_WINDOW` — the menu is an overlay. The manifest declares it, and
  `MainActivity` sends the user to Settings to grant it on API 23+.
- API 26+ for the loader path. `InMemoryDexClassLoader` does not exist below
  that; on 24–25 the loader logs and returns instead of crashing.

## The dex

`lgl/embedded_dex.h` holds a hex-encoded LGL menu dex. To swap it:

```
python3 tools/embed_dex.py your-menu.dex
```

That regenerates `embedded_dex.h`, `lgl_descriptors.h`, and `lgl_bindings.h`.
The descriptors are read *out of the dex*, which matters because LGL ships
variants whose signatures disagree — the one embedded here declares
`Changes(Context, int, String, int, boolean, String)` with no `long lvalue`.
Hardcoding the tutorial signature leaves the method unbound: no build error, no
load error, menu does nothing. Regenerating avoids the whole class of problem.

## Layout

```
app/src/main/cpp/
  lgl/            menu loader and JNI bindings   - do not need to touch
  mod/            your features                  - edit these
app/src/main/java/com/example/hooktemplate/
  HookApp.java    Application entry, loads native
  MainActivity.java  host activity, starts the menu
  Hooks.java      Pine hook examples
  ScoreBoard.java stand-in for your game logic
tools/
  embed_dex.py         dex -> generated headers
  check_descriptors.py validates the feature grammar
```

## Status

The native side compiles clean with `-Wall -Wextra` and all generated headers
are in sync with the embedded dex. It has not been run on a device.
