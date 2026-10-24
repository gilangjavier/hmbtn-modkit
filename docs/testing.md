# Testing

## Levels of testing

| Check | Command | Needs |
|-------|---------|-------|
| Manifests, files, rules | `python hm.py validate` | nothing |
| Catalog is current | `python hm.py catalog --check` | nothing |
| Code compiles, links and fits in RAM | `python hm.py build my_mod --no-disc` | toolchain |
| Retail build still matches | `python hm.py build --no-disc` (code), `python hm.py build` (whole disc) | toolchain (+ disc) |
| It runs | `python hm.py test my_mod` | disc, PCSX-Redux |
| It plays right | `python hm.py build my_mod`, then `python hm.py run` | disc, an emulator |

CI runs the first four for every pull request. The last two need the game, so they are
up to you before you open the PR.

## Headless runs: `hm.py test`

`hm.py test` builds your mods together with two test mods from `tests/mods/`, runs the
disc in [PCSX-Redux](https://github.com/grumpycoders/pcsx-redux) without a window, and
reports what happened:

- **`autotest`** counts every hook call in a record, `hm_test`, and can hold buttons on
  the harness's request.
- **`quickstart`** (a source patch) skips the title menu, name entry and birthday, and goes
  straight into a new game. Because the name entry is skipped, it sets the player, farm and
  dog names to a single `A` (glyph 0), so dialogue that prints them does not crash.

```sh
python hm.py setup --skip-toolchain --emulator "C:\Tools\pcsx-redux\pcsx-redux.exe"
python hm.py test cheat_pad --seconds 600
```

```
vsync=1800 magic=484d5445 frames=206 scenes=0 last_scene=-1 minutes=0 days=0 gold=0 pc=80032d4c
vsync=9000 magic=484d5445 frames=3390 scenes=1 last_scene=2 minutes=0 days=0 gold=0 pc=80032d94
...
```

- `magic=484d5445`: the `boot` hook ran.
- `frames`: `frame` hook calls (the game runs at 30 fps, so about half the vsyncs).
- `scenes` / `last_scene`: `scene` hook calls and the last scene requested (2 = farm).
- `minutes` / `days`: `minute` and `new_day` calls. The game stops its clock during
  events and inside some places, such as the player's house. The opening cutscene ends
  with the player indoors on day 2 (set directly, without a `new_day`), so these stay 0
  until the player walks outside. Use a hold autopilot for that (below).
- `gold`: the player's gold at the last minute.

Screenshots go to `out/test/` as PNGs (needs `pip install pillow`).

### Autopilot

`--autopilot "vsync:buttons,..."` makes `autotest` tap buttons (hex `PAD_*` bits) from
that vsync on: pressed for 2 frames out of every 20. Add `10000` to hold them
instead (`14000` holds DOWN, to walk). `0` stops. The default,
`1500:0800,2400:0040`, taps START, then CROSS forever, which advances dialogue.

To test something specific, write a test mod in `tests/mods/` that sets up the state you
need from its `boot` or `frame` hook, and read it back in `tests/redux_check.lua`.
