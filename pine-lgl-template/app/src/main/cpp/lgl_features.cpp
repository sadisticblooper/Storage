// The one function LGL calls to build the menu.
//
// LGL's own Main.cpp defines GetFeatureList as a JNI export; the Java side
// reflects it and renders whatever descriptors you return. Vendoring the full
// upstream menu (overlay, themes, prefs) is out of scope here — this shows the
// contract so you can wire your own build to it.
//
// Descriptor format: <Number>_<Type>_<Name>_<args>
// The leading number is optional; without it features are numbered in order.
// See README.md for the full type table.

#include <jni.h>
#include <string>
#include <vector>

// Obfuscating the strings is optional. LGL ships an OBFUSCATE macro; plain
// literals are fine for a template you own.
#define OBFUSCATE(s) s

extern "C" jobjectArray GetFeatureList(JNIEnv *env, jobject /*context*/) {
    const char *features[] = {
            OBFUSCATE("Toggle_No death"),
            OBFUSCATE("SeekBar_Score multiplier_1_100"),
            OBFUSCATE("SeekBar_Coins multiplier_1_1000"),
            OBFUSCATE("Category_Examples"),
            OBFUSCATE("100_Toggle_True_Enabled by default"),
            OBFUSCATE("Spinner_Mode_Normal,Hardcore,Custom"),
            OBFUSCATE("InputValue_Max value_0_9999"),
            OBFUSCATE("Button_Reset"),
            OBFUSCATE("Collapse_Advanced"),
            OBFUSCATE("CollapseAdd_Toggle_Debug overlay"),
            OBFUSCATE("RichTextView_Sliders deliver an int in <b>value</b>. "
                      "Toggles deliver a bool in <i>boolean</i>."),
    };

    const int count = static_cast<int>(sizeof(features) / sizeof(features[0]));
    jclass stringClass = env->FindClass("java/lang/String");
    jobjectArray ret = env->NewObjectArray(count, stringClass, nullptr);
    for (int i = 0; i < count; ++i) {
        env->SetObjectArrayElement(ret, i,
                env->NewStringUTF(features[i]));
    }
    return ret;
}

// LGL calls this on every user interaction.
//   featNum  index (or the explicit number you prefixed)
//   featName the display name
//   value    SeekBar / Spinner / InputValue payload
//   lvalue   64-bit variant (InputLValue)
//   boolean  Toggle / CheckBox state
//   text     InputText payload
extern "C" void Changes(JNIEnv *env, jclass /*clazz*/, jobject /*obj*/,
                        jint featNum, jstring featName, jint value,
                        jlong lvalue, jboolean boolean, jstring text) {
    // Route to your hook layer here. Example wiring:
    //   switch (featNum) {
    //     case 0: g_noDeath = boolean; break;   // consumed by your hook body
    //     case 1: g_scoreMul = value; break;
    //   }
    (void) env; (void) featNum; (void) featName; (void) value;
    (void) lvalue; (void) boolean; (void) text;
}
