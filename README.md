# hmbtn-modkit

**A mod kit and community mod collection for *Harvest Moon: Back to Nature* (PlayStation, USA).**

[![CI](https://github.com/gilangjavier/hmbtn-modkit/actions/workflows/ci.yml/badge.svg)](https://github.com/gilangjavier/hmbtn-modkit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Mods](https://img.shields.io/badge/mods-catalog-green.svg)](MODS.md)

Write mods in plain C against the game's real, readable source code, and build a playable
disc image with them in one command:

```c
#include "hm.h"

/* +1,000 G and full stamina every morning. */
void rich_morning_new_day(void) {
    hm_gold_add(1000);
    hm_player.stamina = hm_player.maxStamina;
}
```

```sh
python hm.py build rich_morning cheat_pad     # -> out/hmbtn-mod.cue, play it in any emulator
```

## How it works

This kit is built on [**hmbtn-decomp**](https://github.com/coalslav/hmbtn-decomp), a
complete matching decompilation of the game: C source that compiles back into the retail
executable and its 13 overlays byte for byte. On top of it the kit adds:

- **Hooks**: `boot`, `frame`, `scene`, `minute` and `new_day` calls into your mod's C code.
- **Relocatable memory layout**: code a mod adds moves every overlay automatically, and the
  linker refuses any build that would not fit in the PlayStation's 2 MB of RAM.
- **Source patches**: a mod can change any game function with a `.patch` file.
- **Asset patches**: a mod can change game data (text, textures, ...) with `.xdelta` files.
- **One tool**, `hm.py`, to set up, build, test, validate and catalog mods.

The retail build stays byte-identical to the original game, so a build without mods is
proven correct before any mod is added. See [docs/architecture.md](docs/architecture.md).

## Quick start

You need your own copy of the game: a raw `.bin` dump (MODE2/2352) of the US disc,
`SLUS-01115`, sha1 `cb26381fa1336bdd15f07469e59f1143ccf37b03`. This repository contains
no game data and never will.

| Platform | Requirements |
|----------|--------------|
| Windows 10/11 | Python 3.11+, Git, [WSL](https://learn.microsoft.com/windows/wsl/install) with Debian or Ubuntu |
| Linux | Python 3.11+, Git, Debian/Ubuntu (apt) |
| macOS | Not supported directly: use a Linux VM or container |

```sh
git clone https://github.com/gilangjavier/hmbtn-modkit
cd hmbtn-modkit
python hm.py setup --disc "/path/to/Harvest Moon - Back to Nature (USA).bin"
python hm.py build                      # the retail game: must say "all 17 files match"
python hm.py build --all                # every mod in the catalog
```

The modded disc is `out/hmbtn-mod.cue`. Open it in DuckStation, PCSX-Redux, ePSXe or
any other emulator. Full walkthrough: [docs/getting-started.md](docs/getting-started.md).

## Mods

Browse the catalog in **[MODS.md](MODS.md)**, or pick them from the command line:

```sh
python hm.py list                       # [x] marks the mods you enabled
python hm.py enable cheat_pad daily_allowance
python hm.py play                       # build your selection and start the emulator
```

Mods published elsewhere install the same way:

```sh
python hm.py add https://github.com/someone/their-hmbtn-mods      # every mod in that repo
python hm.py add https://github.com/someone/their-hmbtn-mods --mod fishing_plus
python hm.py remove fishing_plus
```

## Make a mod

```sh
python hm.py new my_mod --author "Your Name"    # mods/my_mod/{mod.json, my_mod.c, README.md}
python hm.py build my_mod
```

- [Writing mods](docs/writing-mods.md): manifest, hooks, API, finding game code
- [Hooks and API reference](docs/hooks-and-api.md)
- [Changing game data](docs/assets.md): text, graphics and other files, as `.xdelta`
- [Sprites](docs/sprites.md): export, reskin and verify the game's animated sprites
- [Memory budget](docs/memory-budget.md): how much code fits
- [Testing](docs/testing.md): headless runs in PCSX-Redux
- [Using AI agents](docs/ai-agents.md): prompts and skills for Claude Code, Codex and others
- [Roadmap](docs/roadmap.md): what mods can do today, and the tools still needed for new content

## Contributing

Mods are added by pull request: fork, add `mods/<your_mod>/`, open a PR. CI builds every
mod and checks it fits. Read [CONTRIBUTING.md](CONTRIBUTING.md) first, especially the
rules about game data.

## Legal

*Harvest Moon: Back to Nature* is © Marvelous Inc. / Natsume. This project is not affiliated
with or endorsed by them. It distributes no game code, data or disc images: the decompiled
source is fetched from its own repository, and every build needs a disc image you own.
Share mods as source (this repository), never as built disc images.

The kit is MIT licensed ([LICENSE](LICENSE)). Each mod states its own license in its
`mod.json`. The decomp is CC0 and its tools keep their own licenses.
