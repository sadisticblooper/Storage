# How the actionmods loader works, and where LGL vs Pine actually sit

Everything below was checked against the binaries with `readelf`, symbol dumps,
DEX parsing, entropy mapping and partial decryption. Claims I could not verify
are marked as such.

## First: the four artifacts are not all from the same sample

| File | Size | SONAME / identity | Where it is |
|---|---|---|---|
| `PHubLoader.apk` | 20.0 MB | `com.sherrytse.parallel.cloner` | the loader APK |
| `PH_original.apk` | 9.0 MB | the unmodified app | original |
| `actionmods/lib/arm64.so` | 944 KB | `libfancy-bypass.so` | inside PHubLoader.apk |
| `libsf4.so` | 768 KB | `libsf4vip.so` | **not in PHubLoader.apk** |
| `payload.dex` | 58.5 KB | LGL menu | **not in PHubLoader.apk** |

I searched every entry and every nested APK in both APKs for `libsf4.so`,
`payload.dex` and the `LGL` marker. Neither is present. They are from a
*different* mod build — a smaller variant than the one shipped in PHubLoader.
Comparing them to PHubLoader is comparing two cousins, not two versions.

## Answer 1: LGL is a menu, not a hooking engine

These are two different layers. LGL does no interception at all.

Verified from `payload.dex`, class `Lcom/android/support/Menu`:

```
<init>                 acc=0x10001   (constructor, has code)
Changes                acc=0x0109    NATIVE static public
CreateMenu             acc=0x0009    static public, has code
GetFeatureList         acc=0x0100    NATIVE
Icon                   acc=0x0100    NATIVE
IconWebViewData        acc=0x0100    NATIVE
Init                   acc=0x0100    NATIVE
SettingsList           acc=0x0100    NATIVE
SeekBar / Toggle / Spinner / Collapse / RichTextView ...  has code
```

So LGL is: a feature-descriptor parser, a View builder (SeekBar, Toggle,
Spinner, Collapse, RichTextView), a draggable overlay, and a preferences
store. The six native methods are the bridge to your `.so`. Nothing in that
list replaces an existing method in another app.

Pine is the opposite: it replaces method entry points in ART so your code runs
*instead of* someone else's. It has no UI.

**So "we don't need Pine" is only true in one specific case — hooking code you
can edit yourself.** If you own the source, you call your own function directly
and no engine is involved. The moment you need to intercept a method you cannot
recompile (final, private, framework, vendored `.so`), you need an engine, and
swapping LGL for something else does not change that. LGL and Pine are not
substitutes.

## Answer 2: was Pine used? Yes, but it is not the visible machinery

Exhaustive string search of `actionmods/lib/arm64.so` turns up exactly one Pine
token:

```
_ZTHN4pine28ScopedMemoryAccessProtection7currentE
  -> "TLS init function for pine::ScopedMemoryAccessProtection::current"
```

That symbol is genuine Pine source. Verified against upstream — it is defined in
`canyie/pine` at `core/src/main/cpp/utils/scoped_memory_access_protection.h`
(GitHub code search returns 4 files: the header, the `.cpp`, and two
`trampoline/` call sites).

But note the details, because they change the conclusion:

- It is `UND` and `WEAK` — imported, never satisfied.
- The binary has **no TLS sections**.
- `NEEDED` is only `liblog, libm, libdl, libc`. `libpine.so` is not linked.
- There are **zero** occurrences of `hook`, `trampoline`, `ArtMethod`,
  `Instrumentation`, `ClassLinker` or `dex` as strings.

Conclusion: Pine was part of the toolchain, and a static link left this one
dangling TLS reference behind, but the shipped library does not depend on Pine
at load time. The reason none of the hooking machinery is legible is that the
library is **symbol-obfuscated**: it exports 2,924 dynamic symbols whose names
are all SHA-1-looking hashes (`d8fdccf33fd7d76e977affaffa94d7e68472ab6c`), and
the whole file holds only 1,649 strings at 34% printable. The functionality is
present; the names are gone.

That is the honest answer: the framework is not identifiable by signature
because it was deliberately stripped of names.

## Answer 3: what libsf4.so actually contains

`libsf4.so` is the leaner variant. It exports exactly one symbol:
`JNI_OnLoad`. Its `.rodata` is **partly encrypted**:

- 48 KB contiguous high-entropy region at `0x8d800`–`0x99800`
- exactly 3 × 16 KB pages
- 21% of `.rodata` sits above entropy 7.0

Partial recovery, and where it stopped: assuming an 8-byte repeating XOR key and
scoring each key byte by how many bytes land inside the base64 alphabet gives a
key of `75 21 09 bb e7 4d 49 ed`, under which **99.74% of the region is base64
characters** (vs a ~25% random baseline). That is not chance, so the region is
an obfuscated string table. Base64-decoding the result yields a 36 KB
high-entropy blob containing a zlib stream that inflates to 106 KB, but that
output uses only 20 distinct byte values and decodes to nothing meaningful.

**I could not recover the plaintext.** The remaining layer needs the runtime key
derivation or the decryption routine, neither of which is reachable by static
analysis alone. Treat the above as partial.

Also decisive for the earlier Android 16 question: the encryption is why no
`GetFeatureList` / `com/android/support` strings appear in the `.so`. They are
not absent because LGL is absent — they are inside the encrypted `.rodata`.

## Answer 4: the loader architecture

Manifest, verified by parsing the AXML:

```
package                    = com.sherrytse.parallel.cloner
android:name               = actionmods.loader.core        (Application)
android:appComponentFactory= actionmods.loader.coreapp     (AppComponentFactory)
android:sharedUserId       = com.sherrytse.parallel.cloner
compileSdkVersion          = 36  / codename "16"
```

Verified from the main `classes.dex`: `Lactionmods/loader/core;` extends
`Landroid/app/Application;` and implements `attachBaseContext`, `onCreate`,
`getPackageName`. `Lactionmods/loader/coreapp;` extends
`Landroid/app/AppComponentFactory;` and implements `instantiateApplication`.

Entry-set diff of `PHubLoader.apk` against `PH_original.apk` (789 entries each,
so the original was repackaged wholesale):

```
only in loader:
  actionmods/dex/classes.dex      519 KB   cloner runtime (com/sherrytse)
  actionmods/lib/arm64.so         944 KB   libfancy-bypass.so
  actionmods/origin.apk           9.0 MB   the original app, repackaged
  lib/arm64-v8a/libparallelhub.so 666 KB   virtualisation engine
  META-INF/*                               re-signed
changed: AndroidManifest.xml, classes.dex, resources.arsc
```

`actionmods/origin.apk` has the *same* 789 entries as `PH_original.apk` and its
`classes.dex` is 8,722,104 bytes vs 8,722,108 — a 4-byte difference. It is the
original app, untouched apart from sealing.

The chain:

1. `appComponentFactory`/`Application` run before any app code.
2. `libparallelhub.so` + the `com.sherrytse.parallel` cloner bring the target up
   inside a virtual process.
3. The LGL menu dex is loaded into that process.
4. `libfancy-bypass.so` handles the native side.
5. LGL renders the overlay. A toggle calls the `Changes` native, which writes the
   value your hook body reads.

Note the separation of concerns: the *loader* is a parallel-space host. LGL is
just the menu that ends up inside the hosted process. Neither knows about the
other.

## Answer 5: the 16 KB finding, which contradicts what I said earlier

`LOAD` segment alignment, read straight from the program headers:

```
libsf4.so   (libsf4vip.so):      0x10000   (64 KB)
arm64.so    (libfancy-bypass.so): 0x4000   (16 KB)
stock Pine  (libpine.so, 0.3.0):  0x1000   ( 4 KB)
```

Both mod libraries ship 16 KB-aligned segments. Stock Pine does not — its
second segment sits at vaddr `0x11770`, not a multiple of 16 KB.

This is why these builds run on newer devices where stock Pine fails, and it
means the fix is exactly what I described: relink with
`-Wl,-z,max-page-size=16384`. The authors of this loader did it; the upstream
AAR has not. It does not rescue LGL-vs-Pine though — the alignment is a
property of the build, not of the menu library.

## What this means for the template

- Keep `lgl/` and `mod/` separate, as the template already does. That split
  mirrors the real design: the menu knows nothing about your features.
- For your own game, do not reach for a hooking engine to change your own code.
  Call your function. Use an engine only for methods you cannot recompile.
- Build with 16 KB alignment from day one:
  `-Wl,-z,max-page-size=16384`. Retrofitting it later is a rebuild anyway.
- Nothing here argues for adopting the loader machinery. The opaque parts —
  symbol hashing, the encrypted `.rodata`, the 3,198-entry `init_array` in
  `libfancy-bypass.so` — exist to hide the mod from inspection, and against your
  own source there is nothing to hide from.
