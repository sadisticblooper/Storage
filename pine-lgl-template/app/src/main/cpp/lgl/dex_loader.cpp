// Dex loader: get the menu dex into the running process and class-load it.
//
// This is the mechanism the actionmods loader uses, reduced to the part that
// matters. Three things have to happen, in this order:
//
//   1. the dex must exist somewhere readable          -> stage it to disk
//   2. a ClassLoader must be able to see it           -> InMemoryDexClassLoader
//   3. the menu class must be constructed on the UI
//      thread, because it adds a Window              -> post to main Looper
//
// Step 2 is the interesting one. InMemoryDexClassLoader takes a ByteBuffer of
// dex bytes and returns a loader with no file behind it, so nothing has to be
// linked or installed. Anything the dex needs at runtime - Activity for
// getTopActivity(), WindowManager for the overlay - is resolved through the
// *app's* loader, which we supply as the parent. That is why the menu resurfaces
// as itself rather than being redefined: the class only exists in our loader.
//
// No hidden API reflection is used. The constructors are public API since
// Android 8.0 (API 26).

#include "dex_loader.h"
#include "embedded_dex.h"
#include "lgl_descriptors.h"
#include "lgl_bindings.h"

#include <android/log.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <unistd.h>
#include <sys/stat.h>

#define LOG_TAG "DexLoader"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

namespace dexload {

// ---- embedded dex -> bytes --------------------------------------------------

bool decode_embedded_dex(std::string *out) {
    const size_t hexLen = kLglDexHexLen;
    if (hexLen % 2 != 0) {
        LOGE("embedded dex has odd hex length: %zu", hexLen);
        return false;
    }
    out->clear();
    out->reserve(hexLen / 2);

    const char *p = kLglDexHex;
    auto nibble = [](char c) -> int {
        if (c >= '0' && c <= '9') return c - '0';
        if (c >= 'a' && c <= 'f') return c - 'a' + 10;
        if (c >= 'A' && c <= 'F') return c - 'A' + 10;
        return -1;
    };
    for (size_t i = 0; i < hexLen; i += 2) {
        const int hi = nibble(p[i]);
        const int lo = nibble(p[i + 1]);
        if (hi < 0 || lo < 0) {
            LOGE("bad hex at offset %zu", i);
            return false;
        }
        out->push_back(static_cast<char>((hi << 4) | lo));
    }
    return true;
}

// ---- staging ----------------------------------------------------------------
//
// InMemoryDexClassLoader does not need a file on disk, but writing one anyway is
// worth it: when a menu fails to load in the field, the artifact you can pull
// with `adb pull` is the difference between a five minute debug and a day of it.
// The write is namespaced to this app's own directory, so it needs no
// permissions on any Android version.

static bool write_bytes(const char *path, const std::string &bytes) {
    FILE *f = fopen(path, "wb");
    if (!f) return false;
    const size_t wrote = fwrite(bytes.data(), 1, bytes.size(), f);
    fclose(f);
    return wrote == bytes.size();
}

static bool read_bytes(const char *path, std::string *out) {
    FILE *f = fopen(path, "rb");
    if (!f) return false;
    fseek(f, 0, SEEK_END);
    const long size = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (size <= 0) {
        fclose(f);
        return false;
    }
    out->resize(static_cast<size_t>(size));
    const size_t got = fread(&(*out)[0], 1, out->size(), f);
    fclose(f);
    return got == out->size();
}

std::string stage_dex_to_disk(const std::string &dex) {
    const char *dir = getenv("LGL_STAGE_DIR");
    if (dir == nullptr) {
        LOGE("LGL_STAGE_DIR not set; skipping staging");
        return {};
    }
    std::string path(dir);
    path += "/menu.dex";

    if (!write_bytes(path.c_str(), dex)) {
        LOGE("staging failed at %s", path.c_str());
        return {};
    }
    LOGE("stage dir is world-readable - for a personal debugging build only");
    chmod(path.c_str(), 0666);
    LOGI("staged %zu bytes to %s", dex.size(), path.c_str());
    return path;
}

// ---- JNI: build the loader and construct the menu ---------------------------

bool load_menu(JNIEnv *env, jobject app_context) {
    std::string dex;
    if (!decode_embedded_dex(&dex)) {
        LOGE("embedded dex did not decode");
        return false;
    }
    LOGI("decoded menu dex: %zu bytes", dex.size());

    if (!stage_dex_to_disk(dex).empty()) {
        // Round-trip check: if what we wrote cannot be read back and does not
        // match, the file is not trustworthy and there is no point continuing.
        const char *dir = getenv("LGL_STAGE_DIR");
        std::string path(dir);
        path += "/menu.dex";
        std::string back;
        if (!read_bytes(path.c_str(), &back) || back != dex) {
            LOGE("staged dex failed round-trip; refusing to use it");
            return false;
        }
        LOGI("staged dex verified");
    }

    // 1. App's own loader becomes the parent, so the menu can see Activity,
    //    WindowManager, Context, and this library's natives.
    jclass contextClass = env->FindClass("android/content/ContextWrapper");
    if (contextClass == nullptr) {
        LOGE("FindClass(ContextWrapper) failed");
        return false;
    }
    jmethodID getClassLoader = env->GetMethodID(
            contextClass, "getClassLoader", "()Ljava/lang/ClassLoader;");
    if (getClassLoader == nullptr) {
        LOGE("getClassLoader missing");
        return false;
    }
    jobject parent_loader = env->CallObjectMethod(app_context, getClassLoader);
    if (env->ExceptionCheck()) {
        env->ExceptionDescribe();
        env->ExceptionClear();
        return false;
    }

    // 2. Our loader, backed by the decoded bytes and nothing else.
    jclass bufferClass = env->FindClass("java/nio/ByteBuffer");
    jmethodID wrap = env->GetStaticMethodID(
            bufferClass, "wrap", "([B)Ljava/nio/ByteBuffer;");
    jbyteArray bytes = env->NewByteArray(static_cast<jsize>(dex.size()));
    env->SetByteArrayRegion(bytes, 0, static_cast<jsize>(dex.size()),
                            reinterpret_cast<const jbyte *>(dex.data()));
    jobject buffer = env->CallStaticObjectMethod(bufferClass, wrap, bytes);

    jclass dexLoaderClass = env->FindClass("dalvik/system/InMemoryDexClassLoader");
    if (dexLoaderClass == nullptr) {
        LOGE("InMemoryDexClassLoader unavailable (needs API 26+)");
        return false;
    }
    jmethodID dexLoaderCtor = env->GetMethodID(
            dexLoaderClass, "<init>",
            "(Ljava/nio/ByteBuffer;Ljava/lang/ClassLoader;)V");
    jobject menu_loader = env->NewObject(dexLoaderClass, dexLoaderCtor,
                                         buffer, parent_loader);
    if (menu_loader == nullptr || env->ExceptionCheck()) {
        env->ExceptionDescribe();
        env->ExceptionClear();
        LOGE("InMemoryDexClassLoader construction failed");
        return false;
    }

    // 3. Load the menu class through THAT loader, not FindClass. FindClass would
    //    search the loader that ran System.loadLibrary and never find it.
    jclass classLoaderClass = env->FindClass("java/lang/ClassLoader");
    jmethodID loadClass = env->GetMethodID(
            classLoaderClass, "loadClass",
            "(Ljava/lang/String;)Ljava/lang/Class;");
    jclass menuClass = static_cast<jclass>(env->CallObjectMethod(
            menu_loader, loadClass, env->NewStringUTF(kLglMenuClass)));
    if (menuClass == nullptr || env->ExceptionCheck()) {
        env->ExceptionDescribe();
        env->ExceptionClear();
        LOGE("loadClass(%s) failed", kLglMenuClass);
        return false;
    }

    // 4. Bind the menu's natives to this library, by hand.
    //
    //    ART resolves a native against the loader that DEFINED the class. This
    //    class was defined by our InMemoryDexClassLoader, which has never run
    //    System.loadLibrary - so the automatic lookup has nowhere to look, and
    //    the methods would silently stay unbound. RegisterNatives takes the
    //    (name, descriptor, function) table explicitly and sidesteps the whole
    //    question. kLglNativeBindings is generated from the dex, so the
    //    descriptors are guaranteed to match what the class actually declares.
    JNINativeMethod methods[64];
    if (kLglNativeBindingCount > 64) {
        LOGE("binding table too large: %u", kLglNativeBindingCount);
        return false;
    }
    for (unsigned int i = 0; i < kLglNativeBindingCount; ++i) {
        methods[i].name = const_cast<char *>(kLglNativeBindings[i].name);
        methods[i].signature = const_cast<char *>(
                kLglNativeBindings[i].descriptor);
        methods[i].fnPtr = kLglNativeBindings[i].function;
    }
    if (env->RegisterNatives(menuClass, methods,
                             static_cast<jint>(kLglNativeBindingCount)) != 0) {
        env->ExceptionDescribe();
        env->ExceptionClear();
        LOGE("RegisterNatives failed - dex and generated table disagree");
        return false;
    }
    LOGI("registered %u natives", kLglNativeBindingCount);

    // 5. Start the menu.
    //
    //    Use the menu's own static CreateMenu(Context) rather than constructing
    //    it here. That method is the designed entry point and it does three
    //    things we would otherwise have to reproduce by hand:
    //      - setTheme(Theme.Material) on the host activity
    //      - SetWindowManagerActivity(), which is what actually attaches the
    //        overlay to the WindowManager
    //      - ShowMenu(), which posts the delayed GetFeatureList() call
    //
    //    Constructing Menu directly and stopping there produces an object that
    //    is never attached and never shown - a menu that silently does nothing.
    //    That is the difference between this working and not.
    //
    //    Note CreateMenu takes a Context, not an Activity, and branches: given a
    //    plain Context it hops to the main Looper and finds the top activity by
    //    reflection, given an Activity it goes straight through. Passing the
    //    Activity is the more predictable path, which is why HookApp is not the
    //    one calling this.
    jmethodID createMenu = env->GetStaticMethodID(
            menuClass, "CreateMenu", "(Landroid/content/Context;)V");
    if (createMenu == nullptr) {
        LOGE("CreateMenu missing - regenerate headers from this dex");
        return false;
    }
    env->CallStaticVoidMethod(menuClass, createMenu, app_context);
    if (env->ExceptionCheck()) {
        env->ExceptionDescribe();
        env->ExceptionClear();
        LOGE("CreateMenu threw");
        return false;
    }
    LOGI("menu started");
    return true;
}

// ---- Java-side helpers ------------------------------------------------------

std::string get_files_dir(JNIEnv *env, jobject context) {
    jclass ctxClass = env->FindClass("android/content/Context");
    jmethodID getFilesDir = env->GetMethodID(ctxClass, "getFilesDir",
                                             "()Ljava/io/File;");
    jobject file = env->CallObjectMethod(context, getFilesDir);
    jclass fileClass = env->FindClass("java/io/File");
    jmethodID getPath = env->GetMethodID(fileClass, "getAbsolutePath",
                                         "()Ljava/lang/String;");
    jstring path = static_cast<jstring>(env->CallObjectMethod(file, getPath));
    const char *utf = env->GetStringUTFChars(path, nullptr);
    std::string result = utf ? utf : "";
    env->ReleaseStringUTFChars(path, utf);
    return result;
}

}  // namespace dexload

// Called from Java on the UI thread. Constructing the menu adds a Window, which
// must happen on the thread that owns the ViewRootImpl, so this is not something
// to farm out to a worker the way the hook installation is.
extern "C" JNIEXPORT jboolean JNICALL
Java_com_example_hooktemplate_HookApp_nativeStartMenu(JNIEnv *env, jclass,
                                                      jobject context) {
    const std::string dir = dexload::get_files_dir(env, context);
    setenv("LGL_STAGE_DIR", dir.c_str(), 1);
    __android_log_print(ANDROID_LOG_INFO, "DexLoader", "files dir: %s",
                        dir.c_str());
    return dexload::load_menu(env, context) ? JNI_TRUE : JNI_FALSE;
}
