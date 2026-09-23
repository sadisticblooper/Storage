package com.example.hooktemplate;

import android.util.Log;

import java.lang.reflect.Method;

import top.canyie.pine.Pine;
import top.canyie.pine.PineConfig;
import top.canyie.pine.callback.MethodHook;
import top.canyie.pine.callback.MethodReplacement;
import top.canyie.pine.utils.ReflectionHelper;

/**
 * Pine hook examples, all pointing at methods in this app.
 *
 * Pine intercepts method calls in the current process by rewriting the ART
 * entry point of the target method, so the hook sees the call before the
 * original body runs and can alter arguments or the result.
 */
public final class Hooks {

    private static final String TAG = "HookTemplate";
    private static boolean installed;

    private Hooks() {
    }

    public static synchronized void install() {
        if (installed) {
            return;
        }
        installed = true;

        PineConfig.debug = true;
        // Must match the manifest's debuggable flag, or Pine may behave oddly.
        PineConfig.debuggable = BuildConfig.DEBUG;

        hookScoreReader();
        hookAlwaysPremium();
    }

    /**
     * beforeCall / afterCall. Read the receiver, then swap the return value.
     */
    private static void hookScoreReader() {
        try {
            Method getScore = ScoreBoard.class.getDeclaredMethod("getScore");
            Pine.hook(getScore, new MethodHook() {
                @Override
                public void beforeCall(Pine.CallFrame callFrame) {
                    // Receiver is available; useful for per-instance logic.
                    Log.i(TAG, "getScore() called on " + callFrame.thisObject);
                }

                @Override
                public void afterCall(Pine.CallFrame callFrame) {
                    Log.i(TAG, "getScore() returned " + callFrame.getResult());
                    callFrame.setResult(9999);
                }
            });
            Log.i(TAG, "hooked ScoreBoard.getScore");
        } catch (NoSuchMethodException e) {
            Log.e(TAG, "getScore not found", e);
        }
    }

    /**
     * Replace a method body entirely. DO_NOTHING makes it a no-op returning
     * null; returnConstant makes it return a fixed value.
     */
    private static void hookAlwaysPremium() {
        try {
            Method isPremium = ScoreBoard.class.getDeclaredMethod("isPremium");
            Pine.hook(isPremium, MethodReplacement.returnConstant(true));
            Log.i(TAG, "hooked ScoreBoard.isPremium -> true");
        } catch (NoSuchMethodException e) {
            Log.e(TAG, "isPremium not found", e);
        }
    }

    /**
     * Argument rewriting: force a method to always see a specific value.
     * ReflectionHelper avoids the getDeclaredMethod try/catch boilerplate.
     */
    public static void hookWithArgs() {
        Method setScore = ReflectionHelper.getMethod(ScoreBoard.class, "setScore", int.class);
        Pine.hook(setScore, new MethodHook() {
            @Override
            public void beforeCall(Pine.CallFrame callFrame) {
                callFrame.args[0] = 7777;
            }
        });
    }

    /**
     * Hooking a method that may not be loaded yet. canInitDeclaringClass=false
     * avoids initializing the target class at hook time, which matters for
     * static initializers that do real work.
     */
    public static void hookWithoutInit() {
        Method late = ReflectionHelper.findMethod(ScoreBoard.class, "lateInit");
        if (late != null) {
            Pine.hook(late, MethodReplacement.DO_NOTHING, false);
        }
    }
}
