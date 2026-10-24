# Writing mods

## Anatomy of a mod

```
mods/rich_morning/
├── mod.json            the manifest (required)
├── README.md           what it does, for players (required)
├── rich_morning.c      C sources (optional)
├── patches/            .patch files against the game's source (optional)
├── afile/              .xdelta patches of A_FILE members (optional)
└── disc/               files that replace files on the disc (optional)
```

### `mod.json`

```json
{
  "id": "rich_morning",
  "name": "Rich Morning",
  "version": "1.0.0",
  "description": "1,000 G and full stamina every morning.",
  "authors": ["Your Name"],
  "license": "MIT",
  "tags": ["money", "stamina"],
  "sources": ["rich_morning.c"],
  "hooks": { "new_day": "rich_morning_new_day" },
  "patches": []
}
```

| Key | Required | Meaning |
|-----|----------|---------|
| `id` | yes | The folder name: 2-32 of `a-z 0-9 _`, starting with a letter. |
| `name`, `description` | yes | Shown in `MODS.md` and `hm.py list`. |
| `version` | yes | `MAJOR.MINOR.PATCH`. Bump it on every change. |
| `authors`, `license` | yes | A list of names; an SPDX license id (`MIT`, `CC0-1.0`, ...). |
| `tags` | no | Free-form keywords: `cheat`, `qol`, `economy`, `translation`, ... |
| `sources` | no | C files, compiled into the game executable. |
| `hooks` | no | `{"<hook>": "<your function>"}`. See [hooks-and-api.md](hooks-and-api.md). |
| `patches` | no | Patch files, applied in order to the game's source before building. |

## A first mod

```sh
python hm.py new rich_morning --author "Your Name"
```

Edit `mods/rich_morning/rich_morning.c`:

```c
#include "hm.h"

void rich_morning_new_day(void) {
    hm_gold_add(1000);
    hm_player.stamina = hm_player.maxStamina;
}
```

Set `"hooks": {"new_day": "rich_morning_new_day"}` in `mod.json`, then:

```sh
python hm.py build rich_morning
python hm.py run
```

## What you can use

`#include "hm.h"` gives you the game state, controller input and helpers. Every header
of the decomp is also on the include path, so you can include whatever you need:
`items.h`, `event_flags.h`, `player.h`, `villager.h`, `clock.h`, `estate.h`, ...

The decomp's source is in `.hm/decomp/src/` after setup:

| Folder | Contents |
|--------|----------|
| `src/main/` | The executable: main loop, CD, graphics, input, sound, text, UI. Always loaded. |
| `src/main/game/farm_state.h` | `FarmState game_state`: **the whole game state**, which is also what gets saved. |
| `src/overlay/11_GF_FARM/` | The farm (all of daily gameplay): player, animals, villagers, events, clock, shops. |
| `src/overlay/27_GF_TITLE/` | The title screen and the new-game setup. |
| `src/overlay/1x_GF_MGn/` | The minigames (horse race, cockfight, tomato, dog race, swimming). |
| `src/overlay/15_saveload/` | Saving and loading. |
| `src/include/items.h` | Every item id. |

Find things with grep: names and comments are descriptive.

```sh
grep -rn "fatigue" .hm/decomp/src --include=*.h
grep -rn "void .*shop" .hm/decomp/src/overlay/11_GF_FARM
```

### Overlay code is not always loaded

Your mod's code lives in the executable and is always resident. The game's own
functions are in two kinds of places:

- `src/main/...`: the executable. You can call these any time.
- `src/overlay/...`: an overlay, loaded only during its scene. A farm function exists
  only while the farm is loaded. Call it only from the `minute` or `new_day` hooks (they
  run inside the farm), or from `frame` after checking `hm_in_farm()`. Calling an
  unloaded overlay's function jumps into whatever else is in that memory.

Data in `game_state` is always safe to read and write.

## Changing game logic: patches

When no hook is in the right place, change the game's source with a patch. Edit
`.hm/decomp/` directly, export the diff, and restore the original:

```sh
cd .hm/decomp
# ... edit src/overlay/11_GF_FARM/people/player.c ...
git diff > ../../mods/your_mod/patches/stamina.patch
git checkout -- .
```

List it in `mod.json`: `"patches": ["patches/stamina.patch"]`. Patches are applied with
`patch -p1` to a copy at build time, in the order mods are given. Keep them small:
two mods that patch the same lines cannot be built together.

You can also add a hook call in a patch and use your own function from it. Declare it
in the patch and define it in your mod's `.c`.

## Changing game data

Text, graphics, sounds and models are in `A_FILE.BIN`. See [assets.md](assets.md).

## Style

- C89 as GCC 2.95 accepts it: declare variables at the top of a block, no `//`
  comments, no `bool`, no mixed declarations and code.
- Prefix every global name with your mod id. Make helpers `static`.
- Integer types from `types.h`: `s8 u8 s16 u16 s32 u32`.
- No `malloc`, no floating point (the PS1 has no FPU, so it is slow and pulls in libraries).
- Keep per-frame work tiny. The game already uses most of each frame.
