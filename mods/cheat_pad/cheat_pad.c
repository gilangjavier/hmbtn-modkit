#include "hm.h"

void cheat_pad_frame(void) {
    if (!hm_in_farm()) {
        return;
    }
    if (hm_pad_held(PAD_L1 | PAD_R1) && (input_pad1->pressed & PAD_SELECT)) {
        hm_gold_add(10000);
    }
    if (hm_pad_held(PAD_L1 | PAD_R1) && (input_pad1->pressed & PAD_TRIANGLE)) {
        hm_player.stamina = hm_player.maxStamina;
        hm_player.fatigue = 0;
    }
}
