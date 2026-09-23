package com.example.hooktemplate;

import android.app.Activity;
import android.os.Bundle;
import android.util.Log;
import android.widget.TextView;

/**
 * Calls into the hooked methods so you can watch the hooks fire in logcat.
 */
public class MainActivity extends Activity {

    private static final String TAG = "HookTemplate";

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
                + "\nscore after arg hook=" + board.getScore());
        setContentView(tv);
    }
}
