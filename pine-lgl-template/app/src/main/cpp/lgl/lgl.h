// Public contract of the menu layer.
//
// The ONLY things here are the JNI symbols the menu library itself provides.
// The mod does not include this file at all — the dependency points one way,
// lgl -> mod, so the menu stays replaceable without touching your features.

#pragma once

#include <jni.h>

// LGL's JNI symbol names. Changing these is changing the menu library.
extern "C" {

// Called once by the menu to build the UI. Returns a String[] of descriptors,
// format "<Number>_<Type>_<Name>_<args>" — see the README type table.
// Implemented in lgl/impl.cpp; calls into the mod's feature table.
jobjectArray GetFeatureList(JNIEnv *env, jobject context);

// Called on every user interaction.
//   featNum  descriptor index, or the explicit number you prefixed
//   featName display name
//   value    SeekBar / Spinner / InputValue payload
//   lvalue   64-bit payload (InputLValue)
//   boolean  Toggle / CheckBox state
//   text     InputText payload
void Changes(JNIEnv *env, jclass clazz, jobject obj, jint featNum,
             jstring featName, jint value, jlong lvalue, jboolean boolean,
             jstring text);

}  // extern "C"
