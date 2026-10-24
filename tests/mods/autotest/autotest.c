#include "hm.h"

/* Read by tests/redux_check.lua, which finds it through program.map. */
typedef struct HmTest {
    u32 magic;          /* 0x484D5445 ("HMTE") once boot ran */
    u32 frames;         /* frame hook calls */
    u32 scenes;         /* scene hook calls */
    s32 lastScene;
    u32 minutes;        /* minute hook calls */
    u32 days;           /* new_day hook calls */
    s32 gold;           /* the player's gold at the last minute */
    s32 autopilot;      /* buttons to tap (2 frames in 20); with AUTOPILOT_HOLD, held */
} HmTest;

#define AUTOPILOT_HOLD 0x10000

HmTest hm_test = { 0, 0, 0, -1, 0, 0, 0, 0 };

void autotest_boot(void) {
    hm_test.magic = 0x484D5445;
}

void autotest_frame(void) {
    hm_test.frames++;
    if (hm_test.autopilot & AUTOPILOT_HOLD) {
        input_pad1->held |= hm_test.autopilot & 0xFFFF;
    } else if (hm_test.autopilot != 0 && (hm_test.frames % 20) < 2) {
        input_pad1->held |= hm_test.autopilot;
        input_pad1->pressed |= hm_test.autopilot;
        input_pad1->triggered |= hm_test.autopilot;
    }
}

void autotest_scene(s32 scene, s32 previous) {
    hm_test.scenes++;
    hm_test.lastScene = scene;
}

void autotest_minute(void) {
    hm_test.minutes++;
    hm_test.gold = hm_player.gold;
}

void autotest_new_day(void) {
    hm_test.days++;
}
