package com.example.hooktemplate;

import android.app.Application;
import android.content.Context;
import android.util.Log;

/**
 * Entry point. Declared as android:name on &lt;application&gt; so it runs before any
 * activity - the same slot the loader occupies with its own Application class.
 *
 * It loads native code and starts the hook thread, then stops. It deliberately
 * does NOT start the menu: see MainActivity. The menu needs an Activity, and at
 * Application.onCreate there is not one yet.
 */
public class HookApp extends Application {

    private static final String TAG = "HookTemplate";
    private static Context appContext;

    @Override
    public void onCreate() {
        super.onCreate();
        appContext = this;

        // Native first: it may want to hook methods the Java hooks below call.
        try {
            System.loadLibrary("hooktemplate");
            Log.i(TAG, "native loaded");
        } catch (UnsatisfiedLinkError e) {
            Log.e(TAG, "native load failed", e);
        }

        Hooks.install();
    }

    public static Context context() {
        return appContext;
    }

    /**
     * Starts the embedded menu, using the given Activity as its host.
     *
     * Called from MainActivity.onResume. Not from Application.onCreate, because
     * the menu sets a theme on its host activity and attaches a window - both
     * need a real Activity that has already been created.
     *
     * @return true if the menu dex decoded, loaded, had its natives registered,
     *         and the menu started.
     */
    public static boolean startMenu(android.app.Activity activity) {
        try {
            return nativeStartMenu(activity);
        } catch (Throwable t) {
            Log.e(TAG, "menu start threw", t);
            return false;
        }
    }

    /** Implemented in lgl/dex_loader.cpp. */
    private static native boolean nativeStartMenu(android.app.Activity activity);
}
