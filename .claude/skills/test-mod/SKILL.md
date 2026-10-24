---
name: test-mod
description: Run a Harvest Moon Back to Nature mod headless in PCSX-Redux and judge whether its hooks ran and the game stayed healthy. Use when the user asks to test, verify, check or debug a mod at run time.
---

# Test a mod at run time

`hm.py test` boots a disc built with the mod plus two test mods (`autotest`, which records
hook calls, and `quickstart`, which jumps straight into a new game) in PCSX-Redux without
a window, and writes a report.

## Requirements

- A disc configured (`python hm.py setup --disc PATH`).
- PCSX-Redux configured (`python hm.py setup --skip-toolchain --emulator PATH`).
- Optional: `pip install pillow` for PNG screenshots.

If either is missing, say so and stop at the `--no-disc` build.

## Run

```sh
python hm.py test <id> [<other ids>] --seconds 600
```

- Use **600+ seconds** to reach normal gameplay: the opening cutscene is long, and the
  clock (and so `minute`/`new_day`) is stopped until it ends.
- `--autopilot "vsync:hexbuttons,..."` changes the button taps. The default taps START,
  then CROSS forever. `PAD_*` bits: L2 0001, R2 0002, L1 0004, R1 0008, TRIANGLE 0010,
  CIRCLE 0020, CROSS 0040, SQUARE 0080, SELECT 0100, START 0800, UP 1000, RIGHT 2000,
  DOWN 4000, LEFT 8000. Add 10000 to hold instead of tap (walking: `14000` = hold DOWN).

## Read the report (`out/test/report.txt`)

| Field | Healthy |
|-------|---------|
| `magic=484d5445` | The `boot` hook ran. `00000000` after about 1800 vsyncs means the game did not boot. |
| `frames` | Rises between reports. Flat while `vsync` rises means a hang or a crash. |
| `last_scene` | `2` once the new game has started (farm). |
| `minutes`, `days` | Rise once the intro is over. They stay 0 during cutscenes. |
| `gold` | The player's gold at the last minute. Use it to check money mods. |
| `pc` | The CPU's program counter. Stuck at one value across reports means a crash loop. |

Look at the screenshots in `out/test/*.png` too: garbage graphics after a mod was
added point to memory corruption.

## Testing a specific effect

To check that a mod did something, add a temporary field to the `autotest` record or
write a small test mod in `tests/mods/` that copies the relevant state into a global,
and read it in `tests/redux_check.lua`.

## Report honestly

State what was observed (counts, scene, screenshots) and what was not reached. "Booted,
hooks ran, reached the farm, but the clock never started within 600 s" is a valid
result. Never report a run-time behavior as verified if the report does not show it.
