// The mod itself: what features exist, and where their values land.
//
// Feature value storage is just plain globals here. The point is that the
// feature list and the consumer of each value live in one file — adding a
// feature is one line in the descriptor table plus one read at the hook site,
// with no menu code to touch.

#include "mod_api.h"

#include <android/log.h>

#define LOG_TAG "Mod"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)

namespace mod {

// ---- feature values ---------------------------------------------------------
// Written by on_feature_changed(), read by your hook bodies. Plain ints/bools
// because they cross threads: the menu thread writes, the game thread reads.

bool g_no_death = false;
int g_score_multiplier = 1;
int g_coin_multiplier = 1;
bool g_debug_overlay = false;

// ---- feature table ----------------------------------------------------------
// Index in this array is the featNum delivered to on_feature_changed().
// Descriptor grammar: "<Number>_<Type>_<Name>_<args>"; leading number optional.

static const char *const kFeatures[] = {
        "Toggle_No death",
        "SeekBar_Score multiplier_1_100",
        "SeekBar_Coins multiplier_1_1000",
        "Category_Examples",
        "Spinner_Mode_Normal,Hardcore,Custom",
        "InputValue_Max value_0_9999",
        "Button_Reset",
        "Collapse_Advanced",
        "CollapseAdd_Toggle_Debug overlay",
        "RichTextView_Sliders deliver an int in <b>value</b>, "
        "toggles a bool in <i>boolean</i>.",
};

const char *const *feature_descriptors(int *count_out) {
    *count_out = static_cast<int>(sizeof(kFeatures) / sizeof(kFeatures[0]));
    return kFeatures;
}

// ---- interaction routing ----------------------------------------------------
// One switch, indexed by featNum. Keep the case numbers in sync with kFeatures.

void on_feature_changed(int featNum, int value, long /*lvalue*/, bool enabled,
                        const char *text) {
    switch (featNum) {
        case 0:  // Toggle_No death
            g_no_death = enabled;
            LOGI("no_death = %d", g_no_death);
            break;
        case 1:  // SeekBar_Score multiplier
            g_score_multiplier = value;
            LOGI("score_multiplier = %d", g_score_multiplier);
            break;
        case 2:  // SeekBar_Coins multiplier
            g_coin_multiplier = value;
            break;
        case 4:  // Spinner_Mode
            LOGI("mode index = %d", value);
            break;
        case 5:  // InputValue_Max value
            LOGI("max value = %d", value);
            break;
        case 6:  // Button_Reset
            g_no_death = false;
            g_score_multiplier = 1;
            g_coin_multiplier = 1;
            break;
        case 8:  // CollapseAdd_Toggle_Debug overlay
            g_debug_overlay = enabled;
            break;
        default:
            if (text != nullptr) {
                LOGI("text input: %s", text);
            }
            break;
    }
}

}  // namespace mod
