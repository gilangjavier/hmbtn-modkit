# Architecture

## The pieces

```
hmbtn-modkit/                       this repository: no game code, no game data
├── hm.py                           the tool
├── framework/
│   ├── upstream.json               the decomp's repository and pinned commit, toolchain pins
│   └── patches/0001-mod-hooks.patch
├── mods/<id>/                      the community mods
├── tests/                          test mods and the PCSX-Redux harness
└── .hm/                            (git-ignored) your config, the patched decomp, extracted files

github.com/coalslav/hmbtn-decomp    the matching decompilation, fetched by `hm.py setup`
```

## What the framework patch changes in the decomp

| File | Change |
|------|--------|
| `src/main/mods.h` | The hook declarations; every `MODS_*()` is empty without `HMBTN_MODS`. |
| `src/main/main.c`, `src/overlay/11_GF_FARM/world/clock.c` | The hook calls. |
| `modkit/hm.h` | The mod API header. |
| `cmake/mods.cmake` | Reads each mod's `mod.json`, compiles its sources, generates the hook dispatchers (`mods/_registry.c`), and collects asset overrides. |
| `CMakeLists.txt` | `HMBTN_MODS`; the overlay regions become linker symbols instead of fixed addresses. |
| `cmake/exe.ld.in`, `cmake/overlay.ld.in` | Mod sections at the end of the executable; an end symbol per overlay. |
| `cmake/program.ld.in` | The RAM budget assertion. |
| `cmake/disc.cmake`, `tools/afile.py` | A_FILE member and disc file overrides. |

None of it changes the retail output: `python hm.py build` still produces the 17 files
of the original disc byte for byte. That is checked on every PR.

## A build, step by step

1. `hm.py` copies `.hm/decomp/` and the selected mods to `~/.cache/hmbtn-modkit/src` on
   the Linux side. The PlayStation compiler is a 32-bit program that cannot read Windows
   drives through WSL, and the copy keeps the repository untouched.
2. Each mod's `patches` are applied with `patch -p1`, in mod order.
3. Each mod's `afile/*.xdelta` is applied to the original member, extracted once from your
   disc, with xdelta3.
4. CMake is configured with `-DHMBTN_MODS=a;b;c`. That defines `HMBTN_MODS` for every
   source (turning the hooks on), compiles the mods' sources with the game's own compiler
   flags, and generates one dispatcher per hook.
5. One GNU ld run links the executable, the mods (after the game's code) and all 13
   overlays. The overlay addresses follow from the new sizes, and the RAM assertion runs.
6. A_FILE is repacked (built overlays, original members, mod overrides), and the disc
   image is rebuilt with every file at a new sector position if sizes changed.

## Why mods live in the executable

The executable is always resident, so mod code can run from any scene. Overlays are
swapped per scene. The cost is that every byte moves the overlays up (see
[memory-budget.md](memory-budget.md)). A future framework version could give mods their
own overlay loaded with the farm.

## Upstream

The framework's hook points are small and compile to nothing in a retail build. They are
good candidates to propose upstream to hmbtn-decomp, which would shrink
`framework/patches/` to almost nothing. To move to a newer upstream commit, update
`framework/upstream.json`, rebase the patch, and check that the retail build still matches.
