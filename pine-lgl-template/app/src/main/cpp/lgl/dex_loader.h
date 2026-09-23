// Menu dex loading. Header only declares the seam; dex_loader.cpp implements it.

#pragma once

#include <jni.h>
#include <string>

namespace dexload {

// Decode kLglDexHex (see embedded_dex.h) into raw dex bytes.
// Returns false if the hex is malformed rather than producing a truncated dex.
bool decode_embedded_dex(std::string *out);

// Write the dex next to the app's own files for debuggability, and hand back the
// path. Returns an empty string if staging is not configured or fails; staging is
// best-effort and never a reason to abort the load.
std::string stage_dex_to_disk(const std::string &dex);

// Decode, then build an InMemoryDexClassLoader over the bytes and construct the
// menu class inside it. Must be called on the UI thread.
bool load_menu(JNIEnv *env, jobject app_context);

// Where the app says we may write - Context.getFilesDir().
std::string get_files_dir(JNIEnv *env, jobject context);

}  // namespace dexload
