package com.example.hooktemplate;

import android.app.Application;
import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

/**
 * Entry point. Declared as android:name on &lt;application&gt; so it runs before any
 * activity - the same position the loader occupies with its own Application
 * class. Here it is just your own code running normally.
 *
 * The menu dex lives inside libhooktemplate.so, not in the APK. What happens on
 * startup:
 *
 *   1. System.loadLibrary runs, which fires the .so's constructor and starts the
 *      hook thread.
 *   2. Once the UI thread is ready we call into native, which decodes the dex,
 *      wraps it in an InMemoryDexClassLoader, registers the menu's natives
 *      against that class, and constructs it.
 *
 * Step 2 has to be on the UI thread. The menu adds its own Window, and only the
 * thread that owns the ViewRootImpl may do that. This is the mistake that makes
 * hand-rolled loaders crash with "Can't create handler inside thread that has
 * not called Looper.prepare()" - the hook thread is the wrong place for it.
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
        startMenuOnUiThread();
    }

    /**
     * Decodes and instantiates the embedded menu dex. Returns nothing useful on
     * its own - watch logcat for "DexLoader" to see how far it got. Each step
     * logs before it fails, so the last line before a stop tells you what broke.
     */
    private void startMenuOnUiThread() {
        new Handler(Looper.getMainLooper()).post(() -> {
            try {
                boolean ok = nativeStartMenu(this);
                Log.i(TAG, "menu start -> " + ok);
            } catch (Throwable t) {
                Log.e(TAG, "menu start threw", t);
            }
        });
    }

    public static Context context() {
        return appContext;
    }

    /**
     * Implemented in lgl/dex_loader.cpp.
     *
     * @return true if the menu dex decoded, class-loaded, had its natives
     *         registered, and the menu object constructed.
     */
    private native boolean nativeStartMenu(Context context);
}
