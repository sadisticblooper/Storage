// LGL glue: translates the menu library's JNI entry points into the mod's
// namespace-level hooks.
//
// This is the ONLY file that knows LGL exists. Swapping to a different menu
// library means rewriting this file and lgl.h; nothing under mod/ changes.

#include "lgl.h"
#include "../mod/mod_api.h"

#include <string>

// ---- JNI entry points -------------------------------------------------------

extern "C" jobjectArray GetFeatureList(JNIEnv *env, jobject /*context*/) {
    int count = 0;
    const char *const *features = mod::feature_descriptors(&count);

    jclass stringClass = env->FindClass("java/lang/String");
    jobjectArray ret = env->NewObjectArray(count, stringClass, nullptr);
    for (int i = 0; i < count; ++i) {
        env->SetObjectArrayElement(ret, i, env->NewStringUTF(features[i]));
    }
    return ret;
}

extern "C" void Changes(JNIEnv *env, jclass /*clazz*/, jobject /*obj*/,
                        jint featNum, jstring /*featName*/, jint value,
                        jlong lvalue, jboolean boolean, jstring text) {
    // Convert the one type that needs it; the mod should not deal with JNI.
    std::string textUtf8;
    if (text != nullptr) {
        const char *chars = env->GetStringUTFChars(text, nullptr);
        if (chars != nullptr) {
            textUtf8 = chars;
            env->ReleaseStringUTFChars(text, chars);
        }
    }

    mod::on_feature_changed(featNum, value, lvalue, boolean == JNI_TRUE,
                           textUtf8.empty() ? nullptr : textUtf8.c_str());
}
