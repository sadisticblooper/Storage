package com.example.hooktemplate;

import android.app.Application;
import android.content.Context;
import android.util.Log;

/**
 * Entry point. Declared as android:name on <application> so it runs before any
 * activity — the same position the loader occupies with its own Application
 * class. Here it is just your own code running normally.
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
}
