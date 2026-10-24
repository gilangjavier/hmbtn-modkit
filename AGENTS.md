# AGENTS.md

Instructions for AI coding agents (Claude Code, Codex, Cursor, Copilot, Gemini CLI, ...)
working in this repository. Humans: see [README.md](README.md) and [docs/](docs/).

## What this repository is

A mod kit and mod collection for *Harvest Moon: Back to Nature* (PS1, USA). Mods are C
code, source patches and asset patches built into the game with `hm.py`, on top of a
matching decompilation that `hm.py setup` fetches into `.hm/decomp/`.

## Commands

Run everything from the repository root with Python 3.11+.

```sh
python hm.py setup --disc PATH        # once; also after framework/ changes
python hm.py build                    # retail build; must print "all 17 files match"
python hm.py build --no-disc          # same, code only (no game data needed)
python hm.py build MOD [MOD...]       # modded disc -> out/hmbtn-mod.cue
python hm.py build MOD --no-disc      # compile + link + RAM check only
python hm.py new ID --author NAME     # scaffold mods/ID/
python hm.py list / enable ID / disable ID / play   # the player's selection (.hm/config.json)
python hm.py add URL|PATH [--mod ID]  # install third-party mods into mods/; remove ID uninstalls
python hm.py validate                 # manifest and file rules, all mods
python hm.py catalog                  # regenerate MODS.md (commit it)
python hm.py test MOD --seconds 600   # headless PCSX-Redux run, report in out/test/report.txt
python hm.py extract                  # original game files -> .hm/original/ (never commit)
# Parallel agents: give each its own HM_WORK (Linux build dir) and HM_OUT (output dir).
python hm.py xdelta MOD MEMBER FILE   # asset patch from an edited A_FILE member
python hm.py sprite list              # known sprite sets (docs/sprites.md)
python hm.py sprite export ID DIR     # sprite -> sheet PNGs, img_N.png, pal_N.png, sprite.json
python hm.py sprite import MOD ID DIR # edited PNGs -> mods/MOD/afile/00_gf.bin.xdelta
python hm.py sprite check [ID]        # decoder and export/import round-trip proof
```

A build takes 10 seconds to a minute. Build output goes through WSL on Windows.

## Before you finish any change

1. `python hm.py validate` passes.
2. `python hm.py build <the mods you touched> --no-disc` passes (or without `--no-disc`
   if a disc is configured).
3. `python hm.py catalog` was run if any `mod.json` changed, and `MODS.md` is included.
4. For framework changes: `python hm.py build --no-disc` still reports `all 14 files match`
   (`all 17` with a disc).
5. Report the RAM line `hm.py build` printed.

## Writing a mod: the rules

- A mod is `mods/<id>/` with `mod.json`, `README.md` and its sources. Use
  `python hm.py new` rather than creating it by hand.
- C is **C89 for GCC 2.95**: declarations at the top of blocks, `/* */` comments only, no
  `bool`, no floating point, no `malloc`, no standard library beyond `memory.h`/`string.h`
  functions the game already links.
- `#include "hm.h"` first. Types: `s8 u8 s16 u16 s32 u32` from `types.h`.
- **Prefix every global symbol with the mod id.** Make helpers `static`.
- Hook functions must match the signatures in [docs/hooks-and-api.md](docs/hooks-and-api.md)
  exactly, and be listed under `"hooks"` in `mod.json`.
- **Never call a function from `src/overlay/...` unless that overlay is loaded.** Farm
  functions are safe in `minute`/`new_day`, or in `frame` after `if (!hm_in_farm()) return;`.
  Reading and writing `game_state` is always safe.
- Prefer hooks over patches. If a patch is needed, generate it from `.hm/decomp/` with
  `git diff` and restore the tree with `git checkout -- .` afterwards. Never leave
  `.hm/decomp/` modified.
- RAM is tight: all mods together get about 55 KB. Keep mods to a few KB.

## Never do this

- Never commit game data: no `.bin`/`.cue`/`.iso`, nothing from `.hm/original/`, no
  extracted or decoded game files. Asset changes are `.xdelta` only.
- Never commit anything under `.hm/` or `out/`.
- Never edit `MODS.md` by hand (it is generated), or `mods/_registry.c` (generated at build).
- Never "fix" a retail mismatch by changing checksums. A mismatch means the framework is wrong.
- Don't guess what a game function does from its name alone. Read its source in
  `.hm/decomp/src/`. The comments there describe behavior.

## Finding things in the game

```sh
grep -rn "stamina" .hm/decomp/src --include=*.h          # fields and types
grep -rn "^void shop_\|^s32 shop_" .hm/decomp/src          # functions by prefix
```

- Game state, which is also the save data: `.hm/decomp/src/main/game/farm_state.h` (`FarmState game_state`).
- Player: `.hm/decomp/src/overlay/11_GF_FARM/people/player.h`.
- Items: `.hm/decomp/src/include/items.h`. Scenes: `.hm/decomp/src/main/main.h`.
- Clock and calendar: `.hm/decomp/src/overlay/11_GF_FARM/world/clock.{c,h}`.

## Skills

Task recipes for agents are in [`.claude/skills/`](.claude/skills/). They are plain
Markdown, usable by any agent:

- [`make-mod`](.claude/skills/make-mod/SKILL.md): from an idea to a validated, built mod.
- [`test-mod`](.claude/skills/test-mod/SKILL.md): run a mod headless and judge the report.
- [`find-game-code`](.claude/skills/find-game-code/SKILL.md): locate the game state and functions for a feature.
