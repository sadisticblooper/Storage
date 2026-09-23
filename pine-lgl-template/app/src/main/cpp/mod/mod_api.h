// What the mod exposes to whatever menu library is in use.
//
// This is the seam. lgl/impl.cpp includes this and calls into it; the mod
// includes this and implements it. Nothing under mod/ includes anything from
// lgl/, so replacing the menu library never touches your feature code.

#pragma once

namespace mod {

// ---- feature values ---------------------------------------------------------
// Written by on_feature_changed() on the menu thread, read by hook bodies on
// the game thread. Plain types on purpose — no locking drama, but also no
// ordering guarantee: a value can change mid-frame. Snap it into a local at
// the top of a hook if a torn read would matter.
extern bool g_no_death;
extern int g_score_multiplier;
extern int g_coin_multiplier;
extern bool g_debug_overlay;

// ---- feature table ----------------------------------------------------------
// Returns the descriptor array and writes its length to *count_out.
// Index in the array is the featNum delivered to on_feature_changed().
const char *const *feature_descriptors(int *count_out);

// Called for every user interaction. One entry point for every type; the menu
// layer does not interpret your features.
void on_feature_changed(int featNum, int value, long lvalue, bool enabled,
                        const char *text);

}  // namespace mod
