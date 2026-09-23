# How the actionmods loader works

Everything here is checked against the binaries. Where I could not verify
something, it says so instead of sounding confident.

## Correction to an earlier claim

I previously said `libsf4.so` and `payload.dex` were "from a different sample"
because they are not present in `PHubLoader.apk`. That was wrong, and the reason
matters: the loader **fetches the library from `https://action-mods.com` at
runtime**, so of course the `.so` is not in the APK. The strings in the loader's
`classes.dex` confirm the host.

And the dex really is inside the library. `libsf4.so` holds the entire
`payload.dex` as **119,856 ASCII hex characters** at file offset `0x701c9`:

```
$ python3 -c "
import hashlib
s=open('libsf4.so','rb').read()
dec=bytes.fromhex(s[0x701c9:0x701c9+119856].decode())
print(hashlib.sha256(dec).hexdigest())"
ecabe3e5566c879e927bc078d6a6767fbf11a8fcde1c5b7f35764d1f4c6cdea1
$ sha256sum payload.dex
ecabe3e5566c879e927bc078d6a6767fbf11a8fcde1c5b7f35764d1f4c6cdea1
```

Byte for byte identical. My earlier searches missed it because I looked for raw
DEX magic and for compressed streams, and never for a hex encoding. Layout:

```
0x701c9  119,856 hex chars  ->  the LGL menu dex (59,928 bytes)
0x8d800  48 KB encrypted region, exactly 3 x 16 KB pages
```

The 48 KB region never decrypted cleanly. I recovered an 8-byte XOR key under
which 99.74% of it lands in the base64 alphabet, and a zlib layer under that
inflating to 106 KB, but the result has 20 distinct byte values and decodes to
nothing meaningful. Reported as unresolved.

## The mechanism, which is what the template now implements

Four steps. Only the third one is subtle.

**1. The dex is data, not a file.** Hex in `.rodata` survives asset stripping and
looks like nothing to a signature scan. Cheap to decode, and it means a single
`.so` carries its own UI.

**2. Bytes go into an `InMemoryDexClassLoader`.** Available since API 26, takes a
`ByteBuffer`, returns a working `ClassLoader` with no file behind it. This is the
same approach `ispointer/NativeModMenu` documents.

**3. Natives must be registered by hand.** This is the step that decides whether
the thing works. ART resolves a native method against the loader that *defined*
the class. The menu class is defined by our `InMemoryDexClassLoader`, which never
ran `System.loadLibrary` - so plain `Java_com_android_support_Menu_Changes`
symbols are never found and every call silently does nothing. `RegisterNatives`
fixes it by handing ART the `(name, descriptor, function)` table explicitly.

Confirming evidence: `libsf4.so` exports **exactly one symbol, `JNI_OnLoad`**, and
has zero `Java_*` exports. A library that relied on automatic resolution would
have to export them. It does not, so it registers.

**4. Construct on the UI thread.** The menu adds a Window; only the thread owning
the ViewRootImpl may do that. Getting this wrong is the classic
`Can't create handler inside thread that has not called Looper.prepare()` crash.
The hook thread is the wrong place for it.

## LGL is a menu, not a hook engine

Parsed from `payload.dex`, `Lcom/android/support/Menu`:

```
Changes          NATIVE static   (Context, int, String, int, boolean, String)
GetFeatureList   NATIVE virtual  () -> String[]
Icon             NATIVE virtual  () -> String
IconWebViewData  NATIVE virtual  () -> String
Init             NATIVE virtual  (Context, TextView, TextView)
SettingsList     NATIVE virtual  () -> String[]
```

Plus non-native `SeekBar`, `Toggle`, `Switch`, `Spinner`, `CheckBox`,
`RadioButton`, `InputNum`, `InputText`, `Button`, `Category`, `Collapse` -
View construction. LGL renders UI and reports which feature changed. It
intercepts nothing.

That is why the earlier framing was off. LGL and Pine sit at different layers:
Pine replaces method entry points in ART, LGL draws a menu. "We don't need Pine"
is true when hooking code you can compile yourself - call your function
directly. The moment the target is `final`, private, framework, or inside a
vendored `.so`, you need an engine, and swapping the menu library does not change
that.

## The signature trap

The most useful thing in this whole analysis. LGL ships variants whose signatures
**disagree**:

```
upstream LGL      Changes(Context, int featNum, String featName,
                          int value, long lvalue, boolean bl, String text)
dex in this repo  Changes(Context, int featNum, String featName,
                          int value, boolean bl, String text)
```

No `long`. The constructor differs too: this dex's is `(Context)V`, not the
`(ContextWrapper, LinearLayout)V` you would copy from a tutorial.

Hardcode the wrong descriptor and `RegisterNatives` fails - or worse, appears to
succeed while the method never binds. Nothing errors at build time and nothing
errors at load time. The menu just does nothing, and you have no idea why.

So the template does not hardcode them. `tools/embed_dex.py` **reads them out of
the dex you embed** and generates three headers:

```
embedded_dex.h      the dex as ASCII hex
lgl_bindings.h      extern "C" decls + the JNINativeMethod table
lgl_descriptors.h   class name, constructor descriptor, Changes descriptor
```

Swap the dex, rerun the tool, everything stays in step. Verified: running it
against `payload.dex` reports `constructor (Landroid/content/Context;)V` and
`Changes (...IZLjava/lang/String;)V`, matching what the dex actually contains.

## Verified in the template

Compiled and linked with the desktop toolchain against real JDK 21 JNI headers:

- All four sources compile clean.
- Links to one `.so`, 164 KB.
- Exports `Changes`, `GetFeatureList`, `Icon`, `IconWebViewData`, `Init`,
  `SettingsList`, `JNI_OnLoad`, `Java_..._nativeStartMenu`.
- The dex hex is present in the built binary (offset `0x61c0`).
- Hex round-trips byte-identically (`sha256` matches `payload.dex`).
- `-Wl,-z,max-page-size=16384` moves every `LOAD` segment to 0x4000 alignment.

Not verified: nothing has been run on a device. The dex loads and the menu
constructs only in principle until someone does.

## What is deliberately not copied

The reference libraries are built to be hard to inspect. `libfancy-bypass.so`
exports 2,924 dynamic symbols whose names are all SHA-1-looking hashes, holds
1,649 strings at 34% printable, and stashes functionality in a 3,198-entry
`init_array`. The 48 KB encrypted `.rodata` is the same instinct.

None of that is here. It hides a mod from analysis, and against your own source
there is nothing to hide from. It also makes debugging impossible: when your
`RegisterNatives` fails at 2am, the difference between a working build and a
wall is being able to read your own logcat.
