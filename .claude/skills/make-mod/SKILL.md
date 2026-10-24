---
name: make-mod
description: Create, implement, build and validate a Harvest Moon Back to Nature mod in this repository. Use when the user asks to make, add, write, change or fix a mod, cheat, tweak or new feature for the game.
---

# Make a mod

Turn a mod idea into a validated, building mod under `mods/<id>/`. Read
[AGENTS.md](../../../AGENTS.md) first if you have not.

## 1. Pin down the idea

Restate the feature as concrete game behavior: what triggers it (a button combo, a new
day, a scene change, every minute), and what state it changes. If that is ambiguous
(for example "make farming easier"), propose one concrete version and go with it.
Do not stall on questions.

## 2. Check the setup

```sh
python hm.py validate
```

If `.hm/decomp/cmake/mods.cmake` does not exist, the decomp is not set up. Run
`python hm.py setup --disc <path>` if the user gave a disc path. Otherwise run
`python hm.py setup --skip-toolchain` to get the source, and build with `--no-disc`.

## 3. Find the game code

Use the `find-game-code` skill (or grep `.hm/decomp/src`) to find:

- the `game_state` fields to read or write, with their ranges from the comments;
- the hook that fires at the right moment ([docs/hooks-and-api.md](../../../docs/hooks-and-api.md));
- if no hook fits, the function to patch.

Read the actual code before relying on a name.

## 4. Scaffold and implement

```sh
python hm.py new <id> --author "<user or 'hmbtn-modkit contributors'>"
```

Then edit `mods/<id>/mod.json` (`name`, `description`, `tags`, `hooks`, `sources`) and
`mods/<id>/<id>.c`. Rules:

- C89 for GCC 2.95: declarations first in a block, `/* */` comments, no floats, no malloc.
- `#include "hm.h"`. Prefix every global with `<id>_`. Make helpers `static`.
- Clamp values to the ranges the game uses (for example gold 0..9,999,999 via `hm_gold_add`).
- Guard farm-only logic in `frame` with `if (!hm_in_farm()) return;`.
- Use overlay functions only where that overlay is loaded.

A patch, only when needed:

```sh
cd .hm/decomp && <edit> && git diff > ../../mods/<id>/patches/<name>.patch && git checkout -- . && cd ../..
```

Add it to `"patches"` in `mod.json`.

## 5. Build and validate

```sh
python hm.py build <id> --no-disc    # or without --no-disc when a disc is configured
python hm.py validate
python hm.py catalog
```

Fix compiler errors by reading them. GCC 2.95 messages are terse: `parse error before`
usually means a declaration after a statement, or a C99 construct. Then also build it with
every other mod to catch symbol clashes and patch conflicts:

```sh
python hm.py build --all --no-disc
```

## 6. Write the README and report

`mods/<id>/README.md`: what it does, controls, the hooks used, known limits.

Report to the user: the files created, the RAM line from the build, and how to play it
(`python hm.py build <id>`, then `python hm.py run`). If you could not run it in an
emulator, say so plainly and suggest the `test-mod` skill.
