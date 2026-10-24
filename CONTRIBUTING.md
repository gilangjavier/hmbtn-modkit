# Contributing

Thanks for helping! Most contributions are new mods. Fixes to the kit itself, the
docs and the framework hooks are just as welcome.

## Adding a mod

1. **Fork** this repository and clone your fork.
2. Set up once: `python hm.py setup --disc /path/to/your.bin`
3. Create the mod: `python hm.py new your_mod --author "Your Name"`
4. Write it, then build and play it: `python hm.py build your_mod`, then `python hm.py run`
5. Check it: `python hm.py validate` and `python hm.py catalog` (this updates `MODS.md`)
6. Commit `mods/your_mod/` and `MODS.md` on a branch, push, and **open a pull request**.

CI builds your mod alone and together with every other mod, checks that it fits in RAM,
and checks that the retail build still matches the original game.

### Rules for a mod

- **One folder, one mod**: everything lives in `mods/<id>/`. The id is 2-32 characters
  (`a-z`, `0-9`, `_`) and starts with a letter.
- **`mod.json`** has `id`, `name`, `version` (`MAJOR.MINOR.PATCH`), `description`,
  `authors`, `license` and `tags`. Bump `version` whenever you change the mod.
- **`README.md`** says what the mod does, its controls, and any known issues.
- **Prefix C names with your mod id** (`your_mod_frame`, `your_mod_state`). Every mod is
  linked into the same executable, so names must not clash. Mark helpers `static`.
- **Keep it small.** All mods share about 55 KB of RAM ([docs/memory-budget.md](docs/memory-budget.md)).
  `hm.py build` prints how much yours uses.
- **Prefer hooks to patches.** A `.patch` against the game's source is fine when no hook
  fits, but it can conflict with other mods that patch the same lines. Keep patches
  small, and say what they change in your README.
- **It must work together with the other mods.** CI builds `--all`. If two mods cannot
  coexist, explain why in the PR.

### Game data: the one hard rule

**Never commit the game's own data.** This includes files from the disc, files extracted
from `A_FILE.BIN`, the executable, and screenshots-turned-textures of the game's art.

- To change game data, commit an **`.xdelta` patch** (`afile/<member>.xdelta`) that turns
  the original file into yours. It holds only your changes, and it only works for someone
  who has the original. See [docs/assets.md](docs/assets.md).
- Whole files in `afile/` or `disc/` are allowed only when they are entirely your own
  work. `hm.py validate` rejects whole files over 64 KB.
- Disc images, `.bin`/`.cue`/`.iso` files and the `SLUS_011.15` executable are never accepted.

PRs that include copyrighted game data will be closed and the data purged from history.

## Changing the kit or the framework

- `hm.py`: the tool. Keep it a single file with the standard library only (Pillow is
  optional, for `hm.py test` screenshots).
- `framework/patches/`: the changes to the decomp (hooks, mod linking, memory layout),
  applied to the upstream commit pinned in `framework/upstream.json`. To change them, edit
  `.hm/decomp/`, then regenerate the patch from there:

  ```sh
  cd .hm/decomp
  git add -N .                      # include new files in the diff
  git diff > ../../framework/patches/0001-mod-hooks.patch
  git reset -q
  ```

  The retail build **must still match**: `python hm.py build` (and `--no-disc`) must
  report `all ... files match`. Hooks compile to nothing without mods, and that is what
  keeps the match.
- A new hook goes in `src/main/mods.h`, a `MODS_*()` call in the game's source,
  `HM_HOOKS` in `cmake/mods.cmake` and `HOOKS` in `hm.py`, plus
  [docs/hooks-and-api.md](docs/hooks-and-api.md).

## Pull requests

- One mod or one change per PR.
- Fill in the PR template checklist.
- Be patient and kind in review. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
