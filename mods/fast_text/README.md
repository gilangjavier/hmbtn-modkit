# Fast Text

Dialogue text types out faster at the normal speed. A one-line source patch, no code.

## What changes

`text_speed_intervals` in `src/main/text/text.c` holds the number of vsyncs between two
glyphs for each speed index:

| Index | Meaning | Before | After |
|-------|---------|--------|-------|
| 0 | instant | 0 | 0 |
| 1 | normal (the default) | 3 vsyncs/glyph | **1 vsync/glyph** |
| 2 | slow | 5 vsyncs/glyph | 5 (unchanged) |

The slow value is left at 5 on purpose: the game recovers the current speed from the
interval (`0` = instant, `5` = slow, anything else = normal) when it restores the speed
after you skip text, so changing slow to another value would turn it into normal.

Holding Circle or Cross still makes text instant, exactly as before.

## Notes

- Text is drawn once per frame; if the game runs at 30 fps (2 vsyncs per frame), 1 and 2
  vsyncs per glyph look the same.
- Patches `src/main/text/text.c` only (one line).
- Not tested at run time.
