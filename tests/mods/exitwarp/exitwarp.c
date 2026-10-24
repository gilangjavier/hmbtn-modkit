#include "hm.h"
#include "scene.h"
#include "player.h"

/* autotest's record starts with magic, frames; only frames is read. */
extern struct { u32 magic; u32 frames; u32 scenes; s32 lastScene; u32 minutes; u32 days; } hm_test;

#ifndef EXITWARP_AT
#define EXITWARP_AT 16500   /* autotest frames to wait (the player is free by then) */
#endif

static s32 warped;

/* Once, teleport the player into the first live zone that is a plain exit. The game's own
 * player step then finds the zone and sets FARM_MODE_EXIT_LOAD. hm_test.days is reused to
 * report the zone: slot * 65536 + id. */
void exitwarp_frame(void) {
    s32 i;
    FarmZone *z;

    if (warped || !hm_in_farm() || hm_test.frames < EXITWARP_AT) {
        return;
    }
    if (farm_area.mode.eventMode != FARM_MODE_IDLE ||
        (hm_player.stateFlags & (PLAYER_FLAG_SCRIPTED | PLAYER_FLAG_NO_INPUT | PLAYER_FLAG_AUTO_WALK))) {
        return;
    }
    for (i = 0; i < FARM_ZONE_COUNT; i++) {
        z = &farm_area.mode.script.zones[i];
        if (z->id == ZONE_ID_EMPTY || z->id == ZONE_ID_NO_RESET) continue;
        if (z->flags & (ZONE_FLAG_DEAD | ZONE_FLAG_TRIGGER | ZONE_FLAG_MARKER | ZONE_FLAG_HAS_EVENT | ZONE_FLAG_FACING)) continue;
        if (z->event != ZONE_EVENT_NONE) continue;
        hm_player.position.vx = (z->min.x + z->max.x) / 2;
        hm_player.position.vz = (z->min.z + z->max.z) / 2;
        hm_test.days = (u32)i * 65536 + z->id;
        warped = 1;
        return;
    }
}
