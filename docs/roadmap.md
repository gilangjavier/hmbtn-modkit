# Roadmap: what mods can do, and what is still missing

Because the whole game is readable, buildable C, **any change to the game's logic is
possible**. The limits are content tooling and the console's memory.

## Possible today

| Kind of mod | How |
|-------------|-----|
| Cheats, balance, economy (prices, stamina, growth speed, affection gain) | Hooks + `game_state`, or a small patch |
| Quality of life (auto-water, faster text, skip intros, extra controls) | Hooks or patches |
| New rules and mechanics built from existing pieces (new jobs, quests, challenge modes) | C in hooks and patches, reusing the game's own systems |
| Changing existing data byte by byte (prices tables, text, graphics) | `.xdelta` asset patches, with your own tools |

## Needs community tooling first

New *content* means new data in formats the game reads from `A_FILE.BIN`. The decomp
contains the code that reads every one of these formats, so each is documented in C,
but there are no editors for them yet:

| Feature | Data involved | Tool to build | Difficulty |
|---------|---------------|---------------|------------|
| **New or changed dialogue** | Text banks (`02_messege0.bin` …), the game's text encoding | Text bank extractor/compiler ([backtonature-decompiled](https://github.com/beruanglaut-com/backtonature-decompiled) has text-bank tools to start from) | ★★ |
| **New events and cutscenes** | Event scripts (`12_event_s.bin`): a bytecode run by `event_script.c` | Event script assembler/disassembler ([gil-unx/EVENT-EDITOR](https://github.com/gil-unx/EVENT-EDITOR) is prior work) | ★★★ |
| **New clothes / player looks** | Player sprites: `.ANI` animations (images, parts, frames; see `src/main/graphics/anim.h`) with pixels in VRAM | `.ANI` + TIM import/export to PNG sprite sheets | ★★★ |
| **Reskinned animals / characters** | Replace an existing sprite set, keeping its frame layout | Same tool; no code needed | ★★ |
| **New animal types** | New sprite set, plus logic reusing livestock (`animals.h` has fixed slot arrays) | Sprite tool + C/patches | ★★★★ |
| **New music** | Streamed XA tracks (`STR/*.XA`, `cd_audio.c`) or sequenced SEQ + VAB banks (`sound.c`, libsnd) | XA encoder (e.g. psxavenc) for full songs; MIDI→SEQ and samples→VAB for sequenced music | ★★ (XA) / ★★★ (SEQ) |
| **New sound effects** | VAB banks in `09_sound.stm` | VAB editor | ★★★ |
| **New characters** | Sprites, portraits (`01_face.bin`), schedules, dialogue, affection logic | All of the above, plus a new villager slot (the villager array has a fixed size, so the save format changes) | ★★★★ |
| **New locations** | Maps, models (TMD), collision and zones in `00_gf.bin` sections | Map section format and a map editor | ★★★★★ |
| **Story overhauls** (e.g. a carpenter or fisherman instead of a farmer) | New progression rules (C), plus new events and dialogue | Text and event tools; the code side is possible now | ★★★★ |

## Hard limits

- **RAM**: 2 MB, and mods share about 55 KB of it (see [memory-budget.md](memory-budget.md)).
  Big features need to load their data from the disc when needed rather than keep it in
  the executable. A future framework version could give mods their own overlay.
- **VRAM**: 1 MB for every texture on screen. New graphics must fit beside the game's.
- **Save data**: `game_state` *is* the save. Adding fields changes the save layout and
  breaks compatibility with existing saves. Use spare/unused fields where the decomp
  marks them, or version your mod's save use clearly.
- **Disc**: plenty of room (about 200 MB used of 700 MB, plus 33 MB of filler in `DUMMY.DAT`).

## Planned framework work

- [ ] More hooks: player actions (tool use, shipping, sleeping), shop purchases, villager
      talk, event start and end, save and load.
- [ ] A mod overlay: mod code loaded with the farm instead of the always-resident executable.
- [ ] A save-data extension area for mods.
- [ ] Text bank tool (`hm.py text`): extract, edit and rebuild dialogue as plain text.
- [ ] Event script tool: disassemble and assemble events.
- [ ] Sprite tool: export and import `.ANI` animations and TIM textures as PNG sprite sheets.
- [ ] Audio tool: add or replace XA music tracks.
- [ ] Propose the hooks upstream to hmbtn-decomp.

Want to work on one? Open an issue so others know, and send a PR.
