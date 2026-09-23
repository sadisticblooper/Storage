package com.example.hooktemplate;

/**
 * Stand-in for your game logic. Replace these with real methods from your app.
 */
public class ScoreBoard {

    private int score = 10;

    public int getScore() {
        return score;
    }

    public void setScore(int value) {
        this.score = value;
    }

    public boolean isPremium() {
        return false;
    }

    public static void lateInit() {
        // Example target for hookWithoutInit().
    }
}
