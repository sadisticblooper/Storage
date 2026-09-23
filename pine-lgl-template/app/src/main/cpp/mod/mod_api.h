// The seam between your mod and whatever menu library renders it.
//
// lgl/impl.cpp includes this and calls into it. mod/features.cpp implements it.
// Nothing under mod/ includes anything from lgl/, so swapping the menu library
// never touches your feature code.

#pragma once

namespace mod {

// ---- feature values ---------------------------------------------------------
// Written on the menu thread, read on the game thread. Plain types on purpose.
// There is no ordering guarantee - a value can change mid-frame. Snap it into a
// local at the top of a hook if a torn read would matter.

extern bool g_no_death;
extern int g_score_multiplier;
extern int g_coin_multiplier;
extern bool g_debug_overlay;

// ---- feature table ----------------------------------------------------------
// Descriptor grammar (the menu's grammar, not ours):
//
//   [<number>_]<Type>_<Name>[_<arg>...][_True]
//
// Where <Type> is one of Toggle, SeekBar, Button, ButtonOnOff, Spinner,
// InputText, InputValue, CheckBox, RadioButton, Collapse, ButtonLink, Category,
// RichTextView, RichWebView.
//
// EVERY entry must carry an explicit leading number. That is the featNum the
// menu hands back, and it is what on_feature_changed routes on. Leaving it off
// falls back to a counter inside the menu that also increments for Category and
// Collapse - widgets that never call back - so the numbers silently drift and
// your features write to the wrong slots. Explicitly numbering every entry
// avoids that entirely.
//
// Returns the array and writes its length to *count_out.
const char *const *feature_descriptors(int *count_out);

// Called for every user interaction, whatever the widget type.
//
// Route on featNum. It is copied straight from your explicit descriptor number
// and is reliable for every widget type. Do not route on `name`: for Spinner
// and RadioButton the menu substitutes the selected item, not your label.
//
// `value` means different things per type:
//   Toggle, CheckBox, Switch   value unused, `enabled` carries the state
//   SeekBar, InputValue        value is the number
//   Spinner, RadioButton       value is the selected index
//   Button, ButtonOnOff        fires once, value unused
//   InputText                  `text` carries the string, value unused
void on_feature_changed(int featNum, int value, bool enabled,
                        const char *text);

}  // namespace mod
