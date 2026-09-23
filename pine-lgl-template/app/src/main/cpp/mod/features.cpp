// The mod: what features exist, and where their values land.
//
// Adding a feature is one line in kFeatures plus one case in
// on_feature_changed. No menu code is involved.

#include "mod_api.h"

#include <android/log.h>

#define LOG_TAG "Mod"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)

namespace mod {

// ---- feature values ---------------------------------------------------------

bool g_no_death = false;
int g_score_multiplier = 1;
int g_coin_multiplier = 1;
bool g_debug_overlay = false;

// ---- feature table ----------------------------------------------------------
//
// The leading number on each entry is the featNum handed to
// on_feature_changed(). Keep them unique and in step with the cases below.
// See mod_api.h for why every entry must have one.

static const char *const kFeatures[] = {
        "0_Toggle_No death",
        "1_SeekBar_Score multiplier_1_100",
        "2_SeekBar_Coins multiplier_1_1000",
        "3_Spinner_Mode_Normal,Hardcore,Custom",
        "4_InputValue_Max value_0_9999",
        "5_Button_Reset",
        "6_Toggle_Debug overlay_True",
        "7_Category_Extras",
        "8_CheckBox_Verbose logging",
        "9_RadioButton_Tier_Bronze,Silver,Gold",
        "10_Collapse_Advanced",
        "11_CollapseAdd_InputText_Pattern",
};

const char *const *feature_descriptors(int *count_out) {
    *count_out = static_cast<int>(sizeof(kFeatures) / sizeof(kFeatures[0]));
    return kFeatures;
}

// ---- interaction routing ----------------------------------------------------

void on_feature_changed(int featNum, int value, bool enabled,
                        const char *text) {
    switch (featNum) {
        case 0:  // Toggle_No death
            g_no_death = enabled;
            LOGI("no_death = %d", g_no_death);
            break;
        case 1:  // SeekBar_Score multiplier
            g_score_multiplier = value;
            LOGI("score_multiplier = %d", value);
            break;
        case 2:  // SeekBar_Coins multiplier
            g_coin_multiplier = value;
            LOGI("coin_multiplier = %d", value);
            break;
        case 3:  // Spinner_Mode - value is the index, 0..2
            LOGI("mode index = %d", value);
            break;
        case 4:  // InputValue_Max value
            LOGI("max value = %d", value);
            break;
        case 5:  // Button_Reset
            g_no_death = false;
            g_score_multiplier = 1;
            g_coin_multiplier = 1;
            LOGI("reset");
            break;
        case 6:  // Toggle_Debug overlay
            g_debug_overlay = enabled;
            LOGI("debug_overlay = %d", enabled);
            break;
        case 8:  // CheckBox_Verbose logging
            LOGI("verbose = %d", enabled);
            break;
        case 9:  // RadioButton_Tier - value is the index, 0..2
            LOGI("tier index = %d", value);
            break;
        case 11:  // CollapseAdd_InputText_Pattern
            LOGI("pattern = %s", text ? text : "(null)");
            break;
        default:
            break;
    }
}

}  // namespace mod
