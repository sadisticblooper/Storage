// Public contract of the menu layer.
//
// The ONLY things here are the JNI symbols the menu library itself provides.
// The mod does not include this file at all - the dependency points one way,
// lgl -> mod, so the menu stays replaceable without touching your features.
//
// The actual signatures are in lgl_bindings.h, which is GENERATED from whatever
// dex you embed (tools/embed_dex.py). Do not hand-write them here. LGL ships
// variants whose signatures disagree, and a mismatch fails silently.

#pragma once

#include <jni.h>

// Documented here for orientation only; the compiler sees lgl_bindings.h.
//
//   GetFeatureList()            -> String[]   your feature descriptor list
//   SettingsList()              -> String[]   optional settings entries
//   Icon()                      -> String     optional menu icon
//   IconWebViewData()           -> String     optional webview icon data
//   Init(Context, TextView, TextView)   called once the views exist
//   Changes(Context, int featNum, String featName, int value,
//           boolean state, String text)   every user interaction
//
// Descriptor grammar: "<Number>_<Type>_<Name>_<args>", leading number optional.
// The array index is the featNum unless you prefix an explicit number.

extern "C" {

// Builds the UI. Implemented in lgl/impl.cpp; calls the mod's feature table.
jarray GetFeatureList(JNIEnv *env, jobject thiz);

// Called on every user interaction.
//   featNum  descriptor index, or the explicit number you prefixed
//   value    SeekBar / Spinner / InputValue payload
//   boolean  Toggle / CheckBox / Switch state
//   text     InputText payload
//
// Note: this menu variant has NO lvalue parameter. Upstream LGL does. That is
// exactly the kind of drift the generator exists to catch.
void Changes(JNIEnv *env, jclass clazz, jobject context, jint featNum,
             jobject featName, jint value, jboolean boolean, jobject text);

}  // extern "C"
