---
name: find-game-code
description: Locate the Harvest Moon Back to Nature game state, structures and functions behind a gameplay feature in the decompiled source (.hm/decomp). Use when a mod needs to know where something lives (money, stamina, animals, villagers, crops, shops, events, items, time) or what a game function does.
---

# Find game code

The decompiled source is in `.hm/decomp/src/` (run `python hm.py setup --skip-toolchain`
if it is missing). Identifiers and comments are descriptive English. Unknown fields keep
offset names like `pad82` or `unknown1C`, so don't invent meanings for them.

## Where things are

| Topic | Look in |
|-------|---------|
| Everything saved: the root of all state | `src/main/game/farm_state.h` (`FarmState game_state`) |
| Player: money, stamina, fatigue, tools, items | `src/overlay/11_GF_FARM/people/player.h` |
| Villagers, affection | `src/overlay/11_GF_FARM/people/villager.h` |
| Livestock, dog, horse | `src/overlay/11_GF_FARM/animals/` |
| Fields, crops, tiles | `src/overlay/11_GF_FARM/field/` |
| Clock, calendar, weather | `src/overlay/11_GF_FARM/world/` |
| Farm buildings, lumber, fodder, shipping | `src/overlay/11_GF_FARM/estate.h` |
| Events (cutscenes), story flags | `src/overlay/11_GF_FARM/event/`, `src/main/game/event_flags.h` |
| Menus, shops | `src/overlay/11_GF_FARM/menu/` |
| Item ids | `src/include/items.h` |
| Main loop, scenes, overlays | `src/main/main.c`, `src/main/main.h` |
| Controller input | `src/main/input/pad.h` |
| Text and dialogue rendering | `src/main/text/` |
| Sound | `src/main/sound/` |
| Minigames | `src/overlay/17_GF_MG1` … `25_GF_MG5` |
| Title screen and new game | `src/overlay/27_GF_TITLE/title.c` |
| Save and load | `src/overlay/15_saveload/` |

## Method

1. Grep the headers for the noun: `grep -rn -i "<word>" .hm/decomp/src --include=*.h`.
2. Find the writers of the field: `grep -rn "<field> *[-+]\?=" .hm/decomp/src`. That is the
   game logic you will hook next to or patch.
3. Read the function around it, and its callers (`grep -rn "<function>(" .hm/decomp/src`).
4. Note **which image** the code is in: `src/main/` is always loaded; `src/overlay/<n>/`
   is loaded only during its scene. Mods can always access `game_state` itself.
5. Check value ranges and units in the comments (for example `day` is 0..29, `fatigue`
   0..100, gold max 9,999,999), and keep mods inside them.

## Answer with evidence

Give file paths with line numbers and quote the declaration. Distinguish what the source
states from what you infer. If a field's meaning is not documented, say so.
