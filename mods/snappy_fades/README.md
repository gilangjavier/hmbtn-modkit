# Snappy Fades

Shorter screen transitions when you walk between areas on the farm.

## What changes

- `fade_start_blend(20)` becomes `fade_start_blend(10)` in `FARM_MODE_EXIT_LOAD`
  (`src/overlay/11_GF_FARM/farm_main.c`). This is the cross-fade used when you leave one
  farm area for another.

Why it is safe: the section load is asynchronous and the arrival state
(`FARM_MODE_EXIT_ARRIVE`) polls `farm_section_load_async(..., 0)` first, and only then
waits for `fade_is_settled()`. The blend ends by itself after its length (the mode goes to
none), so a shorter blend just finishes sooner. If the load takes longer than the blend,
the game still waits for the load. The blend length is not tied to any sound wait.

## What is not changed, and why

- **`FADE_OUT_HOLD` (6 to 2) is left out.** In `screen_fade_frame` the out-fade ends as
  soon as the level reaches `fade_length + 1`, because the end test is
  `level <= fade_length + FADE_OUT_HOLD`, true at that point for any hold of 1 or more. The
  hold steps are therefore never reached and changing the constant would have no visible
  effect. (It is a byte-exact decompilation, so this is how the game really behaves.)
- The 10-step fades at `farm_main.c:79,361` and `main.c:362` are already short and are
  not touched.

Not tested at run time.
