// Native entry point, following the LGL pattern.
//
// The shape here is what matters: a constructor runs the moment
// System.loadLibrary("hooktemplate") executes, and it must NOT do heavy work
// on the calling thread — that thread is the one starting your app. Spawn a
// thread and do the real setup there, waiting for the target library to be
// mapped before touching it.

#include <jni.h>
#include <pthread.h>
#include <unistd.h>
#include <cstring>
#include <android/log.h>

#define LOG_TAG "HookTemplate"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

// Point this at your own library.
static const char *TARGET_LIB = "libhooktemplate.so";

static JavaVM *g_vm = nullptr;

extern "C" JNIEXPORT jint JNI_OnLoad(JavaVM *vm, void *) {
    g_vm = vm;
    LOGI("JNI_OnLoad");
    return JNI_VERSION_1_6;
}

// Is the target already mapped into our address space? Checking on a timer is
// simpler and more portable than a dlopen listener.
static bool is_library_loaded(const char *name) {
    FILE *f = fopen("/proc/self/maps", "r");
    if (!f) {
        return false;
    }
    char line[512];
    bool found = false;
    while (fgets(line, sizeof(line), f)) {
        if (strstr(line, name)) {
            found = true;
            break;
        }
    }
    fclose(f);
    return found;
}

// Replace with real hook installation. Left as a stub on purpose: the
// interesting part for a template is the load/thread/wait choreography, not a
// borrowed hook body.
static void install_native_hooks() {
    LOGI("installing native hooks");
    // if (!is_library_loaded(TARGET_LIB)) { ... }
    //
    // With Dobby linked:
    //   HOOK_LIB(TARGET_LIB, "0x123456", my_hook, orig_my_hook);
    //
    // HOOK_LIB is the LGL helper; plain Dobby is:
    //   DobbyHook((void *)target_addr, (void *)my_hook, (void **)&orig_my_hook);
}

static void *hack_thread(void *) {
    LOGI("waiting for %s", TARGET_LIB);
    while (!is_library_loaded(TARGET_LIB)) {
        sleep(1);
    }
    LOGI("%s mapped, continuing", TARGET_LIB);

    install_native_hooks();

    LOGI("done");
    return nullptr;
}

__attribute__((constructor))
static void lib_main() {
    LOGI("constructor");
    pthread_t t;
    if (pthread_create(&t, nullptr, hack_thread, nullptr) == 0) {
        pthread_detach(t);
    } else {
        LOGE("failed to spawn thread");
    }
}
