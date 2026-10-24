# Hooks and API reference

## Hooks

A hook is a point where the game calls into the mods. A mod asks for one in `mod.json`:
`"hooks": {"frame": "my_mod_frame"}`. When several mods use the same hook, they run in
the order the mods were given to `hm.py build`.

| Hook | Signature | Called | Where (decomp source) |
|------|-----------|--------|-----------------------|
| `boot` | `void f(void)` | Once, after the game has initialized, before the title screen. | `src/main/main.c`, `main()` |
| `frame` | `void f(void)` | Every rendered frame, after the controllers are read and before the scene runs. Not called during loading screens. | `src/main/main.c`, `main_run_frame()` |
| `scene` | `void f(s32 scene, s32 previous)` | When the game requests a scene change (`SCENE_*` in `src/main/main.h`). The new scene loads after the current frame. | `src/main/main.c`, `main_request_scene()` |
| `minute` | `void f(void)` | Each time the farm clock advances one minute. Not called while the clock is stopped (events, menus, pause). | `src/overlay/11_GF_FARM/world/clock.c`, `clock_advance_minute()` |
| `new_day` | `void f(void)` | When the farm clock passes 6:00, the start of a new day, including after sleeping. Runs just before that minute's `minute` hook. | same |

Without mods, every hook compiles to nothing. That keeps the retail build identical to
the original game.

### Scenes

From `src/main/main.h`:

| Id | Scene | Id | Scene |
|----|-------|----|-------|
| 2 | `SCENE_FARM` (new game) | 11 | `SCENE_MG4` (dog race) |
| 3 | `SCENE_MG1` (horse race) | 12 | `SCENE_MG5` (swimming) |
| 4 | `SCENE_MG2` (cockfight) | 13 | `SCENE_TITLE` |
| 5 | `SCENE_MG3` (tomato) | 14 | `SCENE_FARM_LOADED` (after loading a save) |
| 6 | `SCENE_FARM_MINIGAME_EXIT` | 15 | `SCENE_FARM_SAVED` |
| 7 | `SCENE_SAVE` | 16 | `SCENE_STAFF_ROLL` |
| 8 | `SCENE_LOAD` | 18 | `SCENE_MEMCARD` |

## `hm.h`

| Name | What it is |
|------|------------|
| `game_state` | `FarmState`, the whole game state and save data (`src/main/game/farm_state.h`). |
| `hm_player` | `game_state.player` (`FarmPlayer`, `src/overlay/11_GF_FARM/people/player.h`). |
| `hm_date` | `game_state.progress.clock.date`: `year` (0..98), `season` (0..3), `day` (0..29), `weekday`. |
| `hm_time` | `game_state.progress.clock.time.hm`: `hour`, `minute`. |
| `hm_in_farm()` | True while the main loop runs a farm scene. |
| `hm_pad_held(buttons)` | True while every button in `buttons` is held on controller 1. |
| `hm_pad_pressed(buttons)` | True on the frame those buttons are all held and at least one was just pressed. |
| `input_pad1` | Controller 1's `InputRecord` (`src/main/input/pad.h`): `held`, `pressed`, `triggered`. |
| `PAD_*` | Button bits: `PAD_L1 PAD_R1 PAD_L2 PAD_R2 PAD_TRIANGLE PAD_CIRCLE PAD_CROSS PAD_SQUARE PAD_SELECT PAD_START PAD_UP PAD_DOWN PAD_LEFT PAD_RIGHT`. |
| `main_scene` | The current scene id. |
| `hm_gold_add(n)` | Add `n` gold (negative to spend), kept in 0..9,999,999. |

### Commonly used state

| Field | Meaning |
|-------|---------|
| `hm_player.gold` | Money, 0..9,999,999. |
| `hm_player.stamina`, `hm_player.maxStamina` | Stamina, and its maximum (raised by power berries). |
| `hm_player.fatigue` | Fatigue, 0..100. |
| `hm_player.happiness` | Happiness index, 0..0xFFFF. |
| `hm_player.medals` | Horse-race medals. |
| `hm_player.tools[8]`, `hm_player.items[8]` | Rucksack contents (`FarmStoredItem`); item ids in `items.h`. |
| `hm_player.toolExp[5]` | Tool experience: sickle, hoe, ax, hammer, watering can. |
| `game_state.progress.estate` | The farm: `houseLevel`, `barnLevel`, `coopLevel`, `lumber`, `fodder`, `chickenFeed`, `farmName`, ... (`estate.h`) |
| `game_state.villagers[]` | Every villager's state (`villager.h`). |
| `game_state.animals` | Livestock, the dog and the horse (`animals.h`). |
| `game_state.eventFlags` | Story flags: use `event_flag_get(flag)` / `event_flag_set(flag, on)` (`event_flags.h`). |

### Functions in the executable (safe to call any time)

| Function | Header |
|----------|--------|
| `s32 event_flag_get(u16 flag)`, `void event_flag_set(u16 flag, u16 on)` | `event_flags.h` |
| `s32 sound_play(s16 id)` | `sound_request.h` |
| `void main_request_scene(s32 scene)` | `main.h` |
| `s32 rand_range(s32 range)`: a random number below `range` | `screen_fade.h` |

Search `src/main/` for more. Anything under `src/overlay/` is only callable while that
overlay is loaded (see [writing-mods.md](writing-mods.md#overlay-code-is-not-always-loaded)).

## Adding a hook

Hooks are part of the framework (`framework/patches/`). To add one:

1. Declare it in `src/main/mods.h` (both the `#ifdef HMBTN_MODS` prototype/macro and the
   empty macro).
2. Call `MODS_YOURHOOK(...)` where it belongs in the game's source. Include `mods.h`.
3. Add it to `HM_HOOKS` (and its signature) in `cmake/mods.cmake`, and to `HOOKS` in `hm.py`.
4. Check that `python hm.py build` still reports `all 17 files match`.
5. Document it here, and send a PR.
