## What this PR does

<!-- New mod? Update to a mod? Kit/framework change? One sentence. -->

## Mod checklist (skip for non-mod PRs)

- [ ] The mod is in `mods/<id>/` and has `mod.json`, `README.md` and its sources
- [ ] `python hm.py validate` passes
- [ ] `python hm.py catalog` was run and `MODS.md` is included
- [ ] It builds alone and with `--all` (RAM used: ____ bytes)
- [ ] I played it in an emulator (or ran `python hm.py test`) and it does what the README says
- [ ] **No game data**: nothing extracted from the disc, only my own files and `.xdelta` patches
- [ ] Global C names are prefixed with the mod id

## Framework checklist (skip for mod-only PRs)

- [ ] `python hm.py build` still reports `all 17 files match` (or `all 14` with `--no-disc`)
- [ ] Docs updated (`docs/hooks-and-api.md` for new hooks)

## Screenshots

<!-- Optional, but they help reviewers and players. -->
