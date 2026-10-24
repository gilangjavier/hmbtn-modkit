# Pink Chickens

Every adult chicken on the farm turns pink. The comb, beak and eyes keep their colors.

This is an asset-only mod (no C code): it changes one 16-color palette of the chicken
sprite in `00_gf.bin`. It ships as `afile/00_gf.bin.xdelta`, a patch of 332 bytes that
`hm.py build` applies to your own copy of the game. No game art is included.

## How it was made

```sh
python hm.py extract
python hm.py sprite export chicken ~/edits/chicken      # PNGs + sprite.json
# recolor the swatches of ~/edits/chicken/pal_0.png (the cream feather ramp, colors 1-9)
python hm.py sprite import pink_chickens chicken ~/edits/chicken
```

See [docs/sprites.md](../../docs/sprites.md). The patch changes 18 bytes of the file (the
palette, inside the chicken's image bank) and nothing else.

## Known issues

- Chicks (a different sprite, `chick`) keep their yellow color.
- Tested only by building the disc (the patch applies); not played in an emulator.
- Another mod that patches the same `00_gf.bin` bank would replace this one: the mod given
  last wins (docs/assets.md).
