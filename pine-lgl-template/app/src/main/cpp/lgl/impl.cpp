// LGL glue: implements the menu's JNI entry points and translates them into the
// mod's namespace-level API.
//
// This is the ONLY file that knows LGL exists. Swapping the menu library means
// regenerating the headers with tools/embed_dex.py and rewriting this file;
// nothing under mod/ changes.
//
// The signatures below are NOT transcribed from the canonical LGL example. They
// are generated to match whatever dex is embedded - see lgl_bindings.h. That
// matters more than it looks. The dex in this repo declares
//
//   Changes(Context, int featNum, String featName, int value,
//           boolean bl, String text)
//
// with no `long lvalue`, while upstream LGL declares one. Register either
// against the other and the method stays silently unbound.

#include "lgl.h"
#include "lgl_bindings.h"
#include "lgl_descriptors.h"
#include "../mod/mod_api.h"

#include <android/log.h>
#include <string>

#define LOG_TAG "LGL"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)

// ---- JNI entry points -------------------------------------------------------
//
// Signatures come from lgl_bindings.h, generated from the dex. featName is null
// in practice - the menu passes the descriptor index, not the name, so features
// are identified by number and featName is diagnostic only.

extern "C" jarray GetFeatureList(JNIEnv *env, jobject /*thiz*/) {
    int count = 0;
    const char *const *features = mod::feature_descriptors(&count);

    jclass stringClass = env->FindClass("java/lang/String");
    jobjectArray ret = env->NewObjectArray(count, stringClass, nullptr);
    for (int i = 0; i < count; ++i) {
        env->SetObjectArrayElement(ret, i, env->NewStringUTF(features[i]));
    }
    return ret;
}

extern "C" jarray SettingsList(JNIEnv *env, jobject /*thiz*/) {
    jclass stringClass = env->FindClass("java/lang/String");
    return env->NewObjectArray(0, stringClass, nullptr);
}

extern "C" jobject Icon(JNIEnv * /*env*/, jobject /*thiz*/) {
    // Path or URL the menu loads as the menu icon. Empty means none.
    return nullptr;
}

extern "C" jobject IconWebViewData(JNIEnv * /*env*/, jobject /*thiz*/) {
    return nullptr;
}

// Called after CreateMenu with the menu's two TextViews - title bar and footer -
// so you can stamp version or status text. Left as a hook for that.
extern "C" void Init(JNIEnv * /*env*/, jobject /*thiz*/, jobject /*context*/,
                     jobject /*titleView*/, jobject /*footerView*/) {
    LOGI("Init");
}

// The interaction callback. Every user action lands here.
extern "C" void Changes(JNIEnv *env, jclass /*clazz*/, jobject /*context*/,
                        jint featNum, jobject /*featName*/, jint value,
                        jboolean boolean, jobject text) {
    std::string textUtf8;
    if (text != nullptr) {
        const char *chars = env->GetStringUTFChars(
                static_cast<jstring>(text), nullptr);
        if (chars != nullptr) {
            textUtf8 = chars;
            env->ReleaseStringUTFChars(static_cast<jstring>(text), chars);
        }
    }

    mod::on_feature_changed(featNum, value, 0, boolean == JNI_TRUE,
                            textUtf8.empty() ? nullptr : textUtf8.c_str());
}
