package com.example.hooktemplate;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.util.Log;
import android.widget.TextView;

/**
 * Hosts the menu overlay.
 *
 * Two jobs: call into the hooked methods so you can watch the hooks fire in
 * logcat, and start the mod menu.
 */
public class MainActivity extends Activity {

    private static final String TAG = "HookTemplate";
    private static final int REQ_OVERLAY = 1001;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        ScoreBoard board = new ScoreBoard();
        Log.i(TAG, "getScore() before hook visible -> " + board.getScore());

        // getScore is hooked, so this prints the replaced value.
        int score = board.getScore();
        boolean premium = board.isPremium();

        Hooks.hookWithArgs();
        board.setScore(1);            // hook rewrites the argument to 7777
        Log.i(TAG, "setScore(1) then getScore() -> " + board.getScore());

        TextView tv = new TextView(this);
        tv.setText("score=" + score + " premium=" + premium
                + "\nscore after arg hook=" + board.getScore()
                + "\n\nWatch logcat tag \"DexLoader\" for menu startup.");
        setContentView(tv);
    }

    @Override
    protected void onResume() {
        super.onResume();
        maybeStartMenu();
    }

    /**
     * The menu is an overlay, so it needs SYSTEM_ALERT_WINDOW. On API 23+ that is
     * a runtime grant the user has to give in Settings - there is no dialog for
     * it. Send them there once, then start the menu on the way back.
     */
    private void maybeStartMenu() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(this)) {
            Log.i(TAG, "overlay permission missing, asking");
            Intent intent = new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:" + getPackageName()));
            startActivityForResult(intent, REQ_OVERLAY);
            return;
        }

        if (!HookApp.startMenu(this)) {
            Log.e(TAG, "menu failed to start - see DexLoader above for the step");
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQ_OVERLAY) {
            // onResume runs again after this, which retries the start.
            Log.i(TAG, "returned from overlay settings, granted="
                    + (Build.VERSION.SDK_INT < Build.VERSION_CODES.M
                       || Settings.canDrawOverlays(this)));
        }
    }
}
