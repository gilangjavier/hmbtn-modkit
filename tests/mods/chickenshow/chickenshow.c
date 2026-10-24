#include "hm.h"
#include "chicken.h"

/* Keep an extra chicken on the player's map, a little way from the player. */
void chickenshow_frame(void) {
    FarmChicken *chicken;

    if (!hm_in_farm()) {
        return;
    }
    chicken = &game_state.animals.extraChickens[0];
    if (chicken->actor.kind == ITEM_NOTHING) {
        chicken_spawn(ITEM_CHICKEN, -1, 0);
    }
    if (chicken->actor.kind != ITEM_NOTHING) {
        chicken->actor.place.location = hm_player.place.location;
        chicken->actor.place.value = hm_player.place.value;
        chicken->actor.position.vx = hm_player.position.vx + 500;
        chicken->actor.position.vy = hm_player.position.vy;
        chicken->actor.position.vz = hm_player.position.vz;
    }
}
